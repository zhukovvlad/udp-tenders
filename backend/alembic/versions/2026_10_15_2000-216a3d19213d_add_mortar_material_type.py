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

# Позиция — строительный раствор, если наименование НАЧИНАЕТСЯ со слова «раствор», перед
# которым допустимы только прилагательные («Цементный», «Цементно-песчаный», «Готовый
# кладочный»). \M (конец слова) отсекает «растворитель»/«растворонасос», а существительное
# впереди — «Добавка для раствора». Неоднозначное остаётся в other. Класс переносится,
# только если таковы ВСЕ его позиции.
_MORTAR_ITEM_RE = r"^\s*([а-яё]+(-[а-яё]+)?(ый|ий|ой|ая|яя|ое|ее|ые|ие)\s+)*раствор\M"
_MORTAR_CLASSES_SQL = """
    SELECT mc.id, mc.name FROM material_classes mc
    WHERE mc.material_type_id = :other
      AND EXISTS (SELECT 1 FROM invoice_items ii WHERE ii.material_class_id = mc.id)
      AND NOT EXISTS (SELECT 1 FROM invoice_items ii WHERE ii.material_class_id = mc.id
                      AND COALESCE(ii.raw_name, '') !~* :mortar_re)
"""

# Класс без своего правила наследовал правило типа other; после смены типа resolve_corridor
# (класс → тип → нет правила) его бы не нашёл — закрепляем правило на классе в проектах,
# где класс используется (позиции или эталонные цены).
_MATERIALIZE_INHERITED_SQL = """
    INSERT INTO compensation_corridors (project_id, material_class_id, is_compensable, corridor_pct)
    SELECT t.project_id, :cls, t.is_compensable, t.corridor_pct
    FROM compensation_corridors t
    WHERE t.material_type_id = :other AND t.material_class_id IS NULL
      AND NOT EXISTS (SELECT 1 FROM compensation_corridors c
                      WHERE c.material_class_id = :cls AND c.project_id = t.project_id)
      AND (EXISTS (SELECT 1 FROM invoice_items ii
                   JOIN invoices i ON i.id = ii.invoice_id JOIN documents d ON d.id = i.document_id
                   WHERE ii.material_class_id = :cls AND d.project_id = t.project_id)
           OR EXISTS (SELECT 1 FROM reference_prices rp
                      WHERE rp.material_class_id = :cls AND rp.project_id = t.project_id))
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

    Класс с тем же именем в mortar уже есть → слияние в него (уникальность (тип, имя)),
    действуют правила коридоров победителя. Иначе наследуемое правило типа other
    сначала закрепляется на классе — компенсация после переноса не меняется.
    """
    other, mortar = _type_id(conn, "other"), _type_id(conn, "mortar")
    candidates = conn.execute(sa.text(_MORTAR_CLASSES_SQL), {"other": other, "mortar_re": _MORTAR_ITEM_RE}).all()
    for mc in candidates:
        target = conn.execute(sa.text(
            "SELECT id FROM material_classes WHERE material_type_id = :m AND name = :n"
        ), {"m": mortar, "n": mc.name}).scalar()
        if target is None:
            kept = conn.execute(sa.text(_MATERIALIZE_INHERITED_SQL), {"cls": mc.id, "other": other}).rowcount
            if kept:
                logger.info(f"mortar: правило типа «Прочее» закреплено на классе {mc.id} в {kept} проект(ах)")
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
