"""equipment nomenclature: type from the former free-text category (migrate)

ADR 013, étape L5, temps 2/3 (migrer), tenant par tenant (RLS forcée).
- La catégorie libre est conservée intégralement comme désignation du
  fabricant (rien n'est perdu).
- Le type universel est proposé à partir de cette catégorie avec une copie
  figée des alias de l'époque (la migration donne toujours le même résultat,
  même si le vocabulaire évolue ensuite). Sans correspondance certaine :
  « other », à préciser par une personne.

Revision ID: 6c1d9fbc55fb
Revises: 8124d4500034
Create Date: 2026-09-24 12:05:00.000000

"""
import re
import unicodedata
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c1d9fbc55fb'
down_revision: Union[str, None] = '8124d4500034'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ALIASES = {
    'heat_pump': ('pac', 'pompe a chaleur', 'heat pump', 'thermodynamique'),
    'chiller': ('groupe froid', 'groupe d eau glacee', 'gef', 'refroidisseur', 'chiller'),
    'dry_cooler': ('dry cooler', 'drycooler', 'aerorefrigerant', 'aerorefrigerant sec'),
    'air_handling_unit': ('cta', 'centrale de traitement d air', 'ahu', 'air handling unit'),
    'pump': ('pompe', 'circulateur', 'pump'),
    'district_heating_substation': (
        'sous station', 'sous station chaud', 'sst', 'sous station reseau de chaleur',
    ),
    'district_cooling_substation': ('sous station froid', 'sous station reseau de froid'),
    'boiler': ('chaudiere', 'boiler'),
    'fan_coil_unit': ('ventilo convecteur', 'ventiloconvecteur', 'fcu', 'fan coil'),
    'heat_exchanger': ('echangeur', 'echangeur a plaques', 'heat exchanger'),
}


def _normalize(text):
    decomposed = unicodedata.normalize('NFKD', text.casefold())
    ascii_only = ''.join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', ascii_only).strip()


def _suggest(text):
    words = f' {_normalize(text)} '
    best_length, best = 0, set()
    for code, aliases in _ALIASES.items():
        for alias in aliases:
            if f' {alias} ' in words:
                if len(alias) > best_length:
                    best_length, best = len(alias), {code}
                elif len(alias) == best_length:
                    best.add(code)
    return best.pop() if len(best) == 1 else 'other'


def upgrade() -> None:
    connection = op.get_bind()
    tenants = connection.execute(sa.text('SELECT id FROM tenants')).scalars().all()
    for tenant_id in tenants:
        connection.execute(
            sa.text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
            {'tenant': str(tenant_id)},
        )
        rows = connection.execute(
            sa.text('SELECT id, category FROM product_models WHERE equipment_type IS NULL')
        ).all()
        for model_id, category in rows:
            connection.execute(
                sa.text(
                    'UPDATE product_models SET equipment_type = :type, '
                    'manufacturer_designation = :designation WHERE id = :id'
                ),
                {'type': _suggest(category), 'designation': category, 'id': model_id},
            )
    connection.execute(sa.text("SELECT set_config('app.current_tenant_id', '', true)"))


def downgrade() -> None:
    # Rien à défaire : l'ancienne catégorie n'a pas été modifiée, et les
    # colonnes remplies ici disparaissent avec le retour arrière précédent.
    pass
