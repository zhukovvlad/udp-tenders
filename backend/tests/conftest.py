"""Глобальные фикстуры для всех тестов backend.

Слои:
* Unit-тесты используют только in-memory моки (mock_s3, mock_openrouter).
* Integration-тесты используют реальный Postgres (через TEST_DATABASE_URL),
  но Alembic мигрирует один раз на сессию. Каждый тест — в транзакции с rollback.
"""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import httpx as _httpx_module
import pytest
import respx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Делаем импорты "from database import ..." и "import crud" работающими
# из тестов, не привязываясь к sys.path в IDE
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# Гарантируем наличие SECRET_KEY (HS256) до импорта backend-модулей.
# Settings() вызывается при первом импорте config.py (на который ссылается database.py и др.).
# В CI и при локальных unit-тестах .env может отсутствовать — этот setdefault
# подставляет тестовое значение, не перетирая реальный SECRET_KEY из .env.
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-production-32ch!!")

# Сохраняем оригинальный httpx.AsyncClient.send в момент импорта conftest,
# ДО того, как block_real_openrouter автоматически заменит его на guard.
# Используется в mock_openrouter для восстановления рабочего send (вместо
# delattr, который сносит атрибут целиком и оставляет AsyncClient без send).
_REAL_ASYNC_CLIENT_SEND = _httpx_module.AsyncClient.send


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


@pytest.fixture(autouse=True)
def no_real_minio_on_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    """ensure_bucket() в lifespan не должен ходить в реальный MinIO из тестов.

    Каждый `with TestClient(app)` гоняет lifespan → ensure_bucket(). Без подмены
    каждый тест платит за попытку соединения с мёртвым localhost:9000
    (~26с на Windows c firewall-drop, ~3-4с на Linux CI с ретраями boto3) —
    именно это делало полный прогон 20+ минут. main.py вызывает s3.ensure_bucket()
    с поздним связыванием, поэтому патча модуля s3 достаточно.
    """
    import s3

    monkeypatch.setattr(s3, "ensure_bucket", lambda: None)


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
    # Routers импортируют функции напрямую, нужно патчить и там. upload_pdf вызывает
    # upload_file_async (S0-6) — та же функция, что и в модуле s3 (bind на импорте),
    # анлочит через уже пропатченный s3.upload_file (thread-обёртка резолвит имя лениво) —
    # отдельный патч не нужен. ensure_bucket роутер больше не импортирует (bucket — lifespan).
    from routers import invoices as invoices_router

    monkeypatch.setattr(invoices_router, "download_file", fake_download)
    monkeypatch.setattr(invoices_router, "delete_file", fake_delete)

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
def client(db_session, in_memory_s3, session_factory_test) -> Iterator:
    """FastAPI TestClient с переопределёнными зависимостями для интеграционных тестов.

    - get_db заменяется на транзакционную сессию с rollback после теста.
    - get_current_user заменяется на мок суперюзера (auth-флоу тестируется отдельно).
    - get_processing_session_factory заменяется на тест-фабрику (session_factory_test) —
      иначе эндпоинты, доходящие до process_document, открыли бы сессию на реальном
      dev-DATABASE_URL вместо тестовой транзакции (F1).
    - CSRF-токен: клиент отправляет test-значение и в куки, и в заголовок,
      чтобы csrf_middleware пропускал все запросы.
    """
    from unittest.mock import MagicMock

    from fastapi.testclient import TestClient

    from auth import get_current_user
    from database import get_db
    from main import app
    from processing import get_processing_session_factory

    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # cleanup в db_session фикстуре

    def override_get_current_user():
        """Возвращает мок суперюзера — пропускает всю логику JWT/cookie."""
        user = MagicMock()
        user.id = 1
        user.is_superuser = True
        user.org_id = None
        user.org_role = None
        user.is_active = True
        return user

    # CSRF double-submit: одно и то же значение в куки и заголовке
    _csrf_token = "test-csrf-token"

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_processing_session_factory] = lambda: session_factory_test
    with TestClient(app, headers={"X-CSRF-Token": _csrf_token}) as c:
        c.cookies.set("csrf_token", _csrf_token)
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def session_factory_test(db_session):
    """Фабрика сессий, отдающая ту же транзакционную тест-сессию.

    process_document по контракту открывает сессию сам через session_factory;
    в тестах инжектим фабрику, возвращающую db_session, чтобы обработка видела
    данные теста и откатывалась вместе с ним. Контекст-менеджер (__enter__/__exit__)
    имитирован, но close/commit проксируются на общую сессию без реального закрытия.
    """
    from contextlib import contextmanager

    @contextmanager
    def factory():
        """Контекст-менеджер, отдающий общую тест-сессию без реального закрытия."""
        yield db_session  # не закрываем — управляет фикстура db_session

    return factory


