# Тестирование

Живой документ о текущем состоянии тестовой инфраструктуры. Обновлять при каждом
существенном изменении (добавил тесты, перенастроил CI, поднял coverage threshold).

**Spec:** `docs/superpowers/specs/2026-05-11-testing-infrastructure-design.md` (целевая архитектура).
**Plan:** `docs/superpowers/plans/2026-05-11-testing-infrastructure.md` (пошаговый план на 5 этапов).

---

## TL;DR — текущее состояние

| Слой | Файлов | Тестов | Статус |
|---|---|---|---|
| Backend unit | 19 | 189 | ✅ |
| Backend integration | 28 | 327 | ✅ |
| Backend top-level | 1 | 74 | ✅ |
| **Backend total** | **48** | **590** | ✅ |
| Frontend (Vitest + RTL + MSW) | 28 | 219 | ✅ |
| E2E (Playwright) | — | — | ⏳ отложено |
| GitHub Actions CI | — | backend ✅ / frontend ручной | — |
| **Grand total (локально)** | **76** | **809** | ✅ |

Последний прогон `just test` локально: backend **584 passed / 6 skipped** (`uv run pytest`, 590 собрано; локальный Postgres), frontend **219 passed** (28 файлов). CI настроен для backend (GitHub Actions, `.github/workflows/backend-tests.yml`); frontend запускается вручную.

---

## Быстрый старт

```bash
# Установить всё (backend + frontend)
just install

# Backend — нужен TEST_DATABASE_URL в .env.test (отдельная Neon test-ветка)
just test-backend            # все; АВТО: локальный Postgres если установлен (~30 сек), иначе Neon
just test-backend-unit       # быстро (без БД): 155 PASSED за ~1 сек
just test-backend-integration # с реальной Postgres: 220 PASSED
just coverage-backend        # HTML отчёт в backend/htmlcov/

# Backend против ЛОКАЛЬНОГО Postgres (~6.5x быстрее Neon; установка — см. ниже)
just test-int-local          # integration на localhost:5433
just test-int-local-k "patt" # точечный локальный прогон
just test-backend-local      # весь backend на localhost:5433

# Frontend — без БД, всё через MSW-моки
just test-frontend           # 134 PASSED за ~18–20 сек
just test-frontend-watch     # watch режим
just test-frontend-ui        # @vitest/ui дашборд в браузере
just coverage-frontend       # HTML в frontend/coverage/

# Lint
just lint                    # backend (ruff) + frontend (eslint)
just typecheck-frontend      # tsc --noEmit
```

`just install` создаёт изолированный `backend/.venv` из `uv.lock` (uv sync) — отдельный venv активировать не нужно, все рецепты идут через `uv run`.

### Конфигурация

- **`.env.test`** в корне репо (в `.gitignore`) с `TEST_DATABASE_URL` — отдельная Neon test-ветка, **не прод**.
  Шаблон: `.env.test.example`. Префикс должен быть `postgresql+psycopg://`.
- В CI (backend-tests.yml) переменные приходят из GitHub Actions env/secrets, `.env.test` не нужен.
- **`TEST_DATABASE_URL` не появляется в raw shell env автоматически.** Внутри
  `pytest` её подхватывает плагин `pytest-dotenv` через `env_files = [".env.test"]`
  (`backend/pyproject.toml`, `[tool.pytest.ini_options]`) — переменная видна
  ТОЛЬКО внутри процесса `pytest`. `just db-test-migrate` (читает `$TEST_DATABASE_URL`
  из шелла) и любой ad-hoc `psql`/`alembic` вне pytest её не увидят, если
  `.env.test` не подгружен в сам шелл вручную (`export $(cat .env.test)` / аналог
  в PowerShell) — это ожидаемое поведение `pytest-dotenv`, не баг.

---

## Локальный тестовый Postgres (быстрые integration)

