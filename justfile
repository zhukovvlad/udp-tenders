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
    cd backend && pip install -r requirements.txt -r requirements-test.txt

install-frontend:
    cd frontend && npm ci

# === Dev ===

dev-backend:
    cd backend && uvicorn main:app --reload --port 8000

dev-frontend:
    cd frontend && npm run dev

# === Tests ===

# Все backend-тесты
test-backend:
    cd backend && pytest

# Только unit (быстро)
test-backend-unit:
    cd backend && pytest tests/unit -v

# Только integration (нужен TEST_DATABASE_URL)
test-backend-integration:
    cd backend && pytest tests/integration -v

# Watch-режим (нужен pytest-watch)
test-backend-watch:
    cd backend && ptw tests -- -v

# Frontend
test-frontend:
    cd frontend && npm test

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
    cd backend && pytest --cov=. --cov-report=html --cov-report=term

coverage-frontend:
    cd frontend && npm run test:coverage

# === Lint ===

lint-backend:
    cd backend && ruff check .

lint-frontend:
    cd frontend && npm run lint

typecheck-frontend:
    cd frontend && npx tsc -b --noEmit

# Combined lint
lint:
    just lint-backend
    just lint-frontend

format-backend:
    cd backend && ruff format .

# === DB ===

db-migrate:
    cd backend && alembic upgrade head

db-test-migrate:
    cd backend && DATABASE_URL=$TEST_DATABASE_URL alembic upgrade head

# === Misc ===

# Создать суперюзера системы (интерактивный ввод пароля)
create-superuser email:
    cd backend && python -m cli create-superuser --email {{email}}

# Создать организацию
create-org name:
    cd backend && python -m cli create-org --name "{{name}}"

clean:
    rm -rf backend/.pytest_cache backend/htmlcov backend/.coverage backend/coverage.xml
    find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
