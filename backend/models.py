from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    contract_number = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))

    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    reference_prices = relationship("ReferencePrice", back_populates="project", cascade="all, delete-orphan")


class MaterialClass(Base):
    __tablename__ = "material_classes"

    id = Column(Integer, primary_key=True, index=True)
    material_type = Column(String, nullable=False)  # concrete / rebar / other
    name = Column(String, nullable=False)  # В15, В40
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
    uploaded_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))

    project = relationship("Project", back_populates="documents")
    invoices = relationship("Invoice", back_populates="document", cascade="all, delete-orphan")


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    inn = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))

    invoices = relationship("Invoice", back_populates="supplier")


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
