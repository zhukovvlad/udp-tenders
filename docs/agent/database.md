# Модели БД и связи

```
Organization (kind: customer/contractor) → Users (члены org через OrgRole)
Organization → Projects (через ProjectOrganization — ProjectRole: customer/contractor)
Project → Documents → Invoices → InvoiceItems → MaterialClass
Project → ReferencePrices (project ↔ material_class ↔ period)
Project → ProjectSupplierExclusion ← Supplier  (исключения поставщиков из расчётов)
Supplier → Invoices (один поставщик, много проектов)
User → RefreshTokens (много, отзываемые, 14 дней)
```

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
- `CompensationCorridor.corridor_pct` — NUMERIC(5,2), nullable (NULL когда `is_compensable=false`)

Подробности денежного слоя и сериализации — `docs/agent/calculations.md`.
