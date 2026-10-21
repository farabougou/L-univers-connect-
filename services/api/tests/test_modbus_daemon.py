"""Démon de sondage : la configuration vient de l'API (GET /edge/config,
appareil authentifié), plusieurs tours, plusieurs points en même temps, un
tour raté n'arrête pas les suivants, et une mesure lue pendant une coupure
de l'API repart au lieu d'être perdue.

Le démon ne touche plus jamais la base directement (M4) : ces tests
appellent l'application FastAPI réelle par HTTP (ASGITransport), exactement
le chemin qu'emprunte un appareil sur site.

`run(max_cycles=...)` (scripts/modbus_daemon.py) est le même code que celui
lancé en continu sur site, juste borné pour le test.
"""

import threading
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pymodbus.server import ServerStop, StartTcpServer
from sqlalchemy import text
from starlette.testclient import TestClient

import scripts.modbus_daemon as daemon
from app.connectors.edge_client import EdgeApiClient, PrivateKeyCredential
from app.connectors.offline_buffer import BufferedReading, OfflineBuffer
from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from scripts.modbus_daemon import run
from scripts.modbus_simulator import build_context
from tests.modbus_fixtures import (
    activate_device_mapping,
    cleanup_tenant,
    create_tenant_with_energy_and_power_points,
    create_tenant_with_energy_point,
    provision_device_by_public_key_for_tenant,
    provision_device_for_tenant,
)

PORT = 5097


@pytest.fixture(scope="module", autouse=True)
def modbus_simulator():
    thread = threading.Thread(
        target=StartTcpServer,
        args=(build_context(),),
        kwargs={"address": ("127.0.0.1", PORT)},
        daemon=True,
    )
    thread.start()
    time.sleep(0.5)
    yield
    ServerStop()
    thread.join(timeout=2)


def _api(tenant: dict) -> EdgeApiClient:
    # TestClient (Starlette) est une sous-classe de httpx.Client qui sait
    # appeler une application ASGI de façon synchrone : exactement ce dont
    # EdgeApiClient a besoin, sans passer par un vrai socket réseau.
    return EdgeApiClient(
        client=TestClient(app),
        tenant_id=tenant["tenant_id"],
        device_id=tenant["device_id"],
        secret=tenant["secret"],
    )


@pytest.fixture
def tenant():
    created = create_tenant_with_energy_point("ClientModbusDaemon")
    activate_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        host="127.0.0.1",
        port=PORT,
        points=[{"point_id": str(created["point_id"]), "register_name": "total_active_energy"}],
    )
    secret = provision_device_for_tenant(tenant_id=created["tenant_id"], device_id="sdm120-daemon")
    yield {**created, "device_id": "sdm120-daemon", "secret": secret}
    cleanup_tenant(created)


@pytest.fixture
def tenant_two_points():
    created = create_tenant_with_energy_and_power_points("ClientModbusDaemonMulti")
    activate_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        host="127.0.0.1",
        port=PORT,
        points=[
            {"point_id": str(created["energy_point_id"]), "register_name": "total_active_energy"},
            {"point_id": str(created["power_point_id"]), "register_name": "active_power"},
        ],
    )
    secret = provision_device_for_tenant(tenant_id=created["tenant_id"], device_id="sdm120-daemon")
    yield {**created, "device_id": "sdm120-daemon", "secret": secret}
    cleanup_tenant(created)


def test_plusieurs_tours_par_cle_publique_enregistrent_plusieurs_mesures(tenant, tmp_path):
    """Même chemin HTTP réel que les autres tests de ce fichier, mais
    authentifié par la preuve signée du modèle cible (Mohamed, 24/09/2026)
    plutôt que par le secret partagé de compatibilité — voir app/devices.py."""
    private_key_pem = provision_device_by_public_key_for_tenant(
        tenant_id=tenant["tenant_id"], device_id="edge-cle-publique"
    )
    api = EdgeApiClient(
        client=TestClient(app),
        tenant_id=tenant["tenant_id"],
        device_id="edge-cle-publique",
        credential=PrivateKeyCredential(
            private_key_pem=private_key_pem,
            device_id="edge-cle-publique",
            tenant_id=tenant["tenant_id"],
        ),
    )
    with api:
        cycles = run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.05,
            buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
            max_cycles=3,
        )

    assert cycles == 3
    assert _measurement_count(tenant["tenant_id"]) == 3