@pytest.fixture
def factories(db_session):
    """Регистрирует db_session в фабриках. Возвращает модуль с фабриками.

    После теста сбрасываем session-holder, чтобы стейл-ссылка на закрытую
    сессию не пережила тест и не дала путаницу при следующем создании фабрики.
    """
    from tests import factories as f

    f._register_session(db_session)
    yield f
    f._register_session(None)


@pytest.fixture
def openrouter_fixtures_dir() -> Path:
    return BACKEND_ROOT / "tests" / "fixtures" / "openrouter"


@pytest.fixture
def mock_openrouter(openrouter_fixtures_dir, monkeypatch):
    """Подменяет OpenRouter. По умолчанию — happy_path. Меняй сценарий через .use_scenario().

    Восстанавливаем оригинальный AsyncClient.send (вместо delattr, который
    сносит атрибут с класса и ломает все httpx-вызовы). respx работает на
    transport-уровне, оригинальный send через него корректно проходит.

    Использование:
        def test_xxx(client, mock_openrouter):
            mock_openrouter.use_scenario("unparseable")
            client.post("/api/invoices/upload", ...)
            assert len(mock_openrouter.calls) == 1
            req_body = mock_openrouter.last_request_json()
            assert "messages" in req_body
    """
    monkeypatch.setattr(_httpx_module.AsyncClient, "send", _REAL_ASYNC_CLIENT_SEND)

    class _Mock:
        def __init__(self):
            self.scenario = "happy_path"
            self.calls = []
            self.status_code = 200
            self.raw_body = None

        def use_scenario(self, name: str) -> None:
            self.scenario = name

        def use_http_status(self, code: int) -> None:
            """Задаёт HTTP-статус, который вернёт мок OpenRouter вместо 200."""
            self.status_code = code

        def use_raw_body(self, body: bytes) -> None:
            """Заставляет мок вернуть сырое (не-JSON) тело вместо фикстуры-сценария."""
            self.raw_body = body

        def _load(self) -> dict:
            path = openrouter_fixtures_dir / f"{self.scenario}.json"
            if not path.exists():
                available = sorted(p.stem for p in openrouter_fixtures_dir.glob("*.json"))
                raise FileNotFoundError(
                    f"mock_openrouter: нет фикстуры для сценария '{self.scenario}'. "
                    f"Доступны: {available}"
                )
            return json.loads(path.read_text(encoding="utf-8"))

        def last_request_json(self) -> dict | None:
            """Возвращает JSON тела последнего перехваченного запроса или None."""
            if not self.calls:
                return None
            return json.loads(self.calls[-1].content)

        def __enter__(self):
            self._respx = respx.mock(base_url="https://openrouter.ai", assert_all_called=False)
            self._respx.start()

            def handler(request):
                self.calls.append(request)
                if self.raw_body is not None:
                    return _httpx_module.Response(self.status_code, content=self.raw_body)
                return _httpx_module.Response(self.status_code, json=self._load())

            self._respx.post("/api/v1/chat/completions").mock(side_effect=handler)
            return self

        def __exit__(self, *exc):
            self._respx.stop()

    with _Mock() as m:
        yield m
