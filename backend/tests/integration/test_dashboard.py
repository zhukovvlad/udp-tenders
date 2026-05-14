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


def test_summary_with_reference_price_computes_deviation(client, factories):
    project = factories.ProjectFactory.create()
    mc = factories.MaterialClassFactory.create()
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc, date=date(2026, 3, 15))
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=mc, item_type="material",
        quantity=10, unit_price=9000, amount=90000,
    )
    # Reference price: 8000 → avg_price 9000 → deviation = (9000-8000)*10 = 10000
    factories.ReferencePriceFactory.create(
        project=project, material_class=mc,
        price=8000.0,
        period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
    )

    response = client.get(f"/api/dashboard/summary?project_id={project.id}")
    body = response.json()
    assert body["first_invoice_date"] == "2026-03-15"
    assert body["last_invoice_date"] == "2026-03-15"
    assert body["full_deviation_amount"] == 10000.0


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


def test_dashboard_invoices_includes_verified_fields(client, factories):
    project = factories.ProjectFactory.create()
    doc = factories.DocumentFactory.create(project=project)
    factories.InvoiceFactory.create(document=doc)

    response = client.get(f"/api/dashboard/invoices?project_id={project.id}")
    assert response.status_code == 200
    inv = response.json()[0]
    assert "verified" in inv
    assert "verified_at" in inv
    assert inv["verified"] is False
    assert inv["verified_at"] is None


def test_dashboard_invoices_reflects_verification(client, factories):
    project = factories.ProjectFactory.create()
    doc = factories.DocumentFactory.create(project=project)
    invoice = factories.InvoiceFactory.create(document=doc)

    client.post(f"/api/invoices/{invoice.id}/verify")

    response = client.get(f"/api/dashboard/invoices?project_id={project.id}")
    assert response.status_code == 200
    inv = response.json()[0]
    assert inv["verified"] is True
    assert inv["verified_at"] is not None
