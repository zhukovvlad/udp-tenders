# Org Data Isolation — Design

**Date:** 2026-07-30
**Status:** approved design, pending implementation plan
**Closes TECH_DEBT items:** «Изоляция данных по организации нереализована на уровне запросов», «UI обещает изоляцию, которой нет», «`POST /api/projects` создаёт проект вне организации»

## 1. Problem

All business routers are mounted with a bare `get_current_user` dependency (`main.py:183-192`). `get_project_access` / `ProjectAccess` (`auth.py:134-195`) exist but no router uses them. Consequences:

- Any authenticated user of any organization sees all projects, documents, invoices, dashboards, exports, reference prices.
- The supplier registry is global: `GET /suppliers` aggregates turnover across all orgs; `PUT`/`DELETE`/`merge` let org A rename, delete, or merge a supplier with live invoices belonging to org B (merge re-parents foreign invoices).
- `POST /api/projects` creates a project with `customer_org_id = NULL` and no `project_organizations` row — invisible to everyone but the superuser once isolation is enforced.
- UI hints in `AdminOrgCreate.tsx:16-19` promise visibility guarantees that do not exist.

## 2. Decisions (settled during brainstorming)

| # | Decision |
|---|----------|
| D1 | Scope: **project-level isolation** between organizations. Contractor row-level visibility («видит только свои загрузки») is **out of scope** (§10). |
| D2 | `POST /api/projects` for superuser (`org_id IS NULL`): **403**. Superuser links projects via the existing admin flow (`POST /admin/organizations/{org_id}/projects`). |
| D3 | **No alembic backfill** for orphaned dev data. Projects are linked manually via the admin panel; the residual NULL-class is drained by a one-shot script (§12) run *after* manual linking — an alembic data migration would run *before* linking, when both ends of the chain (`project_organizations`, `customer_org_id`) are still empty, and would be a no-op. |
| D4 | Project create/update/delete: **org superadmin/admin only**; member gets 403. Everything else project-scoped (upload, invoice edits, corridors, exclusions, reference prices) stays available to any member. |
| D5 | Suppliers: **org-scoped registry** (`Supplier.org_id`). The same real-world vendor used by two orgs = two independent rows. No shared-registry mutation policy needed; merge/dedup becomes intra-org by construction. |
| D6 | Upload by superuser: **403**. Operations that create org-owned data require an org (same rule as D2). Closes the only replenishment source of the NULL-org class. For "upload on behalf of a client" a future feature with explicit `org_id` may be added — non-goal here. |
| D7 | Enforcement mechanism: dependency + targeted filters (approach A). Rejected: cross-cutting crud refactor (crud functions are also called from CLI/background contexts without a user), PostgreSQL RLS (disproportionate for MVP). The known weakness of A — "forgot to guard a new endpoint" — is compensated by a structural guard test (§9.2). |
| D8 | Reference data `material-classes`, `units`, `material-types`: **deliberately shared** — readable and writable by all authenticated users. Recorded here so the question does not resurface at review. |
| D9 | `/api/settings` is out of scope; "any member of any org can read/write global LLM settings" is recorded as a new TECH_DEBT item (§13). |
| D10 | **One project — one organization is an enforced invariant**, not an assumption (external review 2026-07-30, P1). The schema (composite PK on `project_organizations`) and the admin API (`link_project` rejects only a duplicate of the *same* pair, `crud/admin.py:377-386`) allowed a second org on a project — which would let org B's members edit org A's documents, cascade supplier renames into A's registry, and break the §6.1 `editor org == doc org` claim. Enforced by §3.4. The contractor axis will *deliberately* lift this constraint later, with its own shared-project semantics — designing those now was rejected as scope creep against D1. |

## 3. Data model changes

### 3.1 `Supplier.org_id`

- New column: `org_id INTEGER REFERENCES organizations(id)`, **nullable**, indexed.
- `org_id IS NULL` = legacy/ownerless class: visible and mutable **only by superuser**. Kept nullable deliberately (D3); drained by the §12 script.

### 3.2 Uniqueness constraints (rebuild)

Current: `inn` globally unique (`models.py:293`), partial unique `uq_suppliers_name_no_inn (name) WHERE inn IS NULL`.

New (deliberately named, PG16+ `NULLS NOT DISTINCT`):

| Name | Definition |
|------|------------|
| `uq_suppliers_org_inn` | `UNIQUE NULLS NOT DISTINCT (org_id, inn) WHERE inn IS NOT NULL` |
| `uq_suppliers_org_name_no_inn` | `UNIQUE NULLS NOT DISTINCT (org_id, name) WHERE inn IS NULL` |