def _measurement_count(tenant_id) -> int:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        return connection.execute(
            text("SELECT count(*) FROM measurements WHERE tenant_id = :id"), {"id": tenant_id}
        ).scalar()


def test_plusieurs_tours_enregistrent_plusieurs_mesures(tenant, tmp_path):
    with _api(tenant) as api:
        cycles = run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.05,
            buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
            max_cycles=3,
        )

    assert cycles == 3
    assert _measurement_count(tenant["tenant_id"]) == 3


def test_deux_points_du_meme_appareil_sont_releves_ensemble(tenant_two_points, tmp_path):
    with _api(tenant_two_points) as api:
        cycles = run(
            api=api,
            equipment_id=tenant_two_points["location_id"],
            interval_seconds=0.05,
            buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
            max_cycles=1,
        )

    assert cycles == 1
    # Un seul tour, deux points : deux mesures, pas une seule, pas un point câblé en dur.
    assert _measurement_count(tenant_two_points["tenant_id"]) == 2


def test_aucune_configuration_active_arrete_le_demarrage(tenant, tmp_path):
    equipement_sans_mapping = tenant["point_id"]  # n'importe quel id sans mapping actif
    with _api(tenant) as api, pytest.raises(SystemExit):
        run(
            api=api,
            equipment_id=equipement_sans_mapping,
            interval_seconds=0.05,
            buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
            max_cycles=1,
        )


def test_un_tour_rate_n_arrete_pas_le_demon(tenant, tmp_path):
    # Reconfigure vers un port sans rien qui écoute (nouvelle version active,
    # l'ancienne est remplacée) : chaque tour échoue côté lecture Modbus, mais
    # la boucle continue jusqu'à max_cycles au lieu de lever une exception.
    activate_device_mapping(
        tenant_id=tenant["tenant_id"],
        equipment_id=tenant["location_id"],
        host="127.0.0.1",
        port=1,
        points=[{"point_id": str(tenant["point_id"]), "register_name": "total_active_energy"}],
    )
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")
    with _api(tenant) as api:
        cycles = run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.05,
            buffer=buffer,
            max_cycles=2,
        )

    assert cycles == 2
    assert _measurement_count(tenant["tenant_id"]) == 0
    assert buffer.pending() == []


def test_changement_de_configuration_pris_en_compte_au_tour_suivant(
    tenant_two_points, tmp_path, monkeypatch
):
    from app.connectors.modbus import find_register_by_name
    from app.connectors.sdm120 import SDM120_POINTS

    t = tenant_two_points
    energy_register = find_register_by_name(SDM120_POINTS, "total_active_energy")
    power_register = find_register_by_name(SDM120_POINTS, "active_power")
    energy_mapping = [(t["energy_point_id"], energy_register)]
    power_mapping = [(t["power_point_id"], power_register)]

    calls = {"n": 0}

    def fake_load_config(api, equipment_id):
        calls["n"] += 1
        # Appel 1 : vérification de démarrage. Appel 2 : premier tour, encore
        # l'ancienne configuration. Appel 3 : second tour, après le
        # changement fait "depuis la console" entre les deux tours.
        mappings = energy_mapping if calls["n"] <= 2 else power_mapping
        return ("127.0.0.1", PORT, "sdm120", mappings)

    monkeypatch.setattr(daemon, "_load_config", fake_load_config)

    with _api(t) as api:
        cycles = run(
            api=api,
            equipment_id=t["location_id"],
            interval_seconds=0.02,
            buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
            max_cycles=2,
        )

    assert cycles == 2
    with engine.begin() as connection:
        set_tenant_context(connection, t["tenant_id"])
        measured_points = (
            connection.execute(
                text("SELECT point_id FROM measurements WHERE tenant_id = :id"),
                {"id": t["tenant_id"]},
            )
            .scalars()
            .all()
        )
    # Le premier tour a mesuré le point d'énergie, le second le point de
    # puissance : le changement de configuration a bien été relu entre les
    # deux, sans redémarrer le démon.
    assert {str(p) for p in measured_points} == {
        str(t["energy_point_id"]),
        str(t["power_point_id"]),
    }


