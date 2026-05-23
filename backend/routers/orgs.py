"""Эндпоинты управления собственной организацией (для org admin).

Позволяет org admin-у управлять пользователями внутри своей организации.
org_id берётся из токена текущего пользователя, не из тела запроса.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth import require_org_admin_with_org
from database import get_db
from models import OrgRole, User
from security import hash_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/orgs", tags=["orgs"])


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    # Org admin может создавать только member или admin (не superadmin)
    org_role: OrgRole = OrgRole.member


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_admin_with_org),
):
    """Создать пользователя в собственной организации.

    org_id берётся из токена текущего пользователя — нельзя создать
    пользователя в чужой организации.

    org_role ограничена: member или admin (superadmin — только через /api/admin).
    """
    if body.org_role == OrgRole.superadmin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "superadmin роль назначается только через /api/admin")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        is_superuser=False,
        org_id=current_user.org_id,
        org_role=body.org_role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("user_created id=%s email=%s org_id=%s role=%s", user.id, user.email, current_user.org_id, body.org_role)
    return {"id": user.id, "email": user.email, "org_id": current_user.org_id, "org_role": body.org_role.value}


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_admin_with_org),
):
    """Список пользователей своей организации."""
    users = db.query(User).filter(User.org_id == current_user.org_id).order_by(User.id).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "org_role": u.org_role.value if u.org_role else None,
            "is_active": u.is_active,
        }
        for u in users
    ]