Rationale:

- `NULLS NOT DISTINCT` keeps the `ON CONFLICT` arbiter alive for `org_id IS NULL` rows — without it, two concurrent reparses of a legacy document would silently create duplicate suppliers (BackgroundTasks run several documents concurrently in one process).
- Partiality `WHERE inn IS NOT NULL` on the first index is mandatory: a full `NULLS NOT DISTINCT (org_id, inn)` would collapse all no-INN suppliers of one org into a single row. Default `NULLS DISTINCT` semantics for `inn` *within* an org is the desired behavior and is preserved by splitting into the two partial indexes.
- Model `__table_args__` and the migration change as **one indivisible change**; acceptance criterion — green `just db-test-check` (no autogenerate drift). Note `uq_suppliers_name_no_inn` is currently declared in `__table_args__` (`models.py:301`, PR-1).
- **Spike (first plan task):** does alembic autogenerate handle `postgresql_nulls_not_distinct=True`? Outcome only affects "hand-written DDL vs autogen", not the schema.

### 3.3 `Document.uploaded_by_org_id`

Column and index already exist (`models.py:264`, migration `d1e2f3a4b5c6`) but are **never written** — the only code reference is the model itself. This task starts populating it at upload (§7). No new migration needed. (`uploaded_by_user_id`, `models.py:265`, is populated at the same touch point for the same reason.)

### 3.4 `project_organizations`: one org per project (D10)

- New unique index `uq_project_organizations_project` on `project_organizations (project_id)` — at most one organization per project, enforced by the DB. Safe to create: the table is empty in every known environment (that emptiness is the subject of TECH_DEBT item 3); if a future environment somehow holds multi-org rows, the migration fails loudly — resolve manually, do not auto-pick.
- **Link and `customer_org_id` move together** (external review 2026-07-30, round 2). The unique index alone guarantees «one link row», not «link org == owner org», and the current `link_project` (`crud/admin.py:386-396`) creates the link without touching the project — after the runbook linking step, `customer_org_id` would stay NULL while §5 declares owner and linked org identical. Rules for `POST /admin/organizations/{org_id}/projects` (`link_project`):
  - link is allowed iff `project.customer_org_id IS NULL` or `== org_id`;
  - link **atomically sets** `customer_org_id = org_id` in the same transaction as the `ProjectOrganization` insert;
  - a non-NULL `customer_org_id != org_id` → **409** «Проект принадлежит другой организации — требуется ручное исправление» (legacy/manual state, never produced by this flow);
  - already linked to *any* org → **409** «Проект уже привязан к организации» (the unique index remains the backstop for races).
