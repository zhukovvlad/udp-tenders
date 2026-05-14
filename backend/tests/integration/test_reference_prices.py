def test_create_reference_price(client, factories):
    project = factories.ProjectFactory.create()
    mc = factories.MaterialClassFactory.create()

    response = client.post(
        "/api/reference-prices",
        json={
            "project_id": project.id,
            "material_class_id": mc.id,
            "price": 8500.0,
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
            "source": "контракт",
        },
    )
    assert response.status_code == 200


def test_list_reference_prices_includes_relations(client, factories):
    factories.ReferencePriceFactory.create()

    response = client.get("/api/reference-prices")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert "project_name" in body[0]
    assert "material_class_name" in body[0]


def test_filter_by_project(client, factories):
    p1 = factories.ProjectFactory.create()
    p2 = factories.ProjectFactory.create()
    factories.ReferencePriceFactory.create(project=p1)
    factories.ReferencePriceFactory.create(project=p2)

    response = client.get(f"/api/reference-prices?project_id={p1.id}")
    assert response.status_code == 200
    assert all(rp["project_id"] == p1.id for rp in response.json())


def test_delete_reference_price(client, factories):
    rp = factories.ReferencePriceFactory.create()
    response = client.delete(f"/api/reference-prices/{rp.id}")
    assert response.status_code == 200


def test_update_reference_price(client, factories):
    rp = factories.ReferencePriceFactory.create(price=8000.0, source="старый")

    response = client.put(
        f"/api/reference-prices/{rp.id}",
        json={
            "price": 9500.0,
            "period_start": "2026-03-01",
            "period_end": "2026-09-30",
            "source": "новый контракт",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["price"] == 9500.0
    assert body["period_start"] == "2026-03-01"
    assert body["period_end"] == "2026-09-30"
    assert body["source"] == "новый контракт"


def test_update_reference_price_partial(client, factories):
    rp = factories.ReferencePriceFactory.create(
        price=8000.0,
        period_start="2026-01-01",
        period_end="2026-12-31",
    )

    response = client.put(
        f"/api/reference-prices/{rp.id}",
        json={"price": 7000.0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["price"] == 7000.0
    assert body["period_start"] == "2026-01-01"
    assert body["period_end"] == "2026-12-31"


def test_update_reference_price_not_found(client):
    response = client.put(
        "/api/reference-prices/99999",
        json={"price": 1000.0},
    )
    assert response.status_code == 404

