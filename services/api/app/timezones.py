"""Fuseaux horaires IANA (« Europe/Paris »), jamais un décalage fixe : le
passage à l'heure d'été change le décalage, pas le fuseau."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.errors import DomainError


class TimezoneInvalid(DomainError, ValueError):
    pass


def check_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise TimezoneInvalid("TIMEZONE_UNKNOWN", timezone=name) from exc
