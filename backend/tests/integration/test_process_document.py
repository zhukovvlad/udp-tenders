"""Тесты ядра обработки: process_document, error-пути, CancelledError (S0-3, S0-4, §2.3)."""
import asyncio
from decimal import Decimal

import pytest

from models import Document, Invoice
from processing import get_processing_session_factory, process_document, write_processing_error


def _proc_doc(factories, db_session, s3, s3_key="k/p.pdf"):
    """Документ в статусе processing с байтами в in-memory S3 — типовая заготовка."""
    doc = factories.DocumentFactory.create(s3_key=s3_key, status="processing")
    s3[s3_key] = b"%PDF"
    db_session.commit()
    return doc


@pytest.mark.asyncio
async def test_process_document_success_sets_parsed(
    factories, db_session, in_memory_s3, mock_openrouter, session_factory_test,
):
    """Успешный reparse ставит parsed и создаёт СФ."""
    doc = _proc_doc(factories, db_session, in_memory_s3)
    await process_document(doc.id, mode="parse", session_factory=session_factory_test)
    db_session.expire_all()
    saved = db_session.query(Document).filter(Document.id == doc.id).first()
    assert saved.status == "parsed"


def test_get_processing_session_factory_returns_patched_session_local(monkeypatch):
    """Поздний импорт database.SessionLocal внутри функции подхватывает monkeypatch (F1)."""
    import database

    sentinel = object()
    monkeypatch.setattr(database, "SessionLocal", sentinel)
    assert get_processing_session_factory() is sentinel


@pytest.mark.asyncio
async def test_process_document_none_session_factory_resolves_via_database(
    factories, db_session, in_memory_s3, mock_openrouter, monkeypatch, session_factory_test,
):
    """session_factory=None → поздний резолв через get_processing_session_factory доходит до parsed (F1 e2e)."""
    import database

    monkeypatch.setattr(database, "SessionLocal", session_factory_test)
    doc = _proc_doc(factories, db_session, in_memory_s3)

    await process_document(doc.id, mode="parse")

    db_session.expire_all()
    saved = db_session.query(Document).filter(Document.id == doc.id).first()
    assert saved.status == "parsed"


@pytest.mark.asyncio
async def test_process_document_permanent_error_keeps_old_invoices(
    factories, db_session, in_memory_s3, mock_openrouter, session_factory_test,
):
    """Провал сверки итогов → error, старые СФ невредимы, last_error заполнен (AC-S0-1)."""
    mock_openrouter.use_scenario("incomplete_totals")
    doc = _proc_doc(factories, db_session, in_memory_s3)
    factories.InvoiceFactory.create(document=doc, number="СФ-OLD")
    db_session.commit()

    await process_document(doc.id, mode="parse", session_factory=session_factory_test)

    db_session.expire_all()
    saved = db_session.query(Document).filter(Document.id == doc.id).first()
    assert saved.status == "error"
    assert saved.last_error
    assert saved.parse_count == 1  # платный вызов учтён
    assert [i.number for i in db_session.query(Invoice).filter(Invoice.document_id == doc.id)] == ["СФ-OLD"]


@pytest.mark.asyncio
async def test_process_document_phase_b_failure_writes_error_with_cost(
    factories, db_session, in_memory_s3, mock_openrouter, monkeypatch, session_factory_test,
):
    """Сбой фазы B ПОСЛЕ оплаченной фазы A (через process_document) → status=error,
    last_error заполнен, стоимость фазы A начислена ровно один раз, старые СФ целы (AC-S0-11 e2e, F5)."""
    import processing

    doc = _proc_doc(factories, db_session, in_memory_s3)
    factories.InvoiceFactory.create(document=doc, number="СФ-OLD")
    db_session.commit()

    def boom(*a, **k):
        """Ломает вставку позиции внутри фазы B (детерминированный сбой БД)."""
        raise RuntimeError("db exploded mid-phase-B")
    monkeypatch.setattr(processing, "normalize_item", boom)

    await process_document(doc.id, mode="parse", session_factory=session_factory_test)

    db_session.expire_all()
    saved = db_session.query(Document).filter(Document.id == doc.id).first()
    assert saved.status == "error"
    assert saved.last_error
    assert saved.parse_count == 1                       # detect не было; фаза A оплачена ровно раз
    assert saved.parse_cost_usd > Decimal(0)            # стоимость фазы A начислена
    numbers = [i.number for i in db_session.query(Invoice).filter(Invoice.document_id == doc.id)]
    assert numbers == ["СФ-OLD"]                         # swap откатан, старые СФ целы


