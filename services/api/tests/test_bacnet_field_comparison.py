"""Outil de comparaison terrain (app.bacnet_field_comparison) — UNIT_TESTED,
aucun réseau ni base de données. La méthodologie complète (GTB ↔
découverte ↔ Edge ↔ sémantique ↔ Digital Twin) est décrite dans l'ADR 015,
section 6 ; ce module n'en teste que la logique de rapprochement, seule
partie exécutable sans accès à un site réel."""

from app.bacnet_field_comparison import GtbEntry, compare, render_markdown_report


def _proposal(
    *,
    object_name,
    object_type="analog-input",
    object_instance=1,
    bacnet_units=None,
    proposed_point_class=None,
    confidence=None,
    reason_code="NO_RELIABLE_SIGNAL",
    status="proposed",
):
    return {
        "object_name": object_name,
        "object_type": object_type,
        "object_instance": object_instance,
        "bacnet_units": bacnet_units,
        "proposed_point_class": proposed_point_class,
        "confidence": confidence,
        "reason_code": reason_code,
        "status": status,
    }


def test_correspondance_stricte_sur_le_nom_normalise():
    gtb = [GtbEntry(name="T Départ CTA", unit="°C")]
    proposals = [
        _proposal(
            object_name="T Depart CTA",
            bacnet_units="degrees-celsius",
            proposed_point_class="temperature_sensor",
            confidence=0.9,
            reason_code="BACNET_UNITS_TEMPERATURE",
            status="proposed",
        )
    ]

    rows, summary = compare(gtb, proposals)

    assert summary.matched_count == 1
    assert summary.gtb_only_count == 0
    assert summary.discovery_only_count == 0
    matched = next(row for row in rows if row.match_kind == "matched")
    assert matched.gtb_name == "T Départ CTA"
    assert matched.discovered_name == "T Depart CTA"
    assert matched.proposed_point_class == "temperature_sensor"


def test_point_vu_par_la_gtb_mais_jamais_decouvert():
    gtb = [GtbEntry(name="Sonde Exterieure")]
    proposals: list[dict] = []

    rows, summary = compare(gtb, proposals)

    assert summary.gtb_only_count == 1
    assert summary.matched_count == 0
    row = rows[0]
    assert row.match_kind == "gtb_only"
    assert row.gtb_name == "Sonde Exterieure"
    assert row.discovered_name is None


def test_point_decouvert_absent_de_la_liste_gtb():
    gtb: list[GtbEntry] = []
    proposals = [_proposal(object_name="AI-07")]

    rows, summary = compare(gtb, proposals)

    assert summary.discovery_only_count == 1
    row = rows[0]
    assert row.match_kind == "discovery_only"
    assert row.discovered_name == "AI-07"


def test_jamais_de_correspondance_approximative_inventee():
    """Deux noms proches mais pas strictement identiques une fois
    normalisés restent deux lignes séparées — jamais un rapprochement
    incertain qui masquerait un vrai écart terrain."""
    gtb = [GtbEntry(name="Temperature Depart")]
    proposals = [_proposal(object_name="Temperature de Retour")]

    rows, summary = compare(gtb, proposals)

    assert summary.matched_count == 0
    assert summary.gtb_only_count == 1
    assert summary.discovery_only_count == 1


def test_compte_les_points_a_revoir_cote_gtb_only_jamais_inclus():
    gtb = [GtbEntry(name="Absent")]
    proposals = [
        _proposal(object_name="Classe Connue", proposed_point_class="pressure_sensor"),
        _proposal(object_name="Mode Multi Etat", reason_code="MULTISTATE_NOT_YET_MAPPED"),
    ]

    _rows, summary = compare(gtb, proposals)

    # Un point jamais découvert (gtb_only) n'a pas de classe à revoir : ce
    # n'est pas la même alerte qu'une classe manquante sur un point trouvé.
    assert summary.needs_review_count == 1
    assert summary.gtb_only_count == 1


def test_rapport_markdown_contient_le_resume_et_le_tableau():
    gtb = [GtbEntry(name="T Depart CTA", unit="°C")]
    proposals = [
        _proposal(
            object_name="T Depart CTA",
            proposed_point_class="temperature_sensor",
            confidence=0.9,
            reason_code="BACNET_UNITS_TEMPERATURE",
        ),
        _proposal(object_name="AI-07"),
    ]

    rows, summary = compare(gtb, proposals)
    report = render_markdown_report(rows, summary, title="Site pilote")

    assert "# Site pilote" in report
    assert "Correspondances trouvées" in report
    assert "T Depart CTA" in report
    assert "AI-07" in report
    assert "à revoir" in report