def test_configuration_retiree_entre_deux_tours_n_arrete_pas_le_demon(
    tenant, tmp_path, monkeypatch
):
    calls = {"n": 0}
    real_load_config = daemon._load_config

    def flaky_load_config(api, equipment_id):
        calls["n"] += 1
        # Le troisième appel (second tour) simule la fenêtre où la
        # configuration vient d'être retirée depuis la console.
        if calls["n"] == 3:
            return None
        return real_load_config(api, equipment_id)

    monkeypatch.setattr(daemon, "_load_config", flaky_load_config)

    with _api(tenant) as api:
        cycles = run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.02,
            buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
            max_cycles=2,
        )

    assert cycles == 2
    # Premier tour mesuré, second tour sauté (pas d'exception) faute de
    # configuration active à ce moment précis.
    assert _measurement_count(tenant["tenant_id"]) == 1


def test_api_injoignable_met_en_tampon_puis_transmet_tout_au_retour(tenant, tmp_path, monkeypatch):
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")

    def _echoue_toujours(items, **kwargs):
        raise httpx.ConnectError("API injoignable (simulé)")

    with _api(tenant) as api:
        monkeypatch.setattr(api, "post_measurements", _echoue_toujours)
        run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.05,
            buffer=buffer,
            max_cycles=2,
        )

        # Deux lectures réussies, deux échecs d'envoi : rien en base, tout au tampon.
        assert _measurement_count(tenant["tenant_id"]) == 0
        assert len(buffer.pending()) == 2

        monkeypatch.undo()
        cycles = run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.05,
            buffer=buffer,
            max_cycles=1,
        )

    # Le tour suivant, une fois l'API à nouveau joignable, renvoie les deux
    # mesures en attente en plus de la nouvelle : rien n'a été perdu.
    assert cycles == 1
    assert _measurement_count(tenant["tenant_id"]) == 3
    assert buffer.pending() == []


# --- Coupures de communication, redémarrage, reprise (préparation du test SDM120) ---


def _simulate_api_outage(api, monkeypatch, *, down_after_cycle: int | None, up_after_cycle: int):
    """Coupure COMPLÈTE de l'API (configuration, authentification et envoi échouent
    ensemble), comme une vraie panne réseau : l'ancien test ne faisait échouer que
    l'envoi, ce qui ne peut pas se produire seul. `down_after_cycle=None` : l'API est
    déjà coupée au démarrage. Les tours sont comptés par les pauses entre deux tours."""
    state = {"cycle": 0, "down": down_after_cycle is None}
    real_request = api._authorized_request

    def request(*args, **kwargs):
        if state["down"]:
            raise httpx.ConnectError("API injoignable (coupure simulée)")
        return real_request(*args, **kwargs)

    real_sleep = time.sleep

    def sleep(seconds):
        state["cycle"] += 1
        if down_after_cycle is not None and state["cycle"] == down_after_cycle:
            state["down"] = True
        if state["cycle"] == up_after_cycle:
            state["down"] = False
        real_sleep(min(seconds, 0.01))

    monkeypatch.setattr(api, "_authorized_request", request)
    monkeypatch.setattr(time, "sleep", sleep)
    return state


def test_vraie_coupure_de_l_api_le_demon_continue_de_relever_et_ne_perd_rien(
    tenant, tmp_path, monkeypatch
):
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")

    with _api(tenant) as api:
        _simulate_api_outage(api, monkeypatch, down_after_cycle=1, up_after_cycle=4)
        cycles = run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.05,
            buffer=buffer,
            max_cycles=5,
        )

    # Tour 1 : envoyé. Tours 2 à 4 : API coupée, compteur relevé quand même et mis en
    # tampon. Tour 5 : API revenue, les 3 mesures en attente repartent avec la nouvelle.
    assert cycles == 5
    assert _measurement_count(tenant["tenant_id"]) == 5
    assert buffer.pending() == []


