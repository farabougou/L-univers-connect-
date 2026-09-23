from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.config_versions import activate_version, create_version
from app.desired_states import (
    DesiredStateInvalid,
    declare_desired_state,
    desired_state_at,
    in_daily_window,
)
from app.findings import (
    confirm_finding,
    displayed,
    list_findings,
    raise_or_repeat_finding,
)
from app.points import get_point
from app.rules import ALARM_RULE
from app.signals import SignalConflict, set_handling
from app.telemetry import record_measurement
from app.trust import compute_trust
from tests.analytics_fixtures import cleanup_tenant, create_tenant_with_points, in_tenant
from tests.error_helpers import raises_code

T0 = datetime(2026, 9, 23, 8, 0, tzinfo=UTC)


@pytest.fixture
def two_tenants():
    tenant_a = create_tenant_with_points("ClientRulesA")
    tenant_b = create_tenant_with_points("ClientRulesB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        cleanup_tenant(tenant)


def _activate_rule(connection, tenant, subject_key="cta01-tdep-haute", **overrides):
    content = {
        "kind": "threshold",
        "point_id": str(tenant["sensor"]),
        "operator": ">",
        "threshold": 80,
        "severity": "critical",
        "title": "Départ d'eau trop chaud",
        "recommended_action": "Contrôler la vanne trois voies.",
        "create_work_order": True,
    }
    content.update(overrides)
    content = {key: value for key, value in content.items() if value is not None}
    version_id = create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=ALARM_RULE,
        subject_key=subject_key,
        content=content,
        author="responsable",
        reason="test",
    )
    activate_version(connection, version_id=version_id, activated_by="responsable", activated_at=T0)
    return version_id


def _measure(connection, tenant, value, at, point_key="sensor"):
    return record_measurement(
        connection,
        tenant_id=tenant["tenant_id"],
        point=get_point(connection, tenant[point_key]),
        value=value,
        measured_at=at,
        origin="simulated",
        source="simulator",
        received_at=at,
    )


def _findings(connection, kind=None):
    return list_findings(connection, kind=kind)


# --- Seuil → constat → alarme → ordre de travail ------------------------------------------------


