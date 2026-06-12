from datetime import date
from decimal import Decimal

import pytest


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


def test_calculations_direction_field_and_filter(client, factories):
    project = factories.ProjectFactory.create()
    concrete = factories.MaterialClassFactory.create(name="В25")
    rebar = _rebar_class(factories)
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc, date=date(2026, 3, 10))
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=concrete, item_type="material",
        quantity=10, unit_price=8000, amount=80000)
    _rebar_item(factories, inv, rebar, qty=2, unit_price=10000)

    all_rows = client.get(f"/api/dashboard/calculations?project_id={project.id}").json()
    assert {r["direction"] for r in all_rows} == {"concrete", "rebar"}

    resp = client.get(f"/api/dashboard/calculations?project_id={project.id}&direction=rebar")
    rows = resp.json()
    assert [r["material_class_name"] for r in rows] == ["А500С Ø12"]


def test_calculations_direction_filter_does_not_change_class_rows(client, factories):
    """Тест-страж ADR #2: фильтр на выходе — поклассовые цифры идентичны."""
    project = factories.ProjectFactory.create()
    concrete = factories.MaterialClassFactory.create(name="В25")
    rebar = _rebar_class(factories)
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc, date=date(2026, 3, 10))
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=concrete, item_type="material",
        quantity=10, unit_price=8000, amount=80000)
    _rebar_item(factories, inv, rebar, qty=2, unit_price=10000)
    factories.InvoiceItemFactory.create(
        invoice=inv, item_type="delivery", material_class=None,
        quantity=1, unit_price=5000, amount=5000)
    factories.ReferencePriceFactory.create(project=project, material_class=concrete, price=8000.0)

    full = client.get(f"/api/dashboard/calculations?project_id={project.id}").json()
    scoped = client.get(f"/api/dashboard/calculations?project_id={project.id}&direction=concrete").json()
    full_concrete = [r for r in full if r["direction"] == "concrete"]
    assert scoped == full_concrete  # включая avg_price/deviation/compensation


def test_calculations_unknown_direction_422(client, factories):
    project = factories.ProjectFactory.create()
    resp = client.get(f"/api/dashboard/calculations?project_id={project.id}&direction=bricks")
    assert resp.status_code == 422


def _mixed_project(factories):
    """Объект: смешанный счёт (бетон+арматура+доставка+прочее) + чисто бетонный счёт
    + счёт без direction-позиций (только доставка)."""
    project = factories.ProjectFactory.create()
    concrete = factories.MaterialClassFactory.create(name="В25")
    rebar = _rebar_class(factories)
    doc = factories.DocumentFactory.create(project=project)

    inv_mixed = factories.InvoiceFactory.create(document=doc, date=date(2026, 3, 10))
    factories.InvoiceItemFactory.create(
        invoice=inv_mixed, material_class=concrete, item_type="material",
        quantity=10, unit_price=8000, amount=80000)               # 96000 с НДС
    _rebar_item(factories, inv_mixed, rebar, qty=2, unit_price=10000)  # 24000 с НДС
    factories.InvoiceItemFactory.create(
        invoice=inv_mixed, item_type="delivery", material_class=None,
        quantity=1, unit_price=5000, amount=5000)                 # 6000 с НДС
    factories.InvoiceItemFactory.create(
        invoice=inv_mixed, item_type="other", material_class=None,
        quantity=1, unit_price=2000, amount=2000)                 # 2400 с НДС

    inv_concrete = factories.InvoiceFactory.create(document=doc, date=date(2026, 4, 5))
    factories.InvoiceItemFactory.create(
        invoice=inv_concrete, material_class=concrete, item_type="material",
        quantity=5, unit_price=8200, amount=41000)                # 49200 с НДС

    inv_delivery_only = factories.InvoiceFactory.create(document=doc, date=date(2026, 4, 7))
    factories.InvoiceItemFactory.create(
        invoice=inv_delivery_only, item_type="delivery", material_class=None,
        quantity=1, unit_price=1000, amount=1000)                 # 1200 с НДС

    return project, concrete, rebar


def test_summary_directions_and_invariant(client, factories):
    project, *_ = _mixed_project(factories)
    body = client.get(f"/api/dashboard/summary?project_id={project.id}").json()

    codes = [d["code"] for d in body["directions"]]
    assert codes == ["concrete", "rebar"]          # порядок — по id типа; other отсутствует
    by_code = {d["code"]: d for d in body["directions"]}
    assert by_code["concrete"]["turnover"] == 96000.0 + 49200.0
    assert by_code["rebar"]["turnover"] == 24000.0
    assert by_code["concrete"]["volume"] == 15.0
    assert by_code["concrete"]["volume_unit"] == "м³"
    assert by_code["rebar"]["volume"] == 2.0
    assert by_code["rebar"]["volume_unit"] == "т"
    assert by_code["concrete"]["invoice_count"] == 2
    assert by_code["rebar"]["invoice_count"] == 1
    assert by_code["concrete"]["mixed_invoice_count"] == 1
    assert body["mixed_invoice_count"] == 1
    assert body["other_invoice_count"] == 1        # счёт из одной доставки
    assert body["delivery_total"] == 6000.0 + 1200.0
    assert body["other_total"] == 2400.0
    # ИНВАРИАНТ §5.1 — на сериализованных значениях. Каждое слагаемое округлено
    # до копеек НЕЗАВИСИМО, поэтому сумма округлённых может разойтись с округлённой
    # суммой на ±копейки — approx, не точное равенство. Точная (Decimal, до round)
    # партиция проверяется отдельным тестом test_summary_material_partition_exact.
    assert body["total_amount"] == pytest.approx(
        sum(d["turnover"] for d in body["directions"])
        + body["delivery_total"] + body["other_total"],
        abs=0.05,
    )


