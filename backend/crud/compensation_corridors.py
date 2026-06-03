from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from models import CompensationCorridor


def get_corridors(db: Session, project_id: int) -> list[CompensationCorridor]:
    """Все строки коридоров проекта (для таба — имена классов джойнятся в роутере)."""
    return (
        db.query(CompensationCorridor)
        .filter(CompensationCorridor.project_id == project_id)
        .all()
    )


def get_corridor_map(db: Session, project_id: int) -> dict[int, float]:
    """{material_class_id: corridor_pct} — для compute_calculations."""
    return {
        row.material_class_id: row.corridor_pct
        for row in get_corridors(db, project_id)
    }


def set_corridor(db: Session, project_id: int, material_class_id: int, corridor_pct: float) -> None:
    """Upsert процента коридора. Идемпотентно и race-safe через composite PK."""
    stmt = (
        pg_insert(CompensationCorridor)
        .values(project_id=project_id, material_class_id=material_class_id, corridor_pct=corridor_pct)
        .on_conflict_do_update(
            index_elements=["project_id", "material_class_id"],
            set_={"corridor_pct": corridor_pct},
        )
    )
    db.execute(stmt)
    db.commit()


def delete_corridor(db: Session, project_id: int, material_class_id: int) -> bool:
    """Снять класс с компенсации. Возвращает True если строка была удалена."""
    deleted = (
        db.query(CompensationCorridor)
        .filter(
            CompensationCorridor.project_id == project_id,
            CompensationCorridor.material_class_id == material_class_id,
        )
        .delete()
    )
    db.commit()
    return deleted > 0
