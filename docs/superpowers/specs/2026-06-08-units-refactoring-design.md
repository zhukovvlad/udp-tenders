# Спецификация: справочники единиц измерения и типов материалов

**Дата:** 2026-06-08
**Статус:** утверждён
**Scope:** backend schema + normalization + calculations + API + migration + tests

---

## 1. Контекст и цель

Система трекинга УПД масштабируется с бетона (где единица почти всегда м³) на
арматуру, кирпич, сыпучие смеси. Парсер отдаёт единицы измерения в разнобой:
`т`, `тн`, `тонн`, `кг`.

**Цель:** стандартизировать единицы на бэкенде и корректно считать компенсации
по эталонным ценам, убрав хардкод `material_type` (String) и `unit` (String).

**Принципы:**
- YAGNI — сидим только реальные единицы из данных
- Строгая нормализация — детерминированный маппинг при приёме, без угадывания
- Write-time нормализация — результат вычислен один раз, аудируем, не зависит от будущих изменений справочника
- Никаких физических формул (плотность, удельный вес) — перевод между размерностями вне scope

---

## 2. Scope

### В работе

- Справочники `units_of_measure`, `unit_aliases`, `material_types`
- Конвертация внутри одной размерности (кг↔т, л↔м³)
- Нормализация при приёме: `normalized_*` на `InvoiceItem`
- `unit_id` NOT NULL на `ReferencePrice`
- `material_type_id` FK на `MaterialClass` и `CompensationCorridor`
- `item_type` → Enum + CHECK constraint
- Guard по dimension в калькуляторе
- Delivery distribution: qty для моно-dimension, fallback amount для mixed
- Миграция с предохранителями и down-миграцией
- API: read-only справочники, warning при unknown unit
- Excel: два блока колонок (сырые + расчётные)
- Тесты: unit + integration + migration backfill + edge cases

### Осознанно за scope (backlog)

| Что | Почему отложено |
|---|---|
| Перевод между размерностями через плотность | Требует справочника плотностей, сложная предметная область |
| Множественные единицы на тип материала | Одна базовая единица на размерность достаточна |
| UI-редактор справочников (CRUD units/aliases/types) | MVP — через миграции/CLI, фронтенд-компоненты дорогие |
| Самообучающийся справочник алиасов | Отличная идея, требует UX-дизайна workflow |
| Lazy reprocess (`POST /api/admin/reprocess-units`) | YAGNI сейчас, схема позволяет добавить без изменений |
| Темпоральное версионирование справочников | Не нужно при иммутабельном `to_base_multiplier` |
| BAG и экзотические единицы | Сидим реальные из данных, расширяем append-only |

---

## 3. Схема БД

### 3.1. Новые таблицы

**`UnitDimension`** — enum (`native_enum=False`, VARCHAR + CHECK, name=`ck_unit_dimension`):
`mass`, `volume`, `length`, `count`.

**`ItemType`** — enum (`native_enum=False`, VARCHAR + CHECK, name=`ck_item_type`):
`material`, `delivery`, `other`. Ортогональная ось к `material_type` — определяет
роль строки в расчёте, не семейство материала.

**`units_of_measure`** — канонические единицы:

| Поле | Тип | Описание |
|---|---|---|
| `id` | int PK | |
| `code` | str, UNIQUE | `TON`, `KG`, `M3`, `L`, `M`, `PCS` |
| `name` | str | «Тонна», «Килограмм» |
| `symbol` | str | «т», «кг» (для UI) |
| `dimension` | enum `UnitDimension` | |
| `base_unit_id` | FK self, nullable, ON DELETE RESTRICT | NULL = эта единица базовая в размерности |
| `to_base_multiplier` | Numeric(30,15), default=1 | `qty_base = qty * multiplier` |

- CHECK: `base_unit_id IS NULL => to_base_multiplier = 1`
- Политика: `to_base_multiplier` **иммутабелен** (append-only, часть финансового аудита)
- Самоссылка через `relationship(remote_side=[id])`

**`unit_aliases`** — мост «сырая строка → канон»:

