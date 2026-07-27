"""Тесты guard'а от случайной записи в Neon (db_guard)."""
import pytest

from db_guard import (
    ALLOW_ENV,
    ensure_write_allowed,
    is_neon_url,
    neon_writes_allowed,
    safe_host,
)

# Хост синтетический: реальный прод-эндпоинт в репозитории (и в CI-логах при
# падении) не нужен — ни один тест не зависит от его настоящего значения.
NEON_HOST = "ep-example-0000.c-3.eu-central-1.aws.neon.tech"
NEON_URL = (
    f"postgresql+psycopg://test_owner:secret-pw@{NEON_HOST}/neondb"
    "?sslmode=require&channel_binding=require"
)
LOCAL_URL = "postgresql+psycopg://postgres@localhost:5459/udp_dev"


@pytest.fixture(autouse=True)
def _clear_allow_env(monkeypatch):
    """Убрать ALLOW_NEON_WRITES из окружения — тесты задают его сами."""
    monkeypatch.delenv(ALLOW_ENV, raising=False)


def test_is_neon_url_detects_neon_host():
    """Хост Neon распознаётся по домену neon.tech."""
    assert is_neon_url(NEON_URL) is True


def test_is_neon_url_rejects_local():
    """Локальный DSN не считается Neon."""
    assert is_neon_url(LOCAL_URL) is False


def test_is_neon_url_handles_empty():
    """Пустой DSN не роняет проверку."""
    assert is_neon_url("") is False


def test_is_neon_url_ignores_neon_in_credentials():
    """neon.tech в пароле/имени БД не должен считаться Neon-хостом.

    Проверка идёт по hostname, а не по подстроке во всём DSN — иначе локальная
    база с таким паролем ложно блокировалась бы.
    """
    tricky = "postgresql+psycopg://user:neon.tech@localhost:5459/udp_dev"
    assert is_neon_url(tricky) is False


def test_is_neon_url_requires_domain_suffix():
    """Похожий домен не считается Neon — сравнение по суффиксу, не подстрокой."""
    assert is_neon_url("postgresql://u@myneon.techie.example.com/db") is False


def test_is_neon_url_matches_bare_domain():
    """Сам домен neon.tech без поддомена тоже распознаётся."""
    assert is_neon_url("postgresql://u@neon.tech/db") is True


def test_safe_host_survives_malformed_url():
    """Битый DSN не роняет извлечение хоста (urlsplit кидает ValueError)."""
    assert safe_host("postgresql://u@[bad:ipv6/db") == ""


def test_safe_host_hides_credentials():
    """В хосте нет ни пользователя, ни пароля — их нельзя светить в ошибке."""
    host = safe_host(NEON_URL)
    assert host == NEON_HOST
    assert "secret-pw" not in host
    assert "test_owner" not in host


def test_local_url_always_allowed():
    """Локальная цель не требует разрешения."""
    ensure_write_allowed(LOCAL_URL, "alembic")


def test_neon_url_blocked_without_allow():
    """Без ALLOW_NEON_WRITES запись в Neon отклоняется."""
    with pytest.raises(RuntimeError) as exc:
        ensure_write_allowed(NEON_URL, "alembic")
    assert "Neon" in str(exc.value)


def test_block_message_leaks_no_password():
    """Сообщение об ошибке не содержит пароль из DSN."""
    with pytest.raises(RuntimeError) as exc:
        ensure_write_allowed(NEON_URL, "cli create-superuser")
    message = str(exc.value)
    assert "secret-pw" not in message
    assert "cli create-superuser" in message


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " 1 "])
def test_allow_env_truthy_values(monkeypatch, value):
    """Признанные истинные значения разрешают запись в Neon."""
    monkeypatch.setenv(ALLOW_ENV, value)
    assert neon_writes_allowed() is True
    ensure_write_allowed(NEON_URL, "alembic")


@pytest.mark.parametrize("value", ["", "0", "false", "no", "maybe"])
def test_allow_env_falsy_values(monkeypatch, value):
    """Всё остальное — запрет; неизвестное значение трактуется как «нет»."""
    monkeypatch.setenv(ALLOW_ENV, value)
    assert neon_writes_allowed() is False
    with pytest.raises(RuntimeError):
        ensure_write_allowed(NEON_URL, "alembic")
