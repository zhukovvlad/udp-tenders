from calendar import monthrange
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

import crud
from database import get_db
from models import Document, Invoice, InvoiceItem, MaterialClass, PriceCalculation

router = APIRouter()


@router.get("/summary")
def get_project_summary(project_id: int, db: Session = Depends(get_db)):
    """Сводка по проекту: кол-во документов, СФ, позиций, общие суммы."""
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
    return {
        "doc_count": doc_count or 0,
        "invoice_count": invoice_count or 0,
        "total_amount": round(totals.total_amount or 0, 2),
        "total_qty": round(totals.total_qty or 0, 2),
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
            "vat_rate": inv.vat_rate,
            "ai_confidence": inv.ai_confidence,
            "has_issues": _has_issues(inv),
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
def list_calculations(project_id: int | None = None, material_class_id: int | None = None,
                      db: Session = Depends(get_db)):
    q = db.query(PriceCalculation).order_by(PriceCalculation.period_start.desc())
    if project_id:
        q = q.filter(PriceCalculation.project_id == project_id)
    if material_class_id:
        q = q.filter(PriceCalculation.material_class_id == material_class_id)
    calcs = q.all()
    return [
        {
            "id": c.id,
            "project_id": c.project_id,
            "material_class_id": c.material_class_id,
            "material_class_name": c.material_class.name if c.material_class else None,
            "period_start": c.period_start.isoformat(),
            "period_end": c.period_end.isoformat(),
            "material_total": c.material_total,
            "delivery_total": c.delivery_total,
            "total_qty": c.total_qty,
            "avg_price": c.avg_price,
            "invoice_count": c.invoice_count,
            "reference_price": c.reference_price,
            "deviation_pct": c.deviation_pct,
            "deviation_amount": c.deviation_amount,
        }
        for c in calcs
    ]


@router.post("/auto-calculate")
def auto_calculate(project_id: int, db: Session = Depends(get_db)):
    """Автоматический пересчёт по всем классам помесячно за весь диапазон СФ проекта."""
    bounds = (
        db.query(func.min(Invoice.date), func.max(Invoice.date))
        .join(Document, Invoice.document_id == Document.id)
        .filter(Document.project_id == project_id)
        .first()
    )
    period_start, period_end = bounds if bounds else (None, None)

    # Удаляем все старые расчёты для проекта
    db.query(PriceCalculation).filter(PriceCalculation.project_id == project_id).delete(synchronize_session=False)
    db.commit()

    if not period_start or not period_end:
        return {"message": "Нет СФ в проекте", "period_start": None, "period_end": None, "results": []}

    # Build list of (month_start, month_end) for each calendar month in range
    def months_in_range(start: date, end: date):
        months = []
        cur = date(start.year, start.month, 1)
        while cur <= end:
            last = monthrange(cur.year, cur.month)[1]
            month_end = min(date(cur.year, cur.month, last), end)
            months.append((cur, month_end))
            # Advance to first day of next month
            cur = date(cur.year + (cur.month // 12), (cur.month % 12) + 1, 1)
        return months

    class_ids = [
        row[0] for row in (
            db.query(InvoiceItem.material_class_id)
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .join(Document, Invoice.document_id == Document.id)
            .filter(
                Document.project_id == project_id,
                InvoiceItem.item_type == "material",
                InvoiceItem.material_class_id.isnot(None),
            )
            .distinct()
            .all()
        )
    ]

    results = []
    for month_start, month_end in months_in_range(period_start, period_end):
        for cid in class_ids:
            res = crud.recalculate_prices(db, project_id, cid, month_start, month_end, commit=False, skip_delete=True)
            if res and res.invoice_count > 0:
                results.append({
                    "material_class_id": cid,
                    "period_start": month_start.isoformat(),
                    "avg_price": res.avg_price,
                })
    db.commit()

    return {
        "message": f"Рассчитано: {len(results)} записей",
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "results": results,
    }


@router.post("/calculate")
def run_calculation(project_id: int, period_start: date, period_end: date,
                    material_class_id: int | None = None,
                    db: Session = Depends(get_db)):
    """Пересчитать цены. Удаляет ВСЕ предыдущие расчёты для проекта (или класса)
    и создаёт новые за указанный период."""
    # Удаляем все предыдущие расчёты для этого проекта (для всех или одного класса)
    delete_q = db.query(PriceCalculation).filter(PriceCalculation.project_id == project_id)
    if material_class_id:
        delete_q = delete_q.filter(PriceCalculation.material_class_id == material_class_id)
    delete_q.delete(synchronize_session=False)
    db.commit()

    if material_class_id:
        class_ids = [material_class_id]
    else:
        class_ids = [
            row[0] for row in (
                db.query(InvoiceItem.material_class_id)
                .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
                .join(Document, Invoice.document_id == Document.id)
                .filter(
                    Document.project_id == project_id,
                    Invoice.date >= period_start,
                    Invoice.date <= period_end,
                    InvoiceItem.item_type == "material",
                    InvoiceItem.material_class_id.isnot(None),
                )
                .distinct()
                .all()
            )
        ]

    results = []
    for cid in class_ids:
        res = crud.recalculate_prices(db, project_id, cid, period_start, period_end)
        if res:
            results.append({
                "material_class_id": cid,
                "avg_price": res.avg_price,
                "reference_price": res.reference_price,
                "deviation_pct": res.deviation_pct,
                "deviation_amount": res.deviation_amount,
                "total_qty": res.total_qty,
                "invoice_count": res.invoice_count,
            })

    if not results:
        return {"message": "Нет данных за указанный период", "results": []}
    return {"message": f"Рассчитано классов: {len(results)}", "results": results}
