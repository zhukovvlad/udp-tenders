from calendar import monthrange
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, extract, func, literal, or_
from sqlalchemy.orm import Session

from crud.calculations import compute_calculations, compute_full_deviation
from crud.supplier_exclusions import get_excluded_supplier_ids
from crud.units import item_has_issues
from database import get_db
from models import Document, Invoice, InvoiceItem, Project, ProjectSupplierExclusion

router = APIRouter()


@router.get("/summary")
def get_project_summary(project_id: int, db: Session = Depends(get_db)):
    """Сводка по проекту: кол-во документов, СФ, позиций, общие суммы + отклонение за весь период."""
    excluded = get_excluded_supplier_ids(db, project_id)

    def _excl_filter(q):
        """Добавить фильтр исключённых поставщиков к запросу по Invoice."""
        if not excluded:
            return q
        return q.filter(
            or_(Invoice.supplier_id.is_(None), Invoice.supplier_id.notin_(excluded))
        )

    doc_count = db.query(func.count(Document.id)).filter(Document.project_id == project_id).scalar()
    invoice_count = _excl_filter(
        db.query(func.count(Invoice.id))
        .join(Document, Invoice.document_id == Document.id)
        .filter(Document.project_id == project_id)
    ).scalar()
    totals_by_type = _excl_filter(
        db.query(
            InvoiceItem.item_type,
            func.sum(InvoiceItem.amount + func.coalesce(InvoiceItem.vat_amount, InvoiceItem.amount * func.coalesce(Invoice.vat_rate, literal(Decimal("20.0"))) / 100)).label("amount"),
        )
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .join(Document, Invoice.document_id == Document.id)
        .filter(Document.project_id == project_id)
    ).group_by(InvoiceItem.item_type).all()
    by_type = {row.item_type: float(row.amount or 0) for row in totals_by_type}
    total_all = sum(by_type.values())

    total_qty = _excl_filter(
        db.query(func.sum(InvoiceItem.quantity))
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .join(Document, Invoice.document_id == Document.id)
        .filter(Document.project_id == project_id, InvoiceItem.item_type == "material")
    ).scalar() or 0.0

    # Full invoice date range for this project (по всем инвойсам, без фильтра — для отображения периода)
    date_bounds = (
        db.query(func.min(Invoice.date), func.max(Invoice.date))
        .join(Document, Invoice.document_id == Document.id)
        .filter(Document.project_id == project_id)
        .first()
    )
    first_invoice_date, last_invoice_date = date_bounds if date_bounds else (None, None)

    full_deviation = None
    if first_invoice_date and last_invoice_date:
        # Normalize to full calendar months — same as compute_calculations auto-detect.
        # Using raw invoice dates would clamp month boundaries differently and produce
        # a different delivery proration denominator than the calculations API.
        period_start = first_invoice_date.replace(day=1)
        last_day = monthrange(last_invoice_date.year, last_invoice_date.month)[1]
        period_end = last_invoice_date.replace(day=last_day)
        full_deviation = compute_full_deviation(
            db, project_id, period_start, period_end,
            excluded_supplier_ids=excluded or None,
        )

    return {
        "doc_count": doc_count or 0,
        "invoice_count": invoice_count or 0,
        "total_amount": round(total_all, 2),
        "material_amount": round(by_type.get("material", 0), 2),
        "delivery_amount": round(by_type.get("delivery", 0), 2),
        "other_amount": round(by_type.get("other", 0), 2),
        "total_qty": round(float(total_qty), 2),
        "first_invoice_date": first_invoice_date.isoformat() if first_invoice_date else None,
        "last_invoice_date": last_invoice_date.isoformat() if last_invoice_date else None,
        "full_deviation_amount": full_deviation,
    }


