import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import crud
from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


class MergeRequest(BaseModel):
    source_id: int


@router.get("")
def list_suppliers(db: Session = Depends(get_db)):
    results = crud.get_suppliers(db)
    return [
        {"id": s.id, "name": s.name, "inn": s.inn, "invoice_count": count}
        for s, count in results
    ]


@router.get("/duplicates")
def list_supplier_duplicates(threshold: float = 85.0, db: Session = Depends(get_db)):
    if not (0 < threshold <= 100):
        raise HTTPException(status_code=422, detail="threshold должен быть в диапазоне (0, 100]")
    pairs = crud.get_supplier_duplicates(db, threshold)
    return [
        {
            "supplier_a": {"id": a.id, "name": a.name},
            "supplier_b": {"id": b.id, "name": b.name},
            "score": score,
        }
        for a, b, score in pairs
    ]


@router.get("/{supplier_id}")
def get_supplier(supplier_id: int, db: Session = Depends(get_db)):
    supplier = crud.get_supplier(db, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    invoices = crud.get_supplier_invoices(db, supplier_id)
    return {
        "id": supplier.id,
        "name": supplier.name,
        "inn": supplier.inn,
        "invoices": [
            {"id": inv.id, "number": inv.number, "date": str(inv.date)}
            for inv in invoices
        ],
    }


@router.post("/{supplier_id}/merge")
def merge_suppliers(supplier_id: int, data: MergeRequest, db: Session = Depends(get_db)):
    if data.source_id == supplier_id:
        raise HTTPException(status_code=422, detail="source_id и target_id совпадают")
    result = crud.merge_suppliers(db, source_id=data.source_id, target_id=supplier_id)
    if not result:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    logger.info("Merge: supplier %s absorbed into %s", data.source_id, supplier_id)
    return {"id": result.id, "name": result.name, "inn": result.inn}
