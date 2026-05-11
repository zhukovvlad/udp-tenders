"""Глобальные фикстуры для всех тестов backend.

Слои:
* Unit-тесты используют только in-memory моки (mock_s3, mock_openrouter).
* Integration-тесты используют реальный Postgres (через TEST_DATABASE_URL),
  но Alembic мигрирует один раз на сессию. Каждый тест — в транзакции с rollback.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Делаем импорты "from database import ..." и "import crud" работающими
# из тестов, не привязываясь к sys.path в IDE
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture(autouse=True)
def block_real_openrouter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Защитный assert: ни один тест не должен ходить в реальный OpenRouter.

    Если test забыл подключить mock_openrouter и пытается вызвать реальный API —
    падаем с понятным сообщением. Применяется автоматически ко ВСЕМ тестам.
    """
    real_url = "https://openrouter.ai"

    def _fail(*args, **kwargs):  # noqa: ANN001,ANN202
        raise RuntimeError(
            "Тест попытался обратиться к реальному OpenRouter. "
            "Используй фикстуру `mock_openrouter` или замокай `httpx.AsyncClient.post`."
        )

    # Перехватываем глобально на уровне httpx — если кто-то создаст AsyncClient и пошлёт POST
    # на openrouter.ai, мы об этом узнаем
    import httpx

    original_send = httpx.AsyncClient.send

    async def guarded_send(self, request: httpx.Request, *args, **kwargs):  # noqa: ANN001,ANN202
        if real_url in str(request.url):
            _fail()
        return await original_send(self, request, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", guarded_send)


@pytest.fixture
def in_memory_s3(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    """In-memory подмена S3. Возвращает dict, в котором ключ = object_name, значение = bytes."""
    storage: dict[str, bytes] = {}

    def fake_upload(file_bytes: bytes, object_name: str) -> str:
        storage[object_name] = file_bytes
        return object_name

    def fake_download(object_name: str) -> bytes:
        if object_name not in storage:
            raise FileNotFoundError(object_name)
        return storage[object_name]

    def fake_delete(object_name: str) -> None:
        storage.pop(object_name, None)

    def fake_ensure_bucket() -> None:
        pass

    import s3

    monkeypatch.setattr(s3, "upload_file", fake_upload)
    monkeypatch.setattr(s3, "download_file", fake_download)
    monkeypatch.setattr(s3, "delete_file", fake_delete)
    monkeypatch.setattr(s3, "ensure_bucket", fake_ensure_bucket)
    # Routers импортируют функции напрямую, нужно патчить и там
    from routers import invoices as invoices_router

    monkeypatch.setattr(invoices_router, "upload_file", fake_upload)
    monkeypatch.setattr(invoices_router, "download_file", fake_download)
    monkeypatch.setattr(invoices_router, "delete_file", fake_delete)
    monkeypatch.setattr(invoices_router, "ensure_bucket", fake_ensure_bucket)

    return storage


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Минимальный валидный PDF (~250 байт). Содержимое не важно — бэкенд только пересылает в OpenRouter."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"0000000009 00000 n\n0000000052 00000 n\n0000000092 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n145\n%%EOF\n"
    )


@pytest.fixture(scope="session")
def db_engine() -> Iterator:
    """Engine на TEST_DATABASE_URL. Накатывает Alembic один раз на сессию."""
    test_url = os.getenv("TEST_DATABASE_URL")
    if not test_url:
        pytest.skip("TEST_DATABASE_URL не задан — integration tests пропущены")

    engine = create_engine(test_url, pool_pre_ping=True)

    # Безопасность: отказываемся работать, если TEST_DATABASE_URL совпадает с прод DATABASE_URL.
    # DROP SCHEMA — деструктивная операция; ошибка конфигурации = катастрофа.
    prod_url = os.getenv("DATABASE_URL", "")
    if prod_url and test_url == prod_url:
        pytest.skip(
            "TEST_DATABASE_URL совпадает с DATABASE_URL — отказ от DROP SCHEMA на проде"
        )

    # Накатываем миграции через Alembic
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", test_url)

    # Сбрасываем схему перед накатом — гарантируем чистый старт
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    command.upgrade(cfg, "head")

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Iterator[Session]:
    """Транзакционная фикстура. Каждый тест в своей транзакции, rollback после."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        autoflush=False,
        autocommit=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session, in_memory_s3) -> Iterator:
    """FastAPI TestClient с переопределённым get_db."""
    from fastapi.testclient import TestClient
    from main import app
    from database import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # cleanup в db_session фикстуре

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def factories(db_session):
    """Регистрирует db_session в фабриках. Возвращает модуль с фабриками."""
    from tests import factories as f

    f._register_session(db_session)
    return f
