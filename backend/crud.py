from datetime import UTC, date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from models import (
    Document,
    Invoice,
    InvoiceItem,
    MaterialClass,
    PriceCalculation,
    Project,
    ReferencePrice,
    Supplier,
)

# Sentinel: field was not provided in the update payload (differs from explicit None)
_UNSET = object()

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

def get_reference_prices(db: Session, project_id: int = None, material_class_id: int = None):
    q = db.query(ReferencePrice).options(
        joinedload(ReferencePrice.project),
        joinedload(ReferencePrice.material_class),
    )
    if project_id:
        q = q.filter(ReferencePrice.project_id == project_id)
    if material_class_id:
        q = q.filter(ReferencePrice.material_class_id == material_class_id)
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


def update_reference_price(db: Session, rp_id: int, price=_UNSET,
                           period_start=_UNSET, period_end=_UNSET,
                           source=_UNSET) -> ReferencePrice | None:
    rp = db.query(ReferencePrice).filter(ReferencePrice.id == rp_id).first()
    if not rp:
        return None
    if price is not _UNSET:
        rp.price = price
    if period_start is not _UNSET:
        rp.period_start = period_start
    if period_end is not _UNSET:
        rp.period_end = period_end
    if source is not _UNSET:
        rp.source = source if (isinstance(source, str) and source.strip()) else None
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
    # Нормализуем: пустые строки и whitespace → None
    _inn = (supplier_inn.strip() or None) if supplier_inn else None
    _name = (supplier_name.strip() or None) if supplier_name else None

    # Если поставщик уже есть в БД (напр., по Тому же ИНН) — берём каноническое имя из БД,
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


# --- Price Calculations ---

def compute_full_deviation(
    db: Session, project_id: int, period_start: date, period_end: date
) -> float | None:
    """Compute total deviation_amount for a project over [period_start, period_end]
    without writing anything to the database.
    Returns None if no reference prices are available for any class."""

    # Single grouped query: mat_total + qty per class
    class_rows = (
        db.query(
            InvoiceItem.material_class_id,
            func.sum(InvoiceItem.amount).label("mat_total"),
            func.sum(InvoiceItem.quantity).label("qty"),
        )
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .join(Document, Invoice.document_id == Document.id)
        .filter(
            Document.project_id == project_id,
            Invoice.date >= period_start,
            Invoice.date <= period_end,
            InvoiceItem.item_type == "material",
            InvoiceItem.material_class_id.isnot(None),
        )
        .group_by(InvoiceItem.material_class_id)
        .all()
    )
    if not class_rows:
        return None

    class_ids = [r.material_class_id for r in class_rows]

    # Use ALL material qty (including unclassified) as denominator for delivery allocation,
    # matching the logic in recalculate_prices.
    all_material_qty: float = (
        db.query(func.sum(InvoiceItem.quantity))
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .join(Document, Invoice.document_id == Document.id)
        .filter(
            Document.project_id == project_id,
            Invoice.date >= period_start,
            Invoice.date <= period_end,
            InvoiceItem.item_type == "material",
        )
        .scalar() or 0.0
    )
    delivery_total_period: float = (
        db.query(func.sum(InvoiceItem.amount))
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .join(Document, Invoice.document_id == Document.id)
        .filter(
            Document.project_id == project_id,
            Invoice.date >= period_start,
            Invoice.date <= period_end,
            InvoiceItem.item_type == "delivery",
        )
        .scalar() or 0.0
    )

    # Fetch all relevant reference prices in one query, keep latest by period_start/period_end/id
    ref_rows = (
        db.query(ReferencePrice)
        .filter(
            ReferencePrice.project_id == project_id,
            ReferencePrice.material_class_id.in_(class_ids),
            ReferencePrice.period_start <= period_end,
            ReferencePrice.period_end >= period_start,
        )
        .order_by(
            ReferencePrice.material_class_id,
            ReferencePrice.period_start.desc(),
            ReferencePrice.period_end.desc(),
            ReferencePrice.id.desc(),
        )
        .all()
    )
    # Keep only the first (most recent) ref price per class
    ref_by_class: dict[int, ReferencePrice] = {}
    for ref in ref_rows:
        if ref.material_class_id not in ref_by_class:
            ref_by_class[ref.material_class_id] = ref

    total_deviation: float = 0.0
    any_ref = False

    for r in class_rows:
        if not r.qty:
            continue
        share = r.qty / all_material_qty if all_material_qty > 0 else 0.0
        delivery_for_class = delivery_total_period * share
        avg_price = (r.mat_total + delivery_for_class) / r.qty

        ref = ref_by_class.get(r.material_class_id)
        if ref and ref.price and ref.price > 0:
            any_ref = True
            total_deviation += (avg_price - ref.price) * r.qty  # accumulate unrounded

    return round(total_deviation, 2) if any_ref else None


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

    ref = (
        db.query(ReferencePrice)
        .filter(
            ReferencePrice.project_id == project_id,
            ReferencePrice.material_class_id == material_class_id,
            ReferencePrice.period_start <= period_end,
            ReferencePrice.period_end >= period_start,
        )
        .order_by(
            ReferencePrice.period_start.desc(),
            ReferencePrice.period_end.desc(),
            ReferencePrice.id.desc(),
        )
        .first()
    )

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


