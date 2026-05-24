from sqlalchemy.orm import Session

from models import ProjectSupplierExclusion


def get_excluded_supplier_ids(db: Session, project_id: int) -> set[int]:
    """Возвращает множество supplier_id, исключённых из расчётов для данного проекта."""
    rows = (
        db.query(ProjectSupplierExclusion)
        .filter(ProjectSupplierExclusion.project_id == project_id)
        .all()
    )
    return {row.supplier_id for row in rows}


def set_supplier_excluded(
    db: Session,
    project_id: int,
    supplier_id: int,
    excluded: bool,
    reason: str | None = None,
) -> None:
    """Добавить или убрать исключение поставщика для проекта. Идемпотентно."""
    existing = (
        db.query(ProjectSupplierExclusion)
        .filter(
            ProjectSupplierExclusion.project_id == project_id,
            ProjectSupplierExclusion.supplier_id == supplier_id,
        )
        .first()
    )
    if excluded:
        if existing is None:
            db.add(
                ProjectSupplierExclusion(
                    project_id=project_id,
                    supplier_id=supplier_id,
                    reason=reason,
                )
            )
            db.commit()
    else:
        if existing is not None:
            db.delete(existing)
            db.commit()
