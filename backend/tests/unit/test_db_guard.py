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


def test_safe_host_survives_malformed_url():
    """Битый DSN не роняет извлечение хоста (urlsplit кидает ValueError).

    is_target_allowed полагается на то, что safe_host никогда не бросает —
    поведение load-bearing, а до этого теста было ничем не покрыто.
    """
    assert safe_host("postgresql://u@[bad:ipv6/db") == ""


def test_safe_host_handles_empty():
    """Пустой DSN не роняет извлечение хоста и не даёт ложный loopback."""
    assert safe_host("") == ""


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


@pytest.mark.parametrize("entry", ["h.example.com:²/db", "h.example.com:99999999/db"])
def test_parse_extra_targets_rejects_invalid_port(entry):
    """Юникодная цифра в порте и порт вне 0-65535 — та же ошибка формата.

    '²'.isdigit() is True, но int('²') бросает ValueError с чужим
    текстом — без явной проверки isascii() отвергнутая запись падала бы не
    предсказуемым сообщением этой функции, а трассой int().
    """
    with pytest.raises(ValueError, match="host:port/dbname"):
        parse_extra_targets(entry)


def test_parse_extra_targets_rejects_unknown_host_marker():
    """UNKNOWN_HOST как запись — ошибка, а не заготовка allowlist на все битые DSN.

    UNKNOWN_HOST — маркер нераспознанного хоста в тексте ошибки
    ensure_mutation_allowed; будь он разрешённым host в DB_EXTRA_TARGETS,
    copy-paste из ошибки разрешил бы мутацию для любого хостless/битого DSN
    с тем же портом и именем БД.
    """
    with pytest.raises(ValueError, match="host:port/dbname"):
        parse_extra_targets(f"{UNKNOWN_HOST}:5432/db")


def test_normalize_target_handles_ipv6_literal():
    """IPv6-литерал в скобках даёт хост без скобок."""
    assert normalize_target("postgresql://u@[::1]:5459/db") == "::1:5459/db"


@pytest.mark.parametrize(
    "query",
    ["host=prod.example.com", "port=6543", "dbname=other_db"],
)
def test_normalize_target_rejects_query_key_override(query):
    """`?host=`/`port=`/`dbname=` не дают матчируемую тройку из netloc.

    psycopg-диалект SQLAlchemy делает `opts.update(url.query)` при сборке
    connect-args — эти query-ключи ЗАМЕЩАЮТ значение из netloc в реальном
    подключении, а не дополняют его (проверено эмпирически: `create_connect_args`
    на `postgresql+psycopg://u@localhost:5459/udp_dev?host=prod.example.com`
    даёт `{'host': 'prod.example.com', ...}`). Единица сравнения из netloc в
    этом случае описывает не ту цель, к которой реально подключится psycopg —
    поэтому normalize_target обязан дать UNKNOWN_HOST, а не тройку по netloc.
    """
    url = f"postgresql+psycopg://u@localhost:5459/udp_dev?{query}"
    result = normalize_target(url)
    assert result.startswith(UNKNOWN_HOST)
    # UNKNOWN_HOST не разбирается parse_extra_targets — такая цель не может
    # совпасть ни с одной записью DB_EXTRA_TARGETS.
    with pytest.raises(ValueError):
        parse_extra_targets(result)


@pytest.mark.parametrize(
    "query",
    ["host=prod.example.com", "port=6543", "dbname=other_db"],
)
def test_is_target_allowed_denies_loopback_with_query_key_override(query):
    """`?host=`/`port=`/`dbname=` на loopback-netloc не проходят loopback-шорткат.

    Без этой проверки `is_target_allowed` смотрел бы на `safe_host(url)` ==
    "localhost" и пропускал бы мутацию, хотя реальное соединение (через
    psycopg-диалект) уйдёт на цель, заданную query-ключом — ровно дыра,
    которую реализация guard'а обязана закрывать.
    """
    url = f"postgresql+psycopg://u@localhost:5459/udp_dev?{query}"
    assert is_target_allowed(url, frozenset()) is False


def test_is_target_allowed_still_ignores_ordinary_query_params():
    """Обычные query-параметры (sslmode, channel_binding, ...) не меняют цель.

    Существующее поведение (см. test_normalize_target_drops_query_params) не
    должно пострадать от точечного исключения для host/port/dbname.
    """
    url = "postgresql+psycopg://u@localhost:5459/udp_dev?sslmode=require&channel_binding=require"
    assert is_target_allowed(url, frozenset()) is True


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


def test_dev_allows_target_from_env_list(monkeypatch):
    """DB_EXTRA_TARGETS из окружения действительно снимает запрет.

    Без этого теста ensure_mutation_allowed мог бы игнорировать
    settings.DB_EXTRA_TARGETS целиком (например, звать
    parse_extra_targets("") вместо parse_extra_targets(s.DB_EXTRA_TARGETS)) —
    остальные 23 теста модуля остались бы зелёными, а единственный
    пользовательский escape hatch был бы мёртв.
    """
    monkeypatch.setenv("DB_EXTRA_TARGETS", normalize_target(REMOTE_URL))
    ensure_mutation_allowed(REMOTE_URL, "alembic")


def test_error_lists_configured_targets(monkeypatch):
    """При непустом DB_EXTRA_TARGETS текст ошибки перечисляет его, а не «пусто».

    Покрывает ветку `", ".join(sorted(extra))` — до этого теста исполнялась
    только ветка "сейчас пусто".
    """
    other = "other.example.com:5432/otherdb"
    monkeypatch.setenv("DB_EXTRA_TARGETS", other)
    with pytest.raises(RuntimeError) as exc:
        ensure_mutation_allowed(REMOTE_URL, "alembic")
    message = str(exc.value)
    assert other in message
    assert "сейчас пусто" not in message


def test_ensure_mutation_allowed_propagates_malformed_extra_targets(monkeypatch):
    """Неполная запись в DB_EXTRA_TARGETS даёт ValueError, а не RuntimeError.

    ensure_mutation_allowed сам формат не проверяет — это ошибка конфигурации
    (опечатка в backend/.env), которая обязана падать иначе, чем штатный отказ
    guard'а, а не быть проглочена под RuntimeError на стартовом пути.
    """
    monkeypatch.setenv("DB_EXTRA_TARGETS", "h.example.com")
    with pytest.raises(ValueError, match="host:port/dbname"):
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
