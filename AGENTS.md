# UDP — Трекер цен на материалы из PDF-накладных (УПД)

Русскоязычный B2B для тендерных менеджеров в стройке: PDF УПД → LLM-парсинг → история цен → отчёты об отклонениях в Excel.

## Стек
Backend: Python 3.12+, FastAPI, SQLAlchemy (sync), Alembic, pydantic-settings; auth — pyjwt HS256 + argon2, httpOnly cookies, CSRF.
Frontend: React 19, TS (strict), Vite, shadcn/ui, Tailwind v4, Recharts, TanStack Query v5.
PostgreSQL (Neon) · MinIO (S3) · OpenRouter API (Claude Vision, `PDF_ENGINE=native`).

## Команды — только через `just`, никогда `cd backend && ...`
`install` · `dev-backend` · `dev-frontend` · `test` · `test-backend-unit` · `test-backend-integration` · `test-frontend` · `lint` · `typecheck-frontend` · `db-migrate` · `create-superuser` · `create-org`

Shell (Windows): `& "C:\Program Files\Git\bin\bash.exe" -c "cd /c/Users/zhukov_v/Projects/UDP && just <cmd> 2>&1"`

CI: GitHub Actions (`.github/workflows/backend-tests.yml`) гоняет ruff + полный pytest на каждый push/PR (~1 мин, Postgres+pgvector service-container).

## Жёсткие правила
- Миграции в `backend/alembic/versions/` руками не править — только `just db-migrate`.
- `.env` / `.env.test` не трогать; секреты — через переменные окружения.
- Перед завершением задачи — `just lint` и `just test`.
- Новые зависимости — только по явному запросу.
- Перед правкой кода рядом с известным долгом — свериться с `docs/TECH_DEBT.md`.

## Формат ответа
Код — без объяснений, если не просили. Правки — диффом.

## Где искать детали (читай ТОЛЬКО нужный файл, не весь набор)
- Структура проекта и навигация → `docs/ui/routes-architecture.md`
- Обзор архитектуры и планы → `docs/agent/architecture.md`
- Модели БД и связи → `docs/agent/database.md`
- Расчёты (avg_price, направления/direction, разноска, коридор, Decimal, экспорт) → `docs/agent/calculations.md`
- Парсинг УПД и выбор движка → `docs/agent/pdf-parsing.md`
- Аутентификация и роли → `docs/agent/auth.md`
- Поставщики: исключения и ограничения MVP → `docs/agent/suppliers.md`
- Тестирование → `docs/testing.md`
