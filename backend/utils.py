"""Вспомогательные утилиты для backend."""
from fastapi import Request


def get_client_ip(request: Request) -> str | None:
    """Возвращает реальный IP клиента с учётом reverse-proxy.

    Читает заголовок X-Forwarded-For (добавляется Nginx/Caddy перед приложением).
    Если заголовка нет — берёт request.client.host напрямую.
    Может вернуть None, если приложение запущено без ASGI-сокета (unit-тесты).
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # X-Forwarded-For: client, proxy1, proxy2 — берём самый левый
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
