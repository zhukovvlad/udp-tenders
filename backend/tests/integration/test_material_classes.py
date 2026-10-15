import pytest


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
    factories.MaterialClassFactory.create(name="В25", material_type_code="concrete")
    factories.MaterialClassFactory.create(name="d12", material_type_code="rebar")

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


class TestMaterialTypeResolution:
    def test_create_resolves_material_type_code(self, client):
        resp = client.post("/api/material-classes", json={"name": "В30", "material_type": "concrete"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "В30"
        assert body["material_type"] == "concrete"

    def test_list_emits_material_type_code(self, client, factories):
        factories.MaterialClassFactory.create(material_type_code="rebar", name="d10")
        resp = client.get("/api/material-classes")
        assert resp.status_code == 200
        rebars = [c for c in resp.json() if c["material_type"] == "rebar"]
        assert any(c["name"] == "d10" for c in rebars)

    def test_create_unknown_type_returns_422(self, client):
        resp = client.post("/api/material-classes", json={"name": "X", "material_type": "wood"})
        assert resp.status_code == 422


def test_create_spelling_variants_reuse_one_class(client):
    """«В7,5» и «B7.5» (латиница, точка) — один класс с каноническим именем «В7.5»."""
    r1 = client.post("/api/material-classes", json={"name": "В7,5", "material_type": "concrete"})
    r2 = client.post("/api/material-classes", json={"name": "B7.5", "material_type": "concrete"})
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.json()["name"] == "В7.5"


def test_material_class_name_unique_per_type(db_session, factories):
    """БД не допускает двух классов с одним именем в одном типе (uq_material_classes_type_name)."""
    from sqlalchemy.exc import IntegrityError

    from models import MaterialClass

    mc = factories.MaterialClassFactory.create(name="В45", material_type_code="concrete")
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(MaterialClass(name="В45", material_type_id=mc.material_type_id))
        db_session.flush()


@pytest.mark.parametrize("commit", [True, False])
def test_get_or_create_recovers_from_concurrent_insert(db_session, factories, monkeypatch, commit):
    """Гонка: SELECT не увидел класс, INSERT упал на уникальности → берём созданный параллельно."""
    import crud.materials as cm

    existing = factories.MaterialClassFactory.create(name="В35", material_type_code="concrete")
    real_find = cm._find_class
    calls = {"n": 0}

    def find_misses_first_time(db, name, material_type_id):
        """Первый поиск «не видит» класс — как будто его ещё не закоммитила параллельная транзакция."""
        calls["n"] += 1
        return None if calls["n"] == 1 else real_find(db, name, material_type_id)
    monkeypatch.setattr(cm, "_find_class", find_misses_first_time)

    mc = cm.get_or_create_material_class(db_session, "B35", "concrete", commit=commit)

    assert mc.id == existing.id
    assert db_session.query(cm.MaterialClass).filter_by(name="В35").count() == 1
