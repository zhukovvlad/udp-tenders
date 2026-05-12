# УПД Трекер цен

Веб-приложение для отслеживания динамики цен на материалы по данным из PDF-накладных (УПД).

Загружаете PDF-файлы УПД — ИИ извлекает поставщика, материал, цену и объём. Приложение накапливает историю, строит графики динамики цен и позволяет выгружать отчёты в Excel для обоснования удорожания.

---

## Что делает приложение

- **Загрузка УПД** — drag-and-drop PDF, автоматический парсинг через LLM
- **Проверка** — PDF-просмотрщик + форма редактирования для документов с низкой уверенностью ИИ
- **Дашборд** — графики средней цены по месяцам, KPI-карточки, сравнение поставщиков
- **Отчёты** — выгрузка в Excel: средние цены по периодам, разбивка по поставщикам
- **Справочник** — классы материалов (бетон, арматура и др.) и эталонные цены по проектам

---

## Стек

| Слой | Технология |
|------|-----------|
| Бэкенд | Python 3.11+, FastAPI, SQLAlchemy, Alembic |
| База данных | PostgreSQL (Neon, serverless) |
| Хранилище PDF | MinIO (S3-совместимое) |
| PDF-парсинг | OpenRouter API (Mistral OCR / Claude Vision) |
| Фронтенд | React 18, TypeScript, Vite, shadcn/ui, Tailwind CSS v4, Recharts |
| Task runner | `just` |

---

## Запуск

### Требования

- Python 3.14+ и Node.js 20+
- [just](https://just.systems/) — `pip install rust-just`
- MinIO — скачать `minio.exe` со [страницы загрузки](https://min.io/download)
- Аккаунт на [Neon](https://neon.tech) (бесплатный tier) и [OpenRouter](https://openrouter.ai)

### 1. Настройка переменных окружения

```bash
cp backend/.env.example backend/.env
```

Заполнить в `backend/.env`:

| Переменная | Откуда взять |
|------------|-------------|
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `DATABASE_URL` | Neon Console → Connection string (формат `postgresql+psycopg://...`) |
| `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` | Настройки MinIO (по умолчанию — `minioadmin`) |

Инструкция по настройке Neon: [`docs/setup/neon-setup.md`](docs/setup/neon-setup.md).

### 2. Установка зависимостей

```bash
just install
```

### 3. Запуск MinIO

```bash
minio.exe server ./minio-data --console-address ":9001"
```

MinIO будет доступен на `http://localhost:9000`, веб-консоль — на `:9001`.

### 4. Миграция базы данных

```bash
just db-migrate
```

### 5. Запуск сервисов

В двух отдельных терминалах:

```bash
just dev-backend   # http://localhost:8000  (Swagger: /docs)
just dev-frontend  # http://localhost:5173
```

---

## Разработка

```bash
just test           # backend + frontend тесты
just lint           # ruff + eslint
just coverage-backend   # HTML-отчёт покрытия → backend/htmlcov/index.html
```

Полный список команд: `just` (без аргументов).

---

## Структура проекта

```
UDP/
├── backend/
│   ├── main.py              — FastAPI: CORS, логирование, роутеры
│   ├── models.py            — ORM: Project, Document, Invoice, MaterialClass, ...
│   ├── crud.py              — операции с БД
│   ├── pdf_parser.py        — парсер УПД через OpenRouter API
│   ├── s3.py                — работа с MinIO
│   ├── routers/             — REST API (projects, invoices, dashboard, export, ...)
│   ├── alembic/             — миграции БД
│   └── tests/               — unit + integration тесты
├── frontend/
│   └── src/
│       ├── pages/           — Dashboard, Upload, Review, Reports, Settings, ...
│       ├── components/      — shadcn/ui компоненты
│       └── services/        — API-клиент
├── docs/
│   └── setup/neon-setup.md  — инструкция по настройке БД
└── justfile                 — команды разработки
```
