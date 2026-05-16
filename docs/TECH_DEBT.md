# Технический долг

Зафиксированные компромиссы, которые стоит устранить в будущем.

---

## Backend

- [ ] **auto_calculate: заменить вложенные циклы на bulk-агрегацию**
  `routers/dashboard.py` — `auto_calculate` вызывает `crud.recalculate_prices` в двойном цикле
  `(месяцы × классы)`. Каждая итерация выполняет несколько SQL-запросов и `.all()`.
  При большом проекте (12 месяцев × 50 классов = 600 итераций) это становится заметным.
  **Решение:** заменить на один `GROUP BY month, material_class_id` с агрегатными функциями
  и один `bulk INSERT` результатов.

- [ ] **recalculate_prices: нет индекса по `(project_id, material_class_id, period_start, period_end)`**
  `PriceCalculation` не имеет составного индекса по этим четырём полям,
  по которым идёт DELETE + SELECT в каждом вызове `recalculate_prices`.

- [ ] **SQLAlchemy: синхронный движок вместо async**
  `database.py` использует `create_engine` + синхронный `Session`. FastAPI запускает синхронные
  зависимости в threadpool, что добавляет накладные расходы на переключение потоков.
  **Решение:** перейти на `asyncpg` DSN (`postgresql+asyncpg://`), `AsyncEngine`, `AsyncSession`,
  заменить `db.query()` на `await db.execute(select(...))` и все endpoint-функции сделать `async def`.

---

## Frontend

- [ ] **Review.tsx: нет оптимистичного обновления при сохранении**
  После успешного `update.mutate` сервер возвращает обновлённый документ через `docQ` (invalidate),
  но до перезагрузки страница ненадолго показывает устаревшие данные.
  `setOverrides(null)` сбрасывает черновик сразу, что может вызвать кратковременный «прыжок» UI.

- [ ] **Review.tsx: всегда показывает и верифицирует первую СФ документа (`invoices[0]`)**
  Маршрут `/documents/:id` не содержит id СФ. `serverInv = doc.invoices[0]` — если документ содержит
  несколько СФ, переход с дашборда на любую из них откроет первую, а `verify`/`unverify` будут
  мутировать не ту СФ.
  **Решение:** изменить маршрут на `/documents/:docId/invoices/:invoiceId` (или query-параметр),
  выбирать `serverInv` по id из URL.

- [ ] **PriceChart: нет пагинации/виртуализации при большом числе точек**
  При большом диапазоне дат и десятках классов материалов recharts рендерит все точки сразу.

- [ ] **InvoiceTable: tooltip со статусом СФ недоступен с клавиатуры и тач-устройств**
  Уверенность ИИ и дата верификации показываются только через нативный `title` на `<span tabIndex={0}>`.
  Нативные title-тултипы браузеры показывают только при hover, не при focus — поэтому полной доступности нет.
  **Решение:** заменить на focusable-компонент с `aria-describedby` или отдельный tooltip-компонент,
  либо вынести значения в видимый текст.

- [ ] **Suppliers / SupplierPage: строки таблиц кликабельны только мышью**
  `TableRow onClick={() => navigate(...)}` в `Suppliers.tsx` и `SupplierPage.tsx` не работает с клавиатурой.
  Это cross-cutting concern: тот же паттерн используется в `ProjectPage`, `InvoiceTable` и др.
  **Решение:** добавить `tabIndex={0}` + `onKeyDown` (Enter/Space) или переосмыслить паттерн в пользу
  `<a>` / `<Link>` внутри ячейки, что даёт доступность бесплатно.

- [ ] **`get_supplier_project_stats`: `volume_m3` смешивает единицы измерения**
  Колонка суммирует `InvoiceItem.quantity` для всех `item_type == "material"` позиций,
  включая арматуру (тонны/кг) и другие не-объёмные материалы. Для поставщика смешанного
  профиля число в колонке «Объём, м³» вводит в заблуждение.
  **Решение:** ограничить сумму позициями с `MaterialClass.material_type == "concrete"`,
  либо динамически скрывать колонку если у поставщика нет бетонных категорий,
  либо переименовать в «Объём / Кол-во» с указанием единиц из материала.

- [ ] **N+1 в `get_supplier_project_stats`**
  `crud.get_supplier_project_stats` вызывает `_compute_supplier_project_deviation` в Python-цикле.
  Для поставщика на N объектах — N × ~5 SQL-запросов. При ≥20 объектах становится заметным.
  **Решение:** перенести логику deviation в один batched-запрос с GROUP BY supplier_id, project_id,
  переиспользовав агрегаты из основного SELECT и JOIN reference_prices.

- [ ] **Pydantic response_model для роутера `/api/suppliers`**
  Эндпоинты `GET /suppliers`, `GET /{id}`, `GET /{id}/projects`, `GET /{id}/invoices-list` возвращают
  raw dict/list без `response_model=`, что нарушает соглашение кодовой базы и не генерирует OpenAPI-схему.
  **Решение:** определить Pydantic-схемы в `routers/suppliers.py` и добавить `response_model=` к декораторам.

- [ ] **Backend: TOCTOU-гонки на guard-проверках verified**
  Проверки `invoice.verified` перед `UPDATE`, `DELETE` и `reparse` не атомарны — параллельный запрос
  может подтвердить СФ между проверкой и мутацией. Требует `SELECT FOR UPDATE` или условного
  `UPDATE ... WHERE verified = false` в четырёх эндпоинтах. Нецелесообразно для однопользовательского
  инструмента, но стоит устранить при масштабировании.

---

## Инфраструктура / общее

- [ ] **auto_calculate не идемпотентен при частичном сбое**
  Если транзакция прерывается на середине цикла, часть месяцев будет рассчитана,
  часть — нет. Нет механизма retry или rollback-маркера.

- [ ] **Нет ограничения размера загружаемого PDF**
  `POST /api/invoices/upload` принимает файл без проверки max-size на уровне FastAPI.
  Сейчас защиту обеспечивает только Nginx/прокси (если настроен).
