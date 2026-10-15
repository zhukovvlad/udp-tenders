"""Миграция f1eeaa5a9b51: слияние дублей классов материалов (латиница/кириллица, «,»/«.»)."""
import importlib.util
from datetime import date
from pathlib import Path

import pytest

from models import CompensationCorridor, InvoiceItem, MaterialClass, ReferencePrice

_MIGRATION = next((Path(__file__).parents[2] / "alembic" / "versions").glob("*f1eeaa5a9b51*.py"))


@pytest.fixture(scope="module")
def migration():
    """Модуль ревизии, загруженный по пути (имя файла не годится для import)."""
    spec = importlib.util.spec_from_file_location("migration_f1eeaa5a9b51", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _items(factories, mc, n):
    """n позиций СФ, привязанных к классу mc."""
    for _ in range(n):
        factories.InvoiceItemFactory.create(material_class_id=mc.id)


def _names(db_session) -> dict[int, str]:
    """id → имя всех бетонных классов (тип общий у всех классов теста)."""
    db_session.expire_all()
    return {mc.id: mc.name for mc in db_session.query(MaterialClass)}


def test_merge_keeps_class_with_most_items_and_renames_to_canonical(db_session, factories, migration):
    """Группа «B60»/«В60»: победитель — с бо́льшим числом позиций; позиции дубля перевешены."""
    lat = factories.MaterialClassFactory.create(name="B60")
    cyr = factories.MaterialClassFactory.create(name="В60")
    _items(factories, lat, 1)
    _items(factories, cyr, 3)

    migration.merge_duplicate_classes(db_session.connection())

    assert _names(db_session) == {cyr.id: "В60"}
    assert db_session.query(InvoiceItem).filter_by(material_class_id=cyr.id).count() == 4


def test_merge_three_spellings_and_rename_survivor(db_session, factories, migration):
    """«В7,5» (больше всех позиций) переживает «B7.5» и «В7.5» и получает канон «В7.5»."""
    comma = factories.MaterialClassFactory.create(name="В7,5")
    lat = factories.MaterialClassFactory.create(name="B7.5")
    dot = factories.MaterialClassFactory.create(name="В7.5")
    _items(factories, comma, 6)
    _items(factories, lat, 1)
    _items(factories, dot, 2)

    migration.merge_duplicate_classes(db_session.connection())

    assert _names(db_session) == {comma.id: "В7.5"}
    assert db_session.query(InvoiceItem).filter_by(material_class_id=comma.id).count() == 9


def test_merge_tie_keeps_smaller_id(db_session, factories, migration):
    """При равном числе позиций побеждает меньший id."""
    first = factories.MaterialClassFactory.create(name="В20")
    second = factories.MaterialClassFactory.create(name="B20")
    smaller = min(first.id, second.id)  # до слияния: удалённый экземпляр после него не читается

    migration.merge_duplicate_classes(db_session.connection())

    assert _names(db_session) == {smaller: "В20"}


def test_merge_resolves_reference_price_and_corridor_conflicts(db_session, factories, migration):
    """Пересечение эталона/коридор в том же проекте → у дубля удаляются; иначе — перевешиваются."""
    survivor = factories.MaterialClassFactory.create(name="В30")
    loser = factories.MaterialClassFactory.create(name="B30")
    _items(factories, survivor, 2)
    p1 = factories.ProjectFactory.create()
    p2 = factories.ProjectFactory.create()
    factories.ReferencePriceFactory.create(project=p1, material_class=survivor,
                                           period_start=date(2026, 1, 1), period_end=date(2026, 6, 30))
    clash_rp = factories.ReferencePriceFactory.create(project=p1, material_class=loser,
                                                      period_start=date(2026, 3, 1), period_end=date(2026, 9, 30))
    moved_rp = factories.ReferencePriceFactory.create(project=p1, material_class=loser,
                                                      period_start=date(2026, 7, 1), period_end=date(2026, 12, 31))
    factories.CompensationCorridorFactory.create(project_id=p1.id, material_class_id=survivor.id)
    clash_cor = factories.CompensationCorridorFactory.create(project_id=p1.id, material_class_id=loser.id)
    moved_cor = factories.CompensationCorridorFactory.create(project_id=p2.id, material_class_id=loser.id)
    clash_rp_id, moved_rp_id = clash_rp.id, moved_rp.id
    clash_cor_id, moved_cor_id = clash_cor.id, moved_cor.id

    migration.merge_duplicate_classes(db_session.connection())
    db_session.expire_all()

    assert db_session.get(ReferencePrice, clash_rp_id) is None
    assert db_session.get(ReferencePrice, moved_rp_id).material_class_id == survivor.id
    assert db_session.get(CompensationCorridor, clash_cor_id) is None
    assert db_session.get(CompensationCorridor, moved_cor_id).material_class_id == survivor.id


def test_merge_leaves_distinct_classes_and_types_alone(db_session, factories, migration):
    """Разные канон-имена и одинаковое имя в разных типах — не дубли."""
    b25 = factories.MaterialClassFactory.create(name="В25")
    b40 = factories.MaterialClassFactory.create(name="В40")
    other = factories.MaterialClassFactory.create(name="В25", material_type_code="other")

    migration.merge_duplicate_classes(db_session.connection())
    db_session.expire_all()

    assert {mc.id for mc in db_session.query(MaterialClass)} == {b25.id, b40.id, other.id}