| Поле | Тип | Описание |
|---|---|---|
| `id` | int PK | |
| `raw_text` | str, UNIQUE | нормализованный ключ: `normalize_unit_key()` = `raw.strip().lower()` |
| `unit_id` | FK → `units_of_measure`, ON DELETE CASCADE | |

Ключевое: `normalize_unit_key()` — **одна функция**, используемая и при сидинге,
и при поиске. Поиск в БД — `WHERE raw_text = :normalized_key`, без `lower()` в SQL
(UNIQUE constraint даёт B-Tree индекс бесплатно).

**`material_types`** — семейство материала:

| Поле | Тип | Описание |
|---|---|---|
| `id` | int PK | |
| `code` | str, UNIQUE | `concrete` / `rebar` / `other` |
| `name` | str | «Бетон», «Арматура», «Прочее» |
| `default_unit_id` | FK → `units_of_measure`, nullable | подсказка для UI, **не** источник истины для цен |

### 3.2. Изменяемые таблицы

**`material_classes`:**
- DROP `material_type` (String)
- ADD `material_type_id` FK → `material_types`, NOT NULL (после бэкфилла), ON DELETE RESTRICT

**`invoice_items`:**
- RENAME `unit` → `raw_unit` (сырое из документа, аудит)
- ADD `normalized_unit_id` FK → `units_of_measure`, nullable
- ADD `normalized_quantity` Numeric(20,6), nullable
- ADD `normalized_unit_price` Numeric(24,6), nullable
- `quantity` / `unit_price` / `amount` остаются сырыми (как от парсера)
- `item_type`: String → Enum `ItemType` (VARCHAR + CHECK `ck_item_type`)

**`reference_prices`:**
- ADD `unit_id` FK → `units_of_measure`, NOT NULL (после бэкфилла), ON DELETE RESTRICT
- Валидация: `unit_id` должен быть базовой единицей (`base_unit_id IS NULL`)

**`compensation_corridors`:**
- DROP `material_type` (String)
- ADD `material_type_id` FK → `material_types`, nullable, ON DELETE CASCADE
- UPDATE CHECK: `chk_corridor_target_exclusive` → `(material_type_id IS NOT NULL AND material_class_id IS NULL) OR (material_type_id IS NULL AND material_class_id IS NOT NULL)`
- REBUILD INDEX: `uq_corridor_project_type` → на `material_type_id`

---

## 4. Логика нормализации (при приёме)

### 4.1. Нормализация в `create_invoice()`

Выполняется **один раз** при сохранении строки счёта:

```
normalize_unit_key(raw) → key = raw.strip().lower()
                         ↓
              unit_aliases WHERE raw_text = key
                    ↓                     ↓
               найден alias           не найден
                    ↓                     ↓
        unit = alias.unit         normalized_* = NULL
        base = unit.base_unit     document.has_issues = True
              or unit
                    ↓
    normalized_quantity = quantity × unit.to_base_multiplier
    normalized_unit_price = unit_price / unit.to_base_multiplier
    normalized_unit_id = base.id
                    ↓
          ИНВАРИАНТ: norm_qty × norm_price ≈ amount
          (допуск: max(1₽, 0.1%))
```

Функция-нормализатор: **чистая, unit-тестируемая без БД** (принимает `raw_unit: str`,
`aliases: dict[str, UnitAlias]` → возвращает `NormalizationResult | None`).
Поиск алиасов — один bulk-SELECT при обработке документа (не N запросов на строку).

### 4.2. Guard в калькуляторе

В `compute_calculations`, перед сравнением с эталонной ценой — два уровня защиты:

1. `normalized_unit_id IS NULL` → пропустить строку (нет нормализованной единицы)
2. `item.normalized_unit.dimension != reference_price.unit.dimension` → НЕ считать, пометить на ручную проверку

Оба случая — честный флаг, не тихий неверный расчёт.

### 4.3. Delivery distribution (обновлённая логика)

Текущая логика: доставка распределяется пропорционально `quantity` (м³) каждого класса.

**Проблема «яблок и апельсинов»:** при смешанных размерностях (м³ + т) суммирование
`normalized_quantity` физически бессмысленно: 50 м³ бетона + 2 т арматуры = 52 «условных попугаев».

**Решение:**

