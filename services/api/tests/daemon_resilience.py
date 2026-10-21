"""Garanties de résilience communes aux démons de sondage (V5.1, 21/10/2026).

Le démon Modbus avait trois défauts, corrigés et testés dans tests/test_modbus_daemon.py ; les
démons BACnet, OPC UA et MQTT reproduisaient la même structure. Ces scénarios sont les mêmes
pour tous : chaque fichier de test les appelle avec son propre `run`, son module de démon et
son client d'API, contre son simulateur réel (jamais un faux protocole).

Chaque fonction décrit une situation de site, pas un détail d'implémentation :
- coupure de l'API en cours de route : le démon continue de relever et ne perd rien ;
- démarrage pendant une coupure : le démon ne plante pas ;
- configuration retirée pendant une coupure : jamais relevée sur la foi de la mémoire ;
- arrêt entre l'envoi et le vidage du tampon : aucun doublon ;
- tampon tronqué par une coupure de courant : le démon continue, rien n'est effacé ;
- refus de l'API : journalisé en erreur, jamais présenté comme une relève réussie.
"""

import logging
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.connectors.offline_buffer import BufferedReading, OfflineBuffer


def simulate_api_outage(
    api, daemon, monkeypatch, *, down_from_cycle: int, up_at_cycle: int
) -> None:
    """Coupure COMPLÈTE de l'API (configuration, authentification et envoi échouent
    ensemble), comme une vraie panne réseau. Les tours sont comptés par les demandes de
    configuration du démon : la demande n° 0 est celle du démarrage, la n° k ouvre le tour k.
    L'API est coupée du tour `down_from_cycle` (0 : déjà coupée au démarrage) jusqu'au tour
    `up_at_cycle` exclu. Compter les pauses entre deux tours ne conviendrait pas : un tour
    plus long que l'intervalle (MQTT attend le courtier) n'en fait jamais."""
    state = {"requests": -1, "down": False}
    real_request = api._authorized_request
    real_load_config = daemon._load_config

    def request(*args, **kwargs):
        if state["down"]:
            raise httpx.ConnectError("API injoignable (coupure simulée)")
        return real_request(*args, **kwargs)

    def load_config(api_client, equipment_id):
        state["requests"] += 1
        state["down"] = down_from_cycle <= state["requests"] < up_at_cycle
        return real_load_config(api_client, equipment_id)

    monkeypatch.setattr(api, "_authorized_request", request)
    monkeypatch.setattr(daemon, "_load_config", load_config)


def check_real_outage_loses_nothing(*, run, daemon, make_api, tenant, count, tmp_path, monkeypatch):
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")
    with make_api(tenant) as api:
        simulate_api_outage(api, daemon, monkeypatch, down_from_cycle=2, up_at_cycle=5)
        cycles = run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.05,
            buffer=buffer,
            max_cycles=5,
        )

    # Tour 1 : envoyé. Tours 2 à 4 : API coupée, équipement relevé quand même et mis en
    # tampon. Tour 5 : API revenue, les 3 mesures en attente repartent avec la nouvelle.
    assert cycles == 5
    assert count(tenant["tenant_id"]) == 5
    assert buffer.pending() == []


def check_start_during_outage_does_not_crash(
    *, run, daemon, make_api, tenant, count, tmp_path, monkeypatch
):
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")
    with make_api(tenant) as api:
        simulate_api_outage(api, daemon, monkeypatch, down_from_cycle=0, up_at_cycle=2)
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
    assert count(tenant["tenant_id"]) == 2
    assert buffer.pending() == []


def check_removed_config_is_not_read_from_memory(
    *, run, daemon, make_api, tenant, count, tmp_path, monkeypatch
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
    with make_api(tenant) as api:
        run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.02,
            buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
            max_cycles=3,
        )

    assert count(tenant["tenant_id"]) == 1


def check_kill_before_buffer_clear_creates_no_duplicate(
    *, run, daemon, make_api, tenant, count, tmp_path, monkeypatch
):
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")
    with make_api(tenant) as api:
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
        assert count(tenant["tenant_id"]) == 3
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

    assert count(tenant["tenant_id"]) == 4, "2 anciennes + 1 + 1 nouvelle, sans doublon"
    assert buffer.pending() == []


def check_truncated_buffer_does_not_block_the_daemon(
    *, run, source, make_api, tenant, count, tmp_path
):
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")
    with make_api(tenant) as api:
        buffer.append(
            BufferedReading(
                tenant_id=tenant["tenant_id"],
                point_id=tenant["point_id"],
                value=1.5,
                measured_at=datetime.now(UTC) - timedelta(minutes=5),
                origin="measured",
                source=source,
            )
        )
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
    assert count(tenant["tenant_id"]) == 2, "la mesure valide du tampon est renvoyée"
    assert buffer.pending() == []
    sidecar = buffer.path.with_name(buffer.path.name + ".corrupt")
    assert sidecar.exists(), "les lignes illisibles sont conservées, jamais effacées"


def check_api_refusal_is_logged_as_an_error(
    *, run, make_api, tenant, tmp_path, monkeypatch, caplog
):
    refusal = {
        "inserted": 0,
        "duplicates": 0,
        "conflicts": 0,
        "rejected": 1,
        "errors": [{"code": "MEASUREMENT_VALUE_INVALID", "params": {"point_id": "x"}}],
    }
    with make_api(tenant) as api:
        monkeypatch.setattr(api, "post_measurements", lambda *a, **k: refusal)
        with caplog.at_level(logging.ERROR):
            run(
                api=api,
                equipment_id=tenant["location_id"],
                interval_seconds=0.02,
                buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
                max_cycles=1,
            )

    refusals = [r for r in caplog.records if "mesure refusée par l'API" in r.getMessage()]
    assert refusals, "un refus de l'API doit apparaître en erreur dans le journal"
    assert "MEASUREMENT_VALUE_INVALID" in refusals[0].getMessage()
    assert all(r.levelno >= logging.ERROR for r in refusals)
