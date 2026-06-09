"""Integration tests for unit normalization (write-time)."""
from crud.units import load_alias_map
from models import MaterialType, UnitOfMeasure


class TestSeedData:
    def test_units_seeded(self, db_session):
        codes = {u.code for u in db_session.query(UnitOfMeasure).all()}
        assert {"TON", "KG", "M3", "L", "M", "PCS"} <= codes

    def test_material_types_seeded(self, db_session):
        codes = {m.code for m in db_session.query(MaterialType).all()}
        assert {"concrete", "rebar", "other"} == codes

    def test_aliases_resolve_to_base(self, db_session):
        amap = load_alias_map(db_session)
        # "кг" → base unit TON (mass), multiplier 0.001
        kg = amap["кг"]
        ton_id = db_session.query(UnitOfMeasure).filter_by(code="TON").one().id
        assert kg.base_unit_id == ton_id
        assert str(kg.multiplier) == "0.001000000000000"  # Numeric(30,15)
        assert kg.dimension == "mass"

    def test_factory_builds_material_class(self, factories, db_session):
        mc = factories.MaterialClassFactory.create(material_type_code="rebar")
        assert mc.material_type.code == "rebar"
