"""Тесты guard'а от мутации незапланированной БД (db_guard)."""
import pytest

from db_guard import (
    UNKNOWN_HOST,
    ensure_mutation_allowed,
    is_target_allowed,
    normalize_target,
    parse_extra_targets,
    safe_host,
)

# Хост синтетический: реальный прод-эндпоинт в репозитории и в CI-логах при
# падении не нужен — ни один тест не зависит от его настоящего значения.
REMOTE_HOST = "ep-example-0000.c-3.eu-central-1.aws.neon.tech"
REMOTE_URL = (
    f"postgresql+psycopg://test_owner:secret-pw@{REMOTE_HOST}/neondb"
    "?sslmode=require&channel_binding=require"
)
LOCAL_URL = "postgresql+psycopg://postgres@localhost:5459/udp_dev"


@pytest.fixture(autouse=True)
def _hermetic_guard_env(monkeypatch):
    """Пин APP_ENV и DB_EXTRA_TARGETS через process env.

    Без пина тесты читали бы реальный backend/.env: env_file абсолютный, а
    инструкция плана предписывает вписать туда DB_EXTRA_TARGETS. Тогда «дефолт
    пустой» был бы зелёным в CI (файла нет) и красным у каждого, кто инструкцию
    выполнил. Process env бьёт env_file — тем же механизмом, что и пин.
    """
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DB_EXTRA_TARGETS", "")


def test_normalize_target_builds_triple():
    """DSN → host:port/dbname."""
    assert normalize_target(LOCAL_URL) == "localhost:5459/udp_dev"


def test_normalize_target_drops_query_params():
    """Query-параметры отбрасываются: различие только в них — та же цель."""
    a = "postgresql+psycopg://u@h.example.com:5432/db?sslmode=require"
    b = "postgresql+psycopg://u@h.example.com:5432/db"
    assert normalize_target(a) == normalize_target(b) == "h.example.com:5432/db"


def test_normalize_target_defaults_port():
    """Отсутствующий порт нормализуется в 5432."""
    assert normalize_target("postgresql://u@h.example.com/db") == "h.example.com:5432/db"


def test_normalize_target_lowercases_host():
    """Регистр хоста не создаёт вторую цель."""
    assert normalize_target("postgresql://u@H.Example.COM/db") == "h.example.com:5432/db"


def test_normalize_target_handles_broken_dsn():
    """Битый DSN не роняет нормализацию и даёт нераспознанный хост."""
    assert normalize_target("postgresql://u@[bad:ipv6/db").startswith(UNKNOWN_HOST)


def test_normalize_target_marks_empty_host():
    """Пустой hostname показывается явным маркером, а не пустой строкой."""
    assert normalize_target("postgresql:///db") == f"{UNKNOWN_HOST}:5432/db"


def test_safe_host_hides_credentials():
    """В хосте нет ни пользователя, ни пароля — строка уходит в логи."""
    host = safe_host(REMOTE_URL)
    assert host == REMOTE_HOST
    assert "secret-pw" not in host
    assert "test_owner" not in host


def test_parse_extra_targets_empty():
    """Пустая строка — пустой список."""
    assert parse_extra_targets("") == frozenset()


def test_parse_extra_targets_multiple():
    """Список через запятую, пробелы игнорируются, хост в нижний регистр."""
    raw = "H.Example.com:5432/db1, other.example.com:6000/db2"
    assert parse_extra_targets(raw) == frozenset(
        {"h.example.com:5432/db1", "other.example.com:6000/db2"}
    )


@pytest.mark.parametrize("entry", ["h.example.com/db", "h.example.com:5432", "h.example.com"])
def test_parse_extra_targets_rejects_partial_entry(entry):
    """Неполная тройка — ошибка: иначе allowlist расширился бы до уровня хоста."""
    with pytest.raises(ValueError, match="host:port/dbname"):
        parse_extra_targets(entry)


def test_normalize_target_handles_ipv6_literal():
    """IPv6-литерал в скобках даёт хост без скобок."""
    assert normalize_target("postgresql://u@[::1]:5459/db") == "::1:5459/db"


def test_ipv6_loopback_allowed_without_list():
    """IPv6-loopback разрешён через LOOPBACK_HOSTS, а не через allowlist.

    В DB_EXTRA_TARGETS IPv6 выразить нельзя: разбор записи режет по первому
    двоеточию, и `::1:5459/db` не разбирается. Это осознанный YAGNI — единственная
    нужная IPv6-цель это loopback, а он покрыт LOOPBACK_HOSTS. Появится реальная
    не-loopback IPv6-цель — разбор придётся усложнить.
    """
    assert is_target_allowed("postgresql://u@[::1]:5459/db", frozenset()) is True


def test_loopback_allowed_without_list():
    """Loopback разрешён безусловно — любая база, без DB_EXTRA_TARGETS."""
    assert is_target_allowed(LOCAL_URL, frozenset()) is True
    assert is_target_allowed("postgresql://u@127.0.0.1:5432/anything", frozenset()) is True


def test_remote_target_needs_list():
    """Не-loopback цель без записи в allowlist запрещена."""
    assert is_target_allowed(REMOTE_URL, frozenset()) is False


def test_remote_target_allowed_when_listed():
    """Не-loopback цель разрешена, если её нормализованная тройка в списке."""
    extra = parse_extra_targets(f"{REMOTE_HOST}:5432/neondb")
    assert is_target_allowed(REMOTE_URL, extra) is True


def test_dev_blocks_unlisted_target():
    """При APP_ENV=dev неразрешённая цель прерывает операцию."""
    with pytest.raises(RuntimeError) as exc:
        ensure_mutation_allowed(REMOTE_URL, "alembic")
    assert "APP_ENV=dev" in str(exc.value)


def test_dev_allows_loopback():
    """При APP_ENV=dev loopback проходит без списка."""
    ensure_mutation_allowed(LOCAL_URL, "alembic")


def test_prod_skips_target_check(monkeypatch):
    """При APP_ENV=prod цели не проверяются — роль и есть разрешение."""
    monkeypatch.setenv("APP_ENV", "prod")
    ensure_mutation_allowed(REMOTE_URL, "alembic")


def test_error_names_both_exits():
    """Текст ошибки называет оба выхода: APP_ENV=prod и DB_EXTRA_TARGETS."""
    with pytest.raises(RuntimeError) as exc:
        ensure_mutation_allowed(REMOTE_URL, "alembic")
    message = str(exc.value)
    assert "APP_ENV=prod" in message
    assert "DB_EXTRA_TARGETS" in message


def test_error_target_is_copy_pasteable():
    """Отвергнутая цель напечатана в формате, который принимает DB_EXTRA_TARGETS.

    Требование, не совпадение: пользователь копирует строку из ошибки в
    переменную без редактирования.
    """
    with pytest.raises(RuntimeError) as exc:
        ensure_mutation_allowed(REMOTE_URL, "alembic")
    target = normalize_target(REMOTE_URL)
    assert target in str(exc.value)
    assert parse_extra_targets(target) == frozenset({target})


def test_error_leaks_no_password():
    """Пароль из DSN не попадает в сообщение."""
    with pytest.raises(RuntimeError) as exc:
        ensure_mutation_allowed(REMOTE_URL, "cli create-superuser")
    assert "secret-pw" not in str(exc.value)
