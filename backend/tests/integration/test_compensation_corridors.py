from datetime import date

from crud.calculations import compute_calculations
from crud.compensation_corridors import (
    delete_corridor,
    get_corridor_map,
    get_corridors,
    set_corridor,
)
from tests.factories import (
    CompensationCorridorFactory,
    DocumentFactory,
    InvoiceFactory,
    InvoiceItemFactory,
    MaterialClassFactory,
    ProjectFactory,
    ReferencePriceFactory,
)


def test_set_corridor_creates_then_get_map(db_session, factories):
    project = ProjectFactory.create()
    mc = MaterialClassFactory.create(material_type="concrete", name="В25")

    set_corridor(db_session, project.id, mc.id, 5.0)

    assert get_corridor_map(db_session, project.id) == {mc.id: 5.0}


def test_set_corridor_is_idempotent_upsert(db_session, factories):
    project = ProjectFactory.create()
    mc = MaterialClassFactory.create(material_type="concrete", name="В25")

    set_corridor(db_session, project.id, mc.id, 5.0)
    set_corridor(db_session, project.id, mc.id, 7.0)  # overwrite, no duplicate row

    rows = get_corridors(db_session, project.id)
    assert len(rows) == 1
    assert rows[0].corridor_pct == 7.0


def test_delete_corridor_idempotent(db_session, factories):
    project = ProjectFactory.create()
    mc = MaterialClassFactory.create(material_type="concrete", name="В25")
    set_corridor(db_session, project.id, mc.id, 5.0)

    assert delete_corridor(db_session, project.id, mc.id) is True
    assert delete_corridor(db_session, project.id, mc.id) is False  # already gone
    assert get_corridor_map(db_session, project.id) == {}


def test_zero_corridor_is_stored(db_session, factories):
    project = ProjectFactory.create()
    mc = MaterialClassFactory.create(material_type="concrete", name="В25")
    set_corridor(db_session, project.id, mc.id, 0.0)
    assert get_corridor_map(db_session, project.id) == {mc.id: 0.0}


def _make_invoice_with_item(db_session, project, mc, *, qty, unit_price, inv_date):
    doc = DocumentFactory.create(project=project)
    inv = InvoiceFactory.create(document=doc, date=inv_date, vat_rate=0.0)
    InvoiceItemFactory.create(
        invoice=inv, material_class=mc, item_type="material",
        quantity=qty, unit_price=unit_price, amount=qty * unit_price, vat_amount=0.0,
    )
    return inv


def test_compute_calculations_includes_compensation(db_session, factories):
    project = ProjectFactory.create()
    mc = MaterialClassFactory.create(material_type="concrete", name="В25")
    # base price 100, corridor 5% → upper 105; avg 110 → comp_per_unit = 5, qty 2 → amount 10
    ReferencePriceFactory.create(
        project=project, material_class=mc, price=100.0,
        period_start=date(2026, 3, 1), period_end=date(2026, 3, 31),
    )
    CompensationCorridorFactory.create(project_id=project.id, material_class_id=mc.id, corridor_pct=5.0)
    _make_invoice_with_item(db_session, project, mc, qty=2.0, unit_price=110.0, inv_date=date(2026, 3, 15))

    rows = compute_calculations(db_session, project.id, date(2026, 3, 1), date(2026, 3, 31))
    row = next(r for r in rows if r["material_class_id"] == mc.id)
    assert row["corridor_pct"] == 5.0
    assert row["compensation_per_unit"] == 5.0
    assert row["compensation_amount"] == 10.0


def test_compute_calculations_no_corridor_means_none(db_session, factories):
    project = ProjectFactory.create()
    mc = MaterialClassFactory.create(material_type="concrete", name="В25")
    ReferencePriceFactory.create(
        project=project, material_class=mc, price=100.0,
        period_start=date(2026, 3, 1), period_end=date(2026, 3, 31),
    )
    # no CompensationCorridor row → non-compensated
    _make_invoice_with_item(db_session, project, mc, qty=2.0, unit_price=110.0, inv_date=date(2026, 3, 15))

    rows = compute_calculations(db_session, project.id, date(2026, 3, 1), date(2026, 3, 31))
    row = next(r for r in rows if r["material_class_id"] == mc.id)
    assert row["corridor_pct"] is None
    assert row["compensation_per_unit"] is None
    assert row["compensation_amount"] is None


def test_put_and_list_corridor_via_api(client, db_session, factories):
    project = ProjectFactory.create()
    mc = MaterialClassFactory.create(material_type="concrete", name="В25")

    r = client.put(
        f"/api/projects/{project.id}/compensation-corridors/{mc.id}",
        json={"corridor_pct": 5.0},
    )
    assert r.status_code == 200

    r = client.get(f"/api/projects/{project.id}/compensation-corridors")
    assert r.status_code == 200
    body = r.json()
    assert body == [
        {
            "material_class_id": mc.id,
            "material_class_name": "В25",
            "material_type": "concrete",
            "corridor_pct": 5.0,
        }
    ]


def test_put_corridor_rejects_out_of_range(client, db_session, factories):
    project = ProjectFactory.create()
    mc = MaterialClassFactory.create(material_type="concrete", name="В25")
    r = client.put(
        f"/api/projects/{project.id}/compensation-corridors/{mc.id}",
        json={"corridor_pct": 150.0},
    )
    assert r.status_code == 422


def test_delete_corridor_via_api(client, db_session, factories):
    project = ProjectFactory.create()
    mc = MaterialClassFactory.create(material_type="concrete", name="В25")
    client.put(
        f"/api/projects/{project.id}/compensation-corridors/{mc.id}",
        json={"corridor_pct": 5.0},
    )
    r = client.delete(f"/api/projects/{project.id}/compensation-corridors/{mc.id}")
    assert r.status_code == 204
    assert client.get(f"/api/projects/{project.id}/compensation-corridors").json() == []


def test_dashboard_calculations_exposes_compensation(client, db_session, factories):
    project = ProjectFactory.create()
    mc = MaterialClassFactory.create(material_type="concrete", name="В25")
    ReferencePriceFactory.create(
        project=project, material_class=mc, price=100.0,
        period_start=date(2026, 3, 1), period_end=date(2026, 3, 31),
    )
    CompensationCorridorFactory.create(project_id=project.id, material_class_id=mc.id, corridor_pct=5.0)
    _make_invoice_with_item(db_session, project, mc, qty=2.0, unit_price=110.0, inv_date=date(2026, 3, 15))

    r = client.get(f"/api/dashboard/calculations?project_id={project.id}")
    assert r.status_code == 200
    row = next(x for x in r.json() if x["material_class_id"] == mc.id)
    assert row["corridor_pct"] == 5.0
    assert row["compensation_per_unit"] == 5.0
    assert row["compensation_amount"] == 10.0
