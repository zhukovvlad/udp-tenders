# УПД Трекер цен

B2B веб-приложение для тендерных менеджеров строительных компаний. Загружаете PDF-накладные (УПД / счёт-фактура) — ИИ извлекает поставщика, материал, цену и объём. Приложение накапливает историю цен, строит аналитику и позволяет выгружать отчёты-обоснования в Excel.

---

## Что делает приложение

- **Загрузка УПД** — drag-and-drop PDF прямо из карточки объекта, автоматический парсинг через LLM
- **Проверка** — PDF-просмотрщик + форма редактирования для документов с низкой уверенностью ИИ
- **Дашборд** — графики средней цены по месяцам, KPI-карточки по объекту
- **Объекты** — список проектов, базовые (эталонные) цены, исключение нерепрезентативных поставщиков из расчётов
- **Поставщики** — реестр с оборотом, объёмами, отклонениями в разрезе объектов; дедупликация по ИНН; слияние дублей
- **Номенклатура** — справочник классов материалов (бетон, арматура и др.) и базовые цены по объектам
- **Отчёты** — выгрузка в Excel: средние цены по периодам, отклонения от базовых, разбивка по поставщикам (16 колонок, формулы)
- **Мультиарендность** — организации, роли (superadmin / admin / member), изоляция доступа

---

## Стек

| Слой | Технология |
|------|-----------|
| Бэкенд | Python 3.12+, FastAPI, SQLAlchemy (sync), Alembic, pydantic-settings |
| Аутентификация | pyjwt (HS256), pwdlib[argon2] — httpOnly cookies, double-submit CSRF, ротация refresh-токенов |
| База данных | PostgreSQL via Neon (serverless) — `postgresql+psycopg://` DSN |
| Хранилище PDF | MinIO (S3-совместимое), локальный бинарь `minio.exe` |
| PDF-парсинг | OpenRouter API — Mistral OCR / Claude Vision |
| Фронтенд | React 18, TypeScript, Vite, shadcn/ui, Tailwind CSS v4, Recharts |
| State / данные | TanStack Query v5, axios |
| Тесты (BE) | pytest 8, respx, factory_boy |
| Тесты (FE) | Vitest + Testing Library + MSW v2 |
| Task runner | `just` |

---

## Запуск

### Требования

- Python 3.12+ и Node.js 20+
- [just](https://just.systems/) — установить по инструкции на сайте или `winget install Casey.Just`
- MinIO — скачать `minio.exe` со [страницы загрузки](https://min.io/download)
- Аккаунт на [Neon](https://neon.tech) (бесплатный tier) и [OpenRouter](https://openrouter.ai)

### 1. Настройка переменных окружения

```bash
cp backend/.env.example backend/.env
```

Обязательные переменные в `backend/.env`:

| Переменная | Описание |
|------------|---------|
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `DATABASE_URL` | Neon Console → Connection string (`postgresql+psycopg://...`) |
| `SECRET_KEY` | Сгенерировать: `openssl rand -hex 32` |
| `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` | Настройки MinIO (по умолчанию `http://localhost:9000` / `minioadmin`) |
| `ALLOWED_ORIGINS` | JSON-массив origin'ов фронтенда, например `["http://localhost:5173"]` |

Подробнее о настройке Neon: [docs/setup/neon-setup.md](docs/setup/neon-setup.md).

### 2. Установка зависимостей

```bash
just install
```

### 3. Запуск MinIO

```bash
minio.exe server ./minio-data --console-address ":9001"
```

MinIO API: `http://localhost:9000`, веб-консоль: `http://localhost:9001`.

### 4. Миграция базы данных

```bash
just db-migrate
```

### 5. Создание первого пользователя и организации

```bash
just create-org "Моя компания"
just create-superuser admin@example.com
```

### 6. Запуск сервисов

В двух отдельных терминалах:

```bash
just dev-backend   # http://localhost:8000  (Swagger: /docs)
just dev-frontend  # http://localhost:5173
```

---

## Разработка

```bash
just test                    # backend + frontend тесты
just test-backend-unit       # только unit-тесты, без БД (~1 с)
just test-backend-integration  # integration-тесты (нужен TEST_DATABASE_URL)
just test-frontend           # vitest
just lint                    # ruff + eslint
just typecheck-frontend      # tsc --noEmit
just coverage-backend        # HTML-отчёт → backend/htmlcov/index.html
```

Полный список команд: `just` (без аргументов).

---

## Структура проекта

```
UDP/
├── backend/
│   ├── main.py              — FastAPI: CORS, CSRF middleware, роутеры
│   ├── models.py            — ORM: Project, Document, Invoice, InvoiceItem,
│   │                          MaterialClass, ReferencePrice, Supplier,
│   │                          Organization, User, RefreshToken, ...
│   ├── crud/                — операции с БД (6 модулей):
│   │   ├── projects.py      — Project + ReferencePrice
│   │   ├── materials.py     — MaterialClass
│   │   ├── documents.py     — Document + Invoice
│   │   ├── calculations.py  — avg_price, deviation, export-строки
│   │   ├── suppliers.py     — Supplier + аналитика
│   │   └── supplier_exclusions.py — исключения поставщиков из расчётов
│   ├── security.py          — JWT, хэширование паролей, CSRF
│   ├── auth.py              — FastAPI-зависимости: get_current_user, роли
│   ├── pdf_parser.py        — парсинг УПД через OpenRouter API
│   ├── s3.py                — работа с MinIO
│   ├── cli.py               — CLI: create-superuser, create-org
│   ├── routers/             — REST API:
│   │   ├── auth.py          — login, logout, refresh, me
│   │   ├── projects.py      — объекты, исключения поставщиков
│   │   ├── invoices.py      — загрузка и редактирование УПД
│   │   ├── dashboard.py     — расчётная аналитика
│   │   ├── export.py        — Excel-выгрузка
│   │   ├── suppliers.py     — реестр поставщиков, слияние
│   │   ├── material_classes.py — номенклатура
│   │   ├── reference_prices.py — базовые цены
│   │   ├── orgs.py          — организации
│   │   ├── admin.py         — административные операции
│   │   └── settings.py      — настройки
│   ├── alembic/             — миграции БД
│   └── tests/               — unit/ + integration/ + fixtures/
├── frontend/src/
│   ├── pages/               — Dashboard, Projects, ProjectPage,
│   │                          Suppliers, SupplierPage,
│   │                          Materials, MaterialPage, MaterialClasses,
│   │                          ReferencePrices, Reports, Review,
│   │                          Upload, Settings, LoginPage
│   ├── components/          — ui/, ui-domain/, layout/,
│   │                          dashboard/, projects/, invoices/, review/
│   └── services/            — API-клиент (axios), TanStack Query, queryKeys
├── docs/
│   └── setup/neon-setup.md  — инструкция по настройке БД
└── justfile                 — команды разработки
```
