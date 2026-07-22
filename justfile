# UDP — task runner. Запуск: just <команда> или just (=help)
# Используем bash везде (на Windows — git bash), чтобы команды (&&, find, rm -rf)
# работали одинаково на dev-машине и в CI.

set shell := ["bash", "-cu"]
set windows-shell := ["bash", "-cu"]

# Default — показать список команд
default:
    @just --list

# === Setup ===

# Установить все зависимости (backend + frontend, e2e добавим позже)
install: install-backend install-frontend
    @echo "==> Установка завершена"

install-backend:
    cd backend && uv sync

install-frontend:
    cd frontend && npm ci

# === Dev ===

# ИНВАРИАНТ S1 (async processing): один процесс — workers=1, replicas=1,
# деплой строго stop-then-start (no-overlap; rolling запрещён до Ступени 2).
# Startup-sweep на старте переводит pending/processing в error — при overlap
# новый процесс пометил бы живые таски старого. См. docs/agent/pdf-parsing.md.
dev-backend:
    cd backend && uv run uvicorn main:app --reload --port 8259

dev-frontend:
    cd frontend && npm run dev

# === Tests ===

# Все backend-тесты. Если установлен локальный тестовый Postgres (см. ниже) —
# гоняем на нём (~30 сек); иначе — TEST_DATABASE_URL из .env (Neon, ~6-8 мин).
test-backend:
    @if test -d "{{pg_local}}/data"; then echo "==> backend-тесты на локальном Postgres (localhost:5433)"; just test-backend-local; else echo "==> backend-тесты на TEST_DATABASE_URL из .env (Neon)"; cd backend && uv run pytest; fi

# Только unit (быстро)
test-backend-unit:
    cd backend && uv run pytest tests/unit -v

# Только integration (нужен TEST_DATABASE_URL)
test-backend-integration:
    cd backend && uv run pytest tests/integration -v

# Точечный прогон integration по -k паттерну
test-int-k pattern:
    cd backend && uv run pytest tests/integration -v -k "{{pattern}}"

# --- Локальный тестовый Postgres (быстрые integration) ---
# Портативный PostgreSQL 16 + pgvector (conda-forge, micromamba) в профиле
# пользователя — без админ-прав и Docker; тот же стек, что CI-образ
# pgvector/pgvector:pg16. Запросы ~0.2 мс вместо ~43 мс RTT до Neon —
# интеграционный слой ~6.5x быстрее. Порт 5433, auth trust (только localhost).
# Установка с нуля: docs/testing.md, раздел «Локальный тестовый Postgres».

pg_local := "$LOCALAPPDATA/Programs/udp-pgtest"
test_db_local := "postgresql+psycopg://postgres@localhost:5433/udp_test"

# Запустить локальный тестовый Postgres (no-op, если уже работает)
pg-test-start:
    @test -d "{{pg_local}}/data" || { echo "Локальный тестовый Postgres не установлен — см. docs/testing.md, раздел «Локальный тестовый Postgres»"; exit 1; }
    @"{{pg_local}}/Library/bin/pg_ctl" -D "{{pg_local}}/data" status >/dev/null 2>&1 || "{{pg_local}}/Library/bin/pg_ctl" -D "{{pg_local}}/data" -l "{{pg_local}}/data/log.txt" start

pg-test-stop:
    "{{pg_local}}/Library/bin/pg_ctl" -D "{{pg_local}}/data" stop

# Integration против локального Postgres
test-int-local: pg-test-start
    cd backend && TEST_DATABASE_URL="{{test_db_local}}" uv run pytest tests/integration -v

# Точечный локальный прогон по -k паттерну
test-int-local-k pattern: pg-test-start
    cd backend && TEST_DATABASE_URL="{{test_db_local}}" uv run pytest tests/integration -v -k "{{pattern}}"

# Все backend-тесты против локального Postgres
test-backend-local: pg-test-start
    cd backend && TEST_DATABASE_URL="{{test_db_local}}" uv run pytest

# Точечный прогон unit по -k паттерну
test-unit-k pattern:
    cd backend && uv run pytest tests/unit -v -k "{{pattern}}"

# Frontend
test-frontend:
    cd frontend && npm test

# Точечный фронт-прогон одного файла
test-frontend-file file:
    cd frontend && npx vitest run {{file}}

test-frontend-watch:
    cd frontend && npm run test:watch

test-frontend-ui:
    cd frontend && npm run test:ui

# Combined: backend + frontend (без E2E — он отдельно)
test:
    just test-backend
    just test-frontend

# === Coverage ===

coverage-backend:
    cd backend && uv run pytest --cov=. --cov-report=html --cov-report=term

coverage-frontend:
    cd frontend && npm run test:coverage

# === Lint ===

lint-backend:
    cd backend && uv run ruff check .

lint-frontend:
    cd frontend && npm run lint

typecheck-frontend:
    cd frontend && npx tsc -b --noEmit

# Combined lint
lint:
    just lint-backend
    just lint-frontend

format-backend:
    cd backend && uv run ruff format .

# === DB ===

# Создать НОВУЮ ревизию Alembic (без autogenerate — тело заполняется вручную).
# Это создание нового файла в versions/, НЕ правка исторических миграций.
db-revision message:
    cd backend && uv run alembic revision -m "{{message}}"

db-migrate:
    cd backend && uv run alembic upgrade head

db-test-migrate:
    cd backend && DATABASE_URL=$TEST_DATABASE_URL uv run alembic upgrade head

# Проверка дрейфа ORM/БД: локальная тест-БД до head + alembic check.
# Нулевой код = моделей и схемы совпадают (нет pending upgrade ops).
db-test-check: pg-test-start
    cd backend && DATABASE_URL="{{test_db_local}}" uv run alembic upgrade head
    cd backend && DATABASE_URL="{{test_db_local}}" uv run alembic check

# === Misc ===

# Создать суперюзера системы (интерактивный ввод пароля)
create-superuser email:
    cd backend && uv run python -m cli create-superuser --email {{email}}

# Создать организацию
create-org name:
    cd backend && uv run python -m cli create-org --name "{{name}}"

# Записать snapshot AI-ответа от реального PDF (пути — относительно backend/; см. docs/testing.md)
snapshot-ai pdf scenario:
    cd backend && uv run python scripts/snapshot_ai_responses.py "{{pdf}}" "{{scenario}}"

clean:
    rm -rf backend/.pytest_cache backend/htmlcov backend/.coverage backend/coverage.xml
    find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# === Storage ===

# Локальный MinIO (S3): API :9259, консоль :9260, данные — C:\minio\data
# ВАЖНО: данные и temp держим на Windows-томе C:\ (135 ГБ), а НЕ в профиле.
# Профиль C:\Users\<user>\ смонтирован на отдельный маленький 20-ГБ "User Disk";
# при его переполнении MinIO меряет свободное место по data-каталогу и падает
# с XMinioStorageFull, хотя сам бакет крошечный. Путь вне профиля это лечит.
minio:
    mkdir -p /c/minio/data /c/minio/tmp
    TMP="C:/minio/tmp" TEMP="C:/minio/tmp" TMPDIR="C:/minio/tmp" minio server C:/minio/data --address ":9259" --console-address ":9260"
