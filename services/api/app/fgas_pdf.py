"""Remplissage du formulaire officiel CERFA 15497*04 à partir d'une fiche
`fgas_intervention_records` déjà enregistrée (voir app.fgas).

Le modèle vierge (`app/resources/cerfa_15497-04.pdf`) est le document fourni
par Mohamed le 02/10/2026 — un formulaire public de l'administration
française, pas un secret. Chaque champ rempli ici correspond à une colonne
de la fiche déjà validée par `app.fgas.record_fgas_intervention` : aucune
valeur n'est devinée ou calculée ici qui ne soit déjà en base.

Limite assumée et documentée (ne jamais inventer une donnée réglementaire,
règle du 02/10/2026) : la case à cocher [6]/[8]/[9] du formulaire (tableau de
fréquence minimale de contrôle selon la famille de fluide HCFC/HFC/HFO et la
charge) exigerait de classer `refrigerant_name` (texte libre saisi par
l'opérateur, ex. "R410A") dans une famille chimique. Aucune table de
correspondance fiable et exhaustive n'a été fournie ni vérifiée : ces cases
restent donc vierges sur le PDF généré, à cocher à la main si l'opérateur le
souhaite. Pareil pour [7] (présence d'un système de détection permanente)
quand `permanent_detection_system` est `None` (non renseigné sur le
terrain).
"""

import io
from importlib import resources
from typing import Any

from pypdf import PdfReader, PdfWriter

_TEMPLATE_PACKAGE = "app.resources"
_TEMPLATE_NAME = "cerfa_15497-04.pdf"

_NATURE_CHECKBOX_BY_CODE = {
    "assembly": "Case_Assemblage",
    "commissioning": "Case_MiseService",
    "modification": "Case_Modif",
    "maintenance": "Case_Maintenance",
    "leak_check_periodic": "Case_CtrlPerio",
    "leak_check_non_periodic": "Case_CtrlNonPerio",
    "decommissioning": "Case_Demantel",
    "other": "Case_Autre",
}

_WASTE_CHECKBOX_BY_CODE = {
    "un1078_non_flammable": "Case_12_UN1078",
    "other_non_flammable": "Case_12_Autre140601",
    "un3161_flammable": "Case_12_UN3161",
    "other_flammable": "Case_12_Autre160504",
}


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _amount(value: float | None) -> str:
    if value is None:
        return ""
    formatted = f"{value:.2f}".rstrip("0").rstrip(".")
    return formatted or "0"


def _date(value: Any) -> str:
    return value.strftime("%d/%m/%Y") if value is not None else ""


def _identity_block(name: str, address: str | None, siret: str | None) -> str:
    lines = [name]
    if address:
        lines.append(address)
    if siret:
        lines.append(f"SIRET : {siret}")
    return "\n".join(lines)


def _leak_fields(leaks: list[dict[str, Any]]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for index, leak in enumerate(leaks[:3], start=1):
        fields[f"Fuite_Loca_{index}"] = _text(leak.get("location"))
        repaired = leak.get("repaired")
        if repaired is True:
            fields[f"Case_Rep_Fuite{index}_realisee"] = "/Yes"
        elif repaired is False:
            fields[f"Case_Rep_Fuite{index}_AFaire"] = "/Yes"
    return fields


def build_cerfa_fields(record: dict[str, Any]) -> dict[str, str]:
    """Calcule les valeurs de champs AcroForm à partir d'une fiche fgas
    (telle que renvoyée par `app.fgas.get_fgas_intervention`)."""
    fields: dict[str, str] = {
        "Fiche_no": _text(record["fiche_number"]),
        "Operateur": _identity_block(
            record["operator_name"], record["operator_address"], record["operator_siret"]
        ),
        "Attestation_no": _text(record["operator_capacity_number"]),
        "Detenteur": _identity_block(
            record["detenteur_name"], record["detenteur_address"], record["detenteur_siret"]
        ),
        "Equipement_ID": _text(record["equipment_identification"]),
        "Equipement_Fluide": _text(record["refrigerant_name"]),
        "Equipement_Charge": _amount(record["total_charge_kg"]),
        "Equipement_teqCO2": _amount(record["co2_equivalent_tonnes"]),
        "Detecteur_ID": _text(record["manual_leak_detector_identification"]),
        "11_Quantite": _amount(record["charged_total_kg"]),
        "11_QA": _amount(record["charged_virgin_kg"]),
        "11_QB": _amount(record["charged_recycled_kg"]),
        "11_QC": _amount(record["charged_regenerated_kg"]),
        "11_Denom": _text(record["charged_fluid_name_if_changed"]),
        "11_QDE": _amount(record["recovered_total_kg"]),
        "11_QD": _amount(record["recovered_for_treatment_kg"]),
        "11_QE": _amount(record["recovered_for_reuse_kg"]),
        "11_BSFF": _text(record["bsff_number"]),
        "11_Contenant_ID": _text(record["container_identification"]),
        "Autre-FF-NON-inflammable": _text(record["waste_classification_other_non_flammable"]),
        "Autre-FF-inflammable": _text(record["waste_classification_other_flammable"]),
        "13_Instal": _text(record["destination_installation"]),
        "14_Observations": _text(record["observations"]),
        "Sign_Operateur_Nom": _text(record["operator_signatory_name"]),
        "Sign_Operateur_Qualite": _text(record["operator_signatory_role"]),
        "Sign_Operateur_Date": _date(record["signed_at"]),
        "Sign_Detenteur_Nom": _text(record["detenteur_signatory_name"]),
        "Sign_Detenteur_Qualite": _text(record["detenteur_signatory_role"]),
        "Sign_Detenteur_Date": _date(record["signed_at"]),
    }

    if record["nature_other_detail"]:
        fields["Autre"] = record["nature_other_detail"]
    for code in record["nature_of_intervention"]:
        fields[_NATURE_CHECKBOX_BY_CODE[code]] = "/Yes"
    for code in record["waste_classification"]:
        fields[_WASTE_CHECKBOX_BY_CODE[code]] = "/Yes"

    checked_on = record["manual_leak_detector_checked_on"]
    if checked_on is not None:
        fields["Controle_Jour"] = f"{checked_on.day:02d}"
        fields["Controle_Mois"] = f"{checked_on.month:02d}"
        fields["Controle_Annee"] = str(checked_on.year)

    if record["permanent_detection_system"] is True:
        fields["Bouton_Oui"] = "/1"
    elif record["permanent_detection_system"] is False:
        fields["Bouton_Oui"] = "/2"

    if record["leaks_found"] is True:
        fields["Case_Fuite_Oui"] = "/Yes"
    elif record["leaks_found"] is False:
        fields["Case_Fuite_Non"] = "/Yes"

    fields.update(_leak_fields(record["leaks"]))
    return fields


def render_cerfa_pdf(record: dict[str, Any]) -> bytes:
    """Renvoie le PDF CERFA 15497*04 rempli pour cette fiche, en bytes."""
    template_path = resources.files(_TEMPLATE_PACKAGE).joinpath(_TEMPLATE_NAME)
    with resources.as_file(template_path) as path:
        reader = PdfReader(path)
        writer = PdfWriter()
        writer.append(reader)
        fields = build_cerfa_fields(record)
        for page in writer.pages:
            writer.update_page_form_field_values(page, fields, auto_regenerate=False)
        writer.set_need_appearances_writer(True)

        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()
