import logging

from sqlalchemy.orm import Session

from models import InvoiceItem, MaterialClass, ReferencePrice

logger = logging.getLogger(__name__)

VALID_CALC_ROLES = {"base", "additive", "exclude"}


# --- Material Classes ---

def get_material_classes(db: Session, material_type: str = None):
    q = db.query(MaterialClass).order_by(MaterialClass.material_type, MaterialClass.name)
    if material_type:
        q = q.filter(MaterialClass.material_type == material_type)
    return q.all()


def get_material_class(db: Session, class_id: int):
    return db.query(MaterialClass).filter(MaterialClass.id == class_id).first()


def get_or_create_material_class(
    db: Session, name: str, material_type: str, calc_role: str = "base"
) -> MaterialClass:
    if calc_role not in VALID_CALC_ROLES:
        raise ValueError(f"Unknown calc_role {calc_role!r}; allowed: {sorted(VALID_CALC_ROLES)}")
    mc = db.query(MaterialClass).filter(
        MaterialClass.name == name, MaterialClass.material_type == material_type
    ).first()
    if not mc:
        mc = MaterialClass(name=name, material_type=material_type, calc_role=calc_role)
        db.add(mc)
        db.commit()
        db.refresh(mc)
    elif mc.calc_role != calc_role:
        # Preserved intentionally: the DB record represents a human-reviewed classification;
        # auto-update would allow LLM hallucinations to corrupt it.
        # To reclassify: delete the MaterialClass record via DELETE /api/material-classes/{id}
        # so the next parse recreates it with the correct calc_role, or update directly in the DB.
        logger.warning(
            "get_or_create_material_class: class %r/%r found with calc_role=%r, "
            "but caller expects %r — stored value preserved; "
            "to reclassify, delete the record via DELETE /api/material-classes/{id} "
            "and re-parse, or update directly in the DB",
            name, material_type, mc.calc_role, calc_role,
        )
    return mc


def delete_material_class(db: Session, class_id: int):
    mc = get_material_class(db, class_id)
    if mc:
        db.query(InvoiceItem).filter(InvoiceItem.material_class_id == class_id).update(
            {InvoiceItem.material_class_id: None}, synchronize_session=False
        )
        db.query(ReferencePrice).filter(ReferencePrice.material_class_id == class_id).delete()
        db.delete(mc)
        db.commit()
    return mc