def test_demarrage_pendant_une_coupure_de_l_api_n_arrete_pas_le_demon(
    tenant, tmp_path, monkeypatch
):
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")

    with _api(tenant) as api:
        _simulate_api_outage(api, monkeypatch, down_after_cycle=None, up_after_cycle=1)
        cycles = run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.05,
            buffer=buffer,
            max_cycles=3,
        )

    # Sans configuration connue, rien n'est à relever (et rien n'est inventé) : tour 1
    # sans mesure. Dès le retour de l'API (tours 2 et 3), la relève reprend.
    assert cycles == 3
    assert _measurement_count(tenant["tenant_id"]) == 2
    assert buffer.pending() == []


def test_configuration_retiree_pendant_une_coupure_n_est_plus_relevee_au_retour(
    tenant, tmp_path, monkeypatch
):
    """La configuration en mémoire sert seulement tant que l'API ne répond pas ; une
    configuration retirée (réponse 404) ne doit jamais être relevée sur la foi du cache."""
    calls = {"n": 0}
    real_load_config = daemon._load_config

    def load_config(api, equipment_id):
        calls["n"] += 1
        if calls["n"] == 3:  # tour 2 : la console vient de retirer la configuration
            return None
        if calls["n"] == 4:  # tour 3 : l'API est coupée
            raise httpx.ConnectError("API injoignable (coupure simulée)")
        return real_load_config(api, equipment_id)

    monkeypatch.setattr(daemon, "_load_config", load_config)
    with _api(tenant) as api:
        run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.02,
            buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
            max_cycles=3,
        )

    assert _measurement_count(tenant["tenant_id"]) == 1


def test_arret_entre_l_envoi_et_le_vidage_du_tampon_ne_cree_aucun_doublon(
    tenant, tmp_path, monkeypatch
):
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")

    with _api(tenant) as api:
        real_post = api.post_measurements
        monkeypatch.setattr(
            api,
            "post_measurements",
            lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("envoi impossible (simulé)")),
        )
        run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.02,
            buffer=buffer,
            max_cycles=2,
        )
        assert len(buffer.pending()) == 2

        # Tour 3 : l'envoi réussit (3 mesures en base), puis le processus est tué avant
        # le vidage du tampon.
        monkeypatch.setattr(api, "post_measurements", real_post)

        def killed():
            raise KeyboardInterrupt("processus tué avant le vidage du tampon (simulé)")

        monkeypatch.setattr(buffer, "clear", killed)
        with pytest.raises(KeyboardInterrupt):
            run(
                api=api,
                equipment_id=tenant["location_id"],
                interval_seconds=0.02,
                buffer=buffer,
                max_cycles=1,
            )
        assert _measurement_count(tenant["tenant_id"]) == 3
        assert len(buffer.pending()) == 2, "les deux anciennes mesures sont encore au tampon"

        # Redémarrage : le tampon est renvoyé une seconde fois, l'API les reconnaît.
        monkeypatch.undo()
        run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.02,
            buffer=buffer,
            max_cycles=1,
        )

    assert _measurement_count(tenant["tenant_id"]) == 4, (
        "2 anciennes + 1 + 1 nouvelle, sans doublon"
    )
    assert buffer.pending() == []


def test_tampon_tronque_par_une_coupure_de_courant_ne_bloque_pas_le_demon(tenant, tmp_path):
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")
    with _api(tenant) as api:
        valid = BufferedReading(
            tenant_id=tenant["tenant_id"],
            point_id=tenant["point_id"],
            value=1.5,
            measured_at=datetime.now(UTC) - timedelta(minutes=5),
            origin="measured",
            source="sdm120",
        )
        buffer.append(valid)
        # Écriture interrompue : ligne coupée en plein milieu, puis octets nuls et non UTF-8.
        with buffer.path.open("ab") as handle:
            handle.write(b'{"tenant_id": "' + str(tenant["tenant_id"]).encode() + b'", "point_i')
            handle.write(b"\n\x00\x00\x00\xff\xfe\n")

        cycles = run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.02,
            buffer=buffer,
            max_cycles=1,
        )

    assert cycles == 1
    assert _measurement_count(tenant["tenant_id"]) == 2, "la mesure valide du tampon est renvoyée"
    assert buffer.pending() == []
    sidecar = buffer.path.with_name(buffer.path.name + ".corrupt")
    assert sidecar.exists(), "les lignes illisibles sont conservées, jamais effacées"
