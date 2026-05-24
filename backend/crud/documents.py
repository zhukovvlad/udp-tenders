from datetime import date

from sqlalchemy.orm import Session

from crud.suppliers import get_or_create_supplier
from models import Document, Invoice, InvoiceItem

# --- Documents ---

def get_documents(db: Session, project_id: int = None, status: str = None):
    q = db.query(Document).order_by(Document.uploaded_at.desc())
    if project_id:
        q = q.filter(Document.project_id == project_id)
    if status:
        q = q.filter(Document.status == status)
    return q.all()


def get_document(db: Session, doc_id: int):
    return db.query(Document).filter(Document.id == doc_id).first()


def create_document(db: Session, project_id: int, filename: str, s3_key: str) -> Document:
    doc = Document(project_id=project_id, filename=filename, s3_key=s3_key)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def delete_document(db: Session, doc_id: int):
    doc = get_document(db, doc_id)
    if doc:
        db.delete(doc)
        db.commit()
    return doc


# --- Invoices ---

def create_invoice(db: Session, document_id: int, number: str, invoice_date: date,
                   supplier_name: str | None, supplier_inn: str | None, vat_rate: float,
                   confidence: float, items: list[dict]) -> Invoice:
    # Нормализуем: пустые строки и whitespace → None
    _inn = (supplier_inn.strip() or None) if supplier_inn else None
    _name = (supplier_name.strip() or None) if supplier_name else None

    # ИНН без имени — сбрасываем: нет смысла хранить ИНН без привязанного Supplier.
    if not _name:
        _inn = None

    # Если поставщик уже есть в БД (напр., по тому же ИНН) — берём каноническое имя из БД,
    # а не сырой текст из документа.
    supplier_id = None
    if _name:
        supplier = get_or_create_supplier(db, name=_name, inn=_inn)
        supplier_id = supplier.id
        _name = supplier.name
        _inn = supplier.inn

    invoice = Invoice(
        document_id=document_id,
        supplier_id=supplier_id,
        number=number,
        date=invoice_date,
        supplier_name=_name,
        supplier_inn=_inn,
        vat_rate=vat_rate,
        ai_confidence=confidence,
    )
    db.add(invoice)
    db.flush()

    for item in items:
        db_item = InvoiceItem(
            invoice_id=invoice.id,
            raw_name=item["raw_name"],
            item_type=item["item_type"],
            material_class_id=item.get("material_class_id"),
            quantity=item["quantity"],
            unit=item.get("unit"),
            unit_price=item["unit_price"],
            amount=item["amount"],
            vat_amount=item.get("vat_amount"),
        )
        db.add(db_item)

    db.commit()
    db.refresh(invoice)
    return invoice
