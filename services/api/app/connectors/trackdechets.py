"""Trackdéchets / BSFF (bordereau de suivi de fluides frigorigènes) —
voir docs/regulatory/03-trackdechets-bsff.md. L'API officielle est en
GraphQL ; aucun compte ni jeton Trackdéchets n'a été fourni à ce jour
(directive de Mohamed, 02/10/2026) : l'interface abstraite et sa seule
implémentation (`NotConfiguredTrackDechetsClient`) existent, l'appel réel
est différé (`DEFERRED_EXTERNAL_INTEGRATION`), jamais simulé.

`app.fgas` enregistre déjà le numéro de BSFF saisi par l'opérateur
(`bsff_number`, texte libre, comme sur le CERFA papier) : ce module ne
remplace pas cette saisie, il permettrait un jour de la vérifier auprès de
Trackdéchets plutôt que de lui faire confiance telle quelle.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from app.errors import DomainError


class TrackDechetsError(DomainError, ValueError):
    pass


@dataclass(frozen=True)
class BsffRecord:
    """Champs volontairement minimaux : faute d'accès à l'API réelle, aucune
    correspondance de champ n'a été vérifiée contre le schéma GraphQL
    officiel. `raw` porte la réponse complète une fois une intégration
    réelle écrite, pour ne jamais perdre d'information en attendant que ce
    module soit complété."""

    id: str
    status: str
    raw: dict[str, Any]


class TrackDechetsClient(Protocol):
    def get_bsff(self, bsff_id: str) -> BsffRecord | None:
        """Consulte un bordereau de suivi de fluides frigorigènes par son
        identifiant. Renvoie `None` s'il n'existe pas — jamais une valeur
        inventée faute de réponse."""
        ...


class NotConfiguredTrackDechetsClient:
    """Seule implémentation aujourd'hui : échoue explicitement plutôt que de
    prétendre avoir consulté Trackdéchets."""

    def get_bsff(self, bsff_id: str) -> BsffRecord | None:
        raise TrackDechetsError("TRACKDECHETS_API_NOT_CONFIGURED")


DEFAULT_CLIENT: TrackDechetsClient = NotConfiguredTrackDechetsClient()