```python
dimensions = set(item.normalized_unit.dimension for item in materials if item.normalized_unit_id)

if len(dimensions) == 1:
    # Моно-размерность → распределение по normalized_quantity (физический смысл)
    share = class_qty / total_qty
elif len(dimensions) > 1:
    # Смешанные размерности → fallback по amount (деньги — универсальный знаменатель)
    share = class_amount / total_amount
```

**Edge cases:**
- `total_amount = 0` при fallback по amount (все материалы бесплатные) → доставка не распределяется (0 для всех строк), без DivisionByZero
- Часть строк `amount=0` → эти строки получают 0 доставки, ненулевые делят 100%
- Все `normalized_unit_id IS NULL` → доставка не распределяется (нет базы для пропорции)

### 4.4. Изменения в `compute_calculations()`

- `WHERE normalized_unit_id IS NOT NULL` — строки без нормализации исключены
- `SUM(normalized_quantity)` вместо `SUM(quantity)` для агрегации объёмов
- `avg_price` через нормализованные значения → всегда в базовой единице размерности
- Delivery distribution по обновлённой логике (4.3)

### Без изменений

- `amount` (сырая сумма из СФ) — не пересчитывается
- `vat_amount` / `vat_rate` логика
- Monthly summary (`SUM(amount + vat)`) — оборот = как выставлено поставщиком
- Supplier aggregation endpoints

---

## 5. API

### 5.1. Новые эндпоинты (read-only для MVP)

```
GET /api/units                → list[UnitOfMeasure]  (id, code, name, symbol, dimension)
GET /api/units/{id}/aliases   → list[UnitAlias]
GET /api/material-types       → list[MaterialType]   (id, code, name, default_unit)
```

Управление справочниками — через миграции/CLI, не через UI.

### 5.2. Изменения в существующих эндпоинтах

**`POST /api/documents/{id}/parse`** (и upload flow):
- `create_invoice()` дополняется нормализацией (п. 4.1)
- `normalized_unit_id IS NULL` хотя бы у одной строки → `document.has_issues = True`

**`PUT /api/invoices/{id}`** (ручное редактирование):
- При изменении `raw_unit` или `quantity` → перенормализация
- Новые поля в `InvoiceItemEdit`: `raw_unit` (вместо `unit`)
- Warning при неизвестной единице:
  ```json
  {"warnings": [{"field": "raw_unit", "code": "unknown_unit",
    "message": "Единица измерения «бухта» не найдена в справочнике"}]}
  ```

**`POST /api/reference-prices`** и `PUT`:
- Новое обязательное поле `unit_id: int`
- Валидация: `unit_id` должен быть базовой единицей (`base_unit_id IS NULL`) — 422 иначе

**`GET /api/dashboard/calculations`**:
- Дополнительные поля: `unit_symbol` (символ базовой единицы), `dimension_mismatch: bool`

**`GET /api/export/excel`**:
- Два блока колонок:
  - Сырые данные из УПД: «Кол-во по документу», «Ед. изм. по документу»
  - Данные для расчёта: «Расчётный объём», «Базовая ед. изм.»
  - Пустые ячейки в расчётном блоке при `normalized_* IS NULL`

### 5.3. Без изменений

- `GET /api/dashboard/monthly-summary` — оборот по сырым `amount`
- Supplier endpoints — агрегация по `amount`
- Auth, admin, org endpoints

---

## 6. Парсер (`pdf_parser.py`)

Парсер **не меняется** в части извлечения данных — по-прежнему отдаёт `unit` как
сырую строку из PDF. Нормализация — ответственность `create_invoice()`.

Единственное изменение: `create_invoice()` резольвит `material_type` (строка от парсера)
в `material_type_id`:

```python
material_type_row = db.query(MaterialType).filter_by(code=item["material_type"]).first()
```

Неизвестный `material_type` от парсера → `has_issues`, класс материала не создаётся автоматически.

---

## 7. Миграция (Alembic)

Порядок критичен — NOT NULL ставится **только после** бэкфилла.

### Step 1: Schema — создание таблиц и nullable-колонок

