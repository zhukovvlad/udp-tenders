"""add mortar material type

Revision ID: 216a3d19213d
Revises: f1eeaa5a9b51
Create Date: 2026-10-15 20:00:26.107449

"""
import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '216a3d19213d'
down_revision: Union[str, None] = 'f1eeaa5a9b51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

# Позиция считается растворной, если в наименовании есть «раствор» (кладочный,
# цементный, цементно-песчаный…). Класс переносится, только если таковы ВСЕ его позиции.
_MORTAR_CLASSES_SQL = """
    SELECT mc.id, mc.name FROM material_classes mc
    WHERE mc.material_type_id = :other
      AND EXISTS (SELECT 1 FROM invoice_items ii WHERE ii.material_class_id = mc.id)
      AND NOT EXISTS (SELECT 1 FROM invoice_items ii WHERE ii.material_class_id = mc.id
                      AND COALESCE(ii.raw_name, '') NOT ILIKE '%раствор%')
"""


def _type_id(conn, code: str) -> int:
    """id типа материала по коду."""
    return conn.execute(sa.text("SELECT id FROM material_types WHERE code = :c"), {"c": code}).scalar_one()


def _merge_into(conn, target: int, source: int) -> None:
    """Перевесить ссылки класса source на target и удалить source (коридор-дубль в проекте — удаляется)."""
    conn.execute(sa.text("UPDATE invoice_items SET material_class_id = :t WHERE material_class_id = :s"),
                 {"t": target, "s": source})
    conn.execute(sa.text("UPDATE reference_prices SET material_class_id = :t WHERE material_class_id = :s"),
                 {"t": target, "s": source})
    clashes = conn.execute(sa.text(
        "DELETE FROM compensation_corridors c WHERE c.material_class_id = :s AND EXISTS "
        "(SELECT 1 FROM compensation_corridors t WHERE t.material_class_id = :t AND t.project_id = c.project_id)"
    ), {"t": target, "s": source}).rowcount
    if clashes:
        logger.warning(f"mortar: удалено {clashes} коридор(ов) класса {source}, конфликтующих с классом {target}")
    conn.execute(sa.text("UPDATE compensation_corridors SET material_class_id = :t WHERE material_class_id = :s"),
                 {"t": target, "s": source})
    conn.execute(sa.text("DELETE FROM material_classes WHERE id = :s"), {"s": source})


def move_mortar_classes(conn) -> None:
    """Перенести классы «Прочего», все позиции которых — раствор, в тип mortar.

    Класс с тем же именем в mortar уже есть → слияние в него (уникальность (тип, имя)).
    """
    other, mortar = _type_id(conn, "other"), _type_id(conn, "mortar")
    for mc in conn.execute(sa.text(_MORTAR_CLASSES_SQL), {"other": other}).all():
        target = conn.execute(sa.text(
            "SELECT id FROM material_classes WHERE material_type_id = :m AND name = :n"
        ), {"m": mortar, "n": mc.name}).scalar()
        if target is None:
            conn.execute(sa.text("UPDATE material_classes SET material_type_id = :m WHERE id = :id"),
                         {"m": mortar, "id": mc.id})
        else:
            _merge_into(conn, target, mc.id)
        logger.info(f"mortar: класс {mc.name!r} (id={mc.id}) перенесён из «Прочего» в «Раствор»")


def upgrade() -> None:
    """Тип «Раствор» (м³) и перенос в него растворных классов из «Прочего»."""
    op.execute(
        "INSERT INTO material_types (code, name, default_unit_id) "
        "SELECT 'mortar', 'Раствор', id FROM units_of_measure WHERE code = 'M3' "
        "ON CONFLICT (code) DO NOTHING"
    )
    move_mortar_classes(op.get_bind())


def restore_other(conn) -> None:
    """Вернуть классы раствора в «Прочее» и удалить тип; одноимённый класс в «Прочем» — ошибка."""
    other, mortar = _type_id(conn, "other"), _type_id(conn, "mortar")
    clash = conn.execute(sa.text(
        "SELECT m.name FROM material_classes m JOIN material_classes o "
        "ON o.name = m.name AND o.material_type_id = :o WHERE m.material_type_id = :m LIMIT 1"
    ), {"o": other, "m": mortar}).scalar()
    if clash is not None:
        raise RuntimeError(f"downgrade mortar: класс {clash!r} есть и в «Растворе», и в «Прочем» — "
                           "слейте вручную перед откатом")
    conn.execute(sa.text("UPDATE material_classes SET material_type_id = :o WHERE material_type_id = :m"),
                 {"o": other, "m": mortar})
    conn.execute(sa.text("DELETE FROM compensation_corridors WHERE material_type_id = :m"), {"m": mortar})
    conn.execute(sa.text("DELETE FROM material_types WHERE id = :m"), {"m": mortar})


def downgrade() -> None:
    """Откат: классы раствора — обратно в «Прочее», тип mortar удаляется."""
    restore_other(op.get_bind())
