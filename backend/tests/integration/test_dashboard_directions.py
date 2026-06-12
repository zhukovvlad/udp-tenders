from datetime import date
from decimal import Decimal


def _rebar_class(factories, name="А500С Ø12"):
    return factories.MaterialClassFactory.create(material_type_code="rebar", name=name)


def _rebar_item(factories, invoice, mc, qty, unit_price):
    """Позиция арматуры в тоннах — normalized_* задаём явно (см. факторку)."""
    from tests.factories import _unit_id
    return factories.InvoiceItemFactory.create(
        invoice=invoice, material_class=mc, item_type="material",
        quantity=qty, raw_unit="т", unit_price=unit_price,
        normalized_unit_id=_unit_id("TON"), normalized_quantity=Decimal(str(qty)),
    )


def test_additive_scoped_to_own_type_in_mixed_invoice(client, factories):
    """§5.4: additive типа concrete в смешанном счёте входит только бетону;
    у арматуры — только доля доставки."""
    project = factories.ProjectFactory.create()
    concrete = factories.MaterialClassFactory.create(name="В25")
    rebar = _rebar_class(factories)
    plasticizer = factories.MaterialClassFactory.create(name="Пластификатор", calc_role="additive")
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc, date=date(2026, 3, 10))
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=concrete, item_type="material",
        quantity=10, unit_price=8000, amount=80000)               # бетон 80000 (+20% НДС)
    _rebar_item(factories, inv, rebar, qty=2, unit_price=10000)   # арматура 20000 (+НДС)
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=plasticizer, item_type="material",
        quantity=1, unit_price=1000, amount=1000)                 # additive concrete 1000 (+НДС 200)
    factories.InvoiceItemFactory.create(
        invoice=inv, item_type="delivery", material_class=None,
        quantity=1, unit_price=5000, amount=5000)                 # доставка 5000 (+НДС 1000)

    rows = client.get(f"/api/dashboard/calculations?project_id={project.id}").json()
    by_name = {r["material_class_name"]: r for r in rows}
    # mixed dimensions → delivery по amount (80000 vs 20000 без НДС): 0.8 / 0.2 от 6000 с НДС
    # additive (1200 с НДС) — только бетону
    assert by_name["В25"]["delivery_total"] == 4800.0 + 1200.0
    assert by_name["А500С Ø12"]["delivery_total"] == 1200.0


def test_additive_without_own_type_base_not_allocated(client, factories):
    """Edge §5.4: additive concrete в счёте только с base rebar — никому."""
    project = factories.ProjectFactory.create()
    rebar = _rebar_class(factories)
    plasticizer = factories.MaterialClassFactory.create(name="Пластификатор", calc_role="additive")
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc, date=date(2026, 3, 10))
    _rebar_item(factories, inv, rebar, qty=2, unit_price=10000)
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=plasticizer, item_type="material",
        quantity=1, unit_price=1000, amount=1000)

    rows = client.get(f"/api/dashboard/calculations?project_id={project.id}").json()
    assert len(rows) == 1
    assert rows[0]["delivery_total"] == 0.0  # additive не разнесён


def test_supplier_project_deviation_additive_scoped(client, factories):
    """§5.4: та же разноска в _compute_supplier_project_deviation (карточка поставщика).
    Additive concrete не должен удорожать арматуру в отклонении поставщика."""
    project = factories.ProjectFactory.create()
    concrete = factories.MaterialClassFactory.create(name="В25")
    rebar = _rebar_class(factories)
    plasticizer = factories.MaterialClassFactory.create(name="Пластификатор", calc_role="additive")
    supplier = factories.SupplierFactory.create()
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc, supplier_id=supplier.id, date=date(2026, 3, 10))
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=concrete, item_type="material",
        quantity=10, unit_price=8000, amount=80000)
    _rebar_item(factories, inv, rebar, qty=2, unit_price=10000)
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=plasticizer, item_type="material",
        quantity=1, unit_price=1000, amount=1000)
    # Базовая цена ровно по факту арматуры: 12000 ₽/т с НДС → отклонение арматуры = 0,
    # если additive (1200 с НДС) НЕ протёк в её avg_price.
    from tests.factories import _unit_id
    factories.ReferencePriceFactory.create(
        project=project, material_class=rebar, price=12000.0, unit_id=_unit_id("TON"))

    rows = client.get(f"/api/suppliers/{supplier.id}/projects").json()
    stats = next(r for r in rows if r["project_id"] == project.id)
    assert stats["deviation_amount"] == 0.0
