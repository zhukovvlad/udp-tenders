"""Guard от мутации незапланированной БД.

Ось — **роль окружения**, а не вендор БД: прод не обязательно Neon. Развёртывание
возможно и на сервере компании (БД локальная или в докере), и на стороннем
хостинге. Вендорная ось не защищала первый случай и ломала второй.

При `APP_ENV=dev` (дефолт) мутировать разрешено loopback-цели и нормализованные
записи `DB_EXTRA_TARGETS`. При `APP_ENV=prod` цели не проверяются: декларация роли
и есть разрешение — цель прода и есть его `DATABASE_URL`.

ВАЖНО про loopback: правило «любая база на loopback мутируема без allowlist»
держится, только пока loopback — действительно локальный процесс. SSH-туннель
или `kubectl port-forward`, пробрасывающие удалённую БД на локальный порт,
делают её неотличимой от настоящего localhost — guard её пропустит без
объявления в DB_EXTRA_TARGETS. Осознанный компромисс дизайна (loopback как
источник доверия), а не дыра в проверке; при таком паттерне работы это стоит
держать в уме на ревью операций.

Спека: docs/superpowers/specs/2026-07-27-deploy-env-contract-design.md
"""
from urllib.parse import urlsplit

DEFAULT_PG_PORT = 5432
MAX_PG_PORT = 65535
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
UNKNOWN_HOST = "<нераспознанный хост>"


def safe_host(url: str) -> str:
    """Хост из DSN без креденшелов — пароль не должен попасть в текст ошибки."""
    if not url:
        return ""
    try:
        return (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def normalize_target(url: str) -> str:
    """DSN → нормализованная цель `host:port/dbname`.

    Единица сравнения включает имя БД, потому что CI различает свои цели только
    им: `localhost:5432/postgres` против `localhost:5432/udp_test`.
    Query-параметры отбрасываются — цели, различающиеся только ими, это одна
    цель. Пустой или неразбираемый хост даёт `UNKNOWN_HOST`: такая цель не
    loopback и ни с чем не совпадает (fail-closed).
    """
    try:
        parts = urlsplit(url or "")
        host = (parts.hostname or "").lower().rstrip(".") or UNKNOWN_HOST
        port = parts.port or DEFAULT_PG_PORT
        # dbname сравнивается литералом: без unquote() и без lower() —
        # "/db%2Dname" и "/db-name" считаются разными целями. Это fail-closed
        # в безопасную сторону: лишняя запись в allowlist не совпадёт с
        # настоящей целью, а не наоборот.
        dbname = (parts.path or "").lstrip("/")
    except ValueError:
        return f"{UNKNOWN_HOST}:{DEFAULT_PG_PORT}/"
    return f"{host}:{port}/{dbname}"


def parse_extra_targets(raw: str) -> frozenset[str]:
    """Разобрать `DB_EXTRA_TARGETS` — список `host:port/dbname` через запятую.

    Каждая запись обязана быть полной тройкой: хост, порт в диапазоне
    0-65535 и имя БД. Порт проверяется через `isdigit() and isascii()`, а не
    только `isdigit()`: юникодные цифры вроде "²" проходят `str.isdigit()`, но
    `int()` их не принимает — без явной проверки ASCII отвергнутая запись
    падала бы с чужой трассой `int()` вместо предсказуемого `ValueError` этой
    функции. Хост `UNKNOWN_HOST` отдельно запрещён как запись: это маркер
    нераспознанного DSN, который печатает `ensure_mutation_allowed` в тексте
    ошибки, и его copy-paste в DB_EXTRA_TARGETS разрешил бы мутацию для ЛЮБОГО
    хостless или неразбираемого DSN с тем же портом и именем БД. Запись без
    порта или без имени БД незаметно расширила бы allowlist до уровня хоста,
    что противоречит выбору единицы сравнения, поэтому это тоже ошибка, а не
    «любая база на этом хосте».

    Raises:
        ValueError: запись не имеет вида `host:port/dbname`, порт вне
            диапазона 0-65535 или хост равен `UNKNOWN_HOST`.
    """
    targets = set()
    for chunk in (raw or "").split(","):
        entry = chunk.strip()
        if not entry:
            continue
        host, _, tail = entry.partition(":")
        port, _, dbname = tail.partition("/")
        host = host.lower().rstrip(".")
        valid_port = port.isdigit() and port.isascii() and int(port) <= MAX_PG_PORT
        if not host or host == UNKNOWN_HOST or not valid_port or not dbname:
            raise ValueError(
                f"DB_EXTRA_TARGETS: запись '{entry}' должна иметь вид host:port/dbname"
            )
        targets.add(f"{host}:{int(port)}/{dbname}")
    return frozenset(targets)


def is_target_allowed(url: str, extra: frozenset[str]) -> bool:
    """Разрешена ли цель в dev: loopback (любая база) или запись из allowlist."""
    if safe_host(url) in LOOPBACK_HOSTS:
        return True
    return normalize_target(url) in extra


def ensure_mutation_allowed(url: str, action: str) -> None:
    """Прервать `action`, если цель не разрешена для текущего `APP_ENV`.

    Args:
        url: DSN цели, которую собираются мутировать. Именно цель операции, а не
            `settings.DATABASE_URL`: в `db-test-migrate` она приходит из process
            env, в conftest — из `cfg.set_main_option`.
        action: что собирались сделать — попадёт в текст ошибки.

    Raises:
        RuntimeError: `APP_ENV=dev`, цель не loopback и отсутствует в
            `DB_EXTRA_TARGETS`.
        ValueError: `DB_EXTRA_TARGETS` содержит запись не вида
            `host:port/dbname` — пробрасывается из `parse_extra_targets` как
            есть, без оборачивания в `RuntimeError`: это ошибка конфигурации
            (опечатка в `backend/.env`), а не штатный отказ guard'а.
    """
    # Импорт внутри функции: db_guard остаётся импортируемым без конфига, а
    # Settings() собирается на момент вызова — тестовые monkeypatch действуют.
    from config import Settings

    s = Settings()
    if s.APP_ENV == "prod":
        return
    extra = parse_extra_targets(s.DB_EXTRA_TARGETS)
    if is_target_allowed(url, extra):
        return
    target = normalize_target(url)
    listed = ", ".join(sorted(extra)) if extra else "сейчас пусто"
    raise RuntimeError(
        f"{action}: цель {target} не разрешена при APP_ENV=dev.\n"
        f"Разрешено: loopback + DB_EXTRA_TARGETS ({listed}).\n"
        "Если это развёрнутое окружение — выставьте APP_ENV=prod.\n"
        f"Если это дев-цель — добавьте {target} в DB_EXTRA_TARGETS в backend/.env."
    )
