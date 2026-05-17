from calendar import monthrange
from datetime import UTC, date, datetime

from sqlalchemy import case, func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, aliased, joinedload

from models import (
    Document,
    Invoice,
    InvoiceItem,
    MaterialClass,
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


# --- Price Calculations ---

def _months_in_range(start: date, end: date) -> list[tuple[date, date]]:
    """Split [start, end] into calendar month intervals clamped to the requested bounds."""
    months = []
    cur = date(start.year, start.month, 1)
    while cur <= end:
        last_day = monthrange(cur.year, cur.month)[1]
        month_end = date(cur.year, cur.month, last_day)
        months.append((max(cur, start), min(month_end, end)))
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return months


def compute_calculations(
    db: Session,
    project_id: int,
    period_start: date | None = None,
    period_end: date | None = None,
    material_class_id: int | None = None,
) -> list[dict]:
    """Live-вычисление расчётов по проекту помесячно без записи в БД.

    Если period_start/period_end не заданы — определяет диапазон по MIN/MAX дат инвойсов.
    Возвращает [] если нет инвойсов или нет материальных позиций с классом.
    Строки с total_qty == 0 пропускаются.
    """
    if period_start is None or period_end is None:
        bounds = (
            db.query(func.min(Invoice.date), func.max(Invoice.date))
            .join(Document, Invoice.document_id == Document.id)
            .filter(Document.project_id == project_id)
            .first()
        )
        if not bounds or not bounds[0]:
            return []
        min_date, max_date = bounds
        if period_start is None:
            period_start = min_date.replace(day=1)
        if period_end is None:
            period_end = max_date.replace(day=monthrange(max_date.year, max_date.month)[1])

    months = _months_in_range(period_start, period_end)
    if not months:
        return []

    # Preload material class names once
    class_name_map: dict[int, str] = {
        mc.id: mc.name for mc in db.query(MaterialClass).all()
    }

    results: list[dict] = []

    for month_start, month_end in months:
        # Material items grouped by class for this month
        class_q = (
            db.query(
                InvoiceItem.material_class_id,
                func.sum(InvoiceItem.amount).label("mat_total"),
                func.coalesce(func.sum(InvoiceItem.vat_amount), 0).label("mat_vat"),
                func.sum(InvoiceItem.quantity).label("qty"),
                func.count(Invoice.id.distinct()).label("invoice_count"),
            )
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .join(Document, Invoice.document_id == Document.id)
            .filter(
                Document.project_id == project_id,
                Invoice.date >= month_start,
                Invoice.date <= month_end,
                InvoiceItem.item_type == "material",
                InvoiceItem.material_class_id.isnot(None),
            )
        )
        if material_class_id is not None:
            class_q = class_q.filter(InvoiceItem.material_class_id == material_class_id)
        class_rows = class_q.group_by(InvoiceItem.material_class_id).all()

        if not class_rows:
            continue

        class_ids = [r.material_class_id for r in class_rows]

        # All material qty (denominator for delivery proration)
        all_material_qty: float = (
            db.query(func.sum(InvoiceItem.quantity))
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .join(Document, Invoice.document_id == Document.id)
            .filter(
                Document.project_id == project_id,
                Invoice.date >= month_start,
                Invoice.date <= month_end,
                InvoiceItem.item_type == "material",
            )
            .scalar() or 0.0
        )

        # Total delivery amount and VAT for this month
        delivery_agg = (
            db.query(
                func.coalesce(func.sum(InvoiceItem.amount), 0).label("total"),
                func.coalesce(func.sum(InvoiceItem.vat_amount), 0).label("vat"),
            )
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .join(Document, Invoice.document_id == Document.id)
            .filter(
                Document.project_id == project_id,
                Invoice.date >= month_start,
                Invoice.date <= month_end,
                InvoiceItem.item_type == "delivery",
            )
            .first()
        )
        delivery_total_period: float = float(delivery_agg.total) if delivery_agg else 0.0
        delivery_vat_period: float = float(delivery_agg.vat) if delivery_agg else 0.0

        # Reference prices overlapping this month, latest per class
        ref_rows = (
            db.query(ReferencePrice)
            .filter(
                ReferencePrice.project_id == project_id,
                ReferencePrice.material_class_id.in_(class_ids),
                ReferencePrice.period_start <= month_end,
                ReferencePrice.period_end >= month_start,
            )
            .order_by(
                ReferencePrice.material_class_id,
                ReferencePrice.period_start.desc(),
                ReferencePrice.period_end.desc(),
                ReferencePrice.id.desc(),
            )
            .all()
        )
        ref_by_class: dict[int, ReferencePrice] = {}
        for ref in ref_rows:
            if ref.material_class_id not in ref_by_class:
                ref_by_class[ref.material_class_id] = ref

        for r in class_rows:
            if not r.qty:
                continue
            share = r.qty / all_material_qty if all_material_qty > 0 else 0.0
            delivery_for_class = delivery_total_period * share
            delivery_vat_for_class = delivery_vat_period * share
            avg_price = (float(r.mat_total) + delivery_for_class) / float(r.qty)

            ref = ref_by_class.get(r.material_class_id)
            ref_price = ref.price if ref else None
            deviation_pct = None
            deviation_amount = None
            if ref_price and ref_price > 0:
                deviation_pct = round((avg_price - ref_price) / ref_price * 100, 2)
                deviation_amount = round((avg_price - ref_price) * float(r.qty), 2)

            results.append({
                "project_id": project_id,
                "material_class_id": r.material_class_id,
                "material_class_name": class_name_map.get(r.material_class_id, "?"),
                "period_start": month_start,
                "period_end": month_end,
                "material_total": round(float(r.mat_total), 2),
                "material_vat": round(float(r.mat_vat), 2),
                "delivery_total": round(delivery_for_class, 2),
                "delivery_vat": round(delivery_vat_for_class, 2),
                "total_qty": round(float(r.qty), 3),
                "avg_price": round(avg_price, 2),
                "invoice_count": r.invoice_count,
                "reference_price": ref_price,
                "deviation_pct": deviation_pct,
                "deviation_amount": deviation_amount,
            })

    return results


def compute_full_deviation(
    db: Session, project_id: int, period_start: date, period_end: date
) -> float | None:
    """Compute total deviation_amount for a project over [period_start, period_end].
    Delegates to compute_calculations() — единый источник истины.
    Returns None if no reference prices are available for any class (not 0.0)."""
    rows = compute_calculations(db, project_id, period_start, period_end)
    amounts = [r["deviation_amount"] for r in rows if r["deviation_amount"] is not None]
    return round(sum(amounts), 2) if amounts else None


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
    Защищён от race condition на уникальный ИНН через INSERT ... ON CONFLICT DO NOTHING.
    """
    if inn:
        supplier = db.query(Supplier).filter(Supplier.inn == inn).first()
        if not supplier:
            stmt = (
                pg_insert(Supplier)
                .values(name=name, inn=inn, created_at=datetime.now(UTC).replace(tzinfo=None))
                .on_conflict_do_nothing(index_elements=["inn"])
                .returning(Supplier.id)
            )
            result = db.execute(stmt)
            row = result.fetchone()
            if row:
                db.flush()
            # Повторный SELECT — либо только что вставленная, либо вставленная конкурентом
            supplier = db.query(Supplier).filter(Supplier.inn == inn).first()
            if supplier is None:
                raise RuntimeError(f"get_or_create_supplier: не удалось получить поставщика по ИНН={inn!r}")
    else:
        supplier = db.query(Supplier).filter(Supplier.inn.is_(None), Supplier.name == name).first()
        if not supplier:
            stmt = (
                pg_insert(Supplier)
                .values(name=name, inn=None, created_at=datetime.now(UTC).replace(tzinfo=None))
                .on_conflict_do_nothing(index_elements=["name"], index_where=text("inn IS NULL"))
                .returning(Supplier.id)
            )
            result = db.execute(stmt)
            row = result.fetchone()
            if row:
                db.flush()
            # Повторный SELECT — либо только что вставленная, либо вставленная конкурентом
            supplier = db.query(Supplier).filter(Supplier.inn.is_(None), Supplier.name == name).first()
            if supplier is None:
                raise RuntimeError(f"get_or_create_supplier: не удалось получить поставщика по имени={name!r}")
    return supplier


def merge_suppliers(db: Session, source_id: int, target_id: int) -> Supplier | None:
    """Перенести все инвойсы от source к target и удалить source."""
    if source_id == target_id:
        return db.query(Supplier).filter(Supplier.id == target_id).first()
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


def get_supplier_duplicates(db: Session, threshold: float = 85.0) -> list[tuple]:
    """Вернуть пары поставщиков без ИНН с похожими названиями.

    Использует pg_trgm similarity() на стороне БД. Для отбора кандидатов
    применяется индексируемый оператор `%` (использует GIN-индекс), а
    similarity() остаётся для точного score и сортировки.
    threshold задаётся в диапазоне 0–100 как pg_trgm similarity * 100.
    Внутри SQL similarity() работает в диапазоне 0.0–1.0.
    Возвращаемый score также равен pg_trgm similarity * 100.
    """
    similarity_threshold = threshold / 100.0
    # SET LOCAL влияет только на оператор % внутри текущей транзакции.
    # Параметры не поддерживаются в SET — значение вставляется напрямую.
    # Безопасно: threshold валидируется роутером на диапазон (0, 100].
    db.execute(text(f"SET LOCAL pg_trgm.similarity_threshold = {similarity_threshold!r}"))
    S1 = aliased(Supplier)
    S2 = aliased(Supplier)
    score = func.similarity(S1.name, S2.name).label("score")
    rows = (
        db.query(S1, S2, score)
        .select_from(S1)
        .join(
            S2,
            (S1.id < S2.id)
            & S1.inn.is_(None)
            & S2.inn.is_(None)
            & S1.name.op("%")(S2.name),
        )
        .filter(score >= similarity_threshold)
        .order_by(score.desc())
        .limit(500)
        .all()
    )
    return [(s1, s2, round(float(score) * 100, 1)) for s1, s2, score in rows]


def get_suppliers_with_stats(db: Session) -> list[dict]:
    """Список поставщиков с агрегатами: оборот, число объектов, счетов, дата первого счёта.

    Оборот считается как сумма всех позиций счетов поставщика (материалы + доставка).
    Категории выводятся из классов материалов, которые поставлял данный поставщик.
    """
    turnover_label = func.coalesce(func.sum(InvoiceItem.amount), 0).label("turnover")
    rows = (
        db.query(
            Supplier,
            func.count(Invoice.id.distinct()).label("invoice_count"),
            turnover_label,
            func.count(Document.project_id.distinct()).label("project_count"),
            func.min(Invoice.date).label("first_invoice_date"),
        )
        .outerjoin(Invoice, Invoice.supplier_id == Supplier.id)
        .outerjoin(Document, Invoice.document_id == Document.id)
        .outerjoin(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
        .group_by(Supplier.id)
        .order_by(turnover_label.desc())
        .all()
    )

    # Категории (классы материалов) по каждому поставщику — одним запросом
    cat_rows = (
        db.query(Invoice.supplier_id, MaterialClass.name)
        .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
        .join(MaterialClass, InvoiceItem.material_class_id == MaterialClass.id)
        .filter(Invoice.supplier_id.isnot(None))
        .distinct()
        .all()
    )
    cats_by_supplier: dict[int, list[str]] = {}
    for sid, class_name in cat_rows:
        lst = cats_by_supplier.setdefault(sid, [])
        if class_name not in lst:
            lst.append(class_name)

    return [
        {
            "id": s.id,
            "name": s.name,
            "inn": s.inn,
            "created_at": s.created_at,
            "invoice_count": invoice_count,
            "turnover": float(turnover),
            "project_count": project_count,
            "first_invoice_date": first_invoice_date,
            "categories": cats_by_supplier.get(s.id, []),
        }
        for s, invoice_count, turnover, project_count, first_invoice_date in rows
    ]


def get_supplier_detail(db: Session, supplier_id: int) -> dict | None:
    """Детальная шапка поставщика: агрегаты по всем объектам."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        return None

    agg = (
        db.query(
            func.count(Invoice.id.distinct()).label("invoice_count"),
            func.coalesce(func.sum(InvoiceItem.amount), 0).label("turnover"),
            func.count(Document.project_id.distinct()).label("project_count"),
            func.min(Invoice.date).label("first_invoice_date"),
        )
        .select_from(Invoice)
        .outerjoin(Document, Invoice.document_id == Document.id)
        .outerjoin(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
        .filter(Invoice.supplier_id == supplier_id)
        .first()
    )

    cat_rows = (
        db.query(MaterialClass.name)
        .join(InvoiceItem, InvoiceItem.material_class_id == MaterialClass.id)
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .filter(Invoice.supplier_id == supplier_id)
        .distinct()
        .all()
    )
    categories = [r.name for r in cat_rows]

    return {
        "id": supplier.id,
        "name": supplier.name,
        "inn": supplier.inn,
        "created_at": supplier.created_at,
        "invoice_count": agg.invoice_count if agg else 0,
        "turnover": float(agg.turnover) if agg else 0.0,
        "project_count": agg.project_count if agg else 0,
        "first_invoice_date": agg.first_invoice_date if agg else None,
        "categories": categories,
    }


def _compute_supplier_project_deviation(
    db: Session, supplier_id: int, project_id: int
) -> tuple[float | None, float | None]:
    """Вычислить отклонение от плана для пары поставщик×объект.

    Методология идентична compute_full_deviation, но привязана только к счетам
    данного поставщика. Доставка распределяется пропорционально объёму материалов.

    Отличие от compute_full_deviation: плановая цена выбирается без учёта периода —
    берётся самая свежая актуальная запись по каждому классу (order by period_start desc).
    Это намеренное решение: карточка поставщика показывает обобщённую аналитику
    за весь срок работы, а не за конкретный период. Если требуется сравнение
    с проектной страницей за тот же период — использовать compute_full_deviation напрямую.
    """
    # Подзапрос: ID счетов данного поставщика для данного объекта
    invoice_ids_q = (
        db.query(Invoice.id)
        .join(Document, Invoice.document_id == Document.id)
        .filter(Invoice.supplier_id == supplier_id, Document.project_id == project_id)
        .subquery()
    )

    # Материальные позиции, сгруппированные по классу
    class_rows = (
        db.query(
            InvoiceItem.material_class_id,
            func.sum(InvoiceItem.amount).label("mat_total"),
            func.sum(InvoiceItem.quantity).label("qty"),
        )
        .filter(
            InvoiceItem.invoice_id.in_(invoice_ids_q),
            InvoiceItem.item_type == "material",
            InvoiceItem.material_class_id.isnot(None),
        )
        .group_by(InvoiceItem.material_class_id)
        .all()
    )
    if not class_rows:
        return None, None

    class_ids = [r.material_class_id for r in class_rows]

    all_material_qty: float = (
        db.query(func.sum(InvoiceItem.quantity))
        .filter(
            InvoiceItem.invoice_id.in_(invoice_ids_q),
            InvoiceItem.item_type == "material",
        )
        .scalar() or 0.0
    )
    delivery_total: float = (
        db.query(func.sum(InvoiceItem.amount))
        .filter(
            InvoiceItem.invoice_id.in_(invoice_ids_q),
            InvoiceItem.item_type == "delivery",
        )
        .scalar() or 0.0
    )

    # Последние плановые цены по объекту×класс (без ограничения периода — берём актуальные)
    ref_rows = (
        db.query(ReferencePrice)
        .filter(
            ReferencePrice.project_id == project_id,
            ReferencePrice.material_class_id.in_(class_ids),
        )
        .order_by(
            ReferencePrice.material_class_id,
            ReferencePrice.period_start.desc(),
            ReferencePrice.period_end.desc(),
            ReferencePrice.id.desc(),
        )
        .all()
    )
    ref_by_class: dict[int, ReferencePrice] = {}
    for ref in ref_rows:
        if ref.material_class_id not in ref_by_class:
            ref_by_class[ref.material_class_id] = ref

    total_deviation: float = 0.0
    reference_total: float = 0.0
    any_ref = False

    for r in class_rows:
        if not r.qty:
            continue
        share = r.qty / all_material_qty if all_material_qty > 0 else 0.0
        delivery_for_class = delivery_total * share
        avg_price = (r.mat_total + delivery_for_class) / r.qty

        ref = ref_by_class.get(r.material_class_id)
        if ref and ref.price and ref.price > 0:
            any_ref = True
            total_deviation += (avg_price - ref.price) * r.qty
            reference_total += ref.price * r.qty

    if not any_ref or reference_total == 0.0:
        return None, None

    deviation_amount = round(total_deviation, 2)
    deviation_pct = round(total_deviation / reference_total * 100, 2)
    return deviation_pct, deviation_amount


def get_supplier_project_stats(db: Session, supplier_id: int) -> list[dict]:
    """Статистика по каждому объекту для поставщика: оборот, объём м³, число счетов, наценка."""
    # Базовый агрегат: оборот + объём м³ + число счетов, группировка по объекту
    volume_expr = func.coalesce(
        func.sum(case((InvoiceItem.item_type == "material", InvoiceItem.quantity))),
        0,
    ).label("volume_m3")
    turnover_expr = func.coalesce(func.sum(InvoiceItem.amount), 0).label("turnover")

    rows = (
        db.query(
            Document.project_id,
            Project.name.label("project_name"),
            Project.contract_number,
            func.count(Invoice.id.distinct()).label("invoice_count"),
            turnover_expr,
            volume_expr,
        )
        .select_from(Invoice)
        .join(Document, Invoice.document_id == Document.id)
        .join(Project, Project.id == Document.project_id)
        .outerjoin(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
        .filter(Invoice.supplier_id == supplier_id)
        .group_by(Document.project_id, Project.name, Project.contract_number)
        .order_by(turnover_expr.desc())
        .all()
    )

    result = []
    for project_id, project_name, contract_number, invoice_count, turnover, volume_m3 in rows:
        deviation_pct, deviation_amount = _compute_supplier_project_deviation(
            db, supplier_id, project_id
        )
        result.append({
            "project_id": project_id,
            "project_name": project_name,
            "contract_number": contract_number,
            "invoice_count": invoice_count,
            "turnover": float(turnover),
            "volume_m3": float(volume_m3),
            "deviation_pct": deviation_pct,
            "deviation_amount": deviation_amount,
        })
    return result


def get_supplier_invoices_list(db: Session, supplier_id: int,
                               project_id: int | None = None) -> list[dict]:
    """Список счетов поставщика по всем объектам (для таба «Счета»)."""
    q = (
        db.query(
            Invoice.id,
            Invoice.document_id,
            Invoice.number,
            Invoice.date,
            Invoice.verified,
            Invoice.verified_at,
            Invoice.ai_confidence,
            Document.project_id,
            Project.name.label("project_name"),
            func.coalesce(func.sum(InvoiceItem.amount), 0).label("amount"),
        )
        .join(Document, Invoice.document_id == Document.id)
        .join(Project, Project.id == Document.project_id)
        .outerjoin(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
        .filter(Invoice.supplier_id == supplier_id)
    )
    if project_id is not None:
        q = q.filter(Document.project_id == project_id)
    q = q.group_by(
        Invoice.id, Invoice.document_id, Invoice.number, Invoice.date, Invoice.verified,
        Invoice.verified_at, Invoice.ai_confidence, Document.project_id, Project.name,
    ).order_by(Invoice.date.desc())

    return [
        {
            "id": row.id,
            "document_id": row.document_id,
            "number": row.number,
            "date": str(row.date),
            "verified": row.verified,
            "verified_at": row.verified_at.isoformat() if row.verified_at else None,
            "ai_confidence": row.ai_confidence,
            "project_id": row.project_id,
            "project_name": row.project_name,
            "amount": float(row.amount),
        }
        for row in q.all()
    ]

