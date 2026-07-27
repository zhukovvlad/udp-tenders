"""Тесты обвязки db_guard: что точки входа его действительно зовут.

Отдельно от test_db_guard.py, который проверяет сам модуль. Смысл именно в
обвязке: удалить вызов `_guard(...)` из команды cli или переставить
`ensure_write_allowed` ниже создания движка в alembic/env.py — и все тесты
чистого модуля останутся зелёными. Здесь ловится ровно это.
"""
from pathlib import Path

import pytest
from click.testing import CliRunner

import cli
import main
from db_guard import ALLOW_ENV

NEON_URL = (
    "postgresql+psycopg://test_owner:secret-pw@"
    "ep-example-0000.c-3.eu-central-1.aws.neon.tech/neondb"
)


@pytest.fixture(autouse=True)
def _neon_target_without_permission(monkeypatch):
    """Цель — Neon, разрешения нет: базовое состояние для всех тестов файла."""
    monkeypatch.delenv(ALLOW_ENV, raising=False)
    monkeypatch.setattr(cli.settings, "DATABASE_URL", NEON_URL, raising=False)


@pytest.fixture
def no_db_session(monkeypatch):
    """Взорваться, если команда всё же дошла до открытия сессии.

    Guard обязан срабатывать ДО SessionLocal() — иначе «fail-fast» на деле
    означает коннект к прод-базе и только потом отказ.
    """
    def _explode():
        raise AssertionError("SessionLocal() вызван — guard сработал слишком поздно")

    monkeypatch.setattr(cli, "SessionLocal", _explode)


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("create-superuser", ["--email", "a@b.c", "--password", "pw"]),
        ("create-org", ["--name", "Орг"]),
        ("create-user", ["--email", "a@b.c", "--org-id", "1", "--password", "pw"]),
    ],
)
def test_cli_commands_refuse_neon_target(command, args, no_db_session):
    """Каждая мутирующая cli-команда отказывается писать в Neon."""
    result = CliRunner().invoke(cli.cli, [command, *args])
    assert result.exit_code != 0
    assert isinstance(result.exception, RuntimeError)
    assert "Neon" in str(result.exception)


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("create-superuser", ["--email", "a@b.c", "--password", "pw"]),
        ("create-org", ["--name", "Орг"]),
        ("create-user", ["--email", "a@b.c", "--org-id", "1", "--password", "pw"]),
    ],
)
def test_cli_commands_pass_guard_when_allowed(command, args, monkeypatch):
    """С ALLOW_NEON_WRITES=1 guard пропускает — падение уже на уровне БД.

    Проверяем именно, что барьер снят: до SessionLocal команда доходит.
    """
    monkeypatch.setenv(ALLOW_ENV, "1")
    reached = []

    def _record():
        reached.append(True)
        raise RuntimeError("stop-here")

    monkeypatch.setattr(cli, "SessionLocal", _record)
    CliRunner().invoke(cli.cli, [command, *args])
    assert reached, "guard не пустил дальше, хотя запись разрешена"


def test_startup_sweep_refuses_neon_target(monkeypatch):
    """Sweep на старте приложения не идёт в Neon без разрешения."""
    monkeypatch.delenv(ALLOW_ENV, raising=False)
    monkeypatch.setattr(main.settings, "DATABASE_URL", NEON_URL, raising=False)
    with pytest.raises(RuntimeError, match="startup-sweep"):
        main._sweep_stuck_documents()


def test_startup_sweep_skips_guard_for_injected_factory():
    """С инжектированной фабрикой guard не при чём — цель заведомо тестовая.

    Иначе интеграционные тесты (они подменяют фабрику) требовали бы
    ALLOW_NEON_WRITES только из-за прод-строки в backend/.env.
    """
    class _Result:
        rowcount = 0

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, *_args):
            return _Result()

        def commit(self):
            pass

    assert main._sweep_stuck_documents(session_factory=_Session) == 0


def test_alembic_env_guards_before_engine():
    """alembic/env.py зовёт guard до создания движка.

    Проверка по исходнику: рантайм-запуск env.py потребовал бы живой БД, а
    важен именно порядок — guard обязан стоять выше engine_from_config.
    """
    source = Path(main.__file__).parent / "alembic" / "env.py"
    text = source.read_text(encoding="utf-8")
    guard_at = text.index("ensure_write_allowed(")
    engine_at = text.index("engine_from_config(")
    assert guard_at < engine_at, "guard оказался ниже создания движка"
