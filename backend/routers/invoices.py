import logging
import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crud.documents import create_document, delete_document, get_document, get_documents
from crud.suppliers import get_or_create_supplier
from database import get_db
from models import Invoice, InvoiceItem, MaterialClass
from s3 import delete_file, download_file, ensure_bucket, upload_file

logger = logging.getLogger(__name__)
router = APIRouter()


class InvoiceItemEdit(BaseModel):
    id: int | None = None  # None для новой позиции
    raw_name: str
    item_type: str  # material / delivery / other
    material_class_id: int | None = None
    quantity: float
    unit: str | None = None
    unit_price: float
    amount: float
    vat_amount: float | None = None


class InvoiceUpdate(BaseModel):
    number: str
    date: date
    supplier_name: str | None = None
    supplier_inn: str | None = None
    vat_rate: float = 20.0
    items: list[InvoiceItemEdit]


def _doc_has_issues(doc) -> bool:
    """Документ требует проверки, если есть позиции, по которым нельзя считать аналитику:
    нет количества или нет описания. Цены/класс могут быть пустыми (валидно для
    цементного молока, добавок и т.п.)."""
    for inv in doc.invoices:
        if not inv.items:
            return True
        for item in inv.items:
            if (item.quantity or 0) <= 0:
                return True
            if not (item.raw_name or "").strip():
                return True
    return False


def _avg_confidence(doc) -> float | None:
    confs = [inv.ai_confidence for inv in doc.invoices if inv.ai_confidence is not None]
    if not confs:
        return None
    return round(sum(confs) / len(confs), 2)


def _serialize_document(doc) -> dict:
    """Полная сериализация документа со счетами-фактурами и позициями.
    Используется в GET /documents/{id}, POST /upload, POST /reparse —
    клиент кеширует один и тот же shape независимо от точки входа."""
    return {
        "id": doc.id,
        "project_id": doc.project_id,
        "filename": doc.filename,
        "doc_type": doc.doc_type,
        "status": doc.status,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        "invoice_count": len(doc.invoices),
        "has_issues": _doc_has_issues(doc) if doc.status == "parsed" else False,
        "ai_confidence": _avg_confidence(doc),
        "invoices": [
            {
                "id": inv.id,
                "document_id": doc.id,
                "number": inv.number,
                "date": inv.date.isoformat(),
                "supplier_name": inv.supplier_name,
                "supplier_inn": inv.supplier_inn,
                "vat_rate": inv.vat_rate,
                "ai_confidence": inv.ai_confidence,
                "verified": inv.verified,
                "verified_at": inv.verified_at.isoformat() if inv.verified_at else None,
                "has_issues": False,  # пер-СФ флаг можно вычислить позже, пока на уровне документа
                "items": [
                    {
                        "id": item.id,
                        "raw_name": item.raw_name,
                        "item_type": item.item_type,
                        "material_class": (
                            {"id": item.material_class.id, "name": item.material_class.name}
                            if item.material_class
                            else None
                        ),
                        "material_class_id": item.material_class_id,
                        "quantity": item.quantity,
                        "unit": item.unit,
                        "unit_price": item.unit_price,
                        "amount": item.amount,
                        "vat_amount": item.vat_amount,
                    }
                    for item in inv.items
                ],
            }
            for inv in doc.invoices
        ],
    }


@router.get("/documents")
def list_documents(project_id: int | None = None, db: Session = Depends(get_db)):
    docs = get_documents(db, project_id)
    return [
        {
            "id": doc.id,
            "project_id": doc.project_id,
            "filename": doc.filename,
            "doc_type": doc.doc_type,
            "status": doc.status,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "invoice_count": len(doc.invoices),
            "has_issues": _doc_has_issues(doc) if doc.status == "parsed" else False,
            "ai_confidence": _avg_confidence(doc),
        }
        for doc in docs
    ]


