"""Лимит параллельных фоновых обработок (PROCESSING_CONCURRENCY)."""
import asyncio

import processing
from config import settings


async def test_process_document_limits_concurrency(monkeypatch):
    """Одновременно исполняется не больше PROCESSING_CONCURRENCY попыток, остальные ждут."""
    monkeypatch.setattr(settings, "PROCESSING_CONCURRENCY", 2)
    active = 0
    peak = 0

    async def fake_attempt(session_factory, doc_id, **kwargs):
        """Считает пик одновременно активных попыток."""
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
    monkeypatch.setattr(processing, "run_processing_attempt", fake_attempt)

    await asyncio.gather(*(processing.process_document(i, mode="parse", session_factory=object())
                           for i in range(6)))

    assert peak == 2


async def test_process_document_cancelled_while_waiting_for_slot_writes_error(monkeypatch):
    """Отмена в очереди на слот → терминальный error «Обработка прервана» + CancelledError наружу."""
    monkeypatch.setattr(settings, "PROCESSING_CONCURRENCY", 1)
    release = asyncio.Event()
    errors: list[tuple[int, str]] = []

    async def blocking_attempt(session_factory, doc_id, **kwargs):
        """Держит единственный слот до сигнала."""
        await release.wait()
    monkeypatch.setattr(processing, "run_processing_attempt", blocking_attempt)

    def fake_write_error(session_factory, doc_id, message, **kwargs):
        """Фиксирует error-запись вместо обращения к БД."""
        errors.append((doc_id, message))
    monkeypatch.setattr(processing, "write_processing_error", fake_write_error)

    holder = asyncio.create_task(processing.process_document(1, mode="parse", session_factory=object()))
    await asyncio.sleep(0)
    waiter = asyncio.create_task(processing.process_document(2, mode="parse", session_factory=object()))
    await asyncio.sleep(0)
    waiter.cancel()
    try:
        await waiter
        raise AssertionError("ожидался CancelledError")
    except asyncio.CancelledError:
        pass
    release.set()
    await holder

    assert errors == [(2, "Обработка прервана")]