def test_threshold_breach_raises_finding_alarm_and_work_order(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        rule_version = _activate_rule(connection, tenant_a)
        _measure(connection, tenant_a, 85.0, T0)
        findings = _findings(connection)
        alarms = connection.execute(text("SELECT raised_by, severity FROM alarms")).all()
        work_orders = connection.execute(text("SELECT title, priority FROM work_orders")).all()
        audited = connection.execute(
            text("SELECT count(*) FROM audit_log WHERE action = 'finding.raised'")
        ).scalar()

    assert len(findings) == 1
    finding = findings[0]
    assert (finding["kind"], finding["method"], finding["reason_code"]) == (
        "fault",
        "deterministic_rule",
        "RULE_THRESHOLD_EXCEEDED",
    )
    assert (finding["condition_state"], finding["ack_state"], finding["handling_status"]) == (
        "active",
        "unacknowledged",
        "open",
    )
    assert finding["certainty"] == "detected"
    assert finding["reason_params"] == {
        "point_code": "CTA01-TDEP",
        "value": 85.0,
        "operator": ">",
        "threshold": 80,
    }
    assert finding["rule_config_version_id"] == rule_version
    assert finding["subject_node_id"] == tenant_a["ahu"]
    assert finding["evidence"]["value"] == 85.0
    assert finding["evidence"]["threshold"] == 80
    assert finding["alarm_id"] is not None and finding["work_order_id"] is not None
    assert [tuple(row) for row in alarms] == [("systeme:regles", "critical")]
    assert [tuple(row) for row in work_orders] == [("Départ d'eau trop chaud", "urgent")]
    assert audited == 1


def test_repeated_breach_increments_the_same_finding_without_new_alarm(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_rule(connection, tenant_a)
        for minute in range(3):
            _measure(connection, tenant_a, 85.0 + minute, T0 + timedelta(minutes=minute))
        findings = _findings(connection)
        alarm_count = connection.execute(text("SELECT count(*) FROM alarms")).scalar()

    assert [f["occurrence_count"] for f in findings] == [3]
    assert findings[0]["last_seen_at"] == T0 + timedelta(minutes=2)
    assert alarm_count == 1


def test_normal_value_raises_nothing(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_rule(connection, tenant_a)
        _measure(connection, tenant_a, 45.0, T0)
        assert _findings(connection) == []


def _close(connection, tenant, finding_id, handling="closed"):
    set_handling(
        connection,
        kind="finding",
        tenant_id=tenant["tenant_id"],
        signal_id=finding_id,
        handling_status=handling,
        changed_by="technicien",
        note="Vanne débloquée",
    )


def test_a_new_breach_after_closing_opens_a_new_finding(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_rule(connection, tenant_a)
        _measure(connection, tenant_a, 85.0, T0)
        first = _findings(connection)[0]
        _measure(connection, tenant_a, 45.0, T0 + timedelta(minutes=1))
        _close(connection, tenant_a, first["id"])
        _measure(connection, tenant_a, 86.0, T0 + timedelta(minutes=2))
        statuses = sorted(f["handling_status"] for f in _findings(connection))

    assert statuses == ["closed", "open"]


# --- Retour à la normale, acquittement, traitement (ADR 013) ------------------------------


def _alarm_axes(connection, alarm_id):
    return tuple(
        connection.execute(
            text("SELECT condition_state, ack_state, handling_status FROM alarms WHERE id = :id"),
            {"id": alarm_id},
        ).one()
    )


def test_return_to_normal_clears_finding_and_alarm_but_keeps_them_to_handle(
    two_tenants,
) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_rule(connection, tenant_a)
        _measure(connection, tenant_a, 85.0, T0)
        _measure(connection, tenant_a, 45.0, T0 + timedelta(minutes=1))
        finding = _findings(connection)[0]
        alarm = _alarm_axes(connection, finding["alarm_id"])

    assert (finding["condition_state"], finding["ack_state"], finding["handling_status"]) == (
        "cleared",
        "unacknowledged",
        "open",
    )
    assert alarm == ("cleared", "unacknowledged", "open")


def test_recurrence_before_closing_reactivates_the_same_finding(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_rule(connection, tenant_a)
        _measure(connection, tenant_a, 85.0, T0)
        finding_id = _findings(connection)[0]["id"]
        set_handling(
            connection,
            kind="finding",
            tenant_id=tenant_a["tenant_id"],
            signal_id=finding_id,
            handling_status="in_progress",
            changed_by="technicien",
        )
        _measure(connection, tenant_a, 45.0, T0 + timedelta(minutes=1))
        _measure(connection, tenant_a, 87.0, T0 + timedelta(minutes=2))
        findings = _findings(connection)
        alarm = _alarm_axes(connection, findings[0]["alarm_id"])

    assert [f["id"] for f in findings] == [finding_id]
    assert (findings[0]["condition_state"], findings[0]["ack_state"]) == (
        "active",
        "unacknowledged",
    )
    assert findings[0]["handling_status"] == "in_progress"
    assert findings[0]["occurrence_count"] == 2
    assert alarm[0] == "active"


def test_a_finding_cannot_be_closed_while_its_condition_is_active(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_rule(connection, tenant_a)
        _measure(connection, tenant_a, 85.0, T0)
        finding_id = _findings(connection)[0]["id"]
    with raises_code(SignalConflict, "SIGNAL_CONDITION_STILL_ACTIVE"):
        with in_tenant(tenant_a) as connection:
            _close(connection, tenant_a, finding_id)
    with in_tenant(tenant_a) as connection:
        _close(connection, tenant_a, finding_id, handling="false_positive")
        finding = _findings(connection)[0]
    # Déclarer un faux positif vaut acquittement.
    assert (finding["handling_status"], finding["ack_state"]) == (
        "false_positive",
        "acknowledged",
    )


def test_a_clean_reading_clears_the_quality_finding(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_rule(connection, tenant_a)
        _measure(connection, tenant_a, 150.0, T0)
        _measure(connection, tenant_a, 45.0, T0 + timedelta(minutes=1))
        quality = _findings(connection, kind="data_quality")

    assert [(f["reason_code"], f["condition_state"]) for f in quality] == [
        ("DATA_QUALITY_OUT_OF_RANGE", "cleared")
    ]


def test_major_severity_maps_to_a_high_priority_work_order(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_rule(connection, tenant_a, severity="major")
        _measure(connection, tenant_a, 85.0, T0)
        priority = connection.execute(text("SELECT priority FROM work_orders")).scalar()
        severity = connection.execute(text("SELECT severity FROM alarms")).scalar()

    assert (priority, severity) == ("high", "major")


# --- Textes produits à l'affichage, jamais stockés (ADR 013) ------------------------------


def test_system_findings_store_a_code_not_a_sentence(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_rule(connection, tenant_a)
        _measure(connection, tenant_a, 150.0, T0)
        stored = _findings(connection, kind="data_quality")[0]

    assert stored["title"] is None and stored["recommended_action"] is None
    assert stored["reason_params"] == {"point_code": "CTA01-TDEP"}
    assert displayed(stored, "fr")["title"] == (
        "Valeur hors de la plage physique du capteur sur le point CTA01-TDEP"
    )
    assert displayed(stored, "en")["title"] == (
        "Value outside the sensor's physical range on point CTA01-TDEP"
    )


def test_rule_findings_keep_the_title_written_by_their_author(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_rule(connection, tenant_a)
        _measure(connection, tenant_a, 85.0, T0)
        finding = _findings(connection)[0]

    assert displayed(finding, "en")["title"] == "Départ d'eau trop chaud"
    assert displayed(finding, "en")["recommended_action"] == "Contrôler la vanne trois voies."


# --- Certitude : jamais plus que ce que le système sait (ADR 013, 4.4) ---------------------


def _confirm(connection, tenant, finding_id, by="technicien-1"):
    confirm_finding(
        connection,
        tenant_id=tenant["tenant_id"],
        finding_id=finding_id,
        confirmed_by=by,
        confirmed_at=T0 + timedelta(hours=1),
        note="Vanne trois voies grippée constatée sur site",
    )


def test_a_person_confirms_a_detected_fault(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_rule(connection, tenant_a)
        _measure(connection, tenant_a, 85.0, T0)
        finding_id = _findings(connection)[0]["id"]
        _confirm(connection, tenant_a, finding_id)
        finding = _findings(connection)[0]

    assert (finding["certainty"], finding["confirmed_by"]) == ("confirmed", "technicien-1")


def test_the_system_never_confirms_a_fault(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_rule(connection, tenant_a)
        _measure(connection, tenant_a, 85.0, T0)
        finding_id = _findings(connection)[0]["id"]
    with raises_code(ValueError, "FINDING_CONFIRMATION_REQUIRES_PERSON"):
        with in_tenant(tenant_a) as connection:
            _confirm(connection, tenant_a, finding_id, by="systeme:regles")
    with pytest.raises(DBAPIError, match="ck_findings_confirmation"):
        with in_tenant(tenant_a) as connection:
            connection.execute(
                text(
                    "UPDATE findings SET certainty = 'confirmed', confirmed_at = now(), "
                    "confirmed_by = 'systeme:regles'"
                )
            )


def test_a_prediction_is_never_confirmed(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        finding_id, _ = raise_or_repeat_finding(
            connection,
            tenant_id=tenant_a["tenant_id"],
            dedup_key="prediction:test",
            subject_node_id=tenant_a["ahu"],
            kind="prediction",
            method="statistical",
            severity="warning",
            reason_code="FINDING_UNCLASSIFIED",
            reason_params={},
            evidence={},
            seen_at=T0,
            changed_by="systeme:regles",
        )
        certainty = _findings(connection, kind="prediction")[0]["certainty"]
    assert certainty == "prediction"
    with raises_code(SignalConflict, "FINDING_PREDICTION_NOT_CONFIRMABLE"):
        with in_tenant(tenant_a) as connection:
            _confirm(connection, tenant_a, finding_id)


def test_superseded_rule_version_no_longer_applies(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_rule(connection, tenant_a)
        _activate_rule(connection, tenant_a, threshold=95)
        _measure(connection, tenant_a, 90.0, T0)
        assert _findings(connection) == []


# --- Une donnée douteuse n'est jamais utilisée aveuglément ------------------------------


def test_out_of_range_value_opens_a_quality_finding_not_a_fault(two_tenants) -> None:
    """150 °C dépasse le seuil de 80, mais aussi la plage physique du capteur
    (0-100) : c'est le capteur qu'il faut suspecter, pas l'installation."""
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_rule(connection, tenant_a)
        _measure(connection, tenant_a, 150.0, T0)
        findings = _findings(connection)
        alarm_count = connection.execute(text("SELECT count(*) FROM alarms")).scalar()

    assert [(f["kind"], f["evidence"]["flag"]) for f in findings] == [
        ("data_quality", "out_of_range")
    ]
    assert alarm_count == 0


def test_frozen_sensor_stops_rule_evaluation(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_rule(connection, tenant_a)
        for minute in range(12):
            _measure(connection, tenant_a, 90.0, T0 + timedelta(minutes=minute))
        faults = _findings(connection, kind="fault")
        quality = _findings(connection, kind="data_quality")

    # Les 11 premiers relevés sont crédibles ; au 12e identique, le capteur
    # est jugé figé et les règles ne s'y fient plus.
    assert [f["occurrence_count"] for f in faults] == [11]
    assert [f["dedup_key"].rsplit(":", 1)[1] for f in quality] == ["low_trust"]
    assert quality[0]["evidence"]["trust"]["components"]["frozen"] is True


def test_trust_score_explains_itself(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        for minute in (0, 1, 2):
            _measure(connection, tenant_a, 45.0 + minute, T0 + timedelta(minutes=minute))
        point = get_point(connection, tenant_a["sensor"])
        fresh = compute_trust(connection, point, T0 + timedelta(minutes=2))
        later = compute_trust(connection, point, T0 + timedelta(minutes=10))

    assert fresh["score"] == 100 and fresh["reasons"] == []
    assert fresh["algorithm"] == "trust-v1"
    assert later["components"]["stale"] is True
    assert later["score"] < 50
    assert "donnée périmée" in later["reasons"]


# --- État souhaité / état réel ------------------------------------------------

# 23/09/2026 : heure d'été à Paris (UTC+2).
EVENING_PARIS = datetime(2026, 9, 23, 19, 30, tzinfo=UTC)  # 21 h 30 à Paris
NOON_PARIS = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)  # 12 h 00 à Paris


def _declare_night_off(connection, tenant):
    return declare_desired_state(
        connection,
        tenant_id=tenant["tenant_id"],
        point_id=tenant["run_status"],
        value=0,
        valid_from=T0 - timedelta(days=1),
        daily_start=time(20, 0),
        daily_end=time(7, 0),
        timezone="Europe/Paris",
        reason="CTA arrêtée la nuit (contrat d'exploitation)",
        created_by="responsable",
    )


def test_divergence_from_desired_state_is_a_commissioning_finding(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _declare_night_off(connection, tenant_a)
        _activate_rule(
            connection,
            tenant_a,
            subject_key="cta01-marche-nuit",
            kind="desired_state_divergence",
            point_id=str(tenant_a["run_status"]),
            severity="warning",
            title="CTA en marche la nuit",
            create_work_order=False,
            operator=None,
            threshold=None,
        )
        _measure(connection, tenant_a, 1, NOON_PARIS, point_key="run_status")
        assert _findings(connection) == []
        _measure(connection, tenant_a, 1, EVENING_PARIS, point_key="run_status")
        findings = _findings(connection)

    assert [(f["kind"], f["evidence"]["actual"], f["evidence"]["desired"]) for f in findings] == [
        ("commissioning", 1, 0)
    ]
    assert findings[0]["work_order_id"] is None


@pytest.mark.parametrize(
    ("utc", "expected"),
    [
        (datetime(2026, 9, 23, 17, 59, tzinfo=UTC), False),  # 19 h 59 à Paris
        (datetime(2026, 9, 23, 18, 0, tzinfo=UTC), True),  # 20 h 00 : début inclus
        (datetime(2026, 9, 24, 4, 59, tzinfo=UTC), True),  # 06 h 59
        (datetime(2026, 9, 24, 5, 0, tzinfo=UTC), False),  # 07 h 00 : fin exclue
        # Même heure UTC, saisons différentes : le 25/10/2026 Paris passe à
        # l'heure d'hiver (UTC+1). 18 h 30 UTC = 20 h 30 en été, 19 h 30 en hiver.
        (datetime(2026, 9, 23, 18, 30, tzinfo=UTC), True),
        (datetime(2026, 10, 26, 18, 30, tzinfo=UTC), False),
        (datetime(2026, 10, 26, 19, 0, tzinfo=UTC), True),  # 20 h 00 heure d'hiver
    ],
)
def test_overnight_window_in_local_time(utc, expected) -> None:
    window = {"start": time(20, 0), "end": time(7, 0), "timezone": "Europe/Paris"}
    assert in_daily_window(utc, **window) is expected


def test_desired_state_outside_its_validity_does_not_apply(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _declare_night_off(connection, tenant_a)
        before = desired_state_at(connection, tenant_a["run_status"], T0 - timedelta(days=2))
        during = desired_state_at(connection, tenant_a["run_status"], EVENING_PARIS)
    assert before is None
    assert during["value"] == 0


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"timezone": "Mars/Olympus"}, "TIMEZONE_UNKNOWN"),
        ({"timezone": None}, "DAILY_WINDOW_TIMEZONE_REQUIRED"),
        ({"value": 2}, "VALUE_BOOLEAN_INVALID"),
        ({"daily_end": time(20, 0)}, "DAILY_WINDOW_EMPTY"),
    ],
)
def test_invalid_desired_states_are_refused(two_tenants, overrides, code) -> None:
    tenant_a, _ = two_tenants
    params = {
        "tenant_id": tenant_a["tenant_id"],
        "point_id": tenant_a["run_status"],
        "value": 0,
        "valid_from": T0,
        "daily_start": time(20, 0),
        "daily_end": time(7, 0),
        "timezone": "Europe/Paris",
        "reason": "test",
        "created_by": "test",
    }
    params.update(overrides)
    with raises_code(DesiredStateInvalid, code):
        with in_tenant(tenant_a) as connection:
            declare_desired_state(connection, **params)


# --- Isolation et immuabilité ------------------------------------------------


@pytest.mark.parametrize("table", ["desired_states", "findings", "finding_status_history"])
def test_tenant_isolation_on_analytics_tables(two_tenants, table) -> None:
    tenant_a, tenant_b = two_tenants
    query = text(f"SELECT 1 FROM {table} WHERE tenant_id = :id")
    with in_tenant(tenant_a) as connection:
        _declare_night_off(connection, tenant_a)
        _activate_rule(connection, tenant_a)
        _measure(connection, tenant_a, 85.0, T0)
        seen_by_a = connection.execute(query, {"id": tenant_a["tenant_id"]}).fetchall()
    with in_tenant(tenant_b) as connection:
        seen_by_b = connection.execute(query, {"id": tenant_a["tenant_id"]}).fetchall()
    assert seen_by_a
    assert seen_by_b == []


@pytest.mark.parametrize(
    ("statement", "message"),
    [
        ("UPDATE findings SET title = 'autre'", "non modifiable"),
        ("UPDATE findings SET reason_code = 'AUTRE'", "code de raison non modifiable"),
        ("UPDATE findings SET occurrence_count = 0", "ck_findings_occurrences|en arrière"),
        ("UPDATE desired_states SET value = 1", "non modifiable"),
    ],
)
def test_findings_and_desired_states_are_never_rewritten(two_tenants, statement, message) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _declare_night_off(connection, tenant_a)
        _activate_rule(connection, tenant_a)
        _measure(connection, tenant_a, 85.0, T0)
    with pytest.raises(DBAPIError, match=message):
        with in_tenant(tenant_a) as connection:
            connection.execute(text(statement))
