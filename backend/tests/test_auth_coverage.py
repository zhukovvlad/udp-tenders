"""Тест-сторож: все ручки (кроме явно публичных) должны возвращать 401 без токена.

Этот тест навсегда фиксирует инвариант: новая ручка не может случайно оказаться публичной.
Если тест упадёт — значит добавили новый роутер без auth dependency.
"""
import pytest
from fastapi.testclient import TestClient

from main import app

# Ручки, открытые намеренно — без аутентификации
PUBLIC_PATHS: set[str] = {
    "/api/auth/login",    # единственный вход до получения куки
    "/api/health",        # health-check для мониторинга
    "/docs",              # Swagger UI
    "/openapi.json",      # OpenAPI схема
    "/redoc",             # ReDoc
    "/docs/oauth2-redirect",
}


def _collect_routes() -> list[tuple[str, str]]:
    """Собрать все ручки из app.routes как (method, path)."""
    result = []
    for route in app.routes:
        if not hasattr(route, "methods"):
            continue
        for method in route.methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            result.append((method, route.path))
    return result


@pytest.mark.parametrize("method,path", _collect_routes())
def test_endpoint_requires_auth(method: str, path: str) -> None:
    """Убедиться, что ручка возвращает 401 или 403 при отсутствии токена.

    Для публичных ручек тест пропускается.
    """
    if path in PUBLIC_PATHS:
        pytest.skip("Публичный endpoint — auth не требуется")

    # Подставляем валидные числовые id в path-параметры
    test_path = path
    for placeholder in ["{project_id}", "{id}", "{document_id}", "{org_id}"]:
        test_path = test_path.replace(placeholder, "1")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.request(method, test_path)
    assert response.status_code in (401, 403), (
        f"{method} {path} вернул {response.status_code} без аутентификации — "
        "добавь auth dependency к роутеру."
    )
