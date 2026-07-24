# UDP — Трекер цен на материалы из PDF-накладных (УПД)

Русскоязычный B2B для тендерных менеджеров в стройке: PDF УПД → LLM-парсинг → история цен → отчёты об отклонениях в Excel.

## Стек
Backend: Python 3.12, FastAPI, SQLAlchemy (sync), Alembic, pydantic-settings; auth — pyjwt HS256 + argon2, httpOnly cookies, CSRF. Зависимости — uv (pyproject.toml + uv.lock).
Frontend: React 19, TS (strict), Vite, shadcn/ui, Tailwind v4, Recharts, TanStack Query v5.
PostgreSQL (Neon) · MinIO (S3) · LLM через абстракцию провайдера (`backend/llm.py`): deploy-time `LLM_PROVIDER` (дефолт `openrouter` — Claude Vision, движок `native`); домен зовёт `llm.get_provider().vision_completion(...)`, транспорт живёт в `llm_openrouter.py`. pypdfium2 + pikepdf + Pillow — raster-коррекция ориентации страниц (deskew).

## Команды — только через `just`, никогда `cd backend && ...`
`install` · `dev-backend` · `dev-frontend` · `test` · `test-backend-unit` · `test-backend-integration` · `test-int-local` (integration на локальном Postgres, ~6.5x быстрее — см. `docs/testing.md`) · `test-backend-local` · `test-frontend` · `lint` · `typecheck-frontend` · `db-migrate` · `create-superuser` · `create-org`

Shell (Windows): `& "C:\Program Files\Git\bin\bash.exe" -c "cd /c/Users/zhukov_v/Projects/UDP && just <cmd> 2>&1"`

CI: GitHub Actions (`.github/workflows/backend-tests.yml`) гоняет ruff + полный pytest на каждый push/PR (~1 мин, Postgres+pgvector service-container).

## Жёсткие правила
- Миграции: исторические файлы в `backend/alembic/versions/` не редактировать. Новые ревизии создавать через `just db-revision "..."` (позиционный аргумент — `message="..."` НЕ работает, just примет его как буквальное значение вместе с `message=`; это `alembic revision` без autogenerate — создание нового файла); тело новой ревизии (`upgrade`/`downgrade`) заполнять вручную допустимо. Применять — `just db-migrate` (dev) / `just db-test-migrate` (тестовая БД).
- `.env` / `.env.test` не трогать; секреты — через переменные окружения.
- Перед завершением задачи — `just lint` и `just test`.
- Новые зависимости — только по явному запросу.
- Перед правкой кода рядом с известным долгом — свериться с `docs/TECH_DEBT.md`.
- Докстринги: каждая функция/метод (включая тесты и приватные `_helpers`) — с докстрингом. Порог покрытия в PR — ≥80%, цель — 100% в изменённых файлах. Однострочник по сути — норма.

## Формат ответа
Код — без объяснений, если не просили. Правки — диффом.

## Где искать детали (читай ТОЛЬКО нужный файл, не весь набор)
- Структура проекта и навигация → `docs/ui/routes-architecture.md`
- Обзор архитектуры и планы → `docs/agent/architecture.md`
- Модели БД и связи → `docs/agent/database.md`
- Расчёты (avg_price, направления/direction, разноска, коридор, Decimal, экспорт) → `docs/agent/calculations.md`
- Парсинг УПД, выбор движка, коррекция ориентации (deskew-reparse) → `docs/agent/pdf-parsing.md`
- LLM-провайдер (переключатель `LLM_PROVIDER`, абстракция `llm.py`, инварианты биллинга/ошибок) → `docs/superpowers/specs/2026-07-23-llm-provider-toggle-design.md`
- Аутентификация и роли → `docs/agent/auth.md`
- Поставщики: исключения и ограничения MVP → `docs/agent/suppliers.md`
- Тестирование → `docs/testing.md`