# --- Suppliers ---

def get_suppliers(db: Session) -> list[tuple]:
    """Возвращает список (Supplier, invoice_count)."""
    results = (
        db.query(Supplier, func.count(Invoice.id).label("invoice_count"))
        .outerjoin(Invoice, Invoice.supplier_id == Supplier.id)
        .group_by(Supplier.id)
        .order_by(Supplier.name)
        .all()
    )
    return results


def get_supplier(db: Session, supplier_id: int) -> Supplier | None:
    return db.query(Supplier).filter(Supplier.id == supplier_id).first()


def create_supplier(db: Session, name: str, inn: str | None) -> Supplier:
    """Создать поставщика напрямую. Не дедуплицирует — если ИНН уже занят, бросает IntegrityError."""
    supplier = Supplier(name=name, inn=inn or None)
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


def update_supplier(db: Session, supplier_id: int, name: str, inn: str | None) -> Supplier | None:
    """Обновить каноническое имя/ИНН поставщика и синхронизировать все связанные инвойсы."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        return None
    supplier.name = name
    supplier.inn = inn or None
    # Синхронизируем отображаемые поля в инвойсах
    db.query(Invoice).filter(Invoice.supplier_id == supplier_id).update(
        {Invoice.supplier_name: name, Invoice.supplier_inn: supplier.inn},
        synchronize_session=False,
    )
    db.commit()
    db.refresh(supplier)
    return supplier


def delete_supplier(db: Session, supplier_id: int) -> Supplier | None:
    """Удалить поставщика. Возвращает None если не найден. Вызывать нельзя если
    есть связанные инвойсы — роутер должен проверить это ДО вызова."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        return None
    db.delete(supplier)
    db.commit()
    return supplier


def get_supplier_invoices(db: Session, supplier_id: int) -> list[Invoice]:
    return (
        db.query(Invoice)
        .filter(Invoice.supplier_id == supplier_id)
        .order_by(Invoice.date.desc())
        .all()
    )


def get_or_create_supplier(db: Session, name: str, inn: str | None) -> Supplier:
    """Найти или создать поставщика. По ИНН если задан, иначе по имени (без ИНН).

    Не делает commit — использует flush чтобы оставаться в транзакции вызывающего.
    """
    if inn:
        supplier = db.query(Supplier).filter(Supplier.inn == inn).first()
        if not supplier:
            supplier = Supplier(name=name, inn=inn)
            db.add(supplier)
            db.flush()
    else:
        supplier = db.query(Supplier).filter(Supplier.inn.is_(None), Supplier.name == name).first()
        if not supplier:
            supplier = Supplier(name=name, inn=None)
            db.add(supplier)
            db.flush()
    return supplier


def merge_suppliers(db: Session, source_id: int, target_id: int) -> Supplier | None:
    """Перенести все инвойсы от source к target и удалить source."""
    source = db.query(Supplier).filter(Supplier.id == source_id).first()
    target = db.query(Supplier).filter(Supplier.id == target_id).first()
    if not source or not target:
        return None
    db.query(Invoice).filter(Invoice.supplier_id == source_id).update(
        {
            Invoice.supplier_id: target_id,
            Invoice.supplier_name: target.name,
            Invoice.supplier_inn: target.inn,
        },
        synchronize_session=False,
    )
    db.delete(source)
    db.commit()
    db.refresh(target)
    return target


def _find_duplicate_pairs(
    suppliers: list, threshold: float = 85.0
) -> list[tuple]:
    """Чистая функция: сравнивает имена поставщиков по fuzzy ratio и возвращает
    список кортежей (supplier_a, supplier_b, score) для пар с score >= threshold.

    Принимает любые объекты с атрибутами .id и .name — удобно для тестирования
    без базы данных.
    """
    from rapidfuzz import fuzz

    pairs = []
    for i in range(len(suppliers)):
        for j in range(i + 1, len(suppliers)):
            a = suppliers[i]
            b = suppliers[j]
            score = fuzz.WRatio(a.name, b.name)
            if score >= threshold:
                pairs.append((a, b, float(score)))
    return pairs


def get_supplier_duplicates(db: Session, threshold: float = 85.0) -> list[tuple]:
    """Вернуть пары поставщиков без ИНН с похожими названиями (fuzzy match)."""
    suppliers_no_inn = (
        db.query(Supplier).filter(Supplier.inn.is_(None)).order_by(Supplier.name).all()
    )
    return _find_duplicate_pairs(suppliers_no_inn, threshold)
