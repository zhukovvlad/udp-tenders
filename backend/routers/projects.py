from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from crud.projects import create_project, delete_project, get_projects, update_project
from crud.supplier_exclusions import get_excluded_supplier_ids, set_supplier_excluded
from database import get_db
from models import Document, Invoice, Supplier

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    contract_number: str | None = None


class ExclusionCreate(BaseModel):
    reason: str | None = None


@router.get("")
def list_projects(db: Session = Depends(get_db)):
    projects = get_projects(db)
    return [{"id": p.id, "name": p.name, "contract_number": p.contract_number, "doc_count": len(p.documents)} for p in projects]

@router.post("")
def create_project_route(data: ProjectCreate, db: Session = Depends(get_db)):
    project = create_project(db, data.name, data.contract_number)
    return {"id": project.id, "name": project.name, "contract_number": project.contract_number}

@router.put("/{project_id}")
def update_project_route(project_id: int, data: ProjectCreate, db: Session = Depends(get_db)):
    project = update_project(db, project_id, data.name, data.contract_number)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return {"id": project.id, "name": project.name, "contract_number": project.contract_number}

@router.delete("/{project_id}")
def delete_project_route(project_id: int, db: Session = Depends(get_db)):
    project = delete_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return {"message": "Удалено"}


@router.get("/{project_id}/suppliers")
def list_project_suppliers(project_id: int, db: Session = Depends(get_db)):
    """Список поставщиков проекта с кол-вом счетов. Инвойсы без supplier_id не включаются."""
    rows = (
        db.query(
            Supplier.id,
            Supplier.name,
            Supplier.inn,
            func.count(Invoice.id).label("invoice_count"),
        )
        .join(Invoice, Invoice.supplier_id == Supplier.id)
        .join(Document, Invoice.document_id == Document.id)
        .filter(Document.project_id == project_id)
        .group_by(Supplier.id, Supplier.name, Supplier.inn)
        .order_by(Supplier.name)
        .all()
    )
    return [
        {"id": r.id, "name": r.name, "inn": r.inn, "invoice_count": r.invoice_count}
        for r in rows
    ]


@router.get("/{project_id}/supplier-exclusions")
def list_supplier_exclusions(project_id: int, db: Session = Depends(get_db)):
    """Список supplier_id, исключённых из расчётов для данного проекта."""
    return sorted(get_excluded_supplier_ids(db, project_id))


@router.post("/{project_id}/supplier-exclusions/{supplier_id}", status_code=204)
def add_supplier_exclusion(
    project_id: int,
    supplier_id: int,
    data: ExclusionCreate,
    db: Session = Depends(get_db),
):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    set_supplier_excluded(db, project_id, supplier_id, excluded=True, reason=data.reason)
    return Response(status_code=204)


@router.delete("/{project_id}/supplier-exclusions/{supplier_id}", status_code=204)
def remove_supplier_exclusion(
    project_id: int,
    supplier_id: int,
    db: Session = Depends(get_db),
):
    set_supplier_excluded(db, project_id, supplier_id, excluded=False)
    return Response(status_code=204)

