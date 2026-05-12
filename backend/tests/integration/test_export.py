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
