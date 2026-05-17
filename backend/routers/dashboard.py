from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, extract, func
from sqlalchemy.orm import Session

import crud
from database import get_db
from models import Document, Invoice, InvoiceItem, Project

router = APIRouter()


@router.get("/summary")
def get_project_summary(project_id: int, db: Session = Depends(get_db)):
    """Сводка по проекту: кол-во документов, СФ, позиций, общие суммы + отклонение за весь период."""
    doc_count = db.query(func.count(Document.id)).filter(Document.project_id == project_id).scalar()
    invoice_count = (
        db.query(func.count(Invoice.id))
        .join(Document, Invoice.document_id == Document.id)
        .filter(Document.project_id == project_id)
        .scalar()
    )
    totals = (
        db.query(
            func.sum(InvoiceItem.amount).label("total_amount"),
            func.sum(InvoiceItem.quantity).label("total_qty"),
        )
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .join(Document, Invoice.document_id == Document.id)
        .filter(Document.project_id == project_id, InvoiceItem.item_type == "material")
        .first()
    )

    # Full invoice date range for this project
    date_bounds = (
        db.query(func.min(Invoice.date), func.max(Invoice.date))
        .join(Document, Invoice.document_id == Document.id)
        .filter(Document.project_id == project_id)
        .first()
    )
    first_invoice_date, last_invoice_date = date_bounds if date_bounds else (None, None)

    full_deviation = None
    if first_invoice_date and last_invoice_date:
        full_deviation = crud.compute_full_deviation(
            db, project_id, first_invoice_date, last_invoice_date
        )

    return {
        "doc_count": doc_count or 0,
        "invoice_count": invoice_count or 0,
        "total_amount": round(totals.total_amount or 0, 2),
        "total_qty": round(totals.total_qty or 0, 2),
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
        for it in inv.items:
            if (it.quantity or 0) <= 0:
                return True
            if not (it.raw_name or "").strip():
                return True
        return False

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
                    "unit": item.unit,
                    "unit_price": item.unit_price,
                    "amount": item.amount,
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
        rows: list[dict] = []
        for p in projects:
            rows.extend(crud.compute_calculations(db, p.id))
    else:
        rows = crud.compute_calculations(db, project_id, period_start, period_end, material_class_id)

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
        }
        for r in rows
    ]


@router.get("/monthly-summary")
def get_monthly_summary(project_id: int, db: Session = Depends(get_db)):
    """Помесячная агрегация по проекту: оборот (материалы), объём, количество СФ."""
    year_expr = extract("year", Invoice.date)
    month_expr = extract("month", Invoice.date)

    rows = (
        db.query(
            year_expr.label("year"),
            month_expr.label("month"),
            func.sum(InvoiceItem.amount).label("total_amount"),
            func.sum(InvoiceItem.quantity).label("total_qty"),
            func.count(distinct(Invoice.id)).label("invoice_count"),
        )
        .join(Document, Invoice.document_id == Document.id)
        .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
        .filter(
            Document.project_id == project_id,
            InvoiceItem.item_type == "material",
        )
        .group_by(year_expr, month_expr)
        .order_by(year_expr, month_expr)
        .all()
    )

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
