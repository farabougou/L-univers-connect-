"""Asset Economics Engine — premier maillon (V2, 02/10/2026, ADR 012 §15).

Périmètre de ce premier incrément, volontairement étroit : le coût
énergétique estimé, seule dimension économique calculable aujourd'hui sans
inventer de donnée. Les autres catégories citées par l'addendum (coût
maintenance, pièces, interventions, temps d'arrêt, contrats, garantie,
remplacement) exigeraient une saisie qui n'existe pas encore dans le
produit ; les ajouter ici sans cette saisie reviendrait à fabriquer un
chiffre — interdit par la règle du dépôt. Elles restent `DEFER`.

Le tarif est une configuration versionnée de plus (`config_type =
energy_tariff`, même mécanisme que `app.energy.baseline` : `app.config_versions`
gère déjà création, activation à une seule personne, historique et retour
arrière — aucun nouvel endpoint, les routes génériques `/configs` suffisent).
Un seul tarif actif par site (contrainte déjà en base,
`uq_config_versions_one_active`, `subject_key = site_id`).

Le coût est calculé à la lecture à partir d'un résultat déjà normalisé
(`energy_normalized_results`), jamais stocké : changer le tarif ne doit
jamais réécrire un résultat déjà calculé (même principe que
`app.equipment_status`, « calcul à la lecture, jamais stocké »). Une
estimation de coût n'est jamais présentée comme une facture réelle (ADR 013 :
ne jamais affirmer plus que ce que le système sait).
"""

import uuid
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.config_versions import ConfigInvalid, register_config_type

ENERGY_TARIFF = "energy_tariff"
ENERGY_TARIFF_SCHEMA = "energy_tariff/1"


class EnergyTariffContent(BaseModel):
    model_config = {"extra": "forbid"}

    # Code à 3 lettres majuscules (ex. EUR, USD) : la forme est vérifiée,
    # jamais la validité réelle du code — aucune table ISO 4217 n'est
    # embarquée ici, ce serait prétendre une rigueur qu'on n'a pas.
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    price_per_kwh: float = Field(gt=0)


def _validate_energy_tariff(connection: Connection, content: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = EnergyTariffContent(**content)
    except ValidationError as exc:
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        raise ConfigInvalid("ENERGY_TARIFF_CONTENT_INVALID", fields=fields) from exc
    return parsed.model_dump(mode="json")


register_config_type(ENERGY_TARIFF, ENERGY_TARIFF_SCHEMA, _validate_energy_tariff)


def get_active_tariff(connection: Connection, site_id: uuid.UUID) -> dict[str, Any] | None:
    """Tarif actif du site, ou None si aucun n'a jamais été activé — un
    résultat énergétique reste alors sans coût estimé, jamais un coût à
    zéro ou par défaut."""
    row = connection.execute(
        text(
            "SELECT content FROM config_versions WHERE config_type = :type "
            "AND subject_key = :site_id AND status = 'active'"
        ),
        {"type": ENERGY_TARIFF, "site_id": str(site_id)},
    ).scalar()
    return dict(row) if row else None


def estimate_energy_cost(
    *, raw_consumption: float, normalized_consumption: float | None, tariff: dict[str, Any]
) -> dict[str, Any]:
    """Coût estimé d'un résultat énergétique déjà calculé, à partir d'un
    tarif actif. Préfère la consommation normalisée (comparable d'une
    période à l'autre) quand elle existe, sinon la consommation brute —
    jamais une valeur recalculée différemment de celle déjà affichée à côté."""
    price = tariff["price_per_kwh"]
    basis: str
    consumption: float
    if normalized_consumption is not None:
        basis = "normalized"
        consumption = normalized_consumption
    else:
        basis = "raw"
        consumption = raw_consumption
    return {
        "amount": round(consumption * price, 2),
        "currency": tariff["currency"],
        "price_per_kwh": price,
        "basis": basis,
    }
