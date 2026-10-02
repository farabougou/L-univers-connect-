"""Remplissage du CERFA 15497*04 (app.fgas_pdf) à partir d'une fiche fgas
déjà enregistrée — sans base de données, juste la correspondance de champs."""

import datetime
import io

from pypdf import PdfReader

from app.fgas_pdf import build_cerfa_fields, render_cerfa_pdf

_RECORD = {
    "fiche_number": "F-2026-042",
    "operator_name": "Froid Services SARL",
    "operator_address": "1 rue du Froid, 75000 Paris",
    "operator_siret": "12345678900012",
    "operator_capacity_number": "CAP-9999",
    "detenteur_name": "Client Demo",
    "detenteur_address": "2 avenue du Client, 75000 Paris",
    "detenteur_siret": None,
    "equipment_identification": "PAC-01 — Chaufferie",
    "refrigerant_name": "R410A",
    "total_charge_kg": 12.5,
    "co2_equivalent_tonnes": 26.1,
    "nature_of_intervention": ["maintenance", "leak_check_periodic"],
    "nature_other_detail": None,
    "manual_leak_detector_identification": "Détecteur XYZ",
    "manual_leak_detector_checked_on": datetime.date(2026, 9, 1),
    "permanent_detection_system": False,
    "leaks_found": True,
    "leaks": [
        {"location": "Vanne haute pression", "repaired": True},
        {"location": "Joint compresseur", "repaired": False},
    ],
    "charged_total_kg": 1.0,
    "charged_virgin_kg": 1.0,
    "charged_recycled_kg": 0.0,
    "charged_regenerated_kg": 0.0,
    "charged_fluid_name_if_changed": None,
    "recovered_total_kg": 0.5,
    "recovered_for_treatment_kg": 0.5,
    "recovered_for_reuse_kg": 0.0,
    "bsff_number": "BSFF-123",
    "container_identification": "BOUTEILLE-7",
    "waste_classification": ["un1078_non_flammable"],
    "waste_classification_other_non_flammable": None,
    "waste_classification_other_flammable": None,
    "destination_installation": "Centre de traitement Sud",
    "observations": "RAS",
    "operator_signatory_name": "Mohamed",
    "operator_signatory_role": "Technicien",
    "detenteur_signatory_name": "Marie Curie",
    "detenteur_signatory_role": "Responsable site",
    "signed_at": datetime.date(2026, 10, 2),
}


def test_build_cerfa_fields_maps_every_recorded_value() -> None:
    fields = build_cerfa_fields(_RECORD)

    assert fields["Fiche_no"] == "F-2026-042"
    assert fields["Operateur"] == (
        "Froid Services SARL\n1 rue du Froid, 75000 Paris\nSIRET : 12345678900012"
    )
    # Pas de SIRET détenteur fourni : pas de ligne « SIRET » ajoutée.
    assert fields["Detenteur"] == "Client Demo\n2 avenue du Client, 75000 Paris"
    assert fields["Equipement_Charge"] == "12.5"
    assert fields["Case_Maintenance"] == "/Yes"
    assert fields["Case_CtrlPerio"] == "/Yes"
    assert "Case_Assemblage" not in fields  # case non cochée : laissée au modèle (Off)
    assert fields["Bouton_Oui"] == "/2"  # pas de détection permanente
    assert fields["Case_Fuite_Oui"] == "/Yes"
    assert fields["Fuite_Loca_1"] == "Vanne haute pression"
    assert fields["Case_Rep_Fuite1_realisee"] == "/Yes"
    assert fields["Fuite_Loca_2"] == "Joint compresseur"
    assert fields["Case_Rep_Fuite2_AFaire"] == "/Yes"
    assert fields["Controle_Jour"] == "01"
    assert fields["Controle_Mois"] == "09"
    assert fields["Controle_Annee"] == "2026"
    assert fields["Case_12_UN1078"] == "/Yes"
    assert "Case_12_UN3161" not in fields
    assert fields["Sign_Operateur_Date"] == "02/10/2026"
    assert fields["Sign_Detenteur_Date"] == "02/10/2026"


def test_render_cerfa_pdf_produces_a_readable_filled_pdf() -> None:
    pdf_bytes = render_cerfa_pdf(_RECORD)

    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1
    fields = reader.get_fields()
    assert fields["Fiche_no"]["/V"] == "F-2026-042"
    assert fields["11_BSFF"]["/V"] == "BSFF-123"


def test_unrecognised_leak_detection_state_is_never_guessed() -> None:
    record = {**_RECORD, "permanent_detection_system": None}
    fields = build_cerfa_fields(record)
    assert "Bouton_Oui" not in fields