@router.get("/documents/{doc_id}")
def get_document_detail(doc_id: int, db: Session = Depends(get_db)):
    doc = get_document(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return _serialize_document(doc)


@router.get("/documents/{doc_id}/pdf")
def get_document_pdf(doc_id: int, db: Session = Depends(get_db)):
    doc = get_document(db, doc_id)
    if not doc or not doc.s3_key:
        raise HTTPException(status_code=404, detail="PDF не найден")
    try:
        file_bytes = download_file(doc.s3_key)
    except Exception:
        raise HTTPException(status_code=404, detail="Файл не найден в хранилище")
    return Response(content=file_bytes, media_type="application/pdf")


@router.post("/documents/{doc_id}/reparse")
async def reparse_document(doc_id: int, db: Session = Depends(get_db)):
    """Повторить парсинг документа. Удаляет ранее распознанные СФ и парсит заново из S3."""
    logger.info(f"Reparse документа id={doc_id}")
    doc = get_document(db, doc_id)
    if not doc:
        logger.warning(f"Reparse: документ id={doc_id} не найден")
        raise HTTPException(status_code=404, detail="Документ не найден")
    if not doc.s3_key:
        logger.warning(f"Reparse: документ id={doc_id} без s3_key")
        raise HTTPException(status_code=400, detail="PDF недоступен в хранилище")
    if any(inv.verified for inv in doc.invoices):
        raise HTTPException(status_code=409, detail="Документ содержит подтверждённые СФ — снимите подтверждение перед повторным разбором")

    # Удаляем ранее распознанные СФ (cascade удалит позиции)
    old_count = len(doc.invoices)
    for inv in list(doc.invoices):
        db.delete(inv)
    db.commit()
    logger.info(f"Reparse: удалено старых СФ для doc={doc_id}: {old_count}")

    try:
        file_bytes = download_file(doc.s3_key)
        logger.info(f"Reparse: скачан PDF из S3 (key={doc.s3_key}, размер={len(file_bytes)})")
    except Exception as e:
        logger.exception(f"Reparse: ошибка скачивания из S3 для doc={doc_id}")
        raise HTTPException(status_code=404, detail=f"Файл не найден в хранилище: {e}")

    from pdf_parser import parse_invoice_pdf
    result = await parse_invoice_pdf(file_bytes, db, doc.id)

    if result.get("error"):
        doc.status = "error"
        doc.doc_type = "unknown"
        db.commit()
        logger.warning(f"Reparse doc={doc_id} завершён с ошибкой: {result['error']}")
        db.refresh(doc)
        return _serialize_document(doc)

    doc.doc_type = result.get("doc_type", "invoice")
    doc.status = "parsed"
    db.commit()
    db.refresh(doc)
    logger.info(f"Reparse doc={doc_id} успешно завершён, СФ: {len(result.get('invoices_created', []))}")

    return _serialize_document(doc)


@router.post("/upload")
async def upload_pdf(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".pdf"):
        logger.warning(f"Upload: попытка загрузить не-PDF '{file.filename}' (project={project_id})")
        raise HTTPException(status_code=400, detail="Только PDF-файлы")

    file_bytes = await file.read()
    logger.info(f"Upload: получен файл '{file.filename}' (project={project_id}, размер={len(file_bytes)})")

    now = datetime.now(UTC)
    object_name = f"{now.year}/{now.month:02d}/{uuid.uuid4().hex}_{file.filename}"

    try:
        ensure_bucket()
        upload_file(file_bytes, object_name)
        logger.info(f"Upload: файл сохранён в S3 (key={object_name})")
    except Exception:
        logger.exception("Upload: ошибка загрузки в S3")
        raise HTTPException(status_code=500, detail="Не удалось сохранить файл в хранилище")

    doc = create_document(db, project_id, file.filename, object_name)
    logger.info(f"Upload: создан документ id={doc.id}")

    from pdf_parser import parse_invoice_pdf
    result = await parse_invoice_pdf(file_bytes, db, doc.id)

    if result.get("error"):
        doc.status = "error"
        doc.doc_type = "unknown"
        db.commit()
        logger.warning(f"Upload doc={doc.id} завершён с ошибкой: {result['error']}")
        db.refresh(doc)
        return _serialize_document(doc)

    doc.doc_type = result.get("doc_type", "invoice")
    doc.status = "parsed"
    db.commit()
    db.refresh(doc)
    logger.info(f"Upload doc={doc.id} успешно завершён, СФ: {len(result.get('invoices_created', []))}")

    return _serialize_document(doc)


@router.put("/{invoice_id}")
def update_invoice(invoice_id: int, data: InvoiceUpdate, db: Session = Depends(get_db)):
    """Обновить СФ и её позиции. Удаляет позиции, которых нет в новом списке."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="СФ не найдена")
    if invoice.verified:
        raise HTTPException(status_code=409, detail="СФ подтверждена — снимите подтверждение перед редактированием")

    invoice.number = data.number
    invoice.date = data.date
    _name = (data.supplier_name.strip() or None) if data.supplier_name else None
    _inn = (data.supplier_inn.strip() or None) if data.supplier_inn else None
    if _inn and not _name:
        raise HTTPException(status_code=422, detail="supplier_name обязателен при указании supplier_inn")
    invoice.vat_rate = data.vat_rate
    if _name:
        supplier = get_or_create_supplier(db, name=_name, inn=_inn)
        invoice.supplier_id = supplier.id
        invoice.supplier_name = supplier.name
        invoice.supplier_inn = supplier.inn
    else:
        invoice.supplier_id = None
        invoice.supplier_name = None
        invoice.supplier_inn = None

    incoming_ids = {item.id for item in data.items if item.id is not None}
    existing = {item.id: item for item in invoice.items}

    # Удаляем позиции, которых нет в новом списке
    for existing_id, existing_item in existing.items():
        if existing_id not in incoming_ids:
            db.delete(existing_item)

    # Обновляем существующие, создаём новые
    for item_data in data.items:
        if item_data.id and item_data.id in existing:
            item = existing[item_data.id]
            item.raw_name = item_data.raw_name
            item.item_type = item_data.item_type
            item.material_class_id = item_data.material_class_id
            item.quantity = item_data.quantity
            item.unit = item_data.unit
            item.unit_price = item_data.unit_price
            item.amount = item_data.amount
            item.vat_amount = item_data.vat_amount
        else:
            new_item = InvoiceItem(
                invoice_id=invoice.id,
                raw_name=item_data.raw_name,
                item_type=item_data.item_type,
                material_class_id=item_data.material_class_id,
                quantity=item_data.quantity,
                unit=item_data.unit,
                unit_price=item_data.unit_price,
                amount=item_data.amount,
                vat_amount=item_data.vat_amount,
            )
            db.add(new_item)

    db.commit()
    db.refresh(invoice)
    return {"message": "Сохранено", "invoice_id": invoice.id}


@router.post("/{invoice_id}/verify")
def verify_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Отметить СФ как проверенную человеком."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="СФ не найдена")
    invoice.verified = True
    invoice.verified_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    logger.info(f"Invoice id={invoice_id} помечена как проверенная")
    return {"message": "Проверено", "invoice_id": invoice.id, "verified_at": invoice.verified_at.isoformat()}


@router.post("/{invoice_id}/unverify")
def unverify_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Снять отметку о проверке с СФ."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="СФ не найдена")
    invoice.verified = False
    invoice.verified_at = None
    db.commit()
    logger.info(f"Invoice id={invoice_id}: отметка о проверке снята")
    return {"message": "Отметка снята", "invoice_id": invoice.id}


class BulkDeleteRequest(BaseModel):
    ids: list[int] = Field(..., max_length=1000)


@router.delete("/bulk", status_code=200)
def bulk_delete_invoices(body: BulkDeleteRequest, db: Session = Depends(get_db)):
    """Удалить несколько СФ за раз. Подтверждённые пропускаются (не удаляются)."""
    if not body.ids:
        return {"deleted": 0, "skipped": []}

    invoices = db.query(Invoice).filter(Invoice.id.in_(body.ids)).all()
    deleted = 0
    skipped: list[int] = []
    for inv in invoices:
        if inv.verified:
            skipped.append(inv.id)
        else:
            db.delete(inv)
            deleted += 1
    db.commit()
    return {"deleted": deleted, "skipped": skipped}


@router.delete("/{invoice_id}")
def delete_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Удалить одну СФ из документа (PDF документ остаётся)."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="СФ не найдена")
    if invoice.verified:
        raise HTTPException(status_code=409, detail="СФ подтверждена — снимите подтверждение перед удалением")
    db.delete(invoice)
    db.commit()
    return {"message": "СФ удалена"}


@router.delete("/documents/{doc_id}")
def delete_document_route(doc_id: int, db: Session = Depends(get_db)):
    doc = get_document(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    if any(inv.verified for inv in doc.invoices):
        raise HTTPException(status_code=409, detail="Документ содержит подтверждённые СФ — снимите подтверждение перед удалением")
    if doc.s3_key:
        try:
            delete_file(doc.s3_key)
        except Exception:
            pass
    delete_document(db, doc_id)
    return {"message": "Удалено"}
