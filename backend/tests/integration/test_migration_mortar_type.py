"""Миграция 216a3d19213d: тип материала «Раствор» и перенос в него растворных классов из «Прочего»."""
import importlib.util
from pathlib import Path

import pytest

from models import InvoiceItem, MaterialClass, MaterialType

_MIGRATION = next((Path(__file__).parents[2] / "alembic" / "versions").glob("*216a3d19213d*.py"))


@pytest.fixture(scope="module")
def migration():
    """Модуль ревизии, загруженный по пути (имя файла не годится для import)."""
    spec = importlib.util.spec_from_file_location("migration_216a3d19213d", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _other(factories, name, *raw_names):
    """Класс типа other с позициями под указанными наименованиями."""
    mc = factories.MaterialClassFactory.create(name=name, material_type_code="other")
    for raw in raw_names:
        factories.InvoiceItemFactory.create(material_class_id=mc.id, raw_name=raw)
    return mc


def _type_code(db_session, class_id) -> str:
    """Код типа класса по id (после expire — свежий из БД)."""
    db_session.expire_all()
    return db_session.get(MaterialClass, class_id).material_type.code


def test_mortar_type_seeded_with_cubic_metre(db_session):
    """После head есть тип mortar «Раствор» с единицей по умолчанию м³."""
    mortar = db_session.query(MaterialType).filter_by(code="mortar").one()
    assert mortar.name == "Раствор"
    assert mortar.default_unit.code == "M3"


def test_moves_classes_whose_items_are_all_mortar(db_session, factories, migration):
    """Класс «Прочего», все позиции которого — раствор, переезжает в mortar; прочие — остаются."""
    m200 = _other(factories, "М200", "Раствор М200Пк3F50", "Цементный раствор М200 ПК3 F100")
    brick = _other(factories, "Кирпич М150", "Кирпич керамический М150")
    mixed = _other(factories, "М100", "Раствор кладочный М100", "Смесь сухая М100")
    empty = _other(factories, "М75")
    ids = (m200.id, brick.id, mixed.id, empty.id)

    migration.move_mortar_classes(db_session.connection())

    assert [_type_code(db_session, i) for i in ids] == ["mortar", "other", "other", "other"]


def test_merges_into_existing_mortar_class_with_same_name(db_session, factories, migration):
    """В mortar уже есть класс с тем же именем → позиции перевешиваются, класс «Прочего» удаляется."""
    existing = factories.MaterialClassFactory.create(name="М150", material_type_code="mortar")
    moved = _other(factories, "М150", "Раствор М150")
    existing_id, moved_id = existing.id, moved.id

    migration.move_mortar_classes(db_session.connection())
    db_session.expire_all()

    assert db_session.get(MaterialClass, moved_id) is None
    assert db_session.query(InvoiceItem).filter_by(material_class_id=existing_id).count() == 1


def test_restore_other_moves_classes_back_and_drops_type(db_session, factories, migration):
    """Откат: классы раствора возвращаются в «Прочее», тип mortar удаляется."""
    mc = factories.MaterialClassFactory.create(name="М200", material_type_code="mortar")
    mc_id = mc.id

    migration.restore_other(db_session.connection())

    assert _type_code(db_session, mc_id) == "other"
    assert db_session.query(MaterialType).filter_by(code="mortar").count() == 0


def test_restore_other_refuses_on_name_clash(db_session, factories, migration):
    """Откат невозможен, если одноимённый класс есть и в «Растворе», и в «Прочем»."""
    factories.MaterialClassFactory.create(name="М200", material_type_code="mortar")
    factories.MaterialClassFactory.create(name="М200", material_type_code="other")

    with pytest.raises(RuntimeError, match="М200"):
        migration.restore_other(db_session.connection())


@pytest.mark.parametrize("raw_names", [
    ("Растворитель 646", "Растворитель Р-4"),          # «раствор» внутри другого слова
    ("Растворонасос СО-49",),
    ("Добавка для раствора противоморозная",),          # раствор — не сам товар
    ("Противоморозная добавка для раствора",),
    ("Раствор М150", "Растворитель 646"),               # настоящий раствор вперемешку
])
def test_ambiguous_names_stay_in_other(db_session, factories, migration, raw_names):
    """Совпадение подстроки «раствор» не доказывает, что товар — строительный раствор."""
    mc = _other(factories, "Х1", *raw_names)
    mc_id = mc.id

    migration.move_mortar_classes(db_session.connection())

    assert _type_code(db_session, mc_id) == "other"


def test_mortar_names_with_adjectives_are_moved(db_session, factories, migration):
    """«Раствор …», «Цементный раствор …», «Цементно-песчаный раствор …» — строительный раствор."""
    mc = _other(factories, "М150", "Раствор цементный М150", "Цементный раствор М150 ПК3",
                "Цементно-песчаный раствор М150", "Готовый кладочный раствор М150")
    mc_id = mc.id

    migration.move_mortar_classes(db_session.connection())

    assert _type_code(db_session, mc_id) == "mortar"


def _used_in(factories, project, mc, raw_name="Раствор М200"):
    """Позиция класса mc в документе проекта project."""
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc)
    factories.InvoiceItemFactory.create(invoice=inv, material_class_id=mc.id, raw_name=raw_name)


def test_inherited_other_corridor_is_materialized_on_class(db_session, factories, migration):
    """Класс наследовал правило типа «Прочее» → после переноса правило закреплено на классе."""
    from decimal import Decimal

    from models import CompensationCorridor

    other_id = db_session.query(MaterialType).filter_by(code="other").one().id
    used, unused, overridden = (factories.ProjectFactory.create() for _ in range(3))
    for p in (used, unused, overridden):
        factories.CompensationCorridorFactory.create(
            project_id=p.id, material_type_id=other_id, material_class_id=None,
            is_compensable=True, corridor_pct=Decimal("7.50"))
    mc = factories.MaterialClassFactory.create(name="М200", material_type_code="other")
    _used_in(factories, used, mc)
    _used_in(factories, overridden, mc)
    factories.CompensationCorridorFactory.create(
        project_id=overridden.id, material_class_id=mc.id, is_compensable=False, corridor_pct=None)
    mc_id = mc.id

    migration.move_mortar_classes(db_session.connection())
    db_session.expire_all()

    rows = {r.project_id: r for r in db_session.query(CompensationCorridor).filter_by(material_class_id=mc_id)}
    assert set(rows) == {used.id, overridden.id}
    assert (rows[used.id].is_compensable, rows[used.id].corridor_pct) == (True, Decimal("7.50"))
    assert rows[overridden.id].is_compensable is False   # своё правило класса не трогаем
