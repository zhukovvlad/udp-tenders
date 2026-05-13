from datetime import UTC, date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import (
    Document,
    Invoice,
    InvoiceItem,
    MaterialClass,
    PriceCalculation,
    Project,
    ReferencePrice,
)

# --- Projects ---

def get_projects(db: Session):
    return db.query(Project).order_by(Project.name).all()


def get_project(db: Session, project_id: int):
    return db.query(Project).filter(Project.id == project_id).first()


def create_project(db: Session, name: str, contract_number: str = None) -> Project:
    project = Project(name=name, contract_number=contract_number)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project_id: int, name: str, contract_number: str = None):
    project = get_project(db, project_id)
    if project:
        project.name = name
        project.contract_number = contract_number
        db.commit()
        db.refresh(project)
    return project


def delete_project(db: Session, project_id: int):
    project = get_project(db, project_id)
    if project:
        db.delete(project)
        db.commit()
    return project


# --- Material Classes ---

def get_material_classes(db: Session, material_type: str = None):
    q = db.query(MaterialClass).order_by(MaterialClass.material_type, MaterialClass.name)
    if material_type:
        q = q.filter(MaterialClass.material_type == material_type)
    return q.all()


def get_material_class(db: Session, class_id: int):
    return db.query(MaterialClass).filter(MaterialClass.id == class_id).first()


def get_or_create_material_class(db: Session, name: str, material_type: str) -> MaterialClass:
    mc = db.query(MaterialClass).filter(
        MaterialClass.name == name, MaterialClass.material_type == material_type
    ).first()
    if not mc:
        mc = MaterialClass(name=name, material_type=material_type)
        db.add(mc)
        db.commit()
        db.refresh(mc)
    return mc


def delete_material_class(db: Session, class_id: int):
    mc = get_material_class(db, class_id)
    if mc:
        db.query(InvoiceItem).filter(InvoiceItem.material_class_id == class_id).update(
            {InvoiceItem.material_class_id: None}, synchronize_session=False
        )
        db.query(PriceCalculation).filter(PriceCalculation.material_class_id == class_id).delete()
        db.query(ReferencePrice).filter(ReferencePrice.material_class_id == class_id).delete()
        db.delete(mc)
        db.commit()
    return mc


# --- Reference Prices ---

def get_reference_prices(db: Session, project_id: int = None):
    q = db.query(ReferencePrice)
    if project_id:
        q = q.filter(ReferencePrice.project_id == project_id)
    return q.order_by(ReferencePrice.period_start.desc()).all()


def create_reference_price(db: Session, project_id: int, material_class_id: int,
                           price: float, period_start: date, period_end: date,
                           source: str = None) -> ReferencePrice:
    rp = ReferencePrice(
        project_id=project_id, material_class_id=material_class_id,
        price=price, period_start=period_start, period_end=period_end, source=source,
    )
    db.add(rp)
    db.commit()
    db.refresh(rp)
    return rp


def delete_reference_price(db: Session, rp_id: int):
    rp = db.query(ReferencePrice).filter(ReferencePrice.id == rp_id).first()
    if rp:
        db.delete(rp)
        db.commit()
    return rp


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
                   supplier_name: str, supplier_inn: str, vat_rate: float,
                   confidence: float, items: list[dict]) -> Invoice:
    invoice = Invoice(
        document_id=document_id,
        number=number,
        date=invoice_date,
        supplier_name=supplier_name,
        supplier_inn=supplier_inn,
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


# --- Price Calculations ---

def recalculate_prices(db: Session, project_id: int, material_class_id: int,
                       period_start: date, period_end: date, commit: bool = True,
                       skip_delete: bool = False):
    """Recalculate average price for a project + material class + period."""
    if not skip_delete:
        db.query(PriceCalculation).filter(
            PriceCalculation.project_id == project_id,
            PriceCalculation.material_class_id == material_class_id,
            PriceCalculation.period_start == period_start,
            PriceCalculation.period_end == period_end,
        ).delete()

    items_query = (
        db.query(InvoiceItem)
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .join(Document, Invoice.document_id == Document.id)
        .filter(
            Document.project_id == project_id,
            Invoice.date >= period_start,
            Invoice.date <= period_end,
        )
    )

    material_items = items_query.filter(
        InvoiceItem.item_type == "material",
        InvoiceItem.material_class_id == material_class_id,
    ).all()

    # ВСЕ материалы за период — для распределения доставки пропорционально объёмам
    all_material_items = items_query.filter(InvoiceItem.item_type == "material").all()

    delivery_items = items_query.filter(
        InvoiceItem.item_type == "delivery",
    ).all()

    material_total = sum(i.amount for i in material_items)
    material_vat = sum(i.vat_amount or 0 for i in material_items)
    delivery_total_period = sum(i.amount for i in delivery_items)
    delivery_vat_period = sum(i.vat_amount or 0 for i in delivery_items)
    total_qty = sum(i.quantity for i in material_items)
    all_materials_qty = sum(i.quantity for i in all_material_items)

    if total_qty == 0:
        return None

    # Доставка распределяется пропорционально объёму этого класса в общем объёме материалов
    # delivery_per_m3 = delivery_total_period / all_materials_qty
    # delivery_for_class = delivery_per_m3 * total_qty
    if all_materials_qty > 0:
        share = total_qty / all_materials_qty
    else:
        share = 0
    delivery_total = delivery_total_period * share
    delivery_vat = delivery_vat_period * share

    avg_price = (material_total + delivery_total) / total_qty

    ref = db.query(ReferencePrice).filter(
        ReferencePrice.project_id == project_id,
        ReferencePrice.material_class_id == material_class_id,
        ReferencePrice.period_start <= period_end,
        ReferencePrice.period_end >= period_start,
    ).first()

    reference_price = ref.price if ref else None
    deviation_pct = None
    deviation_amount = None
    if reference_price and reference_price > 0:
        deviation_pct = round((avg_price - reference_price) / reference_price * 100, 2)
        deviation_amount = round((avg_price - reference_price) * total_qty, 2)

    invoice_count = (
        db.query(func.count(Invoice.id.distinct()))
        .join(Document, Invoice.document_id == Document.id)
        .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
        .filter(
            Document.project_id == project_id,
            Invoice.date >= period_start,
            Invoice.date <= period_end,
            InvoiceItem.material_class_id == material_class_id,
        ).scalar()
    )

    calc = PriceCalculation(
        project_id=project_id,
        material_class_id=material_class_id,
        period_start=period_start,
        period_end=period_end,
        material_total=round(material_total, 2),
        material_vat=round(material_vat, 2),
        delivery_total=round(delivery_total, 2),
        delivery_vat=round(delivery_vat, 2),
        total_qty=round(total_qty, 3),
        avg_price=round(avg_price, 2),
        invoice_count=invoice_count,
        reference_price=reference_price,
        deviation_pct=deviation_pct,
        deviation_amount=deviation_amount,
        calculated_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(calc)
    if commit:
        db.commit()
        db.refresh(calc)
    return calc
