from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from crud.projects import create_project, delete_project, get_projects, update_project
from database import get_db

router = APIRouter()

class ProjectCreate(BaseModel):
    name: str
    contract_number: str | None = None

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
