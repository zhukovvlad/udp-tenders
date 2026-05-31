# UDP — CLAUDE.md

## What this project is

**УПД Трекер цен** — a Russian-language B2B web app for construction procurement teams. Users upload PDF invoices (УПД / счёт-фактура), the app parses them via LLM, tracks material price dynamics, and exports deviation reports for cost justification.

Target user: тендерный менеджер (procurement/tender manager) in a construction company.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12+, FastAPI, SQLAlchemy (sync), Alembic, pydantic-settings |
| Auth | pyjwt (HS256), pwdlib[argon2] — httpOnly cookies, double-submit CSRF, refresh token rotation |
| Database | PostgreSQL via **Neon** (serverless) — `postgresql+psycopg://` DSN |
| File storage | MinIO (S3-compatible), local binary `minio.exe` |
| PDF parsing | OpenRouter API (`OPENROUTER_API_KEY`) — Mistral OCR / Claude Vision |
| Frontend | React 18, TypeScript, Vite, shadcn/ui, Tailwind CSS v4, Recharts |
| State / data | TanStack Query v5, axios |
| Testing (BE) | pytest 8, pytest-asyncio (auto mode), respx, factory_boy |
| Testing (FE) | Vitest + Testing Library + MSW v2 |
| Linting | ruff (BE), eslint + tsc (FE) |
| Task runner | `just` — **always use `just` commands, never raw `cd backend && ...`** |

---

## Dev commands (justfile)

```bash
just install              # install backend + frontend deps
just dev-backend          # uvicorn on :8000, hot reload
just dev-frontend         # vite on :5173

just test                 # backend + frontend (no E2E)
just test-backend         # all pytest (~22s)
just test-backend-unit    # unit only, no DB, ~1s
just test-backend-integration  # requires TEST_DATABASE_URL

just test-frontend        # vitest (~10s)
just lint                 # ruff + eslint
just typecheck-frontend   # tsc -b --noEmit
just coverage-backend     # HTML → backend/htmlcov/index.html
just db-migrate           # alembic upgrade head
just create-superuser email  # python -m cli create-superuser (password prompt)
just create-org name         # python -m cli create-org --name
```

Shell on Windows: Git bash at `C:\Program Files\Git\bin\bash.exe`. Invoke as:
`& "C:\Program Files\Git\bin\bash.exe" -c "cd /c/Users/zhukov_v/Projects/UDP && just <command> 2>&1"`
All scripts use Unix syntax.

---

## Project structure

