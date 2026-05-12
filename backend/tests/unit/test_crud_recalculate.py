"""Тесты бизнес-логики crud.recalculate_prices."""
from datetime import date

import crud


def test_recalculate_with_no_items_returns_none(client, factories, db_session):
    project = factories.ProjectFactory.create()
    mc = factories.MaterialClassFactory.create()

    result = crud.recalculate_prices(
        db_session, project.id, mc.id, date(2026, 1, 1), date(2026, 12, 31)
    )
    assert result is None


def test_recalculate_simple_avg(factories, db_session):
    project = factories.ProjectFactory.create()
    mc = factories.MaterialClassFactory.create(name="В25")
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc, date=date(2026, 3, 15))
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=mc, quantity=10.0, unit_price=8000.0, amount=80000.0,
    )

    result = crud.recalculate_prices(
        db_session, project.id, mc.id, date(2026, 1, 1), date(2026, 12, 31)
    )
    assert result is not None
    assert result.total_qty == 10.0
    assert result.avg_price == 8000.0
    assert result.invoice_count == 1


def test_recalculate_with_reference_price_computes_deviation(factories, db_session):
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

    result = crud.recalculate_prices(
        db_session, project.id, mc.id, date(2026, 1, 1), date(2026, 12, 31)
    )
    assert result.reference_price == 10000.0
    assert result.deviation_pct == 10.0
    assert result.deviation_amount == 10000.0
