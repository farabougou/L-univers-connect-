"""archive the equipment still active on archived sites (migrate)

Décision de Mohamed du 23/10/2026 (voir d4b7e91a3c52). Temps 2/3 (migrer), tenant par
tenant (RLS forcée).

Un équipement encore actif sur un site archivé est archivé avec la date et l'auteur de
l'archivage du site, et marqué « archivé avec le site » : désarchiver le site le remettra en
service, exactement comme si la règle avait toujours existé. Un équipement déjà archivé
(par une personne) n'est pas touché. Rien n'est supprimé ni écrasé : la date et l'auteur
d'origine de l'archivage du site restent portés par le site lui-même.

Cette migration n'ajoute pas d'entrée au journal d'audit (chaînée par hachage, calculée par
l'application) : la provenance se lit dans l'équipement lui-même (`archived_at`, `archived_by`
copiés du site, `archived_with_site`). Les archivages faits après cette migration, eux, sont
audités un par un.

Pas de temps 3/3 (contracter) : rien n'est retiré.

Revision ID: b8e3a6d15f94
Revises: d4b7e91a3c52
Create Date: 2026-10-23 21:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b8e3a6d15f94'
down_revision: Union[str, None] = 'd4b7e91a3c52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            t record;
        BEGIN
            FOR t IN SELECT id FROM tenants LOOP
                PERFORM set_config('app.current_tenant_id', t.id::text, true);

                UPDATE functional_locations f SET
                    archived_at = s.archived_at,
                    archived_by = COALESCE(s.archived_by, 'systeme:archivage-du-site'),
                    archived_with_site = true
                FROM sites s
                WHERE s.id = f.site_id
                  AND s.archived_at IS NOT NULL
                  AND f.archived_at IS NULL;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )


def downgrade() -> None:
    # Rien à défaire : les équipements archivés ici restent archivés (réversible depuis la
    # console en désarchivant le site), et le retour arrière du temps « élargir » retire
    # l'indicateur.
    pass
