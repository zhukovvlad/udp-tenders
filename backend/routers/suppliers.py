import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import crud
from database import get_db
from models import Supplier as SupplierModel

logger = logging.getLogger(__name__)

router = APIRouter()


class SupplierCreate(BaseModel):
    name: str
    inn: str | None = None


class SupplierUpdate(BaseModel):
    name: str
    inn: str | None = None


class MergeRequest(BaseModel):
    source_id: int


@router.get("")
def list_suppliers(db: Session = Depends(get_db)):
    results = crud.get_suppliers_with_stats(db)
    return results


@router.get("/{supplier_id}/projects")
def get_supplier_projects(supplier_id: int, db: Session = Depends(get_db)):
    supplier = crud.get_supplier(db, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    return crud.get_supplier_project_stats(db, supplier_id)


@router.get("/{supplier_id}/invoices-list")
def get_supplier_invoices(
    supplier_id: int,
    project_id: int | None = None,
    db: Session = Depends(get_db),
):
    supplier = crud.get_supplier(db, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    return crud.get_supplier_invoices_list(db, supplier_id, project_id=project_id)


@router.post("")
def create_supplier(data: SupplierCreate, db: Session = Depends(get_db)):
    name = data.name.strip() if data.name else None
    inn = (data.inn.strip() or None) if data.inn else None
    if not name:
        raise HTTPException(status_code=422, detail="Название поставщика не может быть пустым")
    supplier = crud.get_or_create_supplier(db, name=name, inn=inn)
    try:
        db.commit()
    except IntegrityError as err:
        db.rollback()
        raise HTTPException(status_code=409, detail="Не удалось сохранить поставщика") from err
    db.refresh(supplier)
    logger.info("Created/found supplier id=%s name=%s inn=%s", supplier.id, supplier.name, supplier.inn)
    return {"id": supplier.id, "name": supplier.name, "inn": supplier.inn}


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
    detail = crud.get_supplier_detail(db, supplier_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    return detail


@router.put("/{supplier_id}")
def update_supplier(supplier_id: int, data: SupplierUpdate, db: Session = Depends(get_db)):
    name = data.name.strip() if data.name else None
    inn = (data.inn.strip() or None) if data.inn else None
    if not name:
        raise HTTPException(status_code=422, detail="Название поставщика не может быть пустым")
    try:
        supplier = crud.update_supplier(db, supplier_id, name=name, inn=inn)
    except IntegrityError as err:
        db.rollback()
        err_str = str(err.orig).lower() if err.orig else ""
        if inn and "uq_suppliers_name_no_inn" not in err_str:
            # ИНН уже занят другим поставщиком — ищем кто именно
            existing = db.query(SupplierModel).filter(
                SupplierModel.inn == inn,
                SupplierModel.id != supplier_id,
            ).first()
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "inn_conflict",
                        "message": f"Поставщик с ИНН {inn} уже существует",
                        "existing": {"id": existing.id, "name": existing.name},
                    },
                ) from err
        detail = (
            "Поставщик с таким названием (без ИНН) уже существует"
            if "uq_suppliers_name_no_inn" in err_str
            else "Поставщик с таким ИНН уже существует" if inn
            else "Не удалось сохранить изменения: нарушение уникальности"
        )
        raise HTTPException(status_code=409, detail=detail) from err
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    logger.info("Updated supplier id=%s name=%s inn=%s", supplier.id, supplier.name, supplier.inn)
    return {"id": supplier.id, "name": supplier.name, "inn": supplier.inn}


@router.delete("/{supplier_id}")
def delete_supplier(supplier_id: int, db: Session = Depends(get_db)):
    from models import Invoice
    linked = db.query(Invoice).filter(Invoice.supplier_id == supplier_id).count()
    if linked:
        raise HTTPException(
            status_code=409,
            detail=f"Нельзя удалить: поставщик связан с {linked} инвойсами. Используйте merge.",
        )
    try:
        supplier = crud.delete_supplier(db, supplier_id)
    except IntegrityError as err:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Нельзя удалить: поставщик связан с инвойсами. Используйте merge.",
        ) from err
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    logger.info("Deleted supplier id=%s", supplier_id)
    return {"message": "Удалено"}


@router.post("/{supplier_id}/merge")
def merge_suppliers(supplier_id: int, data: MergeRequest, db: Session = Depends(get_db)):
    if data.source_id == supplier_id:
        raise HTTPException(status_code=422, detail="source_id и target_id совпадают")
    result = crud.merge_suppliers(db, source_id=data.source_id, target_id=supplier_id)
    if not result:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    logger.info("Merge: supplier %s absorbed into %s", data.source_id, supplier_id)
    return {"id": result.id, "name": result.name, "inn": result.inn}