@pytest.mark.asyncio
async def test_process_document_cancelled_sets_error(
    factories, db_session, in_memory_s3, monkeypatch, session_factory_test,
):
    """CancelledError посреди парсинга → error + last_error='Обработка прервана', re-raise (AC-S0-2)."""
    import pdf_parser  # run_processing_attempt берёт parse_pdf локально из pdf_parser (F6)

    doc = _proc_doc(factories, db_session, in_memory_s3)

    async def boom(*a, **k):
        """Эмулирует отмену таски внутри фазы A."""
        raise asyncio.CancelledError()
    monkeypatch.setattr(pdf_parser, "parse_pdf", boom)

    with pytest.raises(asyncio.CancelledError):
        await process_document(doc.id, mode="parse", session_factory=session_factory_test)

    db_session.expire_all()
    saved = db_session.query(Document).filter(Document.id == doc.id).first()
    assert saved.status == "error"
    assert saved.last_error == "Обработка прервана"


def test_write_error_conditional_skips_when_already_parsed(
    factories, db_session, session_factory_test,
):
    """Условная error-запись при уже parsed → rowcount 0, статус не затёрт (AC-S0-12)."""
    doc = factories.DocumentFactory.create(status="parsed")
    db_session.commit()

    write_processing_error(session_factory_test, doc.id, "боль", cost_usd=Decimal("0.001"), paid_calls=1)

    db_session.expire_all()
    saved = db_session.query(Document).filter(Document.id == doc.id).first()
    assert saved.status == "parsed"           # не затёрт
    assert saved.parse_count == 0             # стоимость не начислена повторно


def test_write_error_reraises_non_connection_operational_error():
    """Не-connection OperationalError (deadlock) → одна попытка, проброс, без глотания (F8)."""
    from contextlib import contextmanager
    from unittest.mock import MagicMock

    from sqlalchemy.exc import OperationalError

    attempts = {"n": 0}

    @contextmanager
    def factory():
        """Фейковая фабрика: execute всегда бросает детерминированный OperationalError."""
        db = MagicMock()

        def _execute(*a, **k):
            """Эмулирует deadlock — OperationalError без connection_invalidated/SQLSTATE 08."""
            attempts["n"] += 1
            raise OperationalError("UPDATE documents ...", {}, Exception("deadlock detected"))

        db.execute.side_effect = _execute
        yield db

    with pytest.raises(OperationalError):
        write_processing_error(factory, 1, "x", cost_usd=Decimal("0.001"), paid_calls=1)
    assert attempts["n"] == 1  # детерминированная ошибка — без ретраев


def test_write_error_retries_on_connection_loss():
    """connection_invalidated=True → ретраит до retries, затем critical-лог без проброса (F8)."""
    from contextlib import contextmanager
    from unittest.mock import MagicMock

    from sqlalchemy.exc import OperationalError

    attempts = {"n": 0}

    @contextmanager
    def factory():
        """Фейковая фабрика: execute бросает connection-invalidated ошибку."""
        db = MagicMock()

        def _execute(*a, **k):
            """Эмулирует обрыв соединения из commit — ретраебельно."""
            attempts["n"] += 1
            err = OperationalError("UPDATE documents ...", {}, Exception("server closed connection"))
            err.connection_invalidated = True
            raise err

        db.execute.side_effect = _execute
        yield db

    # Все попытки — потеря соединения → исчерпание ретраев → critical-лог, исключение НЕ пробрасывается.
    write_processing_error(factory, 1, "x", cost_usd=Decimal("0.001"), paid_calls=1, retries=3)
    assert attempts["n"] == 3