```
UDP/
├── backend/
│   ├── main.py           — FastAPI app, CORS, routers, middleware, CSRF middleware
│   ├── config.py         — pydantic-settings Settings (single source of truth for env vars)
│   ├── models.py         — ORM models (Project, Document, Invoice, InvoiceItem, MaterialClass, ReferencePrice, Supplier, Organization, User, ProjectOrganization, RefreshToken, ProjectSupplierExclusion)
│   ├── crud/             — DB operations split into 6 modules:
│   │   ├── projects.py   — Project + ReferencePrice CRUD
│   │   ├── materials.py  — MaterialClass CRUD + VALID_CALC_ROLES
│   │   ├── documents.py  — Document + Invoice CRUD
│   │   ├── calculations.py — avg_price, deviation, export row calculations
│   │   ├── suppliers.py  — Supplier CRUD + analytics aggregates
│   │   ├── supplier_exclusions.py — get_excluded_supplier_ids, set_supplier_excluded
│   │   └── admin.py      — superuser admin console CRUD: orgs, users, project links, last-superadmin guard, role matrix (can_set_role / can_manage_target)
│   ├── security.py       — pure crypto helpers: hash_password, JWT encode/decode, refresh token, CSRF
│   ├── auth.py           — FastAPI auth dependencies: get_current_user, require_csrf, require_superuser, require_org_admin, require_org_admin_with_org, require_org_superadmin, ProjectAccess
│   ├── cli.py            — Click CLI: create-superuser, create-org, create-user
│   ├── pdf_parser.py     — OpenRouter API parsing
│   ├── s3.py             — MinIO helpers
│   ├── utils.py          — get_client_ip, utcnow helpers
│   ├── routers/          — projects, invoices, dashboard, export, material_classes, reference_prices, settings, suppliers, auth, admin, orgs
│   ├── alembic/          — migrations
│   └── tests/            — unit/ + integration/ + fixtures/ + test_auth_coverage.py
├── frontend/src/
│   ├── pages/            — Dashboard, Projects, ProjectPage, Suppliers, SupplierPage, Materials, Reports, Review, Settings, admin/ (superuser console: AdminOrganizations, AdminOrgCreate, AdminOrgDetail, AdminUserCreate, AdminUsers)
│   ├── components/       — ui/, ui-domain/, layout/, dashboard/, projects/, invoices/, review/, admin/ (RoleBadges, PasswordField)
│   ├── lib/             — format, constants, utils, useDebounce, password (CSPRNG generatePassword + copyToClipboard)
│   ├── services/         — api/ (axios), queries.ts (TanStack Query), queryKeys.ts
│   └── types/            — TypeScript types per domain (common, project, invoice, materialClass, referencePrice, supplier, admin, auth)
├── docs/
│   ├── TECH_DEBT.md      — tracked debt items (check before touching related code)
│   ├── testing.md        — testing architecture, coverage status, how to add tests
│   └── ui/routes-architecture.md  — full route/navigation design doc
└── justfile
```

---

## Architecture principles (from route design doc)

- **Entity-oriented navigation**: business entities first — Projects (Объекты), Suppliers (Поставщики), Materials (Номенклатура), Reports. No technical routes in main nav.
- **Three data axes**: any data point is reachable via Project, Supplier, or Material.
- **Upload is a slide-over panel** inside Project page (`Sheet` from shadcn), not a separate route. `/upload` redirects to `/projects`.
- **No `/documents` list in nav** — invoices are accessed through their parent entity or Reports.
- **Reference prices** (базовые цены) live inside Project card (tab) and Material card — no separate route.
- **Progressive disclosure** — AI confidence percentages are hidden in tooltips; the document card is where the technical layer fully surfaces.

---

## Database models — key relationships

```
Organization (kind: customer/contractor) → Users (org members via OrgRole)
Organization → Projects (via ProjectOrganization — ProjectRole: customer/contractor)
Project → Documents → Invoices → InvoiceItems → MaterialClass
Project → ReferencePrices (project ↔ material_class ↔ period)
Project → ProjectSupplierExclusion ← Supplier  (исключения поставщиков из расчётов)
Supplier → Invoices (one supplier, many projects)
User → RefreshTokens (many, revokable, 14 days)
```

`Organization.kind` (`customer`/`contractor`, реюзает enum `ProjectRole`, `SqlEnum(native_enum=False)`, NOT NULL, `server_default='customer'`) — роль организации по умолчанию. При выдаче доступа к проекту через `/api/admin/.../projects` `ProjectOrganization.project_role` берётся из `organization.kind`, но переопределяется явным значением в теле запроса. Миграция: `2026_05_30_1200-a7b8c9d0e1f2_add_organization_kind` (VARCHAR+CHECK, `server_default` заполняет существующие строки).

`GET /dashboard/calculations` вычисляет данные на лету (нет кеша) через `compute_calculations()` из `crud.calculations` — единый источник истины для аналитики цен. `compute_full_deviation()` делегирует в неё же.

Все три функции расчёта (`compute_calculations`, `compute_full_deviation`, `compute_export_rows`) принимают параметр `excluded_supplier_ids: set[int] | None`. Если передан непустой set, инвойсы исключённых поставщиков фильтруются через `or_(Invoice.supplier_id.is_(None), Invoice.supplier_id.notin_(excluded))` — инвойсы без поставщика всегда включаются. `get_project_summary` в `dashboard.py` также применяет этот фильтр ко всем агрегатам (оборот, объём м³, кол-во счетов).

