"""Интеграционные тесты роутера /api/suppliers."""
import crud

# --- GET /api/suppliers ---

def test_list_suppliers_empty(client):
    response = client.get("/api/suppliers")
    assert response.status_code == 200
    assert response.json() == []


def test_list_suppliers_returns_created(client, factories):
    factories.SupplierFactory.create(name="ООО Альфа", inn="1111111111")
    factories.SupplierFactory.create(name="ООО Бета", inn="2222222222")

    response = client.get("/api/suppliers")
    assert response.status_code == 200
    names = [s["name"] for s in response.json()]
    assert "ООО Альфа" in names
    assert "ООО Бета" in names


def test_list_suppliers_includes_invoice_count(client, factories):
    supplier = factories.SupplierFactory.create(name="ООО Поставщик", inn="3333333333")
    doc = factories.DocumentFactory.create()
    factories.InvoiceFactory.create(document=doc, supplier_id=supplier.id, supplier_inn="3333333333")
    factories.InvoiceFactory.create(document=doc, supplier_id=supplier.id, supplier_inn="3333333333")

    response = client.get("/api/suppliers")
    match = next(s for s in response.json() if s["id"] == supplier.id)
    assert match["invoice_count"] == 2


# --- GET /api/suppliers/{id} ---

def test_get_supplier_returns_data(client, factories):
    supplier = factories.SupplierFactory.create(name="ООО Гамма", inn="4444444444")
    doc = factories.DocumentFactory.create()
    factories.InvoiceFactory.create(document=doc, supplier_id=supplier.id)

    response = client.get(f"/api/suppliers/{supplier.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "ООО Гамма"
    assert body["inn"] == "4444444444"
    assert len(body["invoices"]) == 1


def test_get_supplier_404(client):
    response = client.get("/api/suppliers/99999")
    assert response.status_code == 404


# --- POST /api/suppliers/{id}/merge ---

def test_merge_suppliers_moves_invoices(client, factories, db_session):
    source = factories.SupplierFactory.create(name="ООО Источник", inn="5555555555")
    target = factories.SupplierFactory.create(name="ООО Цель", inn="6666666666")
    doc = factories.DocumentFactory.create()
    inv = factories.InvoiceFactory.create(document=doc, supplier_id=source.id)

    response = client.post(
        f"/api/suppliers/{target.id}/merge",
        json={"source_id": source.id},
    )
    assert response.status_code == 200
    assert response.json()["id"] == target.id

    # Инвойс теперь принадлежит target
    db_session.expire_all()
    from models import Invoice
    updated_inv = db_session.query(Invoice).filter(Invoice.id == inv.id).first()
    assert updated_inv.supplier_id == target.id

    # source удалён
    from models import Supplier
    assert db_session.query(Supplier).filter(Supplier.id == source.id).first() is None


def test_merge_suppliers_target_not_found(client, factories):
    source = factories.SupplierFactory.create(name="ООО Источник 2", inn="7777777777")
    response = client.post(
        "/api/suppliers/99999/merge",
        json={"source_id": source.id},
    )
    assert response.status_code == 404


def test_merge_suppliers_source_not_found(client, factories):
    target = factories.SupplierFactory.create(name="ООО Цель 2", inn="8888888888")
    response = client.post(
        f"/api/suppliers/{target.id}/merge",
        json={"source_id": 99999},
    )
    assert response.status_code == 404


def test_merge_same_id_rejected(client, factories):
    supplier = factories.SupplierFactory.create(name="ООО Один", inn="9999999999")
    response = client.post(
        f"/api/suppliers/{supplier.id}/merge",
        json={"source_id": supplier.id},
    )
    assert response.status_code == 422


# --- GET /api/suppliers/duplicates ---

def test_duplicates_empty(client):
    response = client.get("/api/suppliers/duplicates")
    assert response.status_code == 200
    assert response.json() == []


def test_duplicates_finds_similar_names(client, factories):
    factories.SupplierFactory.create(name="ООО СтройБетон", inn=None)
    factories.SupplierFactory.create(name="ООО Строй Бетон", inn=None)

    response = client.get("/api/suppliers/duplicates")
    assert response.status_code == 200
    pairs = response.json()
    assert len(pairs) == 1
    names = {pairs[0]["supplier_a"]["name"], pairs[0]["supplier_b"]["name"]}
    assert "ООО СтройБетон" in names
    assert "ООО Строй Бетон" in names
    assert pairs[0]["score"] >= 85.0


def test_duplicates_ignores_suppliers_with_inn(client, factories):
    # Поставщики с ИНН — не участвуют в поиске дубликатов
    factories.SupplierFactory.create(name="ООО СтройБетон", inn="1234567890")
    factories.SupplierFactory.create(name="ООО Строй Бетон", inn="0987654321")

    response = client.get("/api/suppliers/duplicates")
    assert response.status_code == 200
    assert response.json() == []


def test_duplicates_invalid_threshold(client):
    response = client.get("/api/suppliers/duplicates?threshold=0")
    assert response.status_code == 422


# --- CRUD: get_or_create_supplier ---

def test_get_or_create_supplier_by_inn(db_session):
    s1 = crud.get_or_create_supplier(db_session, name="ООО Бетон", inn="1112223334")
    s2 = crud.get_or_create_supplier(db_session, name="ООО Бетон Другое", inn="1112223334")
    # Тот же ИНН → тот же объект
    assert s1.id == s2.id
    assert s1.name == "ООО Бетон"


def test_get_or_create_supplier_by_name_no_inn(db_session):
    s1 = crud.get_or_create_supplier(db_session, name="ООО Ромашка", inn=None)
    s2 = crud.get_or_create_supplier(db_session, name="ООО Ромашка", inn=None)
    assert s1.id == s2.id


def test_get_or_create_supplier_different_names_no_inn(db_session):
    s1 = crud.get_or_create_supplier(db_session, name="ООО Ромашка", inn=None)
    s2 = crud.get_or_create_supplier(db_session, name="ООО Лютик", inn=None)
    assert s1.id != s2.id
