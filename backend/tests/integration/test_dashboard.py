from datetime import date


def test_summary_empty(client, factories):
    project = factories.ProjectFactory.create()
    response = client.get(f"/api/dashboard/summary?project_id={project.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["doc_count"] == 0
    assert body["invoice_count"] == 0
    assert body["total_amount"] == 0
    assert body["total_qty"] == 0
    assert body["first_invoice_date"] is None
    assert body["last_invoice_date"] is None
    assert body["full_deviation_amount"] is None


def test_summary_aggregates_materials(client, factories):
    project = factories.ProjectFactory.create()
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc)
    factories.InvoiceItemFactory.create(invoice=inv, item_type="material", quantity=5, amount=40000)
    factories.InvoiceItemFactory.create(invoice=inv, item_type="delivery", quantity=1, amount=2000)

    response = client.get(f"/api/dashboard/summary?project_id={project.id}")
    body = response.json()
    # Только material попадает в total_amount/total_qty
    assert body["total_amount"] == 40000.0
    assert body["total_qty"] == 5.0
    assert body["invoice_count"] == 1


def test_calculate_endpoint_creates_calculation(client, factories):
    project = factories.ProjectFactory.create()
    mc = factories.MaterialClassFactory.create()
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc, date=date(2026, 3, 1))
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=mc, item_type="material",
        quantity=10, unit_price=8000, amount=80000,
    )

    response = client.post(
        f"/api/dashboard/calculate?project_id={project.id}"
        f"&period_start=2026-01-01&period_end=2026-12-31"
    )
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1


def test_auto_calculate_no_invoices(client, factories):
    project = factories.ProjectFactory.create()
    response = client.post(f"/api/dashboard/auto-calculate?project_id={project.id}")
    assert response.status_code == 200
    assert response.json()["period_start"] is None