```sql
CREATE TABLE units_of_measure (...)
CREATE TABLE unit_aliases (...)
CREATE TABLE material_types (...)

ALTER TABLE material_classes
  ADD COLUMN material_type_id INT REFERENCES material_types(id)
    ON DELETE RESTRICT  -- nullable на этом этапе

ALTER TABLE invoice_items
  RENAME COLUMN unit TO raw_unit  -- op.alter_column(..., new_column_name='raw_unit')
  ADD COLUMN normalized_unit_id INT REFERENCES units_of_measure(id)
  ADD COLUMN normalized_quantity NUMERIC(20,6)
  ADD COLUMN normalized_unit_price NUMERIC(24,6)

-- Pre-check перед CHECK constraint:
-- SELECT COUNT(*) FROM invoice_items WHERE item_type NOT IN ('material','delivery','other')
-- Если > 0 → миграция FAIL
ALTER TABLE invoice_items
  ADD CONSTRAINT ck_item_type CHECK (item_type IN ('material','delivery','other'))

ALTER TABLE reference_prices
  ADD COLUMN unit_id INT REFERENCES units_of_measure(id)
    ON DELETE RESTRICT

ALTER TABLE compensation_corridors
  ADD COLUMN material_type_id INT REFERENCES material_types(id)
    ON DELETE CASCADE
```

### Step 2: Seed справочников (data migration)

```python
# Базовые единицы первыми (flush), затем производные с их id
TON = insert(code="TON", name="Тонна",     symbol="т",  dimension="mass",   base_unit_id=None, multiplier=1)
KG  = insert(code="KG",  name="Килограмм", symbol="кг", dimension="mass",   base_unit_id=TON,  multiplier=0.001)
M3  = insert(code="M3",  name="Куб. метр", symbol="м³", dimension="volume", base_unit_id=None, multiplier=1)
L   = insert(code="L",   name="Литр",      symbol="л",  dimension="volume", base_unit_id=M3,   multiplier=0.001)
M   = insert(code="M",   name="Метр",      symbol="м",  dimension="length", base_unit_id=None, multiplier=1)
PCS = insert(code="PCS", name="Штука",     symbol="шт", dimension="count",  base_unit_id=None, multiplier=1)

# Алиасы — собрать из SELECT DISTINCT lower(trim(raw_unit)) FROM invoice_items
# Минимальный набор:
# т/тн/тонн/тонна/t/ton   → TON
# кг/kg                    → KG
# м3/м³/m3/куб/куб.м       → M3
# л/l                      → L
# м/m/пог.м/п.м            → M
# шт/шт./штук/pcs          → PCS

# material_types
concrete = insert(code="concrete", name="Бетон",    default_unit_id=M3)
rebar    = insert(code="rebar",    name="Арматура", default_unit_id=TON)
other    = insert(code="other",    name="Прочее",   default_unit_id=None)
```

### Step 3: Бэкфилл существующих данных

```python
# Предохранитель 1: SELECT DISTINCT material_type FROM material_classes
# Если есть значения вне {concrete, rebar, other} → миграция FAIL

# Предохранитель 2: SELECT DISTINCT mt.code
#   FROM reference_prices rp JOIN material_classes mc ON rp.material_class_id = mc.id
# Должен быть только 'concrete' (все ref_prices = M3)

# material_classes.material_type_id ← маппинг строк
op.execute("""
  UPDATE material_classes SET material_type_id = (
    SELECT id FROM material_types WHERE code = material_classes.material_type
  )
""")

# reference_prices.unit_id ← M3 для всех
op.execute(f"UPDATE reference_prices SET unit_id = {M3_ID}")

# compensation_corridors.material_type_id ← маппинг строк
op.execute("""
  UPDATE compensation_corridors SET material_type_id = (
    SELECT id FROM material_types WHERE code = compensation_corridors.material_type
  ) WHERE material_type IS NOT NULL
""")

# invoice_items — bulk SQL (один запрос, не Python-цикл):
op.execute("""
  UPDATE invoice_items AS i
  SET
    normalized_unit_id = COALESCE(u.base_unit_id, u.id),
    normalized_quantity = i.quantity * u.to_base_multiplier,
    normalized_unit_price = i.unit_price / u.to_base_multiplier
  FROM unit_aliases AS a
  JOIN units_of_measure AS u ON a.unit_id = u.id
  WHERE lower(trim(i.raw_unit)) = a.raw_text
""")
```

