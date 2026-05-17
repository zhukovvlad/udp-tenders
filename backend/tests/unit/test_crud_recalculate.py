"""Тесты бизнес-логики crud.compute_calculations.

Переименован из test_crud_recalculate.py — recalculate_prices() удалён,
compute_calculations() является единственным источником расчётов.
"""
from datetime import date

import crud


def test_compute_calculations_no_items_returns_empty(factories, db_session):
    project = factories.ProjectFactory.create()
    result = crud.compute_calculations(db_session, project.id)
    assert result == []


def test_compute_calculations_no_invoices_returns_empty(factories, db_session):
    project = factories.ProjectFactory.create()
    # Нет инвойсов → авто-диапазон не определяется → []
    result = crud.compute_calculations(db_session, project.id)
    assert result == []


def test_compute_calculations_simple_avg(factories, db_session):
    project = factories.ProjectFactory.create()
    mc = factories.MaterialClassFactory.create(name="В25", material_type="concrete")
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc, date=date(2026, 3, 15))
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=mc, quantity=10.0, unit_price=8000.0, amount=80000.0,
    )

    result = crud.compute_calculations(db_session, project.id)

    assert len(result) == 1
    row = result[0]
    assert row["total_qty"] == 10.0
    assert row["avg_price"] == 8000.0
    assert row["invoice_count"] == 1
    assert row["reference_price"] is None
    assert row["deviation_amount"] is None
    # Auto-detected range is normalized to full month boundaries
    assert row["period_start"] == date(2026, 3, 1)
    assert row["period_end"] == date(2026, 3, 31)


def test_compute_calculations_with_deviation(factories, db_session):
    project = factories.ProjectFactory.create()
    mc = factories.MaterialClassFactory.create()
    factories.ReferencePriceFactory.create(
        project=project, material_class=mc, price=10000.0,
        period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
    )
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc, date=date(2026, 3, 15))
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=mc, quantity=10.0, unit_price=11000.0, amount=110000.0,
    )

    result = crud.compute_calculations(db_session, project.id)

    assert len(result) == 1
    row = result[0]
    assert row["reference_price"] == 10000.0
    assert row["deviation_pct"] == 10.0
    assert row["deviation_amount"] == 10000.0


def test_compute_calculations_delivery_allocation(factories, db_session):
    """Доставка распределяется пропорционально объёму класса в суммарном объёме."""
    project = factories.ProjectFactory.create()
    mc1 = factories.MaterialClassFactory.create(name="В25", material_type="concrete")
    mc2 = factories.MaterialClassFactory.create(name="d12", material_type="rebar")
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc, date=date(2026, 3, 15))

    # mc1: 10 м³ × 8000 = 80 000
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=mc1, quantity=10.0, unit_price=8000.0, amount=80000.0,
    )
    # mc2: 30 м³ × 6000 = 180 000
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=mc2, quantity=30.0, unit_price=6000.0, amount=180000.0,
    )
    # Доставка: 40 000 (всего на 40 м³)
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=None, quantity=1.0, unit_price=40000.0, amount=40000.0,
        item_type="delivery",
    )

    result = crud.compute_calculations(db_session, project.id)
    assert len(result) == 2

    by_class = {r["material_class_id"]: r for r in result}
    r1 = by_class[mc1.id]
    r2 = by_class[mc2.id]

    # mc1 доля = 10/40 = 0.25 → доставка 10 000
    # avg_price = (80 000 + 10 000) / 10 = 9 000
    assert r1["delivery_total"] == 10000.0
    assert r1["avg_price"] == 9000.0

    # mc2 доля = 30/40 = 0.75 → доставка 30 000
    # avg_price = (180 000 + 30 000) / 30 = 7 000
    assert r2["delivery_total"] == 30000.0
    assert r2["avg_price"] == 7000.0


def test_compute_calculations_period_filter(factories, db_session):
    """Явный period_start/period_end отсекает счета вне диапазона."""
    project = factories.ProjectFactory.create()
    mc = factories.MaterialClassFactory.create()
    doc = factories.DocumentFactory.create(project=project)

    inv_jan = factories.InvoiceFactory.create(document=doc, date=date(2026, 1, 15))
    factories.InvoiceItemFactory.create(
        invoice=inv_jan, material_class=mc, quantity=5.0, unit_price=9000.0, amount=45000.0,
    )
    inv_mar = factories.InvoiceFactory.create(document=doc, date=date(2026, 3, 15))
    factories.InvoiceItemFactory.create(
        invoice=inv_mar, material_class=mc, quantity=10.0, unit_price=8000.0, amount=80000.0,
    )

    # Фильтр только март
    result = crud.compute_calculations(
        db_session, project.id,
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
    )
    assert len(result) == 1
    assert result[0]["total_qty"] == 10.0


def test_compute_calculations_multi_month(factories, db_session):
    """Счета в разных месяцах → отдельные строки."""
    project = factories.ProjectFactory.create()
    mc = factories.MaterialClassFactory.create()
    doc = factories.DocumentFactory.create(project=project)

    inv_jan = factories.InvoiceFactory.create(document=doc, date=date(2026, 1, 10))
    factories.InvoiceItemFactory.create(
        invoice=inv_jan, material_class=mc, quantity=5.0, unit_price=9000.0, amount=45000.0,
    )
    inv_feb = factories.InvoiceFactory.create(document=doc, date=date(2026, 2, 20))
    factories.InvoiceItemFactory.create(
        invoice=inv_feb, material_class=mc, quantity=8.0, unit_price=8500.0, amount=68000.0,
    )

    result = crud.compute_calculations(db_session, project.id)
    assert len(result) == 2

    periods = {r["period_start"].month for r in result}
    assert periods == {1, 2}

