"""Роутер суперюзерных операций: организации и пользователи.

Все эндпоинты требуют is_superuser=True.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth import require_superuser
from database import get_db
from models import Organization, OrgRole, User
from security import hash_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------------------------------------------------------------------------
#  Схемы
# ---------------------------------------------------------------------------

class OrgCreate(BaseModel):
    name: str
    inn: str | None = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    org_role: OrgRole = OrgRole.member


# ---------------------------------------------------------------------------
#  Организации
# ---------------------------------------------------------------------------

@router.post("/organizations", status_code=status.HTTP_201_CREATED)
def create_organization(
    body: OrgCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_superuser),
):
    """Создать организацию (только суперюзер)."""
    org = Organization(name=body.name, inn=body.inn)
    db.add(org)
    db.commit()
    db.refresh(org)
    logger.info("organization_created id=%s name=%s", org.id, org.name)
    return {"id": org.id, "name": org.name, "inn": org.inn}


@router.get("/organizations")
def list_organizations(
    db: Session = Depends(get_db),
    _: User = Depends(require_superuser),
):
    """Список всех организаций (только суперюзер)."""
    orgs = db.query(Organization).order_by(Organization.id).all()
    return [{"id": o.id, "name": o.name, "inn": o.inn} for o in orgs]


# ---------------------------------------------------------------------------
#  Пользователи
# ---------------------------------------------------------------------------

@router.post("/organizations/{org_id}/users", status_code=status.HTTP_201_CREATED)
def create_user_in_org(
    org_id: int,
    body: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_superuser),
):
    """Создать пользователя в организации (только суперюзер).

    Первый пользователь в организации автоматически получает роль superadmin.
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    # Первый пользователь в org → superadmin автоматически
    existing_count = db.query(User).filter(User.org_id == org_id).count()
    role = OrgRole.superadmin if existing_count == 0 else body.org_role

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        is_superuser=False,
        org_id=org_id,
        org_role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("user_created id=%s email=%s org_id=%s role=%s", user.id, user.email, org_id, role)
    return {"id": user.id, "email": user.email, "org_id": org_id, "org_role": role.value}


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_superuser),
):
    """Список всех пользователей с информацией об org (только суперюзер)."""
    users = db.query(User).order_by(User.id).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "org_id": u.org_id,
            "org_role": u.org_role.value if u.org_role else None,
            "is_superuser": u.is_superuser,
            "is_active": u.is_active,
        }
        for u in users
    ]
