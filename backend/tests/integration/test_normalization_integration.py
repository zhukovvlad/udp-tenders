"""Integration tests for unit normalization (write-time)."""
from datetime import date
from decimal import Decimal

from crud.documents import create_invoice
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


class TestCreateInvoiceNormalization:
    def test_kg_normalized_to_ton(self, db_session, factories):
        doc = factories.DocumentFactory.create()
        inv = create_invoice(
            db_session, document_id=doc.id, number="N1", invoice_date=date(2026, 3, 1),
            supplier_name=None, supplier_inn=None, vat_rate=20.0, confidence=0.9,
            items=[{
                "raw_name": "Арматура", "item_type": "material", "material_class_id": None,
                "quantity": 5000, "unit": "кг", "unit_price": 0.05,
                "amount": 250, "vat_amount": None,
            }],
        )
        item = inv.items[0]
        assert item.raw_unit == "кг"
        assert item.normalized_quantity == Decimal("5.000000")        # 5000 * 0.001
        assert item.normalized_unit_price == Decimal("50.000000")     # 0.05 / 0.001

    def test_unknown_unit_leaves_normalized_null(self, db_session, factories):
        doc = factories.DocumentFactory.create()
        inv = create_invoice(
            db_session, document_id=doc.id, number="N2", invoice_date=date(2026, 3, 1),
            supplier_name=None, supplier_inn=None, vat_rate=20.0, confidence=0.9,
            items=[{
                "raw_name": "Странное", "item_type": "material", "material_class_id": None,
                "quantity": 1, "unit": "бухта", "unit_price": 100,
                "amount": 100, "vat_amount": None,
            }],
        )
        item = inv.items[0]
        assert item.raw_unit == "бухта"
        assert item.normalized_unit_id is None
        assert item.normalized_quantity is None