### Step 4: Ужесточение

```sql
ALTER TABLE material_classes
  ALTER COLUMN material_type_id SET NOT NULL;
ALTER TABLE material_classes
  DROP COLUMN material_type;

ALTER TABLE reference_prices
  ALTER COLUMN unit_id SET NOT NULL;

ALTER TABLE compensation_corridors
  DROP COLUMN material_type;
  -- material_type_id остаётся nullable (уровень fallback)
  -- UPDATE CHECK: chk_corridor_target_exclusive
  -- REBUILD INDEX: uq_corridor_project_type
```

### Step 5: Down-миграция (обратимость)

```sql
-- Восстановить строковые поля из справочников ДО DROP таблиц:
ALTER TABLE material_classes ADD COLUMN material_type VARCHAR;
UPDATE material_classes SET material_type = (
  SELECT code FROM material_types WHERE id = material_type_id
);

ALTER TABLE compensation_corridors ADD COLUMN material_type VARCHAR;
UPDATE compensation_corridors SET material_type = (
  SELECT code FROM material_types WHERE id = material_type_id
) WHERE material_type_id IS NOT NULL;

-- Откат invoice_items:
ALTER TABLE invoice_items RENAME COLUMN raw_unit TO unit;
ALTER TABLE invoice_items DROP COLUMN normalized_unit_id, normalized_quantity, normalized_unit_price;
ALTER TABLE invoice_items DROP CONSTRAINT ck_item_type;

-- Откат reference_prices:
ALTER TABLE reference_prices DROP COLUMN unit_id;

-- DROP таблиц:
DROP TABLE unit_aliases;
DROP TABLE units_of_measure;
DROP TABLE material_types;
```

---

## 8. Тестирование

### 8.1. Unit-тесты (без БД)

**`test_unit_normalization.py`:**
- `т` → TON, qty=5 → normalized_qty=5, multiplier=1
- `кг` → KG → TON, qty=5000 → normalized_qty=5.0, multiplier=0.001
- `тонн` / `тн` / `t` → все → TON
- Неизвестная единица `"бухта"` → `None`
- Пустая строка / None → `None`
- Инвариант: `normalized_qty × normalized_unit_price ≈ amount`
- Граница допуска: расхождение ровно 0.1% → pass; 0.11% → fail
- Граница допуска: расхождение ровно 1₽ → pass; 1.01₽ → fail

**`test_dimension_guard.py`:**
- Одинаковая размерность (volume/volume) → расчёт проходит
- Разная размерность (volume/mass) → расчёт заблокирован
- `normalized_unit_id IS NULL` → строка пропущена

**`test_delivery_distribution.py`:**
- Моно-размерность (все volume) → по `normalized_quantity`
- Смешанные размерности (volume + mass) → fallback по `amount`
- Все строки без нормализации → доставка не распределяется
- Edge: `amount=0` (бесплатный материал) при fallback → 0 доставки, ненулевые = 100%, без DivisionByZero

**`test_compensation_with_units.py`:**
- `compute_compensation_per_unit` с нормализованными значениями — поведение не меняется
- Dimension mismatch → compensation = None

**`test_item_type_enum.py`:**
- `"material"` / `"delivery"` / `"other"` — ок
- `"unknown"` → ошибка валидации

### 8.2. Интеграционные тесты (с БД)

**`test_normalization_integration.py`:**
- Полный flow: upload PDF → create_invoice → проверить `normalized_*` в БД
- Документ с неизвестной единицей → `has_issues=true`, `normalized_* IS NULL`
- Ручное редактирование `raw_unit` → перенормализация
- Case-insensitive дубли алиасов: `normalize_unit_key("Т ") == "т"` → get_or_create возвращает существующий, не INSERT

**`test_calculations_with_units.py`:**
- `compute_calculations` с нормализованными данными — результат в базовых единицах
- Смешанный счёт (м³ + т) → доставка по amount, расчёт корректен
- Строки с `normalized_unit_id IS NULL` → исключены из агрегатов

