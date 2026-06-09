# Расчёты цен, отклонений и компенсаций

Единый источник истины — `compute_calculations()` в `crud/calculations.py`. `compute_full_deviation()` делегирует туда же. Данные считаются на лету, без кеша.

## Методология avg_price

Средняя цена считается **с НДС** — чтобы сравнение с базовыми ценами было корректным (базовые цены пользователь тоже вводит с НДС).

```
avg_price = (mat_total + mat_vat + delivery_for_class + delivery_vat_for_class) / qty
```

- `mat_total` = `SUM(InvoiceItem.amount)` — сумма без НДС из позиции
- `mat_vat` = `SUM(COALESCE(vat_amount, amount * COALESCE(vat_rate, 20.0) / 100))` — НДС; если `vat_amount` не извлечён парсером, берётся расчётный по ставке счёта
- `qty` = `SUM(InvoiceItem.normalized_quantity)` — суммируется в базовых единицах; один класс материала = одна размерность
- Расчёт помесячный; каждый месяц — отдельная строка

**Размерностный guard (`dimension_mismatch`):**

`compute_calculations` сравнивает размерность базовой единицы класса (из `material_types.default_unit`) с размерностью `reference_prices.unit_id`. При несовпадении или при смешении разных размерностей внутри одного класса (intra-class dimension mix) строка получает флаг `dimension_mismatch=True`. Такие строки **исключаются** из расчёта отклонения и компенсации (поля `deviation_pct`, `deviation_amount`, `compensation_*` возвращаются как `None`). Выходные поля строки: `unit_symbol` и `dimension_mismatch`.

**Отклонение:**
```
deviation_pct    = (avg_price − ref_price) / ref_price × 100
deviation_amount = (avg_price − ref_price) × qty
```

**Распределение доставки:**

- **Моно-размерность** (все классы месяца одной размерности): доставка распределяется пропорционально `SUM(normalized_quantity)` каждого класса.
- **Смешанная размерность** (разные dimension в одном месяце): доставка распределяется пропорционально `amount` (денежной сумме позиций) через `compute_shared_shares`. Строки с нулевой `normalized_quantity` или неизвестной единицей (`normalized_unit_id IS NULL`) при mono-distribution получают нулевую долю.

## Исключённые поставщики

Все три функции (`compute_calculations`, `compute_full_deviation`, `compute_export_rows`) принимают `excluded_supplier_ids: set[int] | None`. При непустом set инвойсы исключённых фильтруются через `or_(Invoice.supplier_id.is_(None), Invoice.supplier_id.notin_(excluded))` — **инвойсы без поставщика всегда включаются**. `get_project_summary` в `dashboard.py` применяет тот же фильтр ко всем агрегатам (оборот, объём м³, кол-во счетов). Загружать: `excluded = get_excluded_supplier_ids(db, project_id)`, передавать `excluded or None`.

## Dashboard и месячный оборот

`GET /dashboard/calculations` — на лету через `compute_calculations()`.

`GET /dashboard/monthly-summary?project_id=` питает таб «По месяцам» (`MonthlyTab.tsx`). **Оборот по месяцам = полная стоимость всех позиций СФ с НДС**: `SUM(item.amount + COALESCE(item.vat_amount, item.amount * COALESCE(invoice.vat_rate, 20.0)/100))` по **всем** `item_type` (material + delivery + прочее), без фильтра по типу. Намеренно отличается от avg_price (которая работает только с `material`): тут нужен полный оборот по счёту, как выставил поставщик.

## VAT guard

`Invoice.vat_rate` не имеет NOT NULL (см. `TECH_DEBT.md`), поэтому во всех SQL-выражениях — `COALESCE(vat_rate, literal(Decimal("20.0")))`: type-bound Decimal literal, чтобы COALESCE оставался NUMERIC в DB-выражении и не смешивался с float.

## Decimal-слой

Весь расчётный слой (`crud/calculations.py`, `crud/suppliers.py`) работает в `Decimal` end-to-end. Округление — `money_round` из `backend/finance.py` (ROUND_HALF_UP, RU-арифметика). Нормализация на входе LLM→DB: `_dec(value)` в `crud/documents.py` через `Decimal(str(value))` отсекает бинарную погрешность float. API-payloads (`price`, `corridor_pct`) — `Decimal`-поля Pydantic. Сериализация: `DecimalJSONResponse` в `main.py` (`default_response_class`) конвертирует Decimal→float при отдаче JSON; фронтенд-контракт не меняется.

