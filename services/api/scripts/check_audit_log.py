"""Vérifie la traçabilité : affiche les dernières entrées du journal d'audit
du tenant de démonstration et confirme que la chaîne de hachage est intacte
(voir app/audit.py — chaque entrée est chaînée à la précédente).

Utilisation, depuis services/api : python scripts/check_audit_log.py
"""

import uuid

from sqlalchemy import text

from app.audit import verify_chain_integrity
from app.db import engine
from app.tenancy import set_tenant_context

DEMO_TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def main() -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, DEMO_TENANT_ID)

        rows = (
            connection.execute(
                text(
                    "SELECT seq, actor, action, entity_type, entity_id, occurred_at "
                    "FROM audit_log WHERE tenant_id = :tenant_id "
                    "ORDER BY seq DESC LIMIT 10"
                ),
                {"tenant_id": DEMO_TENANT_ID},
            )
            .mappings()
            .all()
        )

        if not rows:
            print("Aucune entrée dans le journal d'audit pour ce tenant.")
            return

        print("Dernières entrées (les plus récentes en premier) :")
        for row in rows:
            print(
                f"  #{row['seq']:>4}  {row['occurred_at']}  {row['actor']:<30}  "
                f"{row['action']:<20}  {row['entity_type'] or '-'}:{row['entity_id'] or '-'}"
            )

        result = verify_chain_integrity(connection, tenant_id=DEMO_TENANT_ID)
        if result.valid:
            print("\nChaîne de hachage intacte : aucune entrée modifiée ou supprimée.")
        else:
            print(f"\nCHAÎNE ROMPUE à la séquence {result.broken_at_seq} : {result.reason}")


if __name__ == "__main__":
    main()
