"""Guard от случайной записи в Neon.

Разработка переехала на локальный Postgres (см. docs/testing.md, разделы
«Локальный тестовый Postgres» и «Локальная dev-БД»), но `DATABASE_URL` в `.env`
по-прежнему указывает на Neon — там живёт прод. Значит любая мутирующая команда,
запущенная по привычке без явной цели (`uv run alembic upgrade head`,
`python -m cli create-superuser`), молча уедет в прод-базу.

Этот модуль — единственное место, где такая попытка отсекается. Escape hatch —
переменная `ALLOW_NEON_WRITES=1`; её выставляют:

* рецепты `just` при `db_target=neon` — выбор цели и есть подтверждение;
* тестовый `conftest` — integration-тесты штатно работают с Neon test-веткой.
"""
import os
from urllib.parse import urlsplit

ALLOW_ENV = "ALLOW_NEON_WRITES"
_NEON_DOMAIN = "neon.tech"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def is_neon_url(url: str) -> bool:
    """True, если DSN указывает на хост Neon.

    Сравнение по суффиксу домена, а не подстрокой: `myneon.techie.example.com`
    содержит "neon.tech", но к Neon отношения не имеет.
    """
    host = safe_host(url).lower().rstrip(".")
    return host == _NEON_DOMAIN or host.endswith("." + _NEON_DOMAIN)


def neon_writes_allowed() -> bool:
    """Разрешена ли запись в Neon текущим окружением."""
    return os.getenv(ALLOW_ENV, "").strip().lower() in _TRUTHY


def safe_host(url: str) -> str:
    """Хост из DSN без креденшелов — чтобы пароль не утёк в текст ошибки."""
    if not url:
        return ""
    try:
        return urlsplit(url).hostname or ""
    except ValueError:
        return ""


def ensure_write_allowed(url: str, action: str) -> None:
    """Прервать `action`, если он пишет в Neon без явного разрешения.

    Args:
        url: DSN цели.
        action: что именно собирались сделать — попадёт в текст ошибки.

    Raises:
        RuntimeError: цель — Neon, а `ALLOW_NEON_WRITES` не выставлен.
    """
    if not is_neon_url(url) or neon_writes_allowed():
        return
    raise RuntimeError(
        f"{action}: цель — Neon ({safe_host(url)}), запись туда не разрешена.\n"
        "Разработка идёт на локальной БД: just db-dev-init, just dev-backend.\n"
        f"Если это осознанно — just db_target=neon <рецепт> либо {ALLOW_ENV}=1."
    )
