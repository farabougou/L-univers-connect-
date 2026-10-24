"""Fixtures partagées par toute la suite. Voir aussi tests/jwt_helpers.py et
tests/tenant_cleanup.py, utilisés individuellement par les modules de test.
"""

import pytest

from app.rate_limit import limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """La limitation de débit (app/rate_limit.py) classe par adresse IP —
    `TestClient` utilise toujours la même adresse factice, donc sans cette
    remise à zéro, les appels à `/devices/auth` d'un test épuiseraient le
    quota des tests suivants (faux positifs 429 sans rapport avec leur
    logique). Un vrai client reparti de zéro à chaque minute ; chaque test
    doit pouvoir en faire autant."""
    limiter.reset()
    yield
