# UDP — CLAUDE.md

## What this project is

**УПД Трекер цен** — a Russian-language B2B web app for construction procurement teams. Users upload PDF invoices (УПД / счёт-фактура), the app parses them via LLM, tracks material price dynamics, and exports deviation reports for cost justification.

Target user: тендерный менеджер (procurement/tender manager) in a construction company.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.14+, FastAPI, SQLAlchemy (sync), Alembic |
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
just test-backend         # all pytest (56 tests, ~22s)
just test-backend-unit    # unit only, no DB, ~1s
just test-backend-integration  # requires TEST_DATABASE_URL

just test-frontend        # vitest (18 tests, ~4s)
just lint                 # ruff + eslint
just typecheck-frontend   # tsc -b --noEmit
just coverage-backend     # HTML → backend/htmlcov/index.html
just db-migrate           # alembic upgrade head
```

Shell on Windows: `bash -cu` (git bash). All scripts use Unix syntax.

---

## Project structure

```
UDP/
├── backend/
│   ├── main.py           — FastAPI app, CORS, routers, middleware
│   ├── models.py         — ORM models (Project, Document, Invoice, InvoiceItem, MaterialClass, ReferencePrice, PriceCalculation)
│   ├── crud.py           — DB operations, recalculate_prices
│   ├── pdf_parser.py     — OpenRouter API parsing
│   ├── s3.py             — MinIO helpers
│   ├── routers/          — projects, invoices, dashboard, export, material_classes, reference_prices, settings
│   ├── alembic/          — migrations
│   └── tests/            — unit/ + integration/ + fixtures/
├── frontend/src/
│   ├── pages/            — Dashboard, Projects, ProjectPage, Suppliers, Materials, Reports, Review, Settings
│   ├── components/       — ui/, ui-domain/, layout/, dashboard/, projects/, invoices/, review/
│   ├── services/         — api/ (axios), queries.ts (TanStack Query), queryKeys.ts
│   └── types/            — TypeScript types per domain
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
- **Reference prices** (плановые цены) live inside Project card (tab) and Material card — no separate route.
- **Progressive disclosure** — AI confidence percentages are hidden in tooltips; the document card is where the technical layer fully surfaces.

---

## Database models — key relationships

```
Project → Documents → Invoices → InvoiceItems → MaterialClass
Project → ReferencePrices (project ↔ material_class ↔ period)
Project → PriceCalculations (aggregated monthly stats)
```

`PriceCalculation` is a pre-computed cache — always recalculate after invoice changes via `crud.recalculate_prices`.

---

## Testing conventions

### Backend
- **Unit tests** (`tests/unit/`): no DB, pure functions.
- **Integration tests** (`tests/integration/`): require `TEST_DATABASE_URL` (separate Neon branch). Each test runs in a transaction + savepoint → full isolation, automatic rollback.
- **Fixtures**: `factory_boy` factories in `tests/factories.py`. AI responses mocked via `respx` + JSON fixtures in `tests/fixtures/openrouter/`.
- `block_real_openrouter` autouse fixture — any accidental real call fails loudly.
- `in_memory_s3` — MinIO mocked for upload tests.

### Frontend
- All API calls via MSW v2 (`src/test/server.ts` + `src/test/handlers.ts`). `onUnhandledRequest: "error"` — add a handler for every new endpoint.
- `renderWithProviders` from `src/test/utils.tsx` — wraps in QueryClient (retries=0), MemoryRouter, ThemeProvider.
- New endpoint? Add to `handlers.ts` before writing the test.

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
- Tailwind v4 with custom CSS vars: `--color-fg`, `--color-bg`, `--color-surface`, `--color-accent`, etc. Use semantic vars, not raw colors.
- TanStack Query: queries in `services/queries.ts`, keys in `services/queryKeys.ts`.
- Russian UI labels everywhere — this is a Russian-language product.
- `formatMoney` / `formatNumber` from `@/lib/format` for all number display.
- `MONTH_NAMES_RU` from `@/lib/constants` for month labels.

---

## Environment setup

```
backend/.env          — production config (gitignored)
backend/.env.test     — TEST_DATABASE_URL for integration tests (gitignored)
backend/.env.example  — template
```

MinIO must be running separately: `minio.exe server ./minio-data --console-address ":9001"`

Backend URL: `http://localhost:8000` — Swagger at `/docs`
Frontend URL: `http://localhost:5173`

---

## Known tech debt

See `docs/TECH_DEBT.md` for the full list. Key items:
- `auto_calculate` has N+1 queries (dashboard router) — don't make it worse.
- `Review.tsx` always uses `invoices[0]` — known bug, multi-invoice docs broken.
- No composite index on `PriceCalculation(project_id, material_class_id, period_start, period_end)`.
- `datetime.utcnow()` used in a few places — should be `datetime.now(UTC)`.

---

## What's NOT in the codebase yet (planned)

- E2E tests (Playwright) — spec written, not implemented.
- GitHub Actions CI — not configured yet.
- Auth / multi-user — settings router exists, no real auth yet.
- Production deployment — planned, not live.