@router.get("/invoices")
def list_project_invoices(project_id: int, db: Session = Depends(get_db)):
    """Все СФ по проекту со всеми позициями — для отображения на дашборде."""
    invoices = (
        db.query(Invoice)
        .join(Document, Invoice.document_id == Document.id)
        .filter(Document.project_id == project_id)
        .order_by(Invoice.date.desc())
        .all()
    )
    def _has_issues(inv):
        if not inv.items:
            return True
        return any(item_has_issues(it) for it in inv.items)

    return [
        {
            "id": inv.id,
            "document_id": inv.document_id,
            "number": inv.number,
            "date": inv.date.isoformat(),
            "supplier_name": inv.supplier_name,
            "supplier_inn": inv.supplier_inn,
            "vat_rate": inv.vat_rate,
            "ai_confidence": inv.ai_confidence,
            "has_issues": _has_issues(inv),
            "verified": inv.verified,
            "verified_at": inv.verified_at.isoformat() if inv.verified_at else None,
            "items": [
                {
                    "raw_name": item.raw_name,
                    "item_type": item.item_type,
                    "material_class": item.material_class.name if item.material_class else None,
                    "quantity": item.quantity,
                    "raw_unit": item.raw_unit,
                    "unit": item.raw_unit,  # legacy alias — drop after frontend plan ships
                    "unit_price": item.unit_price,
                    "amount": item.amount,
                    "vat_amount": item.vat_amount,
                }
                for item in inv.items
            ],
        }
        for inv in invoices
    ]


@router.get("/calculations")
def list_calculations(
    project_id: int | None = None,
    material_class_id: int | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    db: Session = Depends(get_db),
):
    """Live-вычисление расчётов помесячно. Если project_id не задан — по всем проектам."""
    if project_id is None:
        projects = db.query(Project).all()
        # Bulk-load all exclusions in a single query to avoid N+1; select only needed columns
        all_exclusions = db.query(
            ProjectSupplierExclusion.project_id,
            ProjectSupplierExclusion.supplier_id,
        ).all()
        exclusions_by_project: dict[int, set[int]] = {}
        for exc_project_id, exc_supplier_id in all_exclusions:
            exclusions_by_project.setdefault(exc_project_id, set()).add(exc_supplier_id)
        rows: list[dict] = []
        for p in projects:
            excl = exclusions_by_project.get(p.id) or None
            rows.extend(
                compute_calculations(
                    db, p.id, period_start, period_end, material_class_id,
                    excluded_supplier_ids=excl,
                )
            )
    else:
        excluded = get_excluded_supplier_ids(db, project_id)
        rows = compute_calculations(
            db, project_id, period_start, period_end, material_class_id,
            excluded_supplier_ids=excluded or None,
        )

    return [
        {
            "project_id": r["project_id"],
            "material_class_id": r["material_class_id"],
            "material_class_name": r["material_class_name"],
            "period_start": r["period_start"].isoformat(),
            "period_end": r["period_end"].isoformat(),
            "material_total": r["material_total"],
            "delivery_total": r["delivery_total"],
            "total_qty": r["total_qty"],
            "avg_price": r["avg_price"],
            "invoice_count": r["invoice_count"],
            "reference_price": r["reference_price"],
            "deviation_pct": r["deviation_pct"],
            "deviation_amount": r["deviation_amount"],
            "corridor_pct": r["corridor_pct"],
            "compensation_per_unit": r["compensation_per_unit"],
            "compensation_amount": r["compensation_amount"],
        }
        for r in rows
    ]


@router.get("/monthly-summary")
def get_monthly_summary(project_id: int, db: Session = Depends(get_db)):
    """Помесячная агрегация по проекту: оборот (материалы), объём, количество СФ."""
    excluded = get_excluded_supplier_ids(db, project_id)

    year_expr = extract("year", Invoice.date)
    month_expr = extract("month", Invoice.date)

    q = (
        db.query(
            year_expr.label("year"),
            month_expr.label("month"),
            func.sum(
                InvoiceItem.amount
                + func.coalesce(InvoiceItem.vat_amount, InvoiceItem.amount * func.coalesce(Invoice.vat_rate, literal(Decimal("20.0"))) / 100)
            ).label("total_amount"),
            func.sum(InvoiceItem.quantity).label("total_qty"),
            func.count(distinct(Invoice.id)).label("invoice_count"),
        )
        .join(Document, Invoice.document_id == Document.id)
        .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
        .filter(Document.project_id == project_id)
    )
    if excluded:
        q = q.filter(
            or_(Invoice.supplier_id.is_(None), Invoice.supplier_id.notin_(excluded))
        )
    rows = q.group_by(year_expr, month_expr).order_by(year_expr, month_expr).all()

    return [
        {
            "year": int(r.year),
            "month": int(r.month),
            "total_amount": round(float(r.total_amount or 0), 2),
            "total_qty": round(float(r.total_qty or 0), 2),
            "invoice_count": int(r.invoice_count),
        }
        for r in rows
    ]
