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
