from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import crud
from database import get_db

router = APIRouter()

class MaterialClassCreate(BaseModel):
    name: str
    material_type: str  # concrete / rebar / other

@router.get("")
def list_material_classes(material_type: str | None = None, db: Session = Depends(get_db)):
    classes = crud.get_material_classes(db, material_type)
    return [{"id": mc.id, "name": mc.name, "material_type": mc.material_type} for mc in classes]

@router.post("")
def create_material_class(data: MaterialClassCreate, db: Session = Depends(get_db)):
    mc = crud.get_or_create_material_class(db, data.name, data.material_type)
    return {"id": mc.id, "name": mc.name, "material_type": mc.material_type}

@router.delete("/{class_id}")
def delete_material_class(class_id: int, db: Session = Depends(get_db)):
    mc = crud.delete_material_class(db, class_id)
    if not mc:
        raise HTTPException(status_code=404, detail="Класс не найден")
    return {"message": "Удалено"}
