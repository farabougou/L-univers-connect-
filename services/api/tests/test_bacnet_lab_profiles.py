"""BACnet Lab — profils multiples (directive de Mohamed, 30/09/2026 :
« enrichir le BACnet Lab avec plusieurs catégories d'équipements et
scénarios réalistes »). Palier SIMULATOR_TESTED : chaque profil est un vrai
appareil BACnet/IP (bacpypes3), jamais un simulacre ; aucun de ces tests ne
constitue une validation terrain (voir tests/bacnet_lab.py et
docs/adr/015-decouverte-bacnet-v1.md)."""

import pytest

from app.connectors.bacnet import discover_device, read_device_objects
from app.connectors.bacnet_semantics import guess_point_class
from tests.bacnet_lab import BacnetLab, BacnetSite, list_profiles

# Une adresse dédiée par profil pour ne jamais se marcher dessus si les
# tests d'un même fichier tournaient en parallèle un jour.
_ADDRESSES = {
    "cta": "127.0.0.1:47840",
    "groupe_froid": "127.0.0.1:47841",
    "groupe_electrogene": "127.0.0.1:47842",
    "vrv_drv": "127.0.0.1:47843",
    "sous_station_thermique": "127.0.0.1:47844",
    "comptage": "127.0.0.1:47845",
}

# Nombre d'objets « point » attendus par profil (voir tests/bacnet_lab.py) :
# preuve que chaque profil expose bien un appareil complet, pas un moignon.
_EXPECTED_OBJECT_COUNTS = {
    "cta": 8,
    "groupe_froid": 7,
    "groupe_electrogene": 6,
    "vrv_drv": 6,
    "sous_station_thermique": 6,
    "comptage": 4,
}


def test_tous_les_profils_declares_ont_une_adresse_de_test():
    assert set(list_profiles()) == set(_ADDRESSES)
    assert set(list_profiles()) == set(_EXPECTED_OBJECT_COUNTS)


def test_profil_inconnu_est_refuse_immediatement_sans_reseau():
    with pytest.raises(ValueError):
        BacnetLab("127.0.0.1:0", profile="pompe_a_licorne")


@pytest.mark.parametrize("profile", list_profiles())
def test_chaque_profil_est_un_appareil_bacnet_reel_et_complet(profile):
    address = _ADDRESSES[profile]
    device_instance = 5100 + list_profiles().index(profile)
    lab = BacnetLab(address, device_instance=device_instance, profile=profile)
    lab.start()
    try:
        info = discover_device(address, timeout=3.0)
        assert info.device_instance == device_instance

        objects = read_device_objects(address, device_instance, timeout=3.0)
        assert len(objects) == _EXPECTED_OBJECT_COUNTS[profile]
        assert all(obj.object_name for obj in objects)

        # Le devineur ne doit jamais planter, quel que soit l'objet réel
        # découvert, et ne doit jamais inventer une correspondance hors de
        # sa compétence documentée.
        guesses = [
            guess_point_class(
                object_type=obj.object_type,
                value_type=obj.value_type,
                units=obj.units,
                object_name=obj.object_name,
                description=obj.description,
            )
            for obj in objects
        ]
        for guess in guesses:
            if guess.point_class is None:
                assert guess.confidence is None
                assert guess.reason_code in ("NO_RELIABLE_SIGNAL", "MULTISTATE_NOT_YET_MAPPED")
    finally:
        lab.stop()


def test_groupe_electrogene_tension_reste_a_revoir():
    # Root cause réel du flake intermittent (trouvé le 02/10/2026, pas
    # seulement contourné) : ce port était partagé à l'identique avec
    # tests/test_bacnet_field_comparison_e2e.py (un simulateur BACnet UDP à
    # portée module, démarré/arrêté une fois pour tout le fichier). Sur la
    # suite complète, selon l'ordre de collecte, le simulateur de ce fichier
    # pouvait démarrer avant que le port libéré par l'autre fichier ne soit
    # réellement disponible côté OS (fermeture asynchrone d'un socket UDP,
    # jamais garantie instantanée) — d'où le délai dépassé observé
    # uniquement sous charge (suite complète), jamais en isolation. Un port
    # dédié « distinct de _ADDRESSES » ne suffisait pas : il fallait un port
    # distinct de TOUTE adresse utilisée ailleurs dans la suite, pas
    # seulement dans ce fichier.
    address = "127.0.0.1:47847"
    lab = BacnetLab(address, device_instance=5200, profile="groupe_electrogene")
    lab.start()
    try:
        objects = read_device_objects(address, 5200, timeout=3.0)
        tension = next(obj for obj in objects if obj.object_name == "Tension Sortie")
        guess = guess_point_class(
            object_type=tension.object_type,
            value_type=tension.value_type,
            units=tension.units,
            object_name=tension.object_name,
            description=tension.description,
        )
        # Aucune classe de tension dans notre vocabulaire actuel (règle des
        # trois) : jamais une correspondance inventée pour « faire complet ».
        assert guess.point_class is None
        assert guess.reason_code == "NO_RELIABLE_SIGNAL"
    finally:
        lab.stop()


def test_bacnet_site_simule_plusieurs_appareils_de_categories_differentes():
    site = BacnetSite(
        {
            "cta-01": ("127.0.0.1:47850", "cta"),
            "groupe-froid-01": ("127.0.0.1:47851", "groupe_froid"),
            "comptage-01": ("127.0.0.1:47852", "comptage"),
        }
    )
    devices = site.start()
    try:
        assert set(devices) == {"cta-01", "groupe-froid-01", "comptage-01"}
        instances = {name: device.device_instance for name, device in devices.items()}
        assert len(set(instances.values())) == 3  # identifiants BACnet distincts

        for name, device in devices.items():
            info = discover_device(device.address, timeout=3.0)
            assert info.device_instance == device.device_instance
            objects = read_device_objects(device.address, device.device_instance, timeout=3.0)
            assert len(objects) == _EXPECTED_OBJECT_COUNTS[device.profile], name
    finally:
        site.stop()
