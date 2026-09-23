from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.config_versions import (
    ConfigConflict,
    ConfigInvalid,
    activate_version,
    content_hash,
    create_version,
    diff_versions,
    get_version,
    list_versions,
    restore_version,
)
from app.rules import ALARM_RULE
from tests.analytics_fixtures import cleanup_tenant, create_tenant_with_points, in_tenant

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


@pytest.fixture
def two_tenants():
    tenant_a = create_tenant_with_points("ClientConfigA")
    tenant_b = create_tenant_with_points("ClientConfigB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        cleanup_tenant(tenant)


def _rule(tenant, **overrides) -> dict:
    rule = {
        "kind": "threshold",
        "point_id": str(tenant["sensor"]),
        "operator": ">",
        "threshold": 80,
        "severity": "critical",
        "title": "Départ d'eau trop chaud",
    }
    rule.update(overrides)
    return rule


def _new(connection, tenant, reason="test", **overrides):
    return create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=ALARM_RULE,
        subject_key="cta01-tdep-haute",
        content=_rule(tenant, **overrides),
        author="responsable",
        reason=reason,
    )


def test_each_change_is_a_new_numbered_version(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        first = _new(connection, tenant_a)
        second = _new(connection, tenant_a, threshold=85)
        v1, v2 = get_version(connection, first), get_version(connection, second)

    assert (v1["version"], v2["version"]) == (1, 2)
    assert v2["parent_version_id"] == first
    assert v1["status"] == v2["status"] == "draft"
    assert v1["content_hash"] == content_hash(v1["content"])
    assert v1["schema_version"] == "alarm_rule/1"


def test_activation_supersedes_the_previous_active_version(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        first = _new(connection, tenant_a)
        activate_version(connection, version_id=first, activated_by="resp", activated_at=NOW)
        second = _new(connection, tenant_a, threshold=85)
        replaced = activate_version(
            connection, version_id=second, activated_by="resp", activated_at=NOW
        )
        statuses = [v["status"] for v in list_versions(connection, config_type=ALARM_RULE)]

    assert replaced == first
    assert statuses == ["superseded", "active"]


def test_restore_creates_a_new_version_with_the_old_content(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        first = _new(connection, tenant_a)
        activate_version(connection, version_id=first, activated_by="resp", activated_at=NOW)
        second = _new(connection, tenant_a, threshold=85)
        activate_version(connection, version_id=second, activated_by="resp", activated_at=NOW)
        restored = restore_version(
            connection,
            tenant_id=tenant_a["tenant_id"],
            version_id=first,
            author="resp",
            reason="Seuil 85 trop tardif",
            activated_at=NOW,
        )
        versions = list_versions(connection, config_type=ALARM_RULE)
        restored_version = get_version(connection, restored)

    assert [(v["version"], v["status"]) for v in versions] == [
        (1, "superseded"),
        (2, "superseded"),
        (3, "active"),
    ]
    assert restored_version["content"]["threshold"] == 80
    assert restored_version["reason"] == "Seuil 85 trop tardif"


def test_diff_shows_what_changed() -> None:
    old = {"threshold": 80, "severity": "critical", "title": "A"}
    new = {"threshold": 85, "severity": "critical", "recommended_action": "Vérifier la vanne"}
    assert diff_versions(old, new) == {
        "added": {"recommended_action": "Vérifier la vanne"},
        "removed": {"title": "A"},
        "changed": {"threshold": {"from": 80, "to": 85}},
    }


def test_only_a_draft_can_be_activated(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(ConfigConflict):
        with in_tenant(tenant_a) as connection:
            first = _new(connection, tenant_a)
            activate_version(connection, version_id=first, activated_by="r", activated_at=NOW)
            activate_version(connection, version_id=first, activated_by="r", activated_at=NOW)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"kind": "magie"}, "règle invalide"),
        ({"surprise": 1}, "règle invalide"),
        ({"threshold": "chaud"}, "règle invalide"),
        ({"severity": "apocalypse"}, "règle invalide"),
    ],
)
def test_invalid_rule_is_never_stored(two_tenants, overrides, message) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(ConfigInvalid, match=message):
        with in_tenant(tenant_a) as connection:
            _new(connection, tenant_a, **overrides)


def test_threshold_rule_requires_a_numeric_point(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(ConfigInvalid, match="point numérique"):
        with in_tenant(tenant_a) as connection:
            _new(connection, tenant_a, point_id=str(tenant_a["run_status"]))


def test_rule_on_another_tenant_point_is_refused(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    with pytest.raises(ConfigInvalid, match="introuvable"):
        with in_tenant(tenant_a) as connection:
            _new(connection, tenant_a, point_id=str(tenant_b["sensor"]))


def test_unknown_config_type_is_refused(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(ConfigInvalid, match="inconnu"):
        with in_tenant(tenant_a) as connection:
            create_version(
                connection,
                tenant_id=tenant_a["tenant_id"],
                config_type="recette_de_cuisine",
                subject_key="x",
                content={},
                author="r",
                reason="r",
            )


def test_tenant_isolation_on_config_versions(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    with in_tenant(tenant_a) as connection:
        _new(connection, tenant_a)
        seen_by_a = list_versions(connection)
    with in_tenant(tenant_b) as connection:
        seen_by_b = list_versions(connection)
    assert len(seen_by_a) == 1
    assert seen_by_b == []


@pytest.mark.parametrize(
    ("statement", "message"),
    [
        ("UPDATE config_versions SET content = '{}'::jsonb WHERE id = :id", "jamais réécrite"),
        ("UPDATE config_versions SET status = 'draft' WHERE id = :id", "interdit"),
        ("DELETE FROM config_versions WHERE id = :id", "suppression interdite"),
    ],
)
def test_a_published_version_is_never_rewritten(two_tenants, statement, message) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        version_id = _new(connection, tenant_a)
        activate_version(connection, version_id=version_id, activated_by="r", activated_at=NOW)
    with pytest.raises(DBAPIError, match=message):
        with in_tenant(tenant_a) as connection:
            connection.execute(text(statement), {"id": version_id})