## DateTime serialization

Все `DateTime`-колонки хранятся как **naive UTC** (без timezone). При ручной сериализации в JSON добавляй `"Z"`: `dt.isoformat() + "Z"` — сигнал браузеру о UTC, исключает сдвиг даты у пользователей не в UTC. Pydantic-схемы с `datetime` делают это сами; правило актуально для dict-ответов (например в `crud/admin.py`).

## Экспорт Excel

`GET /api/export/excel?project_id=&period_start=&period_end=&material_class_id=` → openpyxl через `compute_export_rows()` → `routers/export.py`. Возвращает `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.

**21 колонка (A–U):** два блока единиц — «по документу» (сырые данные из PDF) и «расчётное» (нормализованные). Блок «по документу»: дата, номер СФ, поставщик, «Кол-во по документу», «Ед. изм. по документу». Блок «расчётное»: «Расчётное кол-во», «Базовая ед. изм.», базовая цена, ставка НДС, материал/доставка/прочее без НДС, итого без НДС (формула), те же три с НДС (формулы), итого с НДС (формула), откл. % и откл. ₽ (формулы). Строчная математика (цены на единицу) считается на `normalized_quantity`. Месячные строки — SUMPRODUCT-формулы, разделители между месяцами, grand total на класс. Кнопка «Экспорт» в `ProjectPage.tsx` использует `periodStart`/`periodEnd` напрямую (не debounced) — правильно для действия по кнопке.

## Коридор компенсации (Spec 2 — fallback иерархия)

Таблица `compensation_corridors(id PK, project_id, material_type_id? FK→material_types, material_class_id?, is_compensable, corridor_pct?)` — иерархические правила per-project. Ровно одно из `material_type_id`/`material_class_id` заполнено (CHECK constraint). `material_type` (String) заменён на `material_type_id` FK → `material_types`; резолвер `get_corridor_map` использует ключи по `material_type_id`. HTTP API по-прежнему принимает `material_type` code (напр. `PUT .../corridors/type/concrete`) — роутер маппит code→id перед передачей в CRUD.

**Whitelist-дефолт:** нет строки = не компенсируется.

**Fallback-резолв:** class-level → type-level → нет записи. Class-level override побеждает в обе стороны.

- `is_compensable=false` — явно выключено на данном уровне
- `is_compensable=true, corridor_pct=X` — допуск ±X%, компенсация за пределами коридора
- `is_compensable=true, corridor_pct=0` — любое отклонение компенсируется

**Формула** (нелинейная, на единицу объёма, P = avg_price, B = ref_price, k = corridor_pct/100):
```
P > B*(1+k):  comp = P - B*(1+k)    # + удорожание
P < B*(1-k):  comp = P - B*(1-k)    # − экономия
иначе:        comp = 0
```
На объём: `compensation_amount = comp * qty`. Знак: + доплата поставщику / − возврат заказчику.

**Важно:** формула нелинейна → считается от средней цены за месяц, не из построчных значений.

- **Batch-резолв в `crud/calculations.py`:** `get_corridor_map(db, project_id)` → `(by_class, by_type)` dicts; `resolve_corridor(by_class, by_type, class_id, material_type)` → `(compensable, corridor_pct)`. Один запрос на проект, без N+1.
- **Чистая формула:** `compute_compensation_per_unit(avg_price, ref_price, corridor_pct)` — unit-тестируема без БД.
- **Три поля в dict строки:** `corridor_pct`, `compensation_per_unit`, `compensation_amount`. `None` = не компенсируется (нет строки или `is_compensable=false`), `Decimal("0")` = внутри коридора.
- **API:** `GET /api/projects/{id}/corridors` (resolved matrix), `PUT/DELETE /api/projects/{id}/corridors/type/{material_type}`, `PUT/DELETE /api/projects/{id}/corridors/class/{material_class_id}`. PUT тело: `{is_compensable, corridor_pct?}` — `corridor_pct` обязателен при `is_compensable=true` (422 иначе). Upsert через `pg_insert ON CONFLICT` по partial unique index.
- **Excel:** колонки Q «Коридор, %», R «Компенсация, ₽». `None` → пусто.
- **Frontend:** таб «Коридоры» (`CorridorsTab.tsx`) — единая таблица, сгруппированная по типу. Заголовки типов с toggle вкл/выкл + %; строки классов с индикацией «(наследовано)» / «[своё]» + кнопкой `×` для удаления class-override.