**`test_reference_prices_unit.py`:**
- Создание ref_price с `unit_id` — ок
- Попытка создать ref_price с производной единицей (KG вместо TON) → 422
- Guard: ref_price dimension != item dimension → расчёт заблокирован

**`test_migration_backfill.py`** (одноразовый):
- Предохранитель: неизвестный `material_type` → миграция падает
- Бэкфилл `material_classes.material_type_id` — все строки заполнены
- Бэкфилл `reference_prices.unit_id` — все = M3
- Бэкфилл `invoice_items.normalized_*` — сматченные через алиасы

### 8.3. Frontend тесты

- MSW handlers: `GET /api/units`, `GET /api/material-types`
- `PUT /api/invoices/{id}` с unknown unit → warning в UI
- Форма создания ref_price — выпадающий список единиц, валидация

### 8.4. Что НЕ тестируем (YAGNI)

- UI-редактор справочников (его нет)
- Reprocess endpoint (его нет)
- Самообучение алиасов (backlog)
- Конвертацию между размерностями (вне scope)

---

## 9. Риски и митигация

| Риск | Митигация |
|---|---|
| Бэкфилл `material_type` не покрывает все значения | `SELECT DISTINCT` + fail перед UPDATE |
| Бэкфилл `item_type` содержит мусор | Pre-check `COUNT(*) WHERE NOT IN (...)` перед CHECK |
| Изменение `to_base_multiplier` ломает историю | Иммутабельность (append-only политика) |
| Float-погрешность в деньгах | Везде `Numeric`, `money_round`, `_dec()` |
| Скрытый межразмерностный расчёт | Guard по `dimension` + инвариант на приёме |
| Парсер выдаёт невиданное написание единиц | `normalized_*=NULL`, `has_issues=true`, append-only алиасы |
| Delivery distribution DivisionByZero | Edge case: `amount=0` → 0 доставки, явно в коде и тестах |
| Down-миграция теряет данные | Восстановление строковых полей из справочников до DROP |

---

## 10. Критерии приёмки

- [ ] `т`/`тн`/`тонн`/`кг` маппятся в единый канон через `unit_aliases`
- [ ] При приёме строки заполняются `normalized_*`; инвариант `qty × price ≈ amount`
- [ ] Неизвестная единица → `normalized_*=NULL`, document `has_issues=true`
- [ ] Компенсация и avg_price считаются в базовой единице размерности
- [ ] Dimension mismatch блокируется guard'ом, не считается молча
- [ ] Delivery: моно-dimension → по qty, mixed → по amount, zero-amount → без деления на 0
- [ ] `item_type` валидируется CHECK constraint (`ck_item_type`)
- [ ] `CompensationCorridor.material_type_id` — FK, не строка
- [ ] `reference_prices.unit_id` — NOT NULL, только базовые единицы
- [ ] Миграция up/down проходит без потери данных
- [ ] Предохранители в миграции: неизвестные значения → fail
- [ ] Excel: два блока колонок (сырые + расчётные)
- [ ] Warning в API при unknown unit после ручного редактирования
- [ ] Именованные CHECK constraints (`ck_unit_dimension`, `ck_item_type`)
- [ ] ON DELETE: CASCADE для алиасов, RESTRICT для `material_type_id` и `base_unit_id`

---

## 11. Ключевые решения (ADR)

1. **item_type остаётся** — ортогональная ось к `material_type` (роль строки в расчёте vs семейство материала). Переезжает на Enum + CHECK.
2. **CompensationCorridor.material_type → material_type_id FK** — избежание split-brain (FK + строка в одном рефакторинге).
3. **Write-time нормализация** — единственный корректный подход для финансовой системы (аудируемость, детерминистичность, иммутабельность истории).
4. **Delivery distribution: qty для моно-dimension, amount для mixed** — физический смысл в строительной логистике (фрахт зависит от объёма/массы, не от стоимости груза).
5. **Неизвестная единица → has_issues, не error** — гранулярность (49 из 50 строк считаются), не блокировка всего документа.
6. **BAG вне scope** — YAGNI, расширяем append-only когда появится в данных.
7. **Арматура: default_unit=TON** — ~90% приходит в тоннах; пог.м отловит guard.
