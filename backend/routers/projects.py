from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
import crud

router = APIRouter()

class ProjectCreate(BaseModel):
    name: str
    contract_number: str | None = None

@router.get("")
def list_projects(db: Session = Depends(get_db)):
    projects = crud.get_projects(db)
    return [{"id": p.id, "name": p.name, "contract_number": p.contract_number, "doc_count": len(p.documents)} for p in projects]

@router.post("")
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    project = crud.create_project(db, data.name, data.contract_number)
    return {"id": project.id, "name": project.name, "contract_number": project.contract_number}

@router.put("/{project_id}")
def update_project(project_id: int, data: ProjectCreate, db: Session = Depends(get_db)):
    project = crud.update_project(db, project_id, data.name, data.contract_number)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return {"id": project.id, "name": project.name, "contract_number": project.contract_number}

@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = crud.delete_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return {"message": "Удалено"}
