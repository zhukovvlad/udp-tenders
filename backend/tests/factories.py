"""factory_boy фабрики для интеграционных тестов.

Использование: `project = ProjectFactory.create()` в тесте, который имеет
фикстуру `db_session`. Фабрики привязываются к session через `_register_session`.
"""
from datetime import date

import factory
from factory.alchemy import SQLAlchemyModelFactory

from models import (
    Document,
    Invoice,
    InvoiceItem,
    MaterialClass,
    Project,
    ReferencePrice,
)

# Глобальный slot — устанавливается фикстурой db_session
_session_holder: dict = {"session": None}


def _register_session(session) -> None:
    _session_holder["session"] = session


class _BaseFactory(SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session_persistence = "flush"

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        session = _session_holder["session"]
        if session is None:
            raise RuntimeError("Session не зарегистрирована. Используй фикстуру `factories`.")
        cls._meta.sqlalchemy_session = session
        return super()._create(model_class, *args, **kwargs)


class ProjectFactory(_BaseFactory):
    class Meta:
        model = Project

    name = factory.Sequence(lambda n: f"Объект {n}")
    contract_number = factory.Sequence(lambda n: f"Д-{n:03d}")


class MaterialClassFactory(_BaseFactory):
    class Meta:
        model = MaterialClass

    name = factory.Iterator(["В15", "В25", "В40", "d12", "d16"])
    material_type = factory.Iterator(["concrete", "concrete", "concrete", "rebar", "rebar"])


class ReferencePriceFactory(_BaseFactory):
    class Meta:
        model = ReferencePrice

    project = factory.SubFactory(ProjectFactory)
    material_class = factory.SubFactory(MaterialClassFactory)
    price = 8000.0
    period_start = date(2026, 1, 1)
    period_end = date(2026, 12, 31)
    source = "контракт"


class DocumentFactory(_BaseFactory):
    class Meta:
        model = Document

    project = factory.SubFactory(ProjectFactory)
    filename = factory.Sequence(lambda n: f"doc_{n}.pdf")
    s3_key = factory.Sequence(lambda n: f"2026/05/{n}_doc.pdf")
    doc_type = "invoice"
    status = "parsed"


class InvoiceFactory(_BaseFactory):
    class Meta:
        model = Invoice

    document = factory.SubFactory(DocumentFactory)
    number = factory.Sequence(lambda n: f"СФ-{n}")
    date = date(2026, 3, 15)
    supplier_name = "ООО Поставщик"
    supplier_inn = "0000000000"
    vat_rate = 20.0
    ai_confidence = 0.9


class InvoiceItemFactory(_BaseFactory):
    class Meta:
        model = InvoiceItem

    invoice = factory.SubFactory(InvoiceFactory)
    raw_name = "Бетон В25"
    item_type = "material"
    quantity = 5.0
    unit = "м3"
    unit_price = 8000.0
    amount = 40000.0
    vat_amount = 6666.67