**Зачем.** `TEST_DATABASE_URL` по умолчанию указывает на Neon (eu-central-1) —
каждый SQL-запрос платит ~43 мс сетевого RTT, и 324 integration-теста идут
6–8 минут (замер 2026-07-20: `test_invoices.py`, 59 тестов — 63 с). Против
localhost тот же файл проходит за 9.7 с (~6.5x). CI уже так работает
(`pgvector/pgvector:pg16` service-container, полный прогон ~1 мин) — локальная
установка воспроизводит тот же стек без Docker и без админ-прав.

**Что установлено.** PostgreSQL 16 + pgvector 0.8.3 из conda-forge через
портативный micromamba, целиком в профиле пользователя:

- Окружение: `%LOCALAPPDATA%\Programs\udp-pgtest` (бинарники в `Library\bin`),
  кластер — в `...\udp-pgtest\data`, лог — `data\log.txt`.
- Порт **5433** (чтобы не конфликтовать с возможным системным Postgres),
  auth `trust` — только localhost, тестовые данные.
- База `udp_test`; conftest сам делает `DROP SCHEMA public CASCADE` + Alembic
  на каждую pytest-сессию.
- Сервер НЕ служба Windows: после перезагрузки его поднимает `just pg-test-start`
  (вызывается автоматически из `test-int-local` / `test-backend-local`).

**Установка с нуля (новая машина), без админ-прав:**

```bash
cd "$LOCALAPPDATA/Programs"
curl -L -o micromamba.exe "https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-win-64.exe"
./micromamba.exe create -y -p "$LOCALAPPDATA/Programs/udp-pgtest" -c conda-forge "postgresql=16" pgvector
BIN="$LOCALAPPDATA/Programs/udp-pgtest/Library/bin"
DATA="$LOCALAPPDATA/Programs/udp-pgtest/data"
"$BIN/initdb.exe" -D "$DATA" -U postgres -E UTF8 --locale="en-US"
echo "port = 5433" >> "$DATA/postgresql.conf"
"$BIN/pg_ctl.exe" -D "$DATA" -l "$DATA/log.txt" start
"$BIN/psql.exe" -h localhost -p 5433 -U postgres -c "CREATE DATABASE udp_test;"
```

Проверка: `just test-int-local-k "test_upload_creates_supplier_record"`.

**Важно про локаль:** `--locale=C` НЕ подходит — в C-локали кириллица не
считается alnum, `pg_trgm` строит пустые триграммы и
`test_duplicates_finds_similar_names` падает (similarity=0). Нужна UTF-8-совместимая
локаль (`en-US`): на Windows PostgreSQL использует wide-char CRT-функции, и
кириллица корректно классифицируется/фолдится. ICU в conda-forge win-64 сборке
не собран (`initdb --locale-provider=icu` → «ICU is not supported in this build»).

`.env` не меняется: рецепты `*-local` передают `TEST_DATABASE_URL` инлайн —
шелл-переменная имеет приоритет над значением из dotenv внутри pytest.

`just test-backend` (и, следовательно, `just test`) сам выбирает БД: если
каталог `%LOCALAPPDATA%\Programs\udp-pgtest\data` существует — локальный
Postgres, иначе — Neon из `.env` (у контрибьюторов без локальной установки
поведение прежнее). Явный прогон против Neon — `just test-backend-integration`:
полезная финальная проверка перед PR, максимально близкая к прод-БД.

---

## Архитектура

### Backend

- **pytest 9** + `pytest-asyncio` (auto-mode), `pytest-cov`, `pytest-dotenv`.
- **`db_engine`** (session-scoped): открывает соединение к Neon test-ветке, накатывает Alembic
  миграции один раз на всю сессию pytest.
- **`db_session`** (function-scoped): каждый тест запускается в своей транзакции с
  `join_transaction_mode="create_savepoint"`. Любые `db.commit()` внутри теста
  делают только savepoint — внешняя транзакция откатывается → полная изоляция.
- **`client`** (function-scoped): `TestClient(app)` с переопределённым `get_db`.
- **`factories`** (factory_boy): фабрики для всех моделей. `LazyAttribute` гарантирует
  согласованность производных полей (`amount = quantity * unit_price`).
