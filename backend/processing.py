"""Ядро обработки документов: парсинг (фаза A) + персистенция (фаза B).

См. docs/superpowers/specs/2026-07-16-async-processing-design.md.
На ступени 0 process_document вызывается инлайн (await в хэндлере).
"""
from decimal import Decimal


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
