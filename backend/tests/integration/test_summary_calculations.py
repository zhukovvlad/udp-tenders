"""Интеграционные тесты: /summary отдаёт calc-rows и они совпадают с /calculations."""
from datetime import date


def _sort(rows: list[dict]) -> list[dict]:
    """Сортировка обеих сторон — порядок compute_calculations не детерминирован."""
    return sorted(rows, key=lambda r: (r["period_start"], r["material_class_id"]))


def test_summary_includes_calculations(client, factories):
    """Проект с данными: summary['calculations'] непуст и совпадает с /calculations."""
    project = factories.ProjectFactory.create()
    mc = factories.MaterialClassFactory.create(calc_role="base", name="В25")
    doc = factories.DocumentFactory.create(project=project)
    inv = factories.InvoiceFactory.create(document=doc, date=date(2026, 3, 10), vat_rate=20.0)
    factories.InvoiceItemFactory.create(
        invoice=inv, material_class=mc, item_type="material",
        quantity=10.0, unit_price=9000.0, amount=90000.0, vat_amount=18000.0,
    )

    summary = client.get(f"/api/dashboard/summary?project_id={project.id}").json()
    calc = client.get(f"/api/dashboard/calculations?project_id={project.id}").json()

    assert len(summary["calculations"]) > 0
    assert _sort(summary["calculations"]) == _sort(calc)


def test_summary_calculations_empty_for_project_without_invoices(client, factories):
    """Пустой проект: calculations == []."""
    project = factories.ProjectFactory.create()
    summary = client.get(f"/api/dashboard/summary?project_id={project.id}").json()
    assert summary["calculations"] == []