- **`mock_openrouter`** (respx): перехват `httpx.AsyncClient` к `openrouter.ai`,
  возвращает JSON из `tests/fixtures/openrouter/`. Сценарий переключается через
  `mock_openrouter.use_scenario("unparseable")`.
- **`block_real_openrouter`** (autouse): защитный assert — если тест случайно
  попытается обратиться к реальному OpenRouter, упадёт с понятной ошибкой.
- **`in_memory_s3`**: in-memory подмена S3 (для upload-тестов).

### Frontend

- **Vitest** + `jsdom` + `@testing-library/react` + `@testing-library/user-event`.
- **MSW v2** (`setupServer` в `src/test/server.ts`): перехватывает `axios`-запросы,
  возвращает фикстуры из `src/test/fixtures.ts`. `onUnhandledRequest: "error"` —
  любой неучтённый запрос падает явно.
- **`renderWithProviders`** (`src/test/utils.tsx`): оборачивает компонент в
  `QueryClient` (retries=0), `MemoryRouter`, `ThemeProvider` — те же провайдеры,
  что в реальном `App.tsx`.
- **`window.matchMedia` mock** в setup — `next-themes` его требует, jsdom не
  реализует.
- **`css: false`** в `vitest.config.ts` (дефолт Vitest — НЕ включать обратно).
  jsdom не считает layout/каскад, поэтому обработка CSS не даёт реальной проверки
  стилей, а с Tailwind v4 раздувает transform/import/environment: полный прогон
  ~87с → ~33с при выключении (219/219 зелёные). Тесты через RTL проверяют
  DOM/атрибуты (`className` остаётся в разметке — `toHaveClass` работает).
  Визуальные проверки, если появятся, — отдельным слоем (Playwright/Storybook),
  не в jsdom.

---

## Что покрыто, а что нет

### ✅ Backend — покрыто

**Routers:** `projects` (100%), `material_classes` (100%), `reference_prices` (92%),
`export` (90%), `settings` (80%), `invoices` (66%), `dashboard` (49%),
`/api/units` и `/api/material-types` (auth-protected, покрыты интеграционными тестами).

**Бизнес-логика:** `crud.recalculate_prices` (95%), `pdf_parser._calculate_completeness`,
`_final_confidence`, `routers/invoices._doc_has_issues`, `_avg_confidence` —
ключевые функции расчёта средних цен и валидации документов.

**Units-рефакторинг (добавлено):**
- `test_unit_normalization.py` — `normalize_unit_key` (NFKC, unicode-fold, whitespace, dots) + reconcile-invariant.
- `test_dimension_guard.py` — размерностный guard в `compute_calculations` (class vs ref-price dimension; intra-class mix).
- `test_delivery_distribution.py` — моно- и смешанная размерность, распределение по `normalized_quantity` vs `amount`, edge-cases нулевых/ненормализованных строк.
- `test_units_api.py` — `GET /api/units`, `GET /api/units/{id}/aliases`, `GET /api/material-types`.
- `test_normalization_integration.py` — end-to-end нормализация единиц при создании инвойса, PUT-ренормализация, `warnings` по неизвестным единицам.
- `test_calculations_with_units.py` — расчёт avg_price на `normalized_quantity`, dimension_mismatch → null deviation.
- `test_reference_prices_unit.py` — валидация `unit_id` (base-unit only, dimension match vs material_type); immutability после создания.

### ⚠️ Backend — пробелы (в backlog)

- `routers/invoices.reparse` endpoint не покрыт.
- Pydantic-валидация payload'ов (POST с пустыми полями → 422) не тестируется.
- Cascade-delete для `MaterialClass` с привязанными InvoiceItem.
- `recalculate_prices` edge cases: multi-item, multi-period (частично закрыто `test_calculations_with_units.py`).
- Supplier deviation dimension guard отсутствует (см. `TECH_DEBT.md`).

### ✅ Frontend — покрыто

**Компоненты:** `Dropzone`, `EntitySelect` (4+4 теста, behavioural).
**Страницы (smoke):** `Upload`, `Review`, `Dashboard`, `Reports`, `ReferencePrices`.
**Units-рефакторинг (добавлено):**
- Выбор единицы измерения в справочных ценах: default-by-type (class onChange) + ручной выбор.
- `ReviewItemsTable` inline-edit поля `raw_unit`.
- Отображение и сброс `warnings[]` после сохранения СФ: первый save показывает предупреждение, последующий чистый save его убирает.

### ⚠️ Frontend — пробелы (в backlog)

- Coverage не измерен (Task 3.11 отложен).
- KPI-цифры на Dashboard (требуют `userEvent.click` для выбора проекта).
- Полный flow Upload → парсинг → Review (это уровень E2E).

### ⏳ E2E (Playwright) — отложено

- 5 spec'ов запланировано: golden path upload, edge cases, reference prices,
  projects CRUD, navigation/themes.
- Mock-OpenRouter сервис на FastAPI (`e2e/mock_openrouter/`), `/api/test/reset`
  роутер на бэкенде под `TEST_MODE=1`.

### ✅ Backend CI — настроен

- `.github/workflows/backend-tests.yml`: ruff lint → pytest (unit + integration + top-level, 447 тестов) на каждый push/PR.
- Postgres + pgvector запускается как service-container; `TEST_DATABASE_URL` подставляется из env.
- Frontend в CI **не гоняется** — запускать вручную (`just test-frontend`).

### ⏳ Frontend CI + E2E — отложено

- GitHub Actions workflow с frontend / e2e jobs.
- `branch protection` на `main` через UI.

---

## Как добавить новый тест

### Backend integration

```python
# backend/tests/integration/test_<router>.py
def test_<feature>(client, factories):
    obj = factories.ProjectFactory.create(name="...")
    response = client.get(f"/api/projects/{obj.id}")
    assert response.status_code == 200
    assert response.json()["name"] == "..."
```

### Backend unit

```python
# backend/tests/unit/test_<module>.py
from <module> import some_function

def test_some_function():
    assert some_function(input) == expected
```

### Frontend

```tsx
// src/components/<Component>.test.tsx
import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { MyComponent } from "./MyComponent";

describe("MyComponent", () => {
  it("renders correctly", async () => {
    renderWithProviders(<MyComponent />);
    await waitFor(() => {
      expect(screen.getByText(/text/)).toBeInTheDocument();
    });
  });
});
```

Нестандартный API endpoint? Добавить handler в `frontend/src/test/handlers.ts`.

### Snapshot AI-ответа от реального PDF

```bash
# Реальный PDF лежит локально, в .gitignore
cp /path/to/real.pdf backend/tests/fixtures/pdf/real/
# Пути — относительно backend/ (рецепт сам делает cd backend)
just snapshot-ai tests/fixtures/pdf/real/real.pdf my_scenario
# → backend/tests/fixtures/openrouter/my_scenario.json (sanitized, ИНН/имена → фейки)
git add backend/tests/fixtures/openrouter/my_scenario.json
```

---

## Tech debt / backlog

См. `docs/superpowers/plans/2026-05-11-testing-infrastructure.md` секция backlog.
Кратко:

- **Prod-code:** `datetime.utcnow()` → `datetime.now(UTC)` в `routers/invoices.py:210`,
  `crud.py:285`, `models.py` (3 места). Python 3.16 сделает их ошибкой.
- **Settings router refactor:** `update_settings` пишет в `os.environ` — выкинуть
  это в пользу только-в-файл (избавит от пайтест-pollution).
- **Test placement:** `tests/unit/test_crud_recalculate.py` использует БД —
  технически это integration, переместить в `tests/integration/`.
- **Дополнительные тесты:** см. «пробелы» выше.

---

## Roadmap

- **Этап 4 (Playwright E2E):** 10 задач (`Task 4.1-4.10` в плане). Mock-OpenRouter
  сервер, `/api/test/reset`, 5 spec'ов.
- **Этап 5 (CI + docs):** 5 задач (`Task 5.1-5.5`). GitHub Actions workflow,
  branch protection.
