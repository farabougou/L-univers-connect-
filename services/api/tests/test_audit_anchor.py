"""Ancrage externe du journal d'audit (app/audit_anchor.py) : un témoin dans
les journaux applicatifs, séparé de Postgres, pour qu'une réécriture
complète de la chaîne interne (accès direct à la base) ne passe pas
inaperçue."""

import logging
import uuid
from unittest.mock import patch

from sqlalchemy import text

from app.audit import append_audit_entry
from app.audit_anchor import anchor_once
from app.db import engine
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant


def _new_tenant(name: str) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": name, "slug": f"{name.lower()}-{tenant_id}"},
        )
    return tenant_id


def _cleanup(tenant_id: uuid.UUID) -> None:
    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def _latest_entry_hash(tenant_id: uuid.UUID) -> tuple[int, str]:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        row = connection.execute(
            text(
                "SELECT seq, entry_hash FROM audit_log WHERE tenant_id = :id "
                "ORDER BY seq DESC LIMIT 1"
            ),
            {"id": tenant_id},
        ).one()
    return row.seq, row.entry_hash


def test_un_tenant_avec_des_entrees_est_ancre(caplog):
    tenant_id = _new_tenant("ClientAncrageA")
    try:
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_id)
            append_audit_entry(connection, tenant_id=tenant_id, actor="test", action="site.created")
            append_audit_entry(connection, tenant_id=tenant_id, actor="test", action="site.renamed")
        expected_seq, expected_hash = _latest_entry_hash(tenant_id)

        with caplog.at_level(logging.INFO, logger="paios.audit_anchor"):
            summary = anchor_once(engine)

        assert summary["tenants_anchored"] >= 1
        matching = [
            r
            for r in caplog.records
            if getattr(r, "event", None) == "audit.anchored"
            and getattr(r, "audit_tenant_id", None) == str(tenant_id)
        ]
        assert len(matching) == 1
        assert matching[0].seq == expected_seq
        assert matching[0].entry_hash == expected_hash
    finally:
        _cleanup(tenant_id)


def test_un_tenant_sans_entree_n_est_pas_ancre(caplog):
    tenant_id = _new_tenant("ClientAncrageVide")
    try:
        with caplog.at_level(logging.INFO, logger="paios.audit_anchor"):
            summary = anchor_once(engine)

        assert summary["tenants_empty"] >= 1
        matching = [
            r
            for r in caplog.records
            if getattr(r, "event", None) == "audit.anchored"
            and getattr(r, "audit_tenant_id", None) == str(tenant_id)
        ]
        assert matching == []
    finally:
        _cleanup(tenant_id)


def test_isolation_chaque_tenant_ancre_son_propre_dernier_hachage(caplog):
    tenant_a = _new_tenant("ClientAncrageIsoA")
    tenant_b = _new_tenant("ClientAncrageIsoB")
    try:
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a)
            append_audit_entry(connection, tenant_id=tenant_a, actor="test", action="a.first")
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_b)
            append_audit_entry(connection, tenant_id=tenant_b, actor="test", action="b.first")
            append_audit_entry(connection, tenant_id=tenant_b, actor="test", action="b.second")

        seq_a, hash_a = _latest_entry_hash(tenant_a)
        seq_b, hash_b = _latest_entry_hash(tenant_b)
        assert hash_a != hash_b

        with caplog.at_level(logging.INFO, logger="paios.audit_anchor"):
            anchor_once(engine)

        by_tenant = {
            getattr(r, "audit_tenant_id", None): r
            for r in caplog.records
            if getattr(r, "event", None) == "audit.anchored"
        }
        assert by_tenant[str(tenant_a)].seq == seq_a
        assert by_tenant[str(tenant_a)].entry_hash == hash_a
        assert by_tenant[str(tenant_b)].seq == seq_b
        assert by_tenant[str(tenant_b)].entry_hash == hash_b
    finally:
        _cleanup(tenant_a)
        _cleanup(tenant_b)


def test_un_tenant_en_erreur_n_empeche_pas_l_ancrage_des_autres():
    tenant_a = _new_tenant("ClientAncrageErreurA")
    tenant_b = _new_tenant("ClientAncrageErreurB")
    try:
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_b)
            append_audit_entry(connection, tenant_id=tenant_b, actor="test", action="b.only")

        with engine.begin() as connection:
            total_tenants = connection.execute(text("SELECT count(*) FROM tenants")).scalar()

        def _boom_for_a(connection, tenant_id):
            if tenant_id == tenant_a:
                raise RuntimeError("panne simulée")
            return True

        with patch("app.audit_anchor._anchor_tenant", side_effect=_boom_for_a) as mock_anchor:
            summary = anchor_once(engine)

        called_tenant_ids = {call.args[1] for call in mock_anchor.call_args_list}
        assert {tenant_a, tenant_b} <= called_tenant_ids
        assert summary["tenants_failed"] >= 1
        assert (
            summary["tenants_anchored"] + summary["tenants_empty"] + summary["tenants_failed"]
            == total_tenants
        )
    finally:
        _cleanup(tenant_a)
        _cleanup(tenant_b)
