# Тестирование

Живой документ о текущем состоянии тестовой инфраструктуры. Обновлять при каждом
существенном изменении (добавил тесты, перенастроил CI, поднял coverage threshold).

**Spec:** `docs/superpowers/specs/2026-05-11-testing-infrastructure-design.md` (целевая архитектура).
**Plan:** `docs/superpowers/plans/2026-05-11-testing-infrastructure.md` (пошаговый план на 5 этапов).

---

## TL;DR — текущее состояние

| Слой | Файлов | Тестов | Статус |
|---|---|---|---|
| Backend unit | 14 | 155 | ✅ |
| Backend integration | 17 | 220 | ✅ |
| Backend top-level | 1 | 72 | ✅ |
| **Backend total** | **32** | **447** | ✅ |
| Frontend (Vitest + RTL + MSW) | 20 | 134 | ✅ |
| E2E (Playwright) | — | — | ⏳ отложено |
| GitHub Actions CI | — | backend ✅ / frontend ручной | — |
| **Grand total (локально)** | **52** | **581** | ✅ |

Все 581 тест зелёный локально (backend — `pytest --co` собирает 447; frontend — 134). CI настроен для backend (GitHub Actions, `.github/workflows/backend-tests.yml`); frontend запускается вручную.

---

## Быстрый старт

```bash
# Установить всё (backend + frontend)
just install

# Backend — нужен TEST_DATABASE_URL в .env.test (отдельная Neon test-ветка)
just test-backend            # все: 447 PASSED
just test-backend-unit       # быстро (без БД): 155 PASSED за ~1 сек
just test-backend-integration # с реальной Postgres: 220 PASSED
just coverage-backend        # HTML отчёт в backend/htmlcov/

# Frontend — без БД, всё через MSW-моки
just test-frontend           # 134 PASSED за ~18–20 сек
just test-frontend-watch     # watch режим
just test-frontend-ui        # @vitest/ui дашборд в браузере
just coverage-frontend       # HTML в frontend/coverage/

# Lint
just lint                    # backend (ruff) + frontend (eslint)
just typecheck-frontend      # tsc --noEmit
```

### Конфигурация

- **`.env.test`** в корне репо (в `.gitignore`) с `TEST_DATABASE_URL` — отдельная Neon test-ветка, **не прод**.
  Шаблон: `.env.test.example`. Префикс должен быть `postgresql+psycopg://`.
- В CI (backend-tests.yml) переменные приходят из GitHub Actions env/secrets, `.env.test` не нужен.

---

## Архитектура

### Backend

- **pytest 8** + `pytest-asyncio` (auto-mode), `pytest-cov`, `pytest-dotenv`.
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
cd backend
python scripts/snapshot_ai_responses.py tests/fixtures/pdf/real/real.pdf my_scenario
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
