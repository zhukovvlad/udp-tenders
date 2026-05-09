from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from openpyxl import Workbook
from io import BytesIO
from datetime import date

from database import get_db
from models import PriceCalculation, Project, MaterialClass, Invoice, Document, InvoiceItem

router = APIRouter()


@router.get("/excel")
def export_excel(project_id: int, period_start: date, period_end: date,
                 material_class_id: int | None = None, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {"error": "Проект не найден"}

    q = db.query(PriceCalculation).filter(
        PriceCalculation.project_id == project_id,
        PriceCalculation.period_start >= period_start,
        PriceCalculation.period_end <= period_end,
    )
    if material_class_id:
        q = q.filter(PriceCalculation.material_class_id == material_class_id)

    calcs = q.order_by(PriceCalculation.period_start).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Отчёт по удорожанию"

    ws.append(["Объект:", project.name])
    ws.append(["Договор:", project.contract_number or ""])
    ws.append(["Период:", f"{period_start} — {period_end}"])
    ws.append([])

    headers = ["Материал", "Период", "Ср. цена (₽)", "Эталон (₽)", "Отклонение (%)", "Отклонение (₽)", "Объём (м3)", "Кол-во СФ"]
    ws.append(headers)

    for c in calcs:
        mc_name = c.material_class.name if c.material_class else "?"
        ws.append([
            mc_name,
            f"{c.period_start} — {c.period_end}",
            c.avg_price,
            c.reference_price,
            c.deviation_pct,
            c.deviation_amount,
            c.total_qty,
            c.invoice_count,
        ])

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 2

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    from urllib.parse import quote
    filename = f"report_{project.name}_{period_start}_{period_end}.xlsx"
    encoded = quote(filename)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )
