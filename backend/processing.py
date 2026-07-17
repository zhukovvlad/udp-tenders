"""Ядро обработки документов: парсинг (фаза A) + персистенция (фаза B).

См. docs/superpowers/specs/2026-07-16-async-processing-design.md.
На ступени 0 process_document вызывается инлайн (await в хэндлере).
"""
# from __future__ import annotations — постоянно откладывает вычисление аннотаций,
# что позволяет типизировать persist_parse_result(outcome: ParseOutcome) без
# импорта ParseOutcome в рантайме (pdf_parser импортирует ProcessingError/
# TransientError/PermanentError из этого модуля — прямой импорт по кругу упал бы).
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from crud.materials import VALID_CALC_ROLES, UnknownMaterialType, get_or_create_material_class
from crud.suppliers import get_or_create_supplier
from crud.units import load_alias_map, normalize_item
from models import Document, Invoice, InvoiceItem

if TYPE_CHECKING:  # только для типизации — не вызывает циклический импорт в рантайме
    from pdf_parser import ParseOutcome

logger = logging.getLogger(__name__)

_LAST_ERROR_MAXLEN = 500


class ProcessingError(Exception):
    """Базовая доменная ошибка попытки обработки.

    Несёт накопленный учёт платных вызовов OpenRouter (cost_usd, paid_calls),
    чтобы error-путь мог начислить стоимость даже при провале (инвариант
    parse-cost-tracking: HTTP 200 → деньги потрачены → стоимость учтена).
    """

    def __init__(self, message: str, *, cost_usd: Decimal = Decimal(0), paid_calls: int = 0,
                 http_status: int | None = None):
        """Сохраняет сообщение, накопленный учёт стоимости и подсказку HTTP-статуса.

        http_status задают только доменные ошибки, которые на ступени 0 должны
        дойти до клиента прежним HTTP-кодом (deskew: 413 слишком много страниц,
        502 сервис распознавания недоступен) — см. AC-S0-8. Ошибки парсинга
        http_status не задают → гасятся в status='error' + 200.
        """
        super().__init__(message)
        self.message = message
        self.cost_usd = cost_usd
        self.paid_calls = paid_calls
        self.http_status = http_status


class TransientError(ProcessingError):
    """Транзиентная ошибка (S3 недоступен, httpx timeout/сетевой сбой, 5xx/429/408 OpenRouter, сбой detect).

    На ступени 2 получит retry-политику; на ступени 0/1 ведёт к терминальному error.
    """


class PermanentError(ProcessingError):
    """Перманентная ошибка контента (невалидный JSON, провал сверки итогов,

    finish_reason=length, doc_type != invoice, слишком много страниц для deskew).
    Не ретраится никогда.
    """


def _dec(value):
    """LLM/JSON float → Decimal через str() (отсекает бинарную погрешность). None-safe."""
    return None if value is None else Decimal(str(value))


def _resolve_material_class_id(db: Session, item, *, document_id: int) -> int | None:
    """Резолвит material_class позиции в id (flush, без commit) — перенос из старого parse.

    Только для item_type='material' с непустым material_class. Неизвестный calc_role → 'base';
    неизвестный material_type → 'other'.
    """
    if item.item_type != "material" or not item.material_class:
        return None
    raw_role = str(item.calc_role or "base").strip().lower()
    if raw_role not in VALID_CALC_ROLES:
        logger.warning("[doc=%d] неизвестный calc_role=%r → 'base'", document_id, raw_role)
        raw_role = "base"
    try:
        mc = get_or_create_material_class(
            db, name=item.material_class, material_type=item.material_type or "other",
            calc_role=raw_role, commit=False,
        )
    except UnknownMaterialType:
        mc = get_or_create_material_class(
            db, name=item.material_class, material_type="other", calc_role=raw_role, commit=False,
        )
    return mc.id


def persist_parse_result(db: Session, doc_id: int, outcome: ParseOutcome) -> None:
    """Фаза B: в одной транзакции заменить СФ документа результатом парсинга.

    Удаляет старые СФ, резолвит поставщиков/классы (flush), вставляет новые СФ,
    ставит status='parsed', инкремент стоимости, единственный commit. Никаких
    промежуточных commit — инвариант транзакционности (§2.3/§2.4).

    Все выходы-ошибки НЕСУТ учёт стоимости outcome (фаза A уже оплачена → error-путь
    обязан начислить, инвариант §2.3). Детерминированный сбой (flush/insert) → явный
    rollback (сессия в failed state, без него последующая error-запись через ту же
    сессию упадёт PendingRollbackError) + TransientError с учётом. Сбой из commit
    (ambiguous) → тоже TransientError; условная error-запись (§2.3) разрулит, лёг ли swap.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc is None:
        raise PermanentError(f"Документ id={doc_id} не найден на фазе B",
                             cost_usd=outcome.cost_usd, paid_calls=outcome.paid_calls)

    try:
        for inv in list(doc.invoices):
            db.delete(inv)

        aliases = load_alias_map(db)
        for pinv in outcome.invoices:
            _inn = (pinv.supplier_inn.strip() or None) if pinv.supplier_inn else None
            _name = (pinv.supplier_name.strip() or None) if pinv.supplier_name else None
            if not _name:
                _inn = None
            supplier_id = None
            if _name:
                supplier = get_or_create_supplier(db, name=_name, inn=_inn)  # уже flush-only
                supplier_id, _name, _inn = supplier.id, supplier.name, supplier.inn

            invoice = Invoice(
                document_id=doc_id, supplier_id=supplier_id, number=pinv.number, date=pinv.date,
                supplier_name=_name, supplier_inn=_inn, vat_rate=_dec(pinv.vat_rate),
                ai_confidence=pinv.confidence,
            )
            db.add(invoice)
            db.flush()

            for item in pinv.items:
                mc_id = _resolve_material_class_id(db, item, document_id=doc_id)
                quantity, unit_price = _dec(item.quantity), _dec(item.unit_price)
                norm = normalize_item(item.unit, quantity, unit_price, aliases)
                db.add(InvoiceItem(
                    invoice_id=invoice.id, raw_name=item.raw_name, item_type=item.item_type,
                    material_class_id=mc_id, quantity=quantity, raw_unit=item.unit,
                    normalized_unit_id=norm.normalized_unit_id if norm else None,
                    normalized_quantity=norm.normalized_quantity if norm else None,
                    normalized_unit_price=norm.normalized_unit_price if norm else None,
                    unit_price=unit_price, amount=_dec(item.amount), vat_amount=_dec(item.vat_amount),
                ))

        doc.status = "parsed"
        doc.last_error = None
        doc.doc_type = "invoice"  # успешный разбор → документ точно СФ
        # (на error-пути doc_type НЕ трогается — см. write_processing_error: документ
        #  хранит живые старые СФ, флип invoice→unknown был бы противоречив.)
        # Атомарный SQL-инкремент (x = x + v) — защита от гонки параллельных разборов.
        doc.parse_cost_usd = Document.parse_cost_usd + outcome.cost_usd
        doc.parse_count = Document.parse_count + outcome.paid_calls
        db.commit()
    except ProcessingError:
        # verified-abort (Task 9) и doc-not-found уже несут cost — не оборачиваем.
        # Мутаций либо не было (raise до тела), либо откатятся close()/rollback вызывающего.
        raise
    except Exception as exc:  # noqa: BLE001 — детерминированный сбой ИЛИ ambiguous commit
        db.rollback()
        raise TransientError(f"Ошибка сохранения (фаза B): {exc}",
                             cost_usd=outcome.cost_usd, paid_calls=outcome.paid_calls) from exc
    logger.info(f"[doc={doc_id}] Фаза B: сохранено СФ {len(outcome.invoices)}, статус parsed")


def get_processing_session_factory():
    """FastAPI-dependency: фабрика сессий для инлайн-обработки (F1).

    Возвращает SessionLocal (поздний импорт — не связываем на этапе модуля, чтобы
    тестовый override и патч database.SessionLocal работали). В тестах переопределяется
    через app.dependency_overrides на тест-фабрику, чтобы обработка видела тест-данные.
    """
    from database import SessionLocal
    return SessionLocal


def _is_connection_error(exc: DBAPIError) -> bool:
    """Потеря соединения по SQLAlchemy-флагу ИЛИ SQLSTATE класса 08 (connection exception).

    Только такие ошибки из commit ретраебельны (запись идемпотентна). Прочие
    OperationalError (deadlock 40P01, lock_timeout, statement cancellation 57014, …)
    и любой другой DBAPIError детерминированы → пробрасываются вызывающим немедленно (F8).
    """
    sqlstate = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
    return bool(exc.connection_invalidated or (sqlstate and str(sqlstate).startswith("08")))


def write_processing_error(session_factory, doc_id: int, message: str, *,
                           cost_usd: Decimal, paid_calls: int, retries: int = 3) -> None:
    """Идемпотентная условная error-запись (§2.3).

    UPDATE ... WHERE status='processing' — при уже закоммитившемся swap (ambiguous
    commit) предикат ложен после ожидания блокировки (EvalPlanQual), rowcount 0.
    Ретраим ТОЛЬКО потерю соединения из самого commit (`connection_invalidated` ИЛИ
    SQLSTATE класса 08 — см. `_is_connection_error`) — запись идемпотентна. Прочие ошибки,
    ВКЛЮЧАЯ не-connection `OperationalError` (deadlock 40P01, lock_timeout, statement
    cancellation 57014) и любой другой `DBAPIError`/Exception, детерминированы → НЕ глотаем,
    пробрасываем, чтобы баг падал в тестах, а не оставлял документ processing молча (F8).
    Исчерпание connection-ретраев → лог critical, документ остаётся processing (доберёт
    startup-sweep S1-4); стоимость этой попытки теряется (at-most-once).
    """
    # doc_type НЕ трогаем: при parse-then-swap error-документ хранит живые старые СФ,
    # флип doc_type invoice→unknown у документа с СФ противоречив (§2.3 SQL его не содержит).
    sql = text(
        "UPDATE documents SET status='error', last_error=:msg, "
        "parse_cost_usd = parse_cost_usd + :cost, parse_count = parse_count + :calls "
        "WHERE id=:id AND status='processing'"
    )
    params = {"msg": message[:_LAST_ERROR_MAXLEN], "cost": cost_usd, "calls": paid_calls, "id": doc_id}
    for attempt in range(1, retries + 1):
        try:
            with session_factory() as db:
                result = db.execute(sql, params)
                db.commit()
            if result.rowcount == 0:
                # rowcount 0: swap уже лёг (parsed), ИЛИ документ удалён/уже error —
                # различить постфактум нельзя; во всех случаях повторно писать нечего.
                logger.warning(f"[doc={doc_id}] error-запись пропущена (rowcount 0): "
                               f"документ не в статусе processing (swap лёг / удалён / уже error)")
            return
        except DBAPIError as exc:
            # Только потеря соединения ретраебельна; прочий DBAPIError (в т.ч. deadlock/
            # lock_timeout/cancel OperationalError, ProgrammingError) детерминирован — проброс.
            if not _is_connection_error(exc):
                raise
            logger.warning(f"[doc={doc_id}] error-запись, попытка {attempt}/{retries} "
                           f"не удалась (потеря соединения): {exc}")
    logger.critical(f"[doc={doc_id}] error-запись НЕ выполнена: БД недоступна. "
                    f"Документ остаётся processing до рестарта/ручного восстановления; "
                    f"стоимость ${cost_usd} не учтена.")


async def run_processing_attempt(session_factory, doc_id: int, *, mode: str,
                                 pdf_bytes: bytes | None = None) -> None:
    """Одна попытка обработки: (скачать байты) → фаза A → фаза B.

    Доменные ошибки (Transient/Permanent) НЕ гасит — пробрасывает наверх с учётом
    стоимости. Это ядро, неизменное между ступенями (обёртки завершения — разные).
    deskew-режим будет расширен в Task 7 (детект + коррекция до фазы A).
    """
    from pdf_parser import parse_pdf  # локальный импорт против кругового; патчится через pdf_parser (F6)
    from s3 import download_file_async

    if pdf_bytes is None:
        with session_factory() as db:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc is None or not doc.s3_key:
                raise PermanentError(f"Документ id={doc_id} без s3_key")
            s3_key = doc.s3_key
        try:
            pdf_bytes = await download_file_async(s3_key)
        except Exception as exc:  # noqa: BLE001
            raise TransientError(f"Не удалось скачать PDF из S3: {exc}") from exc

    outcome = await parse_pdf(pdf_bytes, document_id=doc_id)
    with session_factory() as db:
        persist_parse_result(db, doc_id, outcome)


async def process_document(doc_id: int, *, mode: str, pdf_bytes: bytes | None = None,
                           session_factory=None, reraise: bool = False) -> None:
    """Обёртка ступени 0/1: выполнить попытку, любую доменную ошибку → терминальный error.

    session_factory=None → поздний резолв SessionLocal (F1: не связываем дефолт на этапе
    def — это открывало сессию на реальном dev-DATABASE_URL в тестах и плохо патчилось).

    Всегда пишет status='error' + last_error через условную запись. Если reraise=True
    И ошибка несёт http_status (только ориентация deskew: 413/502) — после записи
    пробрасывает её, чтобы эндпоинт смапил на прежний HTTP-код (AC-S0-8, поведение API
    на S0 не меняется). Ошибки парсинга (http_status=None) не пробрасываются → 200 + error.
    На S1 reraise=False (фоновой таске отвечать некому — контракт §2.2 не ломается).

    CancelledError (обрыв клиента / отмена таски) → error + 'Обработка прервана' + re-raise
    (детерминированный исход, AC-S0-2). Успех фиксируется внутри фазы B.
    """
    if session_factory is None:
        session_factory = get_processing_session_factory()
    try:
        await run_processing_attempt(session_factory, doc_id, mode=mode, pdf_bytes=pdf_bytes)
    except ProcessingError as exc:
        logger.warning(f"[doc={doc_id}] обработка завершилась ошибкой: {exc.message}")
        write_processing_error(session_factory, doc_id, exc.message,
                               cost_usd=exc.cost_usd, paid_calls=exc.paid_calls)
        if reraise and exc.http_status is not None:
            raise
    except asyncio.CancelledError:
        logger.warning(f"[doc={doc_id}] обработка прервана (CancelledError)")
        write_processing_error(session_factory, doc_id, "Обработка прервана",
                               cost_usd=Decimal(0), paid_calls=0)
        raise
    except Exception as exc:  # noqa: BLE001 — подлинно непредвиденное (не ProcessingError)
        logger.exception(f"[doc={doc_id}] непредвиденная ошибка обработки")
        write_processing_error(session_factory, doc_id, f"Ошибка обработки: {exc}",
                               cost_usd=Decimal(0), paid_calls=0)
