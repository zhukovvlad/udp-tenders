from io import BytesIO

from openpyxl import load_workbook


def test_export_excel_returns_xlsx(client, factories):
    project = factories.ProjectFactory.create(name="Тест-Объект")
    response = client.get(
        f"/api/export/excel?project_id={project.id}"
        f"&period_start=2026-01-01&period_end=2026-12-31"
    )
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]

    wb = load_workbook(BytesIO(response.content))
    ws = wb.active
    # Ожидаем заголовки в первых строках
    assert ws.cell(row=1, column=1).value == "Объект:"
    assert ws.cell(row=1, column=2).value == "Тест-Объект"


def test_export_unknown_project_returns_error(client):
    response = client.get(
        "/api/export/excel?project_id=9999"
        "&period_start=2026-01-01&period_end=2026-12-31"
    )
    assert response.status_code == 200
    assert response.json() == {"error": "Проект не найден"}


def test_export_excel_includes_calculation_rows(client, factories):
    """Экспорт содержит строку данных когда есть инвойс с позицией и плановой ценой."""
    from datetime import date

    project = factories.ProjectFactory.create(name="Экспорт-Объект")
    mc = factories.MaterialClassFactory.create(name="В25", material_type="concrete")
    factories.ReferencePriceFactory.create(
        project=project, material_class=mc, price=6000.0,
        period_start=date(2026, 3, 1), period_end=date(2026, 3, 31),
    )
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc, date=date(2026, 3, 10))
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=mc,
        quantity=100.0, unit_price=6600.0, amount=660000.0,
    )

    response = client.get(
        f"/api/export/excel?project_id={project.id}"
        f"&period_start=2026-03-01&period_end=2026-03-31"
    )
    assert response.status_code == 200
    wb = load_workbook(BytesIO(response.content))
    ws = wb.active

    # Collect all non-empty cell values from the sheet
    values = [ws.cell(row=r, column=c).value
              for r in range(1, ws.max_row + 1)
              for c in range(1, ws.max_column + 1)]

    assert "В25" in values
    # avg_price includes VAT: (660000 + 132000) / 100 = 7920.0; reference_price = 6000; deviation > 0
    assert 7920.0 in values
    assert 6000.0 in values


def test_export_excel_material_class_filter(client, factories):
    """Фильтр material_class_id оставляет только строки нужного класса."""
    from datetime import date

    project = factories.ProjectFactory.create()
    mc1 = factories.MaterialClassFactory.create(name="В25", material_type="concrete")
    mc2 = factories.MaterialClassFactory.create(name="В30", material_type="concrete")
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc, date=date(2026, 3, 10))
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=mc1, quantity=10.0, unit_price=6000.0, amount=60000.0,
    )
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=mc2, quantity=5.0, unit_price=9000.0, amount=45000.0,
    )

    response = client.get(
        f"/api/export/excel?project_id={project.id}"
        f"&period_start=2026-03-01&period_end=2026-03-31"
        f"&material_class_id={mc1.id}"
    )
    assert response.status_code == 200
    wb = load_workbook(BytesIO(response.content))
    ws = wb.active

    values = [ws.cell(row=r, column=c).value
              for r in range(1, ws.max_row + 1)
              for c in range(1, ws.max_column + 1)]

    assert "В25" in values
    assert "В30" not in values


def test_export_excel_without_dates_uses_data_range(client, factories):
    """Экспорт без period_start/period_end возвращает 200, диапазон берётся из данных."""
    from datetime import date

    project = factories.ProjectFactory.create(name="Без-Дат-Объект")
    mc = factories.MaterialClassFactory.create(name="В25", material_type="concrete")
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc, date=date(2026, 4, 15))
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=mc, quantity=50.0, unit_price=7000.0, amount=350000.0,
    )

    response = client.get(f"/api/export/excel?project_id={project.id}")
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]

    wb = load_workbook(BytesIO(response.content))
    ws = wb.active
    values = [ws.cell(row=r, column=c).value
              for r in range(1, ws.max_row + 1)
              for c in range(1, ws.max_column + 1)]
    assert "В25" in values