- `DELETE /admin/organizations/{org_id}/projects/{project_id}` (`unlink_project`): **409** if the project has *any* project-scoped business entity — `documents`, `reference_prices`, `compensation_corridors`, `project_supplier_exclusions` (external review round 2: a documents-only guard would let a new org inherit the previous org's reference prices, corridors, and exclusions) — «Проект содержит данные — перепривязка проекта с данными в MVP не поддерживается». Unlinking a truly empty project (mis-click fix) stays allowed and **atomically clears** `customer_org_id`. Re-linking a project with data to a different org would strand attribution — this guard closes that path instead of defining relink data-migration semantics (deferred with the contractor axis).
- **Serialization of unlink vs data creation** (external review 2026-07-30, round 3). The guard above is check-then-delete; a concurrent upload can pass its access check, lose the race to unlink, and then insert the document — producing exactly the forbidden state (data on an unlinked, ownerless project). The window is wide: upload holds an S3 transfer between check and insert. Mechanism, single lock target so no deadlock cycles:
  - The four creators of guarded entities — upload (`documents`), `POST /reference-prices`, corridor `PUT` (type/class), `POST supplier-exclusions` — take a **`FOR SHARE` row lock** on the project's `project_organizations` row inside the same transaction as their INSERT: `check_project_access(..., for_data_creation=True)` (§4) executes `SELECT project_id FROM project_organizations WHERE project_id = :pid FOR SHARE`. No row (unlinked project — reachable only by superuser for non-upload creators) → no-op, and no race exists because there is nothing to unlink. Concurrent creators share the lock and do not serialize each other.
  - `unlink_project` runs as: lock the row **`FOR UPDATE`** → **re-check all four entity counts under the lock** → any data → 409; else DELETE the row + clear `customer_org_id` → commit. If a creator holds `FOR SHARE`, unlink waits; after the creator commits, the re-check sees the new entity → 409. If unlink wins, the creator's `FOR SHARE` finds no row and its access check fails with 404.
  - Mutations under *existing* entities (invoice edits, verify, reparse) need no lock: their parent document already blocks unlink via the count guard.
  - Grid: a concurrent `upload ↔ unlink` integration test (two real sessions, modeled after `tests/integration/test_upload_race_e2e.py`), asserting one of the two legal outcomes: document created and unlink → 409, or unlink succeeded and upload → 404.
- Tests assert **both** columns (`project_organizations` row and `customer_org_id`) after create (§5), link, and unlink.
- Admin routes stay in the structural-guard whitelist (§9.2) — these behavior changes are in scope regardless; the grid covers them (§9.1).

## 4. Authorization core (`auth.py`)

1. `check_project_access(db, user, project_id, *, for_data_creation: bool = False) -> ProjectAccess` — plain function, the core. Raises **404, not 403** for foreign/missing projects (invariant, frozen in the existing `get_project_access` docstring; pinned by a test). With `for_data_creation=True` it additionally takes the `FOR SHARE` lock on the project's `project_organizations` row (§3.4 serialization) — used only by the four creators of guarded entities. `get_project_access` becomes a thin dependency wrapper over it (without the lock) — one code path, one 404 convention.
2. `accessible_project_ids(db, user)` — subquery `SELECT project_id FROM project_organizations WHERE org_id = :org`. Superuser → `None` (no filter).
3. `scope_to_projects(query, project_id_col, user, db)` — applies `IN (subquery)` or nothing for superuser. The **only** place with the None-branch, so "forgot the superuser case" has one home.

Fail-closed contract: a non-superuser with `org_id IS NULL` sees an empty world (`accessible_project_ids` yields an empty set; `check_project_access` → 404 always). This is correct by construction but is a side effect of `WHERE org_id = NULL` — the isolation grid pins it as a contract (§9.1).

## 5. Endpoint enforcement matrix

| Group | Mechanism |
|---|---|
| `GET /projects` (list) | `scope_to_projects` on `Project.id` |
| `POST /projects` | `require_org_admin_with_org` (reused as-is — already blocks superuser and requires org). Sets `customer_org_id = user.org_id` and creates `ProjectOrganization(project_role = organization.kind)` in the same transaction |
| `PUT/DELETE /projects/{id}` | `check_project_access` (membership, 404) + `require_org_admin` semantics (role; superuser passes; member → 403). Ownership (`customer_org_id`) is *not* separately checked — «the linked org» and «the owner org» are the same organization by the D10/§3.4 invariant |
| `projects/{id}/*` (suppliers, exclusions, corridors) | `get_project_access` dependency replaces the manual `Project`-exists checks (404 semantics preserved). **Creators of guarded entities** — `POST supplier-exclusions`, corridor `PUT` (type/class) — call `check_project_access(..., for_data_creation=True)` instead (§3.4 lock) |
| `dashboard/*`, `export`, `invoices?project_id=` | `check_project_access` on `project_id` from query |
| upload | `check_project_access(..., for_data_creation=True)` on `project_id` from form (§3.4 lock; full order §7) |
| `GET /dashboard/calculations` (no `project_id`) | iterate accessible projects via `scope_to_projects` instead of `Project.all()` — shrinks the recorded N+1 for non-superusers as a side effect |
| `documents/{doc_id}`, `invoices/{invoice_id}` (get/put/verify/unverify/delete/reparse/deskew/pdf) | load resource → `check_project_access(doc.project_id)`; 404 on refusal |
| `GET /invoices/documents` (no `project_id`) | JOIN on `scope_to_projects` |
| `DELETE /invoices/bulk` | silent filtering **in the first query** (JOIN `document_id` → accessible projects), *before* the `_load_document_locked` loop: foreign = nonexistent (consistent with current ignore semantics), and foreign documents are **never locked** — otherwise org A could take `FOR UPDATE` on org B's documents and stall their phase B. Do not invent a batch-wide 404 |
| `GET /reference-prices` | `project_id` given → `check_project_access`; absent → `scope_to_projects` |
| `POST /reference-prices` | `check_project_access(data.project_id, for_data_creation=True)` (§3.4 lock) |
| `PATCH/DELETE /reference-prices/{rp_id}` | derive from `rp.project_id` → `check_project_access` |
| `suppliers/*` | `WHERE org_id = user.org_id`; superuser — no filter (sees all orgs + NULL rows). Details §6 |
| `material-classes`, `units`, `material-types` | shared by decision D8 — no isolation |
| `settings` | out of scope (D9) |

## 6. Suppliers: org-scoped registry

### 6.1 `get_or_create_supplier`

Gains a required `org_id: int | None` parameter. Both lookup paths get an org filter with an explicit `.is_(None)` branch; `ON CONFLICT` arbiters switch to the new composite indexes (§3.2). Call sites (all four):

| Call site | Org source |
|---|---|
| `processing.py:143` (background parse) | `document.uploaded_by_org_id` |
| `crud/documents.py:83` (`create_invoice`, second parse-path writer) | `document.uploaded_by_org_id` |
| `routers/invoices.py:344` (`PUT /invoices/{id}`, user edit) | `document.uploaded_by_org_id` — **no fallback to the editor's org**. Post-isolation, a regular user can only edit documents of their own org's projects, and post-drain those have a non-NULL uploader of the same org, so editor org == doc org always — this holds *because* D10/§3.4 enforces one org per project (with multi-org links it would be false, see D10). The only NULL case is the superuser editing a document of an unlinked project: the supplier stays in the NULL-org class (ownerless data does not silently migrate into someone's registry). The canonical-rename cascade for NULL-org suppliers is thereby reachable only by the superuser |
| `routers/suppliers.py:74` (`POST /suppliers`) | creator's `user.org_id`; superuser → **403** (D6 rule family) |

Legacy documents (`uploaded_by_org_id IS NULL`) reparsed before the drain create NULL-org suppliers without crashing; the arbiter still works thanks to `NULLS NOT DISTINCT`.

### 6.2 Endpoints

All `/api/suppliers/*` filter `WHERE org_id = user.org_id` (superuser — unfiltered): list-with-stats (aggregates automatically count only own invoices), `GET /{id}`, `PUT`, `DELETE`, `GET /duplicates`, `POST /{id}/merge`. `GET /{id}/projects` and `GET /{id}/invoices-list` apply a double filter: own supplier + accessible projects.

**Merge is intra-org unconditionally — including for the superuser** (external review 2026-07-30, P1). «Superuser — unfiltered» governs *visibility* only; for the org user merge is intra-org via visibility, but the unfiltered superuser could pick a source from org A and a target from org B, and `merge_suppliers` (`crud/suppliers.py:119`) would re-parent A's invoices onto B's supplier and delete the source. Two unconditional rules:

- `POST /{id}/merge`: require `source.org_id IS NOT DISTINCT FROM target.org_id`, else **422** «Поставщики принадлежат разным организациям — merge невозможен». NULL↔NULL (two legacy suppliers) is equal and allowed.
- `GET /duplicates`: the pair-join gains `S1.org_id IS NOT DISTINCT FROM S2.org_id` — the superuser sees only intra-org (and NULL-class) pairs, never false cross-org "duplicates" that would invite a forbidden merge.

### 6.3 Constraint-name matching in error handling

`routers/suppliers.py:119` and `:136` parse `err.orig` by substrings `"uq_suppliers_name_no_inn"` and `"inn"`. With the new names this matching silently degrades to the generic branch. Plan items:

- Update the matcher to the new names. **Order matters**: check `uq_suppliers_org_name_no_inn` before `uq_suppliers_org_inn` — the substring `inn` occurs in both names.
- The existing-supplier lookup in the inn-conflict branch gets the org filter.
- Pin both frozen user-facing 409 bodies («Поставщик с таким ИНН уже существует», inn_conflict with existing reference) with tests.

## 7. Upload flow (`POST /invoices/upload`)

The handler gains `current_user` and one edit resolves four things, **in this order**:

1. `user.is_superuser` → **403** (D6).
2. `check_project_access(project_id, for_data_creation=True)` — takes the §3.4 `FOR SHARE` lock (held through the `create_document` commit — the S3 transfer sits inside the window, which is exactly why the lock exists; unlink waiting a few seconds on a rare admin op is acceptable), **strictly before the dedup fast-path**, and also **before the existing `.pdf` filename validation** (currently first in the handler, `invoices.py:261`). Full resulting order: 403 (superuser) → 404 (access) → 400 (format) → hash → dedup → create. Authz before validation is consistent with «foreign = nonexistent»: a user without access to the project must not receive even format feedback about their file. The dedup query (`invoices.py:267-273`) currently runs immediately after hashing and returns `200 {**_serialize_document(existing), duplicate: true}`; if the access check came after it, a user of a foreign project uploading the same PDF would receive the full serialization of a foreign document (metadata, status, invoices). Grid test: foreign `project_id` + existing `file_hash` → **404, not 200-duplicate**. Side bonus: the check also closes the current «nonexistent project_id → FK error → 500» path.
3. Dedup fast-path (unchanged).
4. `create_document(..., uploaded_by_org_id=user.org_id)` — starts populating §3.3.

## 8. UI changes (minimal, three touch points)

1. **`AdminOrgCreate.tsx:16-19` hints.** Customer hint stays (becomes true): «Заказчик — видит все данные проекта». Contractor hint is rewritten in terms of intent, with **no roadmap promises** (they expire like the original did): «Подрядчик — роль организации на проекте». These exact strings go into the implementation plan.
2. **Hiding dead mutations.** Project create/update/delete controls are hidden when `is_superuser || org_role === 'member'` (both fields already served by `/api/auth/me`, `routers/auth.py:192-210`, and typed in `types/auth.ts:21-22`; `Projects.tsx` currently reads no auth context). Upload and invoice editing remain visible for members — they are fully entitled there. Backend 403 stays the source of truth; the UI merely stops offering dead actions (the raw-axios-onError debt makes ugly toasts otherwise).
3. **Suppliers page** — no changes: the server returns filtered data. The superuser additionally sees NULL-org rows; expected.

MSW handlers and existing frontend tests are untouched except where hiding controls changes rendering (targeted).

## 9. Testing

### 9.1 Isolation grid (integration)

Fixtures: two organizations, each with a project, a document, invoices, and org-scoped suppliers. Parameterized sweep:

- Foreign `project_id` / derived resources → **404**; lists → own rows only; bulk delete → silent skip of foreign ids (and no locks taken on them); upload dedup of a foreign hash → 404 (§7).
- **Superuser rows**: sees both worlds — pins the None-branch of `scope_to_projects` (otherwise a «superuser went blind» regression is invisible to the grid).
- **Role rows**: member → 403 on project update/delete vs admin → 200 — pins the 403-vs-404 distribution (foreign = 404, own-but-wrong-role = 403).
- **Org-less user row**: non-superuser with `org_id IS NULL` sees an empty world (fail-closed contract, §4).
- Suppliers: each org sees/mutates only its registry; 409 bodies per §6.3; superuser cross-org merge → 422, duplicates never pair suppliers of different orgs (§6.2).
- **D10 invariant rows**: linking a second org to an already-linked project → 409; link to a project with foreign non-NULL `customer_org_id` → 409; unlink of a project holding any business entity (documents / reference prices / corridors / exclusions — one case each) → 409; successful link sets `customer_org_id`, successful unlink clears it (both columns asserted) (§3.4).
- **Concurrency row**: `upload ↔ unlink` race test with two real sessions (§3.4) — either the document lands and unlink → 409, or unlink wins and upload → 404; never both.

### 9.2 Structural guard

The registry is not a list *beside* the tests — it is the **parameterization source of the grid** (external review 2026-07-30, P2: a declaration-only registry passes even when the endpoint's `check_project_access`/SQL filter was forgotten; "in the registry" must mean "a foreign-access case was executed").

- `ISOLATION_CASES: dict[tuple[str, str], CaseSpec]` — key is **`(method, path_format)`** (one path carries methods with different semantics, e.g. corridors PUT vs DELETE — a path-only key gives false coverage). `CaseSpec` carries a request builder (URL/body/files against the two-org fixture, acting as org B against org A's resource) and the expected foreign-access outcome (`404`, or «silent skip» for bulk, or `200`-with-empty-list for scoped lists).
- One parameterized test executes every `CaseSpec` — an entry cannot exist without its foreign-access case running.
- The structural test iterates `app.routes`, collects `/api/*` routes keyed by `(method, path)`, subtracts an explicit whitelist (`auth`, `admin`, `orgs`, `settings`, `units`, `material-classes`, `material-types`) and fails if a route is missing from `ISOLATION_CASES`. Second assert: **whitelist ∩ ISOLATION_CASES = ∅** — otherwise a route could be "covered" twice and lose the signal when moved.

A new endpoint fails CI until it has an *executable* isolation case, not merely a registry line. Role/superuser/D10 rows from §9.1 remain targeted tests on top of this sweep.

## 10. Out of scope: contractor axis (written waiver)

`ProjectAccess.is_contractor` and the original UI hint promise «подрядчик видит только свои загрузки» — a **second axis** (row-level split within a project by uploader), separate from org-level membership isolation delivered here. Deferred deliberately. What this task does now, cheaply, to avoid a NULL backfill problem later: populate `Document.uploaded_by_org_id` at upload (§7). When the contractor axis lands, the filter has data from day one.

Known consequence, recorded, not fixed: `ProjectSupplierExclusion` and project dashboards reference suppliers via invoices — once a project contains invoices uploaded by another org (contractor axis), the customer will see foreign-registry supplier names (from the invoice) in project analytics. Not reproducible in the MVP «one project — one org» world.

## 11. Dev deployment runbook (numbered, in order)

Between deploy and step 2, org users see an empty world and the superuser can no longer upload — a correct but breakage-looking state; do not diagnose it as a bug.

1. Stop-then-start deploy (async S1 no-overlap invariant) with `just db-migrate`.
2. Superuser links existing dev projects to their organizations via `POST /admin/organizations/{org_id}/projects`.
3. Run the drain script (§12).
4. Review the script's conflict report (suppliers left in NULL-org); resolve manually.
5. Org users resume work.

## 12. Drain script (one-shot, not a migration)

Stored in the repo at `backend/scripts/drain_null_org.sql` (with a usage note in the runbook doc). Runs **after** manual project linking (D3 rationale). Steps:

1. `documents.uploaded_by_org_id ← project → project_organizations` (one org per project — now enforced by §3.4, so the multi-org branch is defense-in-depth: → conflict report, leave NULL).
2. `suppliers.org_id ← invoices → documents → uploaded_by_org_id`: **deterministic rule** — if all of a supplier's invoices resolve to exactly one org, set it; if they span multiple orgs (possible in dev: one vendor's PDFs uploaded into projects now linked to different orgs), leave `NULL` and emit it in the report for manual resolution. No "first match wins".

The report must enumerate **both classes of residual NULL**, not just conflicts: «конфликт (несколько org)» *and* «проект без привязки» (documents of projects the superuser did not link at runbook step 2 are not multi-org and would otherwise pass step 4's review silently, hiding incomplete drainage).

Idempotent: re-running after manual fixes only touches still-NULL rows.

## 13. TECH_DEBT updates shipped with this task

- Close: «Изоляция данных по организации…», «UI обещает изоляцию…», «`POST /api/projects` создаёт проект вне организации».
- Add: «`/api/settings` доступен любому member — глобальные LLM-настройки читает и пишет вся платформа» (found during this design; out of scope, D9).
- Update `docs/agent/auth.md` to describe the enforced model.

## 14. Work order (plan skeleton)

1. **Spike**: alembic autogenerate × `postgresql_nulls_not_distinct` (outcome: hand-written DDL vs autogen; schema unchanged either way).
2. **Migration + models** (one indivisible change): `Supplier.org_id`, rebuild of the two uniqueness constraints under the new names, `uq_project_organizations_project` (§3.4); criterion — green `just db-test-check`.
3. **Authz core**: `check_project_access` (+ `get_project_access` wrapper), `accessible_project_ids`, `scope_to_projects`; unit tests incl. the 404 invariant and org-less fail-closed.
4. **Suppliers**: `get_or_create_supplier(org_id=...)` + 4 call sites, endpoint org filters, constraint matcher + 409-body tests.
5. **Projects router + admin link/unlink guards**: create / update / delete / list / subresources per §5; `link_project` — 409 on already-linked project or foreign `customer_org_id`, atomic `customer_org_id` sync; `unlink_project` — 409 on project with any project-scoped data, atomic `customer_org_id` clear (§3.4).
6. **Remaining routers**: invoices (upload order §7, bulk first-query filter, resource-derive), dashboard, export, reference prices.
7. **Isolation grid + structural guard** (§9). May be pulled up before step 4 for a red-first TDD flow — decided in the plan.
8. **UI** (§8).
9. **Finalization**: drain script + runbook doc, TECH_DEBT updates, `docs/agent/auth.md`.

**Dependency note (4←6):** supplier attribution reads `document.uploaded_by_org_id`, which only starts being written by the upload change in step 6 — until then the parse path passes `org_id=None` for fresh uploads too. Acceptable during development (NULL-arbiter works), but the grid's supplier-attribution assertions require the upload change to land first; the plan must sequence or explicitly cross-reference this.