def test_summary_material_partition_exact(client, factories, db_session):
    """Точный Decimal-инвариант §5.1 ДО сериализации: группировка material-позиций
    по типу (направления / other / NULL-класс) разбивает их без пересечений и
    пропусков — суммы сходятся точно. Значит, расхождение сериализованного
    инварианта может дать только независимое округление, не потеря позиций."""
    project, *_ = _mixed_project(factories)
    from sqlalchemy import func, literal

    from models import Document, Invoice, InvoiceItem, MaterialClass, MaterialType

    vat = func.coalesce(
        InvoiceItem.vat_amount,
        InvoiceItem.amount * func.coalesce(Invoice.vat_rate, literal(Decimal("20.0"))) / 100,
    )
    grouped = (
        db_session.query(MaterialType.code, func.sum(InvoiceItem.amount + vat))
        .select_from(InvoiceItem)
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .join(Document, Invoice.document_id == Document.id)
        .outerjoin(MaterialClass, InvoiceItem.material_class_id == MaterialClass.id)
        .outerjoin(MaterialType, MaterialClass.material_type_id == MaterialType.id)
        .filter(Document.project_id == project.id, InvoiceItem.item_type == "material")
        .group_by(MaterialType.code)
        .all()
    )
    total_material = (
        db_session.query(func.sum(InvoiceItem.amount + vat))
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .join(Document, Invoice.document_id == Document.id)
        .filter(Document.project_id == project.id, InvoiceItem.item_type == "material")
        .scalar()
    )
    assert sum((row[1] for row in grouped), Decimal("0")) == total_material  # точно, без round


def test_summary_other_type_class_goes_to_other_total(client, factories):
    """ADR #9: классы типа other — в other_total, направления не образуют."""
    project = factories.ProjectFactory.create()
    misc = factories.MaterialClassFactory.create(material_type_code="other", name="Крепёж")
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc)
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=misc, item_type="material",
        quantity=1, unit_price=3000, amount=3000)

    body = client.get(f"/api/dashboard/summary?project_id={project.id}").json()
    assert body["directions"] == []
    assert body["other_total"] == 3600.0
    assert body["other_invoice_count"] == 1
    assert body["mixed_invoice_count"] == 0


def test_summary_concrete_only_matches_legacy_fields(client, factories):
    """Критерий приёмки #1: моно-бетонный объект — directions согласован со старыми полями."""
    project = factories.ProjectFactory.create()
    mc = factories.MaterialClassFactory.create()
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc)
    factories.InvoiceItemFactory.create(invoice=inv, material_class=mc, item_type="material",
                                        quantity=5, amount=40000)
    body = client.get(f"/api/dashboard/summary?project_id={project.id}").json()
    assert [d["code"] for d in body["directions"]] == ["concrete"]
    d = body["directions"][0]
    assert d["turnover"] == body["material_amount"]
    assert d["volume"] == 5.0
    assert d["invoice_count"] == body["invoice_count"]
    assert body["mixed_invoice_count"] == 0 and body["other_invoice_count"] == 0


def test_summary_overpayment_per_direction_sums_to_full(client, factories):
    project, concrete, rebar = _mixed_project(factories)
    factories.ReferencePriceFactory.create(project=project, material_class=concrete, price=8000.0)
    from tests.factories import _unit_id
    factories.ReferencePriceFactory.create(
        project=project, material_class=rebar, price=10000.0, unit_id=_unit_id("TON"))

    body = client.get(f"/api/dashboard/summary?project_id={project.id}").json()
    by_code = {d["code"]: d for d in body["directions"]}
    overpayments = [d["overpayment"] for d in body["directions"] if d["overpayment"] is not None]
    # Слагаемые округлены независимо при сериализации → approx (та же причина,
    # что у инварианта оборота; источник один — calc_rows, потерь быть не может).
    assert sum(overpayments) == pytest.approx(body["full_deviation_amount"], abs=0.05)
    assert by_code["concrete"]["overpayment"] is not None


def test_summary_volume_excluded_count(client, factories):
    """§5.2: арматура в пог.м (length) не входит в объём «т» и попадает в счётчик."""
    project = factories.ProjectFactory.create()
    rebar = _rebar_class(factories)
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc)
    _rebar_item(factories, inv, rebar, qty=2, unit_price=10000)   # 2 т — входит
    from tests.factories import _unit_id
    factories.InvoiceItemFactory.create(                          # 100 пог.м — НЕ входит
        invoice=inv, material_class=rebar, item_type="material",
        quantity=100, raw_unit="м", unit_price=50,
        normalized_unit_id=_unit_id("M"), normalized_quantity=Decimal("100"))

    body = client.get(f"/api/dashboard/summary?project_id={project.id}").json()
    d = body["directions"][0]
    assert d["volume"] == 2.0
    assert d["volume_excluded_count"] == 1
