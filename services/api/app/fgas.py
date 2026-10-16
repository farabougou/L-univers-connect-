"""Fiche d'intervention fluides frigorigènes fluorés (CERFA 15497*04,
articles R. 543-79 et R. 543-82 du code de l'environnement).

Document officiel fourni par Mohamed le 02/10/2026 (`fgas_intervention_records`,
migration adce8b5d46b8) : une fiche est une preuve légale, enregistrée une
fois, jamais modifiée ni supprimée (déclencheurs en base), rattachée à une
intervention existante — même principe que app.closures (clôture
structurée), même protection contre la double saisie (réponse perdue sur le
terrain : un renvoi identique renvoie la fiche déjà créée, un renvoi
différent est refusé).

Le tonnage équivalent CO2 ([3] du formulaire) reste une saisie manuelle de
l'opérateur : aucune table officielle de PRG vérifiée n'a été fournie,
aucune valeur n'est donc calculée ni devinée (voir app.properties).

Les totaux de manipulation ([11], A+B+C et D+E) sont calculés ici à partir de
leurs composants, jamais acceptés indépendamment : un total qui ne
correspond plus à ses composants est une erreur possible sur le papier,
impossible dans ce domaine.
"""

import json
import uuid
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import DomainError
from app.fgas_vocabulary import NATURE_CODES, WASTE_CLASSIFICATION_CODES


class FgasError(DomainError, ValueError):
    pass


class FgasNotFound(DomainError, LookupError):
    status = 404


class FgasConflict(DomainError, ValueError):
    status = 409


_COLUMNS = (
    "id, intervention_id, fiche_number, operator_name, operator_address, operator_siret, "
    "operator_capacity_number, detenteur_name, detenteur_address, detenteur_siret, "
    "equipment_identification, refrigerant_name, total_charge_kg, co2_equivalent_tonnes, "
    "nature_of_intervention, nature_other_detail, manual_leak_detector_identification, "
    "manual_leak_detector_checked_on, permanent_detection_system, leaks_found, leaks, "
    "charged_total_kg, charged_virgin_kg, charged_recycled_kg, charged_regenerated_kg, "
    "charged_fluid_name_if_changed, recovered_total_kg, recovered_for_treatment_kg, "
    "recovered_for_reuse_kg, bsff_number, container_identification, waste_classification, "
    "waste_classification_other_non_flammable, waste_classification_other_flammable, "
    "destination_installation, observations, operator_signatory_name, operator_signatory_role, "
    "detenteur_signatory_name, detenteur_signatory_role, signed_at, created_by, created_at"
)


def _check_codes(codes: list[str], vocabulary: tuple[str, ...], field: str) -> None:
    for code in codes:
        if code not in vocabulary:
            raise FgasError("FGAS_CODE_UNKNOWN", field=field, code=code)


def record_fgas_intervention(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    intervention_id: uuid.UUID,
    fiche_number: str | None,
    # [1] Opérateur
    operator_name: str,
    operator_address: str | None,
    operator_siret: str | None,
    operator_capacity_number: str | None,
    # [2] Détenteur
    detenteur_name: str,
    detenteur_address: str | None,
    detenteur_siret: str | None,
    # [3] Équipement concerné
    equipment_identification: str,
    refrigerant_name: str,
    total_charge_kg: float,
    co2_equivalent_tonnes: float | None,
    # [4] Nature de l'intervention
    nature_of_intervention: list[str],
    nature_other_detail: str | None,
    # [5]/[6] Contrôle d'étanchéité
    manual_leak_detector_identification: str | None,
    manual_leak_detector_checked_on: date | None,
    permanent_detection_system: bool | None,
    # [10] Fuites constatées
    leaks_found: bool | None,
    leaks: list[dict[str, Any]],
    # [11] Manipulation du fluide frigorigène
    charged_virgin_kg: float,
    charged_recycled_kg: float,
    charged_regenerated_kg: float,
    charged_fluid_name_if_changed: str | None,
    recovered_for_treatment_kg: float,
    recovered_for_reuse_kg: float,
    bsff_number: str | None,
    container_identification: str | None,
    # [12] Dénomination ADR/RID
    waste_classification: list[str],
    waste_classification_other_non_flammable: str | None,
    waste_classification_other_flammable: str | None,
    # [13]/[14]
    destination_installation: str | None,
    observations: str | None,
    # Signatures
    operator_signatory_name: str,
    operator_signatory_role: str | None,
    detenteur_signatory_name: str | None,
    detenteur_signatory_role: str | None,
    signed_at: date,
    created_by: str,
) -> tuple[uuid.UUID, bool]:
    """Enregistre la fiche ; renvoie (identifiant, créée maintenant ?)."""
    if total_charge_kg < 0:
        raise FgasError("FGAS_QUANTITY_NEGATIVE", field="total_charge_kg")
    if co2_equivalent_tonnes is not None and co2_equivalent_tonnes < 0:
        raise FgasError("FGAS_QUANTITY_NEGATIVE", field="co2_equivalent_tonnes")
    for value, field in (
        (charged_virgin_kg, "charged_virgin_kg"),
        (charged_recycled_kg, "charged_recycled_kg"),
        (charged_regenerated_kg, "charged_regenerated_kg"),
        (recovered_for_treatment_kg, "recovered_for_treatment_kg"),
        (recovered_for_reuse_kg, "recovered_for_reuse_kg"),
    ):
        if value < 0:
            raise FgasError("FGAS_QUANTITY_NEGATIVE", field=field)

    if not nature_of_intervention:
        raise FgasError("FGAS_NATURE_REQUIRED")
    _check_codes(nature_of_intervention, NATURE_CODES, "nature_of_intervention")
    if "other" in nature_of_intervention and not nature_other_detail:
        raise FgasError("FGAS_OTHER_DETAIL_REQUIRED", field="nature_other_detail")

    _check_codes(waste_classification, WASTE_CLASSIFICATION_CODES, "waste_classification")
    if "other_non_flammable" in waste_classification and not (
        waste_classification_other_non_flammable
    ):
        raise FgasError(
            "FGAS_OTHER_DETAIL_REQUIRED", field="waste_classification_other_non_flammable"
        )
    if "other_flammable" in waste_classification and not waste_classification_other_flammable:
        raise FgasError("FGAS_OTHER_DETAIL_REQUIRED", field="waste_classification_other_flammable")

    for leak in leaks:
        if not leak.get("location"):
            raise FgasError("FGAS_LEAK_LOCATION_REQUIRED")

    charged_total_kg = charged_virgin_kg + charged_recycled_kg + charged_regenerated_kg
    recovered_total_kg = recovered_for_treatment_kg + recovered_for_reuse_kg

    exists = connection.execute(
        text("SELECT 1 FROM interventions WHERE id = :id"), {"id": intervention_id}
    ).scalar()
    if not exists:
        raise FgasNotFound("INTERVENTION_NOT_FOUND")

    existing = get_fgas_intervention(connection, intervention_id)
    submitted = {
        "fiche_number": fiche_number,
        "operator_name": operator_name,
        "operator_address": operator_address,
        "operator_siret": operator_siret,
        "operator_capacity_number": operator_capacity_number,
        "detenteur_name": detenteur_name,
        "detenteur_address": detenteur_address,
        "detenteur_siret": detenteur_siret,
        "equipment_identification": equipment_identification,
        "refrigerant_name": refrigerant_name,
        "total_charge_kg": total_charge_kg,
        "co2_equivalent_tonnes": co2_equivalent_tonnes,
        "nature_of_intervention": json.loads(json.dumps(nature_of_intervention)),
        "nature_other_detail": nature_other_detail,
        "manual_leak_detector_identification": manual_leak_detector_identification,
        "manual_leak_detector_checked_on": manual_leak_detector_checked_on,
        "permanent_detection_system": permanent_detection_system,
        "leaks_found": leaks_found,
        "leaks": json.loads(json.dumps(leaks)),
        "charged_total_kg": charged_total_kg,
        "charged_virgin_kg": charged_virgin_kg,
        "charged_recycled_kg": charged_recycled_kg,
        "charged_regenerated_kg": charged_regenerated_kg,
        "charged_fluid_name_if_changed": charged_fluid_name_if_changed,
        "recovered_total_kg": recovered_total_kg,
        "recovered_for_treatment_kg": recovered_for_treatment_kg,
        "recovered_for_reuse_kg": recovered_for_reuse_kg,
        "bsff_number": bsff_number,
        "container_identification": container_identification,
        "waste_classification": json.loads(json.dumps(waste_classification)),
        "waste_classification_other_non_flammable": waste_classification_other_non_flammable,
        "waste_classification_other_flammable": waste_classification_other_flammable,
        "destination_installation": destination_installation,
        "observations": observations,
        "operator_signatory_name": operator_signatory_name,
        "operator_signatory_role": operator_signatory_role,
        "detenteur_signatory_name": detenteur_signatory_name,
        "detenteur_signatory_role": detenteur_signatory_role,
        "signed_at": signed_at,
        "created_by": created_by,
    }
    if existing is not None:
        # Renvoi d'une fiche déjà reçue (réponse perdue côté terrain) : même
        # contenu → la fiche existante ; contenu différent → refus, une
        # fiche signée n'est jamais réécrite.
        if any(existing[field] != value for field, value in submitted.items()):
            raise FgasConflict("FGAS_ALREADY_RECORDED")
        return existing["id"], False

    record_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO fgas_intervention_records (id, tenant_id, intervention_id, "
            "fiche_number, operator_name, operator_address, operator_siret, "
            "operator_capacity_number, detenteur_name, detenteur_address, detenteur_siret, "
            "equipment_identification, refrigerant_name, total_charge_kg, "
            "co2_equivalent_tonnes, nature_of_intervention, nature_other_detail, "
            "manual_leak_detector_identification, manual_leak_detector_checked_on, "
            "permanent_detection_system, leaks_found, leaks, charged_total_kg, "
            "charged_virgin_kg, charged_recycled_kg, charged_regenerated_kg, "
            "charged_fluid_name_if_changed, recovered_total_kg, recovered_for_treatment_kg, "
            "recovered_for_reuse_kg, bsff_number, container_identification, "
            "waste_classification, waste_classification_other_non_flammable, "
            "waste_classification_other_flammable, destination_installation, observations, "
            "operator_signatory_name, operator_signatory_role, detenteur_signatory_name, "
            "detenteur_signatory_role, signed_at, created_by) VALUES "
            "(:id, :tenant_id, :intervention_id, :fiche_number, :operator_name, "
            ":operator_address, :operator_siret, :operator_capacity_number, :detenteur_name, "
            ":detenteur_address, :detenteur_siret, :equipment_identification, "
            ":refrigerant_name, :total_charge_kg, :co2_equivalent_tonnes, "
            "CAST(:nature_of_intervention AS JSONB), :nature_other_detail, "
            ":manual_leak_detector_identification, :manual_leak_detector_checked_on, "
            ":permanent_detection_system, :leaks_found, CAST(:leaks AS JSONB), "
            ":charged_total_kg, :charged_virgin_kg, :charged_recycled_kg, "
            ":charged_regenerated_kg, :charged_fluid_name_if_changed, :recovered_total_kg, "
            ":recovered_for_treatment_kg, :recovered_for_reuse_kg, :bsff_number, "
            ":container_identification, CAST(:waste_classification AS JSONB), "
            ":waste_classification_other_non_flammable, "
            ":waste_classification_other_flammable, :destination_installation, "
            ":observations, :operator_signatory_name, :operator_signatory_role, "
            ":detenteur_signatory_name, :detenteur_signatory_role, :signed_at, :created_by)"
        ),
        {
            "id": record_id,
            "tenant_id": tenant_id,
            "intervention_id": intervention_id,
            **{
                key: (
                    json.dumps(value, ensure_ascii=False)
                    if key in ("nature_of_intervention", "leaks", "waste_classification")
                    else value
                )
                for key, value in submitted.items()
            },
        },
    )
    return record_id, True


def get_fgas_intervention(
    connection: Connection, intervention_id: uuid.UUID
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(
                f"SELECT {_COLUMNS} FROM fgas_intervention_records WHERE intervention_id = :id"
            ),
            {"id": intervention_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None
