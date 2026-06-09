# Модели БД и связи

```
Organization (kind: customer/contractor) → Users (члены org через OrgRole)
Organization → Projects (через ProjectOrganization — ProjectRole: customer/contractor)
Project → Documents → Invoices → InvoiceItems → MaterialClass
Project → ReferencePrices (project ↔ material_class ↔ period)
Project → ProjectSupplierExclusion ← Supplier  (исключения поставщиков из расчётов)
Supplier → Invoices (один поставщик, много проектов)
User → RefreshTokens (много, отзываемые, 14 дней)

UnitOfMeasure (id, code, name, symbol, dimension, base_unit_id self-FK, to_base_multiplier)
UnitAlias (raw_text unique → unit_id FK)
MaterialType (code: concrete/rebar/other, default_unit_id FK → UnitOfMeasure)
MaterialClass.material_type_id FK → MaterialType (ON DELETE RESTRICT, indexed)
InvoiceItem: raw_unit (сырая строка из PDF), normalized_unit_id FK → UnitOfMeasure (nullable),
             normalized_quantity NUMERIC(20,6), normalized_unit_price NUMERIC(24,6)
ReferencePrice.unit_id FK → UnitOfMeasure NOT NULL (только базовая единица)
CompensationCorridor.material_type_id FK → MaterialType
```

## Справочные таблицы единиц измерения

**`units_of_measure`** — справочник единиц: `id`, `code` (уникальный строковый ключ), `name`, `symbol`, `dimension` (`mass`/`volume`/`length`/`count`), `base_unit_id` (self-FK, NULL у базовой единицы), `to_base_multiplier` NUMERIC(30,15). Используется как источник правды при нормализации.

**`unit_aliases`** — сопоставление сырых строк из PDF с единицами: `raw_text` UNIQUE → `unit_id` FK. Ключ нормализуется через `normalize_unit_key` (NFKC, lowercase, collapse whitespace, strip trailing dots) — единый источник правды в `crud/units.py`.

**`material_types`** — типы материалов: `code` (`concrete`/`rebar`/`other`), `default_unit_id` FK → `units_of_measure`. Используется для определения ожидаемой размерности при создании базовых цен и для коридоров компенсации.

## MaterialClass

`material_classes.material_type` (String) заменён на `material_type_id` FK → `material_types` (`ON DELETE RESTRICT`, индекс). `get_or_create_material_class` при создании резолвит `material_type` code → id; неизвестный code → 422 через API / fallback на `"other"` в PDF-парсере с предупреждением в лог.

## InvoiceItem — нормализация единиц

- `unit` (колонка сырой единицы) переименована в `raw_unit` — сохраняет исходную строку из PDF без изменений.
- `normalized_unit_id` FK → `units_of_measure` (nullable, NULL означает неизвестную единицу — строка помечается как «проблемная»).
- `normalized_quantity` NUMERIC(20,6) — количество, пересчитанное в базовую единицу.
- `normalized_unit_price` NUMERIC(24,6) — цена за базовую единицу.
- `item_type` теперь CHECK-constrained enum `ck_item_type` (значения: `material`/`delivery`/`other`).

Нормализация выполняется в `create_invoice` (load_alias_map + normalize_item). PUT-обновление инвойса ренормализует позиции и возвращает `warnings` по неизвестным единицам. Хелпер `item_has_issues` в `crud/units.py` используется совместно `_doc_has_issues` и dashboard `_has_issues` для флага проблемных строк (normalized_unit_id IS NULL).

## ReferencePrice — единица измерения

`reference_prices.unit_id` FK → `units_of_measure`, NOT NULL. При создании валидируется: должна быть базовая единица (`base_unit_id IS NULL`) с размерностью, соответствующей `material_type.default_unit`. Поле `unit_id` неизменяемо после создания.

## CompensationCorridor — material_type_id

`compensation_corridors.material_type` (String) заменён на `material_type_id` FK → `material_types`. Резолвер `get_corridor_map` использует ключи по `material_type_id`. HTTP API коридоров по-прежнему принимает `material_type` code — роутер маппит code→id перед вызовом CRUD.

## Organization.kind

`Organization.kind` (`customer` / `contractor`, реюзает enum `ProjectRole`, `SqlEnum(native_enum=False)`, NOT NULL, `server_default='customer'`) — роль организации по умолчанию. При выдаче доступа к проекту через `/api/admin/.../projects` поле `ProjectOrganization.project_role` берётся из `organization.kind`, но переопределяется явным значением в теле запроса.

Миграция: `2026_05_30_1200-a7b8c9d0e1f2_add_organization_kind` (VARCHAR+CHECK, `server_default` заполняет существующие строки).

## Точность Decimal по колонкам

Финансовые колонки — `Numeric` (не `Float`). SQLAlchemy возвращает их как `decimal.Decimal`.

- `ReferencePrice.price` — NUMERIC(19,4)
- `Invoice.vat_rate` — NUMERIC(5,2) (**без NOT NULL** — см. VAT guard в `calculations.md`)
- `InvoiceItem.quantity` — NUMERIC(15,4)
- `InvoiceItem.unit_price` — NUMERIC(19,4)
- `InvoiceItem.amount`, `InvoiceItem.vat_amount` — NUMERIC(15,2)
- `InvoiceItem.normalized_quantity` — NUMERIC(20,6)
- `InvoiceItem.normalized_unit_price` — NUMERIC(24,6)
- `CompensationCorridor.corridor_pct` — NUMERIC(5,2), nullable (NULL когда `is_compensable=false`)
- `UnitOfMeasure.to_base_multiplier` — NUMERIC(30,15)

Подробности денежного слоя и сериализации — `docs/agent/calculations.md`.
