import logging
import re

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from models import InvoiceItem, MaterialClass, MaterialType, ReferencePrice

logger = logging.getLogger(__name__)

VALID_CALC_ROLES = {"base", "additive", "exclude"}


class UnknownMaterialType(ValueError):
    """Raised when a material_type code is not in the material_types table."""


def _material_type_id_by_code(db: Session, code: str) -> int:
    mt = db.query(MaterialType).filter(MaterialType.code == code).first()
    if mt is None:
        raise UnknownMaterialType(code)
    return mt.id


# --- Material Classes ---

# Латинские двойники кириллицы: модель пишет то «B60», то «В60» — визуально одно и то же.
_LATIN_TO_CYRILLIC = str.maketrans("ABCEHKMOPTXYaceopxyk", "АВСЕНКМОРТХУасеорхук")
# Код класса: 1–3 буквы, число (дробь через точку или запятую), суффикс до 2 букв —
# «В25», «В7,5», «А500С», «Ат800», «М200». Всё прочее (добавки, exclude-имена,
# полные спецификации вроде «B25 W8 F200») кодом не считается.
_CLASS_CODE_RE = re.compile(
    r"^([A-Za-zА-Яа-яЁё]{1,3})\s*(\d+(?:[.,]\d+)?)\s*([A-Za-zА-Яа-яЁё]{0,2})$"
)


def normalize_class_name(name: str) -> str:
    """Канон имени класса: схлопнуть пробелы; для кода класса — кириллица, точка, без пробелов.

    Для кода латинские двойники заменяются кириллицей, первая буква — заглавная (регистр
    остальных сохраняется: «Ат800» по ГОСТ), дробная часть — через точку («В7.5»).
    Не-коды не транслитерируются — латинское торговое имя добавки остаётся как есть.
    """
    collapsed = " ".join(name.split())
    match = _CLASS_CODE_RE.match(collapsed)
    if not match:
        return collapsed
    prefix, number, suffix = match.groups()
    prefix = prefix.translate(_LATIN_TO_CYRILLIC)
    return prefix[0].upper() + prefix[1:] + number.replace(",", ".") + suffix.translate(_LATIN_TO_CYRILLIC)


def _find_class(db: Session, name: str, material_type_id: int) -> MaterialClass | None:
    """Класс по точному (уже каноническому) имени внутри типа."""
    return db.query(MaterialClass).filter(
        MaterialClass.name == name, MaterialClass.material_type_id == material_type_id
    ).first()

def get_material_classes(db: Session, material_type: str | None = None) -> list[MaterialClass]:
    q = (
        db.query(MaterialClass)
        .options(joinedload(MaterialClass.material_type))
        .join(MaterialType, MaterialClass.material_type_id == MaterialType.id)
        .order_by(MaterialType.code, MaterialClass.name)
    )
    if material_type:
        q = q.filter(MaterialType.code == material_type)
    return q.all()


def get_material_class(db: Session, class_id: int):
    return db.query(MaterialClass).filter(MaterialClass.id == class_id).first()


def get_or_create_material_class(
    db: Session, name: str, material_type: str, calc_role: str = "base", *, commit: bool = True
) -> MaterialClass:
    """Найти или создать класс материала (имя приводится к канону normalize_class_name).

    commit=True (по умолчанию) — самостоятельная транзакция (ручные CRUD-пути).
    commit=False — только flush, чтобы остаться в транзакции вызывающего (фаза B).
    Гонка параллельных обработок (оба SELECT пусты) разрешается уникальным индексом
    uq_material_classes_type_name: проигравший INSERT откатывает только свой savepoint
    и берёт класс, созданный победителем.
    """
    if calc_role not in VALID_CALC_ROLES:
        raise ValueError(f"Unknown calc_role {calc_role!r}; allowed: {sorted(VALID_CALC_ROLES)}")
    name = normalize_class_name(name)
    material_type_id = _material_type_id_by_code(db, material_type)
    mc = _find_class(db, name, material_type_id)
    if not mc:
        try:
            with db.begin_nested():
                mc = MaterialClass(name=name, material_type_id=material_type_id, calc_role=calc_role)
                db.add(mc)
        except IntegrityError:
            mc = _find_class(db, name, material_type_id)
            if mc is None:
                raise  # уникальность ни при чём (например, FK) — не маскируем
            return mc
        if commit:
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