`GET /api/export/excel?project_id=&period_start=&period_end=&material_class_id=` генерирует openpyxl-файл через `compute_export_rows()` из `crud.calculations` → `routers/export.py`. Возвращает `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. **16 колонок (A–P):** дата, номер СФ, поставщик, объём м³, базовая цена, ставка НДС, материал/доставка/прочее без НДС, итого без НДС (формула), те же три с НДС (формулы), итого с НДС (формула), откл. % и откл. ₽ (формулы). Месячные строки с агрегатами через SUMPRODUCT-формулы, разделители между месяцами, grand total на класс. Кнопка «Экспорт» в `ProjectPage.tsx` использует `periodStart`/`periodEnd` напрямую (не debounced) — правильно для действия по кнопке.

### Методология расчёта avg_price

Средняя цена (`avg_price`) вычисляется **с НДС** — чтобы сравнение с базовыми ценами было корректным (базовые цены вводятся пользователем тоже с НДС).

```
avg_price = (mat_total + mat_vat + delivery_for_class + delivery_vat_for_class) / qty
```

- `mat_total` = `SUM(InvoiceItem.amount)` — сумма без НДС из позиции
- `mat_vat` = `SUM(COALESCE(vat_amount, amount * COALESCE(vat_rate, 20.0) / 100))` — НДС; если поле `vat_amount` не заполнено (парсер не извлёк), берётся расчётный НДС по ставке счёта
- Доставка (`item_type = "delivery"`) распределяется пропорционально объёму м³ (`qty`) каждого класса материала относительно общего объёма за месяц
- Расчёт ведётся помесячно; каждый месяц — отдельная строка в `compute_calculations()`

**Отклонение:**
```
deviation_pct    = (avg_price − ref_price) / ref_price × 100
deviation_amount = (avg_price − ref_price) × qty
```

**Оборот в supplier-агрегатах** считается аналогично:
`SUM(amount + COALESCE(vat_amount, amount * COALESCE(vat_rate, 20.0) / 100))`

**VAT guard:** `Invoice.vat_rate` не имеет `NOT NULL` в БД (см. TECH_DEBT.md), поэтому во всех SQL-выражениях используется `COALESCE(vat_rate, 20.0)` как fallback.

**Supplier aggregation** is computed on-the-fly (not cached). Key functions in `crud.suppliers`:
- `get_suppliers_with_stats` — registry list with turnover, project_count, invoice_count, categories
- `get_supplier_detail` — same aggregates for a single supplier (card header)
- `get_supplier_project_stats` — per-project rows with volume_m3 and deviation_pct/amount
- `_compute_supplier_project_deviation` — deviation scoped to supplier's own invoices (same aggregation logic as `compute_full_deviation`, but uses the most recent reference price per class without period filtering — intentional, see docstring). Do not use when period-accurate comparison with the project page is required.

**Supplier deduplication rules** (enforced in both PDF parsing and manual edit):
- `crud.suppliers.get_or_create_supplier(db, name, inn)` — deduplicate by INN if present, else by exact name where `inn IS NULL`. Race-condition safe via `INSERT ... ON CONFLICT DO NOTHING` + re-SELECT. Always sets `created_at` explicitly (ORM default doesn't fire through `pg_insert`).
- `supplier_inn` without `supplier_name` is invalid: `PUT /api/invoices/{id}` returns 422; `crud.documents.create_invoice()` silently clears `_inn` (no Supplier row without a name).
- Editing an invoice sets `supplier_name`/`supplier_inn` from the **canonical DB record** (not raw user input) when INN matches an existing supplier.
- `PUT /suppliers/{id}` returns 409 with different messages for INN conflict (`suppliers.inn` unique) vs name conflict (`uq_suppliers_name_no_inn` partial index for inn IS NULL rows).

---

## Auth system

- **Transport**: httpOnly cookies — `access_token` (Path=/), `refresh_token` (Path=/api/auth), `csrf_token` (readable by JS, Path=/).
- **CSRF**: double-submit cookie pattern — CSRF middleware in `main.py` + `require_csrf` dependency. Exempt paths: login, /docs, /openapi.json.
- **JWT**: HS256, 30 min expiry. Payload: `sub` (user id), `org_id`, `is_superuser`, `org_role`, `exp`, `iat`, `jti`.
- **Refresh tokens**: stored in DB (`refresh_tokens` table), hashed (SHA-256), 14-day expiry, revokable. Rotated on each `/api/auth/refresh` call.
- **Roles**: `OrgRole` (superadmin / admin / member) per organization. `ProjectRole` (customer / contractor) per project link. First user in a new org auto-gets `superadmin` (enforced in `crud.admin.create_user_in_org`).
- **Role matrix (enforced in guards/CRUD, not just UI)**: внутри организации `superadmin` управляет admin+member и назначает роли admin/member; `admin` управляет только member и назначает только member; `member` — ничего. Роль `superadmin` назначается **только** через `/api/admin` (платформенным `is_superuser`). Хелперы `can_set_role` / `can_manage_target` в `crud.admin`; новый guard `require_org_superadmin` в `auth.py`. **Последний активный `superadmin` организации защищён**: нельзя деактивировать/понизить (4xx) — проверка в `crud.admin.set_user_role_and_active`, **атомарная** через `SELECT ... FOR UPDATE` на строках superadmin'ов (`_count_other_active_superadmins_locked`), чтобы два параллельных запроса не сняли последнего. Платформенный `is_superuser` может всё во всех организациях через `/api/admin/*` и не подчиняется матрице.
- **Endpoints**: `POST /api/auth/login`, `POST /api/auth/refresh`, `POST /api/auth/logout`, `GET /api/auth/me` (отдаёт `organization.kind`).
- **Superuser admin console** (`routers/admin.py`, все под `require_superuser`): `GET/POST /api/admin/organizations`, `GET/PATCH /api/admin/organizations/{id}` (вкл. `kind`), `POST /api/admin/organizations/{id}/users` (первый = superadmin), `GET /api/admin/users` (пагинация `q`/`page`/`page_size` → `{items, total, page, page_size}` + `org_name`; **это не голый массив, в отличие от прежнего ответа**), `PATCH /api/admin/users/{id}` (role/active + защита последнего superadmin → 409), `POST /api/admin/users/{id}/reset-password` (сервер генерит пароль через `secrets`, отдаёт plaintext один раз), `POST /api/admin/organizations/{id}/projects` (project_role default = `kind`), `DELETE /api/admin/organizations/{id}/projects/{project_id}`. **Org self-service** (`routers/orgs.py`, под `require_org_admin_with_org`): `GET/POST /api/orgs/users`, `PATCH /api/orgs/users/{id}` — всё по матрице. **Frontend**: маршруты `/admin/*` под guard `RequireSuperuser` (экспортируется из `App.tsx`); пункт «Админ» в `TopNav` виден только суперюзеру.
- **All business routers** require `get_current_user`. Org-level data isolation for project/invoice queries is **not yet enforced** (see TECH_DEBT.md) — auth only prevents unauthenticated access.
- **CLI**: `just create-superuser` / `just create-org` — use these to bootstrap the first users.
- **Auth coverage guardian**: `tests/test_auth_coverage.py` — hits every route without a token, expects 401/403. Run with `just test-backend-unit`.

---

## Testing conventions

### Backend
- **Unit tests** (`tests/unit/`): no DB, pure functions. Representative coverage includes `test_security.py`, `test_auth_deps.py`, and `test_supplier_exclusions.py`.
- **Integration tests** (`tests/integration/`): require `TEST_DATABASE_URL` (separate Neon branch). Loaded by **pytest-dotenv** from `.env.test` (`env_files` in `pyproject.toml`) — the file lives in the **repo root** (`UDP/.env.test`), NOT in `backend/`. Each test runs in a transaction + savepoint → full isolation, automatic rollback. Safety guard in `conftest.py`: refuses `DROP SCHEMA` if `TEST_DATABASE_URL == DATABASE_URL`. To run admin matrix tests that need a non-superuser actor, the `_login_as(user)` contextmanager in `test_admin.py` re-overrides `get_current_user` per-test (the default `client` fixture mocks a platform superuser).
- **Fixtures**: `factory_boy` factories in `tests/factories.py`. AI responses mocked via `respx` + JSON fixtures in `tests/fixtures/openrouter/`.
- `block_real_openrouter` autouse fixture — any accidental real call fails loudly.
- `in_memory_s3` — MinIO mocked for upload tests.
- **Auth in tests**: the `client` fixture in `conftest.py` overrides `get_current_user` with a mock superuser and sets the CSRF cookie + header (`X-CSRF-Token: test-csrf-token`). Integration tests are auth-transparent.

### Frontend
- All API calls via MSW v2 (`src/test/server.ts` + `src/test/handlers.ts`). `onUnhandledRequest: "error"` — add a handler for every new endpoint.
- `renderWithProviders` from `src/test/utils.tsx` — wraps in QueryClient (retries=0), MemoryRouter, ThemeProvider. Accepts `initialUser` param (default: `DEFAULT_TEST_USER`); pass `null` for unauthenticated scenarios.
- New endpoint? Add to `handlers.ts` before writing the test.
- Binary endpoints (blob/arraybuffer) must return `HttpResponse.arrayBuffer(...)` in MSW handlers, not `HttpResponse.json(...)`.
- Auth endpoints already handled in `handlers.ts` (`GET /api/auth/me`, `POST /api/auth/login`, `POST /api/auth/logout`, `POST /api/auth/refresh`). Admin endpoints (`/api/admin/*`) also have default handlers.
- **Testing superuser guards**: `RequireSuperuser` is exported from `App.tsx`. Mount it in a small local `<Routes>` and pass `initialUser` to `renderWithProviders` (a user with `is_superuser: true` vs an org admin) to assert content-vs-redirect — see `pages/admin/RequireSuperuser.test.tsx`.
- **Asserting request payloads**: override the default MSW handler per-test with `server.use(http.put(..., async ({ request, params }) => { onUpdate({ id: params.id, body: await request.json() }); return HttpResponse.json(...); }))` and assert on a `vi.fn()` spy. The default handlers in `handlers.ts` echo `sampleProject` and similar fixtures — they're enough for happy-path GETs but don't capture request bodies.
- **Destructive UI flows must test the confirmation step**, not just the API call. For `AlertDialog`-based confirmations: assert that the API mock is NOT called on first click, only after clicking the explicit confirm button. Verifies that the dialog can't be bypassed by Escape/overlay-click (base-ui `AlertDialog` blocks both).
- **Component-level tests live next to the component** (e.g. `ProjectCard.test.tsx` next to `ProjectCard.tsx`). Page-level tests live in `src/pages/*.test.tsx`. Prefer component-level tests when the logic is isolated to a single component — they're faster and survive page refactors.
- **Interacting with shadcn DropdownMenu / AlertDialog (base-ui under the hood)**: trigger via `getByRole("button", { name: "<aria-label>" })`, then `findByText(...)` for menu items (they render in a Portal but are reachable via `screen`). AlertDialog confirm/cancel buttons are reachable as `getByRole("button", { name: "Удалить" | "Отмена" })`.
- **recharts дублирует текст в служебном span** (для измерений размеров). `getByText("B25")` упадёт с «Found multiple elements». Используй `getAllByText("B25")[0]` или вынеси хелпер `findAxisLabel(name) { return screen.getAllByText(name)[0]; }`.
- **`Cell` в recharts нельзя обернуть в `Tooltip`** — `Cell` не рендерит DOM-элемент сам по себе (потребляется `Bar`). Для аттрибутов на SVG-прямоугольниках баров используй кастомный `shape` prop на `Bar`, возвращающий `<rect ... data-*="..." />`. Recharts `ChartTooltip` через `formatter` — единственный способ показать доп. инфо при наведении внутри SVG-чарта.
- **`TooltipProvider`** из `@/components/ui/tooltip` должен оборачивать всё дерево: добавлен в `App.tsx` и в `AllProviders` в `src/test/utils.tsx`. При добавлении shadcn tooltip — проверяй оба места.
- **base-ui `Tooltip.Trigger` не поддерживает `asChild`** (это паттерн Radix). Не пытайся передать `asChild` в компоненты из `@base-ui/react`.
- **Тестирование derived-selection (useMemo из состояния)**: при наличии `effectiveSelectedIds`-паттерна (trim выборки к видимым строкам) покрывай три кейса: (1) выбрать всё → применить фильтр → проверить счётчик (должен уменьшиться); (2) выбрать всё → применить фильтр → подтвердить удаление → проверить что API получил только видимые id; (3) базовый bulk-delete без фильтра. Пример в `InvoiceTable.test.tsx`.

---

## Code style

### Backend
- `ruff` line-length = 120, target python 3.12.
- Linting rules: E, F, I, B, UP, SIM — see `pyproject.toml` for per-file ignores.
- FastAPI `Depends()` in function args is fine (B008 ignored).
- Pydantic models for request/response bodies (defined in router files).
- Logging via `logging.getLogger(__name__)` — structured via `logging_config.py`.

### Frontend
- TypeScript strict mode.
- shadcn/ui components via `@/components/ui/`. Domain wrappers in `@/components/ui-domain/` (Button, Skeleton, EmptyState, etc.).
- **`Surface`** (`ui-domain/Surface.tsx`) — standard card/panel wrapper: `rounded-lg border border-border-subtle` + bg + padding. Props: `tone` (`default`/`sunken`), `padding` (`none`/`sm`/`md`/`lg`). Use `<Surface padding="none" className="overflow-x-auto">` for all table containers — do NOT hand-roll the same classes as a plain `<div>`.
- **`InputGroup`** (`ui/input-group.tsx`) — shadcn/base-ui component for inputs with icons/addons. Use `InputGroupInput` + `InputGroupAddon` instead of manually positioning icons over a plain `<input>`.
- Tailwind v4 with custom CSS vars: `--color-fg`, `--color-bg`, `--color-surface`, `--color-accent`, etc. Use semantic vars, not raw colors.
- TanStack Query: queries in `services/queries.ts`, keys in `services/queryKeys.ts`.
- Russian UI labels everywhere — this is a Russian-language product.
- `formatMoney` / `formatNumber` / `pluralRu` from `@/lib/format` for all number display.
- `MONTH_NAMES_RU` from `@/lib/constants` for month labels.
- **Tables with pagination/sorting:** use shadcn `Table` + `Pagination` + `Select` for simple cases (client-side state). For complex tables with column visibility, faceted filters, or row selection, consider **TanStack Table** (`@tanstack/react-table`) as one option — see [shadcn tasks example](https://ui.shadcn.com/examples/tasks) as a reference implementation. Manual state management (useState/useMemo) is also valid when the full TanStack API isn't needed.

---

## Environment setup

```
backend/.env          — production config (gitignored)
.env.test             — TEST_DATABASE_URL for integration tests (gitignored; lives in REPO ROOT, loaded by pytest-dotenv via pyproject env_files)
backend/.env.example  — template (includes SECRET_KEY, COOKIE_SECURE, ALLOWED_ORIGINS)
```

Required env variables for auth: `SECRET_KEY` (≥32 random bytes, hex), `COOKIE_SECURE` (true in prod), `ALLOWED_ORIGINS` (JSON array: `["http://localhost:5173"]`).

MinIO must be running separately: `minio.exe server ./minio-data --console-address ":9001"`

Backend URL: `http://localhost:8000` — Swagger at `/docs`
Frontend URL: `http://localhost:5173`

---

## Known tech debt

See `docs/TECH_DEBT.md` for the full list. Key items:
- `GET /dashboard/calculations` without `project_id` has N+1 queries (dashboard router) — don't make it worse.
- `Review.tsx` always uses `invoices[0]` — known bug, multi-invoice docs broken.

---

## Supplier exclusion — key design rules

Пользователь может исключить поставщика из расчётов по конкретному проекту (например, субподрядчик, чьи цены не репрезентативны). Исключение хранится в таблице `project_supplier_exclusions(project_id PK, supplier_id PK, reason TEXT, created_at)`.

- **Scope**: исключение per-project, не глобальное. Поставщик исключается из расчётов avg_price, deviation, export и всех KPI-карточек (оборот, объём м³, счетов) только в рамках этого проекта.
- **Supplier-side stats** (`crud.suppliers`) — исключения **не применяются**: оборот и аналитика поставщика считаются по всем его инвойсам независимо от проектных исключений.
- **Invoice.supplier_id IS NULL** — инвойсы без привязанного поставщика **всегда включаются** в расчёт (фильтр: `or_(supplier_id IS NULL, supplier_id NOT IN (excluded))`).
- **API**: `GET /api/projects/{id}/suppliers` → `[{ id, name, inn, invoice_count }]`; `GET /api/projects/{id}/supplier-exclusions` → `list[int]` (sorted supplier_ids, not objects); `POST/DELETE /api/projects/{id}/supplier-exclusions/{supplier_id}` — добавить/снять исключение (204). Тело POST: `{ reason?: string }`.
- **Frontend**: вкладка «Поставщики» в ProjectPage — чекбоксы с инлайн-формой причины (Escape/Enter). Баннер в обзоре проекта, если есть активные исключения.
- **Idempotent**: повторный POST не создаёт дублей; повторный DELETE не падает.
- **Загрузка exclusions** в роутерах: `excluded = get_excluded_supplier_ids(db, project_id)` из `crud.supplier_exclusions`. Передавать `excluded or None` (пустой set → None, чтобы не добавлять лишний WHERE).

---

## Suppliers section — key design rules (MUST NOT violate)

The `/suppliers` and `/suppliers/:id` sections implement MVP analytics. The following are **intentional constraints**, not gaps:

- **No cross-project average markup** (`средняя наценка поставщика`). Planned prices are per-project/contract. Averaging deviations across different planned bases is methodologically wrong. Deviation lives only in per-project rows of the «По объектам» tab.
- **No market comparison** («дешевле/дороже рынка»). Deferred to backlog — requires fixed basket, enough suppliers per class, logistics correction.
- **No «Сравнение» tab**. Deliberately excluded from MVP.
- **Totals row**: turnover/volume/invoices sum; project_count → `—`; deviation → «не суммируем» italic grey.
- **«Новый» badge** threshold: 30 days from `first_invoice_date`.
- **Merge on INN conflict**: `PUT /suppliers/{id}` returns `409` with `{ code: "inn_conflict", existing: { id, name } }` when the edited INN belongs to another supplier. Frontend shows a merge confirmation dialog, then `POST /suppliers/{target_id}/merge { source_id }` redirects to the surviving supplier's card.

---

## What's NOT in the codebase yet (planned)

- E2E tests (Playwright) — spec written, not implemented.
- GitHub Actions CI — not configured yet.
- Org-level data isolation — auth is enforced but project/invoice queries don't yet filter by org (see TECH_DEBT.md).
- Password reset / email verification — not implemented.
- Production deployment — planned, not live.
- Suppliers: «Сравнение» tab (market benchmark) — backlog, needs ≥3 suppliers per material class.
- Suppliers: Excel/PDF export — button is a stub.