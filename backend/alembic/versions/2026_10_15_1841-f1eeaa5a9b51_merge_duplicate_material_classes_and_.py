"""merge duplicate material classes and unique name

Revision ID: f1eeaa5a9b51
Revises: 6e3b8dc47ba9
Create Date: 2026-10-15 18:41:46.628864

"""
import logging
import re
from collections import defaultdict
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f1eeaa5a9b51'
down_revision: Union[str, None] = '6e3b8dc47ba9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

# Замороженная копия crud.materials.normalize_class_name на момент ревизии: миграция
# не импортирует код приложения, который может измениться после неё.
_LATIN_TO_CYRILLIC = str.maketrans("ABCEHKMOPTXYaceopxykt", "АВСЕНКМОРТХУасеорхукт")
_CLASS_CODE_RE = re.compile(
    r"^([A-Za-zА-Яа-яЁё]{1,3})\s*(\d+(?:[.,]\d+)?)\s*([A-Za-zА-Яа-яЁё]{0,2})$"
)


def _normalize(name: str) -> str:
    """Канон имени класса (копия normalize_class_name, см. комментарий выше)."""
    collapsed = " ".join(name.split())
    match = _CLASS_CODE_RE.match(collapsed)
    if not match:
        return collapsed
    prefix, number, suffix = match.groups()
    # Сначала регистр, потом транслитерация: строчных «b»/«m» в таблице нет, и «b25»
    # иначе остался бы латинским «B25» — дублем «В25» и не неподвижной точкой.
    code = prefix[0].upper() + prefix[1:] + number.replace(",", ".") + suffix.upper()
    return code.translate(_LATIN_TO_CYRILLIC)


def _merge_reference_prices(conn, survivor: int, loser: int) -> None:
    """Перевесить эталонные цены дубля; пересекающийся период у победителя → цена дубля удаляется."""
    rows = conn.execute(sa.text(
        "SELECT id, project_id, period_start, period_end FROM reference_prices WHERE material_class_id = :c"
    ), {"c": loser}).all()
    for rp in rows:
        clash = conn.execute(sa.text(
            "SELECT id FROM reference_prices WHERE material_class_id = :s AND project_id = :p "
            "AND period_start <= :e AND :b <= period_end LIMIT 1"
        ), {"s": survivor, "p": rp.project_id, "b": rp.period_start, "e": rp.period_end}).scalar()
        if clash is not None:
            logger.warning(f"material_classes merge: reference_price id={rp.id} класса {loser} "
                           f"пересекается с id={clash} класса {survivor} (проект {rp.project_id}) — удалена")
            conn.execute(sa.text("DELETE FROM reference_prices WHERE id = :id"), {"id": rp.id})
        else:
            conn.execute(sa.text("UPDATE reference_prices SET material_class_id = :s WHERE id = :id"),
                         {"s": survivor, "id": rp.id})


def _merge_corridors(conn, survivor: int, loser: int) -> None:
    """Перевесить коридоры дубля; у победителя уже есть коридор в проекте → коридор дубля удаляется."""
    rows = conn.execute(sa.text(
        "SELECT id, project_id FROM compensation_corridors WHERE material_class_id = :c"
    ), {"c": loser}).all()
    for cor in rows:
        clash = conn.execute(sa.text(
            "SELECT id FROM compensation_corridors WHERE material_class_id = :s AND project_id = :p"
        ), {"s": survivor, "p": cor.project_id}).scalar()
        if clash is not None:
            logger.warning(f"material_classes merge: corridor id={cor.id} класса {loser} конфликтует "
                           f"с id={clash} класса {survivor} (проект {cor.project_id}) — удалён")
            conn.execute(sa.text("DELETE FROM compensation_corridors WHERE id = :id"), {"id": cor.id})
        else:
            conn.execute(sa.text("UPDATE compensation_corridors SET material_class_id = :s WHERE id = :id"),
                         {"s": survivor, "id": cor.id})


def merge_duplicate_classes(conn) -> None:
    """Слить классы, совпадающие после канонизации имени, в один и переименовать в канон.

    Победитель группы (тип, канон) — класс с бо́льшим числом позиций, при равенстве —
    меньший id. Позиции СФ перевешиваются; конфликты эталонных цен/коридоров решаются
    в пользу победителя с warning в лог. Расчёты не хранятся — пересчитывать нечего.
    """
    classes = conn.execute(sa.text(
        "SELECT mc.id, mc.material_type_id, mc.name, mc.calc_role, "
        "(SELECT count(*) FROM invoice_items ii WHERE ii.material_class_id = mc.id) AS items "
        "FROM material_classes mc"
    )).all()
    groups: dict[tuple[int, str], list] = defaultdict(list)
    for mc in classes:
        groups[(mc.material_type_id, _normalize(mc.name))].append(mc)

    for (_, canonical), members in groups.items():
        survivor, *losers = sorted(members, key=lambda m: (-m.items, m.id))
        for loser in losers:
            if loser.calc_role != survivor.calc_role:
                logger.warning(f"material_classes merge: calc_role {loser.calc_role!r} класса {loser.id} "
                               f"отброшен в пользу {survivor.calc_role!r} класса {survivor.id}")
            conn.execute(sa.text("UPDATE invoice_items SET material_class_id = :s WHERE material_class_id = :l"),
                         {"s": survivor.id, "l": loser.id})
            _merge_reference_prices(conn, survivor.id, loser.id)
            _merge_corridors(conn, survivor.id, loser.id)
            conn.execute(sa.text("DELETE FROM material_classes WHERE id = :l"), {"l": loser.id})
            logger.info(f"material_classes merge: {loser.name!r} (id={loser.id}) → "
                        f"{canonical!r} (id={survivor.id})")
        if survivor.name != canonical:
            conn.execute(sa.text("UPDATE material_classes SET name = :n WHERE id = :id"),
                         {"n": canonical, "id": survivor.id})


def upgrade() -> None:
    """Слить дубли классов материалов и запретить новые уникальным индексом (тип, имя)."""
    merge_duplicate_classes(op.get_bind())
    op.create_index("uq_material_classes_type_name", "material_classes",
                    ["material_type_id", "name"], unique=True)


def downgrade() -> None:
    """Снять уникальный индекс; слияние дублей необратимо (исходные id/имена не хранятся)."""
    op.drop_index("uq_material_classes_type_name", table_name="material_classes")
