import enum
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy import (
    text as sa_text,
)
from sqlalchemy.orm import relationship

from database import Base

# ---------------------------------------------------------------------------
#  Auth enums
# ---------------------------------------------------------------------------

class OrgRole(str, enum.Enum):
    """Роль пользователя внутри организации."""
    superadmin = "superadmin"
    admin = "admin"
    member = "member"


class ProjectRole(str, enum.Enum):
    """Роль организации на проекте."""
    customer = "customer"      # заказчик — видит все данные, управляет базовыми ценами
    contractor = "contractor"  # подрядчик — видит только свои загрузки


# ---------------------------------------------------------------------------
#  Auth models
# ---------------------------------------------------------------------------

class Organization(Base):
    """Организация — единица изоляции данных."""
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    inn = Column(String, nullable=True, index=True)
    # Роль организации (заказчик/подрядчик). Используем тот же enum, что и
    # ProjectOrganization.project_role — значения идентичны. NOT NULL со
    # server_default='customer': для УПД-трекера типичная организация — заказчик
    # (загружает счета своих подрядчиков); существующие строки миграция заполнит
    # этим значением. native_enum=False → VARCHAR + CHECK (см. примечание у org_role).
    kind = Column(
        SqlEnum(ProjectRole, name="org_kind", native_enum=False),
        nullable=False,
        server_default=ProjectRole.customer.value,
    )
    created_at = Column(DateTime, server_default=sa_text("(now() AT TIME ZONE 'utc')"))

    users = relationship("User", back_populates="organization")
    project_links = relationship("ProjectOrganization", back_populates="organization")


class User(Base):
    """Пользователь системы — принадлежит организации (или суперюзер без org)."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    email = Column(String, nullable=False, unique=True)  # unique уже создаёт индекс в PG
    password_hash = Column(String, nullable=False)
    is_superuser = Column(Boolean, nullable=False, default=False)
    # native_enum=False: хранит VARCHAR с CHECK constraint, а не PG ENUM.
    # Это позволяет добавлять значения без ALTER TYPE и без блокировки таблицы.
    org_role = Column(
        SqlEnum(OrgRole, name="org_role", native_enum=False),
        nullable=True,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=sa_text("(now() AT TIME ZONE 'utc')"))

    organization = relationship("Organization", back_populates="users")
    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )


class ProjectOrganization(Base):
    """Связь проект ↔ организация с ролью (customer/contractor)."""
    __tablename__ = "project_organizations"

    project_id = Column(Integer, ForeignKey("projects.id"), primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), primary_key=True)
    project_role = Column(
        SqlEnum(ProjectRole, name="project_role", native_enum=False),
        nullable=False,
    )
    created_at = Column(DateTime, server_default=sa_text("(now() AT TIME ZONE 'utc')"))

    project = relationship("Project", back_populates="org_links")
    organization = relationship("Organization", back_populates="project_links")


class RefreshToken(Base):
    """Refresh-токены — хранимые в БД, отзываемые.

    Хранится хэш токена (sha256), сам токен пользователю отдаётся в httpOnly cookie.
    Ротация: при каждом /refresh старый revoked_at проставляется, создаётся новый.
    """
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True)  # unique уже создаёт индекс в PG
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=sa_text("(now() AT TIME ZONE 'utc')"))
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)

    user = relationship("User", back_populates="refresh_tokens")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    contract_number = Column(String)
    customer_org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))

    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    reference_prices = relationship("ReferencePrice", back_populates="project", cascade="all, delete-orphan")
    org_links = relationship(
        "ProjectOrganization", back_populates="project", cascade="all, delete-orphan"
    )


class MaterialClass(Base):
    __tablename__ = "material_classes"

    id = Column(Integer, primary_key=True, index=True)
    material_type = Column(String, nullable=False)  # concrete / rebar / other
    name = Column(String, nullable=False)  # В15, В40
    calc_role = Column(String, nullable=False, default="base")  # base / additive / exclude
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))

    reference_prices = relationship("ReferencePrice", back_populates="material_class")
    invoice_items = relationship("InvoiceItem", back_populates="material_class")


class ReferencePrice(Base):
    __tablename__ = "reference_prices"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    material_class_id = Column(Integer, ForeignKey("material_classes.id"), nullable=False)
    price = Column(Float, nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    source = Column(String)

    project = relationship("Project", back_populates="reference_prices")
    material_class = relationship("MaterialClass", back_populates="reference_prices")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    filename = Column(String, nullable=False)
    s3_key = Column(String)
    doc_type = Column(String, default="unknown")
    status = Column(String, default="parsed")
    # sha256 hex дайджест файла — дедупликация до парсинга (экономит вызовы AI)
    file_hash = Column(String(64), nullable=True, index=True)
    uploaded_by_org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))

    __table_args__ = (
        UniqueConstraint("project_id", "file_hash", name="uq_documents_project_file_hash"),
    )

    project = relationship("Project", back_populates="documents")
    invoices = relationship("Invoice", back_populates="document", cascade="all, delete-orphan")


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    inn = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))

    invoices = relationship("Invoice", back_populates="supplier")


class ProjectSupplierExclusion(Base):
    __tablename__ = "project_supplier_exclusions"

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id", ondelete="CASCADE"), primary_key=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=sa_text("(now() AT TIME ZONE 'utc')"))


class CompensationCorridor(Base):
    """Коридор компенсации: допуск (%) вокруг базовой цены, в пределах которого
    удорожание/удешевление не компенсируется. Задаётся per (проект × класс материала),
    не периодичен (действует весь срок договора).

    Семантика: нет строки → класс некомпенсируемый; corridor_pct=0 → компенсируется
    любое отклонение (нет мёртвой зоны); corridor_pct=X → допуск ±X%.
    """
    __tablename__ = "compensation_corridors"

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    material_class_id = Column(
        Integer, ForeignKey("material_classes.id", ondelete="CASCADE"), primary_key=True
    )
    corridor_pct = Column(Float, nullable=False)  # 5.0 = ±5%; хранится в процентах, не в долях
    created_at = Column(DateTime, server_default=sa_text("(now() AT TIME ZONE 'utc')"))
    updated_at = Column(
        DateTime,
        server_default=sa_text("(now() AT TIME ZONE 'utc')"),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    number = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    supplier_name = Column(String)
    supplier_inn = Column(String)
    vat_rate = Column(Float, default=20.0)
    ai_confidence = Column(Float)
    verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))

    document = relationship("Document", back_populates="invoices")
    supplier = relationship("Supplier", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    raw_name = Column(String)
    item_type = Column(String, nullable=False)
    material_class_id = Column(Integer, ForeignKey("material_classes.id"), nullable=True)
    quantity = Column(Float, nullable=False)
    unit = Column(String)
    unit_price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    vat_amount = Column(Float)

    invoice = relationship("Invoice", back_populates="items")
    material_class = relationship("MaterialClass", back_populates="invoice_items")
