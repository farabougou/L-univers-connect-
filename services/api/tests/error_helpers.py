"""Vérifier une erreur métier par son code stable, jamais par sa phrase
(ADR 013 : les tests dépendent du code, pas du texte traduit)."""

from contextlib import contextmanager

import pytest


@contextmanager
def raises_code(exception_type: type[Exception], code: str):
    with pytest.raises(exception_type) as info:
        yield info
    assert getattr(info.value, "code", None) == code, str(info.value)
