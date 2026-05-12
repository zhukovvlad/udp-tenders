def test_create_material_class(client):
    response = client.post(
        "/api/material-classes",
        json={"name": "В30", "material_type": "concrete"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "В30"
    assert body["material_type"] == "concrete"


def test_create_is_idempotent(client):
    """get_or_create — повторный вызов не плодит дубликаты."""
    r1 = client.post("/api/material-classes", json={"name": "В25", "material_type": "concrete"})
    r2 = client.post("/api/material-classes", json={"name": "В25", "material_type": "concrete"})
    assert r1.json()["id"] == r2.json()["id"]


def test_list_filtered_by_material_type(client, factories):
    factories.MaterialClassFactory.create(name="В25", material_type="concrete")
    factories.MaterialClassFactory.create(name="d12", material_type="rebar")

    response = client.get("/api/material-classes?material_type=concrete")
    assert response.status_code == 200
    assert all(c["material_type"] == "concrete" for c in response.json())


def test_delete_material_class(client, factories):
    mc = factories.MaterialClassFactory.create()
    response = client.delete(f"/api/material-classes/{mc.id}")
    assert response.status_code == 200


def test_delete_404(client):
    response = client.delete("/api/material-classes/9999")
    assert response.status_code == 404
