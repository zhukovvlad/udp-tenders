"""Integration tests for routers/invoices.py — upload, reparse, update, delete."""


def test_upload_rejects_non_pdf(client, factories):
    project = factories.ProjectFactory.create()
    response = client.post(
        "/api/invoices/upload",
        files={"file": ("doc.txt", b"not a pdf", "text/plain")},
        data={"project_id": project.id},
    )
    assert response.status_code == 400


def test_upload_creates_document_with_invoices(client, factories, sample_pdf_bytes, mock_openrouter):
    project = factories.ProjectFactory.create()
    response = client.post(
        "/api/invoices/upload",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"project_id": project.id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "parsed"
    assert body["doc_type"] == "invoice"
    assert body["invoice_count"] == 1
    assert body["invoices"][0]["number"] == "СФ-101"
    assert len(body["invoices"][0]["items"]) == 1


def test_upload_unparseable_marks_doc_type_unknown(
    client, factories, sample_pdf_bytes, mock_openrouter,
):
    mock_openrouter.use_scenario("unparseable")
    project = factories.ProjectFactory.create()
    response = client.post(
        "/api/invoices/upload",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"project_id": project.id},
    )
    assert response.status_code == 200
    body = response.json()
    # При doc_type=unknown бэкенд проставляет ОБА поля: doc_type=unknown и status=error.
    assert body["doc_type"] == "unknown"
    assert body["status"] == "error"
    assert body["invoice_count"] == 0


def test_upload_invalid_json_marks_error(
    client, factories, sample_pdf_bytes, mock_openrouter,
):
    mock_openrouter.use_scenario("invalid_json")
    project = factories.ProjectFactory.create()
    response = client.post(
        "/api/invoices/upload",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"project_id": project.id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    # Невалидный JSON не должен оставлять полу-сохранённых СФ в БД.
    assert body["invoice_count"] == 0


def test_get_document_404(client):
    response = client.get("/api/invoices/documents/9999")
    assert response.status_code == 404


def test_list_documents_filtered_by_project(client, factories):
    p1 = factories.ProjectFactory.create()
    p2 = factories.ProjectFactory.create()
    factories.DocumentFactory.create(project=p1)
    factories.DocumentFactory.create(project=p2)

    response = client.get(f"/api/invoices/documents?project_id={p1.id}")
    assert response.status_code == 200
    assert all(d["project_id"] == p1.id for d in response.json())


def test_update_invoice_replaces_items(client, factories):
    invoice = factories.InvoiceFactory.create()
    factories.InvoiceItemFactory.create(invoice=invoice, raw_name="Старая позиция")
    document_id = invoice.document_id

    response = client.put(
        f"/api/invoices/{invoice.id}",
        json={
            "number": "СФ-NEW",
            "date": "2026-05-01",
            "supplier_name": "Новый",
            "supplier_inn": None,
            "vat_rate": 20.0,
            "items": [
                {
                    "id": None,
                    "raw_name": "Новая",
                    "item_type": "material",
                    "material_class_id": None,
                    "quantity": 3.0,
                    "unit": "м3",
                    "unit_price": 9000.0,
                    "amount": 27000.0,
                    "vat_amount": 4500.0,
                }
            ],
        },
    )
    assert response.status_code == 200

    # Проверяем, что новый шейп действительно сохранился — старая позиция удалена,
    # новая на месте, поля СФ обновлены.
    doc_response = client.get(f"/api/invoices/documents/{document_id}")
    assert doc_response.status_code == 200
    doc = doc_response.json()
    assert len(doc["invoices"]) == 1
    inv = doc["invoices"][0]
    assert inv["number"] == "СФ-NEW"
    assert inv["supplier_name"] == "Новый"
    assert len(inv["items"]) == 1
    assert inv["items"][0]["raw_name"] == "Новая"
    assert inv["items"][0]["quantity"] == 3.0


def test_delete_invoice(client, factories):
    invoice = factories.InvoiceFactory.create()
    document_id = invoice.document_id

    response = client.delete(f"/api/invoices/{invoice.id}")
    assert response.status_code == 200

    # Проверяем, что СФ действительно убрана из документа.
    doc_response = client.get(f"/api/invoices/documents/{document_id}")
    assert doc_response.status_code == 200
    assert doc_response.json()["invoice_count"] == 0
    assert doc_response.json()["invoices"] == []


def test_delete_document_removes_from_s3(
    client, factories, in_memory_s3,
):
    doc = factories.DocumentFactory.create(s3_key="2026/05/test.pdf")
    in_memory_s3["2026/05/test.pdf"] = b"fake"

    response = client.delete(f"/api/invoices/documents/{doc.id}")
    assert response.status_code == 200
    assert "2026/05/test.pdf" not in in_memory_s3
