from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import date
from database import get_db
import crud

router = APIRouter()

class ReferencePriceCreate(BaseModel):
    project_id: int
    material_class_id: int
    price: float
    period_start: date
    period_end: date
    source: str | None = None

@router.get("")
def list_reference_prices(project_id: int | None = None, db: Session = Depends(get_db)):
    prices = crud.get_reference_prices(db, project_id)
    return [
        {
            "id": rp.id,
            "project_id": rp.project_id,
            "project_name": rp.project.name,
            "material_class_id": rp.material_class_id,
            "material_class_name": rp.material_class.name,
            "material_type": rp.material_class.material_type,
            "price": rp.price,
            "period_start": rp.period_start.isoformat(),
            "period_end": rp.period_end.isoformat(),
            "source": rp.source,
        }
        for rp in prices
    ]

@router.post("")
def create_reference_price(data: ReferencePriceCreate, db: Session = Depends(get_db)):
    rp = crud.create_reference_price(db, data.project_id, data.material_class_id, data.price, data.period_start, data.period_end, data.source)
    return {"id": rp.id}

@router.delete("/{rp_id}")
def delete_reference_price(rp_id: int, db: Session = Depends(get_db)):
    rp = crud.delete_reference_price(db, rp_id)
    if not rp:
        raise HTTPException(status_code=404, detail="Эталон не найден")
    return {"message": "Удалено"}
