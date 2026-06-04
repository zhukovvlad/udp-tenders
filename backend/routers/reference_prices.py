from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from crud.projects import create_reference_price, delete_reference_price, get_reference_prices, update_reference_price
from database import get_db

router = APIRouter()

class ReferencePriceCreate(BaseModel):
    project_id: int
    material_class_id: int
    price: Decimal
    period_start: date
    period_end: date
    source: str | None = None

@router.get("")
def list_reference_prices(project_id: int | None = None, material_class_id: int | None = None, db: Session = Depends(get_db)):
    prices = get_reference_prices(db, project_id, material_class_id)
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
def create_reference_price_route(data: ReferencePriceCreate, db: Session = Depends(get_db)):
    rp = create_reference_price(db, data.project_id, data.material_class_id, data.price, data.period_start, data.period_end, data.source)
    return {"id": rp.id}

class ReferencePriceUpdate(BaseModel):
    price: Decimal | None = None
    period_start: date | None = None
    period_end: date | None = None
    source: str | None = None

    @field_validator("price", "period_start", "period_end", mode="before")
    @classmethod
    def not_null(cls, v, info):
        if v is None:
            raise ValueError(f"{info.field_name} не может быть null")
        return v

@router.patch("/{rp_id}")
def update_reference_price_route(rp_id: int, data: ReferencePriceUpdate, db: Session = Depends(get_db)):
    fields = data.model_fields_set
    kwargs = {k: getattr(data, k) for k in ("price", "period_start", "period_end", "source") if k in fields}
    rp = update_reference_price(db, rp_id, **kwargs)
    if not rp:
        raise HTTPException(status_code=404, detail="Эталон не найден")
    return {
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

@router.delete("/{rp_id}")
def delete_reference_price_route(rp_id: int, db: Session = Depends(get_db)):
    rp = delete_reference_price(db, rp_id)
    if not rp:
        raise HTTPException(status_code=404, detail="Эталон не найден")
    return {"message": "Удалено"}
