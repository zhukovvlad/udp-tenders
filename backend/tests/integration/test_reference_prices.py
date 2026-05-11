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
