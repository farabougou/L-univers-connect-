"""Catalogues de messages et choix de la langue (ADR 013).

Les catalogues vivent dans `shared/i18n/<langue>/` à la racine du dépôt, pour
être partagés par l'API, le web et le mobile : un même code a le même texte
partout. L'API n'utilise que des paramètres simples (`{nom}`) ; les pluriels
et accords restent aux interfaces (ICU MessageFormat).

En déploiement, le dossier `shared/` doit être copié avec l'API, ou désigné par
la variable d'environnement `I18N_DIR`.
"""

import json
import os
from functools import cache
from pathlib import Path
from typing import Any

SUPPORTED_LOCALES = ("fr", "en")
DEFAULT_LOCALE = "fr"

def _catalog_dir() -> Path:
    """`I18N_DIR` s'il est défini (voir Dockerfile de déploiement) ; sinon,
    `shared/i18n` à la racine du dépôt, calculé seulement ici et pas au
    chargement du module : en déploiement, `services/api/app/` n'est plus à la
    même profondeur que dans un clone complet du dépôt, et ce calcul lèverait
    une erreur avant même de lire la variable d'environnement censée l'éviter."""
    override = os.environ.get("I18N_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "shared" / "i18n"


@cache
def load_catalog(locale: str, namespace: str = "errors") -> dict[str, Any]:
    return json.loads((_catalog_dir() / locale / f"{namespace}.json").read_text("utf-8"))


def negotiate_locale(accept_language: str | None) -> str:
    """Langue préférée parmi celles prises en charge (en-tête Accept-Language,
    pondérations q comprises) ; le français par défaut."""
    if not accept_language:
        return DEFAULT_LOCALE
    choices: list[tuple[float, int, str]] = []
    for position, part in enumerate(accept_language.split(",")):
        pieces = part.strip().split(";")
        language = pieces[0].strip().lower().split("-")[0]
        weight = 1.0
        for parameter in pieces[1:]:
            name, _, value = parameter.strip().partition("=")
            if name.strip() == "q":
                try:
                    weight = float(value)
                except ValueError:
                    weight = 0.0
        if language in SUPPORTED_LOCALES and weight > 0:
            choices.append((-weight, position, language))
    return min(choices)[2] if choices else DEFAULT_LOCALE


def _format_param(value: Any) -> str:
    if isinstance(value, list | tuple | set):
        return ", ".join(str(item) for item in value)
    return str(value)


class _KeepMissing(dict):
    """Un paramètre manquant reste visible (« {nom} ») au lieu de faire
    échouer l'affichage d'une erreur : un test vérifie les paramètres."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render_text(template: str, params: dict[str, Any]) -> str:
    return template.format_map(_KeepMissing({k: _format_param(v) for k, v in params.items()}))


def render(code: str, params: dict[str, Any], locale: str = DEFAULT_LOCALE) -> str:
    template = load_catalog(locale)["codes"].get(code)
    if template is None:
        return code
    return render_text(template, params)


def title(status: int, locale: str = DEFAULT_LOCALE) -> str:
    titles = load_catalog(locale)["titles"]
    return titles.get(str(status), titles["400" if status < 500 else "500"])
