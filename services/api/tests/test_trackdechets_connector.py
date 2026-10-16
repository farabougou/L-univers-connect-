"""Trackdéchets / BSFF (app.connectors.trackdechets) : aucun accès API
aujourd'hui — l'adaptateur par défaut échoue explicitement plutôt que de
prétendre avoir consulté le bordereau."""

import pytest

from app.connectors.trackdechets import DEFAULT_CLIENT, TrackDechetsError


def test_default_client_fails_explicitly_rather_than_pretend_to_look_up_a_bsff() -> None:
    with pytest.raises(TrackDechetsError) as excinfo:
        DEFAULT_CLIENT.get_bsff("BSFF-2026-000001")
    assert excinfo.value.code == "TRACKDECHETS_API_NOT_CONFIGURED"
