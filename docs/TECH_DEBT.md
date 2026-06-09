# Технический долг

Зафиксированные компромиссы, которые стоит устранить в будущем.

---

## Backend

- [ ] **`GET /api/projects` не возвращает `created_at`**
  Роутер `routers/projects.py:list_projects` отдаёт `{id, name, contract_number, doc_count}`, но
  фронтенд (`Project` тип в `frontend/src/types/project.ts`) объявляет `created_at` обязательным
  и читает его в `ProjectCard.tsx` («Создан {formatDate(project.created_at)}») и `ProjectPage.tsx`
  («создан {formatDate(project.created_at)}»). В живой UI отображается «Создан Invalid Date» / «—».
  Расхождение всплыло при правке фикстуры `sampleProject` для типобезопасных тестов карточки.
  **Решение:** добавить `"created_at": p.created_at.isoformat() if p.created_at else None` в dict
  ответа `list_projects` (и аналогично в `create_project_route` / `update_project_route` для
  консистентности). Альтернатива — определить Pydantic `ProjectOut` с `model_config = ConfigDict(from_attributes=True)`
  и навесить `response_model=ProjectOut` на все три endpoint'а.

- [ ] **`Invoice.vat_rate` допускает NULL в БД**
  Колонка объявлена без `nullable=False` и без `NOT NULL` в миграции. ORM-дефолт `20.0`
  применяется только при создании через ORM-объект, старые/мигрированные строки могут иметь `NULL`.
  В SQL-выражениях добавлен защитный `COALESCE(Invoice.vat_rate, 20.0)`, но правильнее закрыть
  проблему на уровне схемы.
  **Решение:** добавить `nullable=False` в `models.py` и сгенерировать миграцию
  `ALTER TABLE invoices ALTER COLUMN vat_rate SET NOT NULL`.

- [ ] **`GET /dashboard/calculations` без `project_id`: N запросов к БД**
  При вызове без `project_id` (глобальный Dashboard) функция выполняет `compute_calculations()`
  по одному разу на каждый проект. При N проектах = N × ~4 SQL-запросов на месяц × M месяцев.
  Для MVP с единицами проектов приемлемо.
  **Решение:** объединить в один SQL с `GROUP BY project_id, material_class_id, month` и
  переиспользовать delivery-аллокацию через window-функцию.

- [ ] **SQLAlchemy: синхронный движок вместо async**
  `database.py` использует `create_engine` + синхронный `Session`. FastAPI запускает синхронные
  зависимости в threadpool, что добавляет накладные расходы на переключение потоков.
  **Решение:** перейти на `asyncpg` DSN (`postgresql+asyncpg://`), `AsyncEngine`, `AsyncSession`,
  заменить `db.query()` на `await db.execute(select(...))` и все endpoint-функции сделать `async def`.

- [ ] **Parser: chunking для очень длинных СФ**
  `_reconcile_totals` теперь *детектирует* потерянные строки, но восстановление для СФ с 100+
  позициями требует постраничного разбора с последующей склейкой. Не реализовано. Также: prompt
  от mistral-ocr занимает ~24K токенов на 8-страничном бланке (повторяющиеся шапки/подвалы
  каждой страницы) — сжатие prompt-нагрузки оставило бы больше места для completion.

- [ ] **Parser: reparse удаляет данные до валидации**
  `routers/invoices.reparse_document` удаляет существующие Invoice-строки *до* запуска нового
  разбора. Если новый разбор отклонён guard'ом completeness, документ остаётся с 0 инвойсов
  (старые корректные данные уже удалены). Правильная схема: разобрать → провалидировать → затем
  удалить старое и записать новое (parse-then-swap).

---

## Frontend

- [ ] **`ui-domain/Button` дублирует shadcn `ui/button`**
  Проект содержит два Button-компонента: shadcn `ui/button.tsx` (Base UI primitive + CVA) и
  кастомный `ui-domain/Button.tsx` (hand-rolled forwardRef). Весь приложенческий код использует
  второй. Причина: `ui-domain/Button` добавляет пропсы `leftIcon`, `rightIcon`, `loading` и
  использует проектные CSS-токены (`--color-action`, `--color-surface-hover` и др.), которых нет
  в shadcn-заготовке. `ui/button.tsx` используется только внутри shadcn-компонентов (pagination,
  alert-dialog, dialog, input-group) и содержит баг: `secondary` вариант ссылается на
  `var(--secondary)` вместо `var(--color-secondary)`.
  **Решение:** перенести логику `ui-domain/Button` (иконки, loading, проектные токены) в `ui/button.tsx`,
  добавить вариант `primary` / `danger`, обновить CSS-переменные — и удалить `ui-domain/Button.tsx`.
  Все ~11 import-точек переключить на `@/components/ui/button`.

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

- [ ] **InvoiceTable: клиентская пагинация — нужна серверная при ~1000+ СФ на проекте**
  Таб «Счета» в `ProjectPage` загружает все СФ проекта за один запрос (`GET /dashboard/invoices?project_id=`)
  и пагинирует их на клиенте. Реально на одном проекте может быть 1000+ инвойсов по одному материалу,
  что делает первоначальную загрузку тяжёлой и перегружает TanStack Query кеш.
  **Решение:** добавить `?page=&page_size=&sort_by=&sort_dir=` к эндпоинту + вернуть
  `{ items: [...], total: N }`, перевести `useDashboardInvoices` на серверную пагинацию,
  убрать клиентскую логику из `InvoiceTable`. Фильтр по месяцу (сейчас клиентский) потребует
  отдельного `?month=YYYY-MM` param на бекенде.
  **Триггер:** проект с ≥300 СФ или жалобы на медленное открытие таба «Счета».

- [ ] **InvoiceTable: tooltip со статусом СФ недоступен с клавиатуры и тач-устройств**
  Уверенность ИИ и дата верификации показываются только через нативный `title` на `<span tabIndex={0}>`.
  Нативные title-тултипы браузеры показывают только при hover, не при focus — поэтому полной доступности нет.
  **Решение:** заменить на focusable-компонент с `aria-describedby` или отдельный tooltip-компонент,
  либо вынести значения в видимый текст.

- [ ] **Дублирование blob-download паттерна в трёх местах**
  `ProjectPage.tsx` (xlsx-экспорт), `MonthlyTab.tsx` (CSV) и `Reports.tsx` используют одинаковую
  последовательность: `createObjectURL` → `appendChild(a)` → `click()` → `removeChild(a)` → `revokeObjectURL`.
  Реализации немного расходятся (синхронный vs async revoke, санитизация имени файла).
  **Решение:** вынести в хелпер `src/lib/downloadBlob.ts(blob, filename)` и обновить все три вызывающих.

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

- [ ] **`compute_calculations`: `invoice_ids_month` через Python-список в `IN (...)`**
  При большом числе счетов за месяц функция материализует все ID в Python-список и передаёт
  их в каждый из четырёх последующих SQL-запросов как `IN (id1, id2, ...)`. Запросы
  пересылают весь список по wire. Для типичного проекта (десятки счетов в месяц) некритично,
  но при крупном объёме данных стоит заменить на subquery/CTE.

- [ ] **Нет кеширования расчётов — потенциальная проблема при ~1000+ СФ**
  Все аналитические эндпоинты (`/dashboard/calculations`, `/api/deviation-chart`, экспорт Excel)
  вычисляют агрегаты на лету при каждом запросе. При ~1000 СФ × 10 позиций = 10 000 строк
  PostgreSQL справляется, но узкие места:
  1. **Dashboard без `project_id`**: N+1 (уже зафиксирован выше) × объём каждого проекта — нагрузка растёт мультипликативно.
  2. **Excel-экспорт**: `compute_export_rows()` материализует все строки за период в Python-памяти для openpyxl. При 500+ СФ за квартал — граница комфорта.
  3. **Deviation chart**: запускается при каждом открытии карточки проекта; при большом диапазоне дат — тяжёлый запрос.
  **Решение (при достижении порога):** добавить Redis-кеш на `compute_calculations()` с инвалидацией
  по событию «загружена новая СФ / изменена базовая цена» (event-based, не TTL). Materialized view
  в Postgres — альтернатива без внешней зависимости, но требует явного `REFRESH`.
  **Триггер для реализации:** p95 latency на `/dashboard/calculations` > 2 сек или Excel-экспорт > 10 сек.

- [ ] **N+1 в `get_projects` / `get_documents` / `get_document`**
  `crud.projects.get_projects` не делает eager-loading `documents`, но роутер обращается к
  `p.documents` для подсчёта `doc_count` — один SELECT на проект. Аналогично `get_documents` /
  `get_document` не загружают `invoices`/`items`, но роутеры их обходят.
  **Решение:** добавить `selectinload(Project.documents)` в `get_projects` (или считать `doc_count`
  агрегатной колонкой через `func.count`); добавить `selectinload(Document.invoices)` и
  `selectinload(Invoice.items)` в `get_documents`/`get_document`.

- [ ] **N+1 в `get_supplier_project_stats`**
  `crud.get_supplier_project_stats` вызывает `_compute_supplier_project_deviation` в Python-цикле.
  Для поставщика на N объектах — N × ~5 SQL-запросов. При ≥20 объектах становится заметным.
  **Решение:** перенести логику deviation в один batched-запрос с GROUP BY supplier_id, project_id,
  переиспользовав агрегаты из основного SELECT и JOIN reference_prices.

- [ ] **Excel-экспорт: только интеграционные тесты, нет unit-тестов для генерации workbook**
  `routers/export.py` покрыт интеграционными тестами (`tests/integration/test_export.py`),
  которые проверяют и HTTP-слой, и структуру workbook. Чистую логику генерации Excel (формулы,
  стили, заголовки) можно вынести в отдельную функцию без зависимости от БД и покрыть unit-тестами,
  что ускорит CI и упростит отладку вёрстки файла.
  **Решение:** извлечь `_build_workbook(rows, project, period) -> openpyxl.Workbook` в отдельную
  функцию, написать unit-тесты на неё без TEST_DATABASE_URL.

- [ ] **Pydantic response_model для роутера `/api/suppliers`**
  Эндпоинты `GET /suppliers`, `GET /{id}`, `GET /{id}/projects`, `GET /{id}/invoices-list` возвращают
  raw dict/list без `response_model=`, что нарушает соглашение кодовой базы и не генерирует OpenAPI-схему.
  **Решение:** определить Pydantic-схемы в `routers/suppliers.py` и добавить `response_model=` к декораторам.

- [ ] **Backend: TOCTOU-гонки на guard-проверках verified**
  Проверки `invoice.verified` перед `UPDATE`, `DELETE` и `reparse` не атомарны — параллельный запрос
  может подтвердить СФ между проверкой и мутацией. Требует `SELECT FOR UPDATE` или условного
  `UPDATE ... WHERE verified = false` в четырёх эндпоинтах. Нецелесообразно для однопользовательского
  инструмента, но стоит устранить при масштабировании.
  (Примечание: аналогичная гонка в `crud.admin.set_user_role_and_active` уже закрыта через
  `SELECT ... FOR UPDATE` на строках superadmin'ов — см. `_count_other_active_superadmins_locked`.)

- [ ] **MSW-хендлеры некоторых admin-эндпоинтов всё ещё статичны**
  Хендлеры `/api/admin/*` в `frontend/src/test/handlers.ts` частично возвращают фикстуры.
  Например, `GET /api/admin/organizations` отдаёт фиксированный список.
  Из-за этого happy-path тесты могут пройти даже при неверной сериализации query/тела.
  Тесты, которым важна проверка контракта (поиск, пагинация, редактирование), уже переопределяют хендлер
  через `server.use` со спаем — это корректный паттерн.
  **Решение:** в дефолтных хендлерах читать `req.url.searchParams` / `await req.json()` и отражать их
  в ответе (фильтрация/echo полей).

---

## Auth

- [ ] **Нет ограничения частоты запросов на `POST /api/auth/login`**
  Эндпоинт не защищён rate-limiting'ом: атака перебора паролей ничем не ограничена кроме сетевого прокси.
  **Решение:** добавить SlowAPI / custom middleware с лимитом по IP (например, 10 req/min) и логировать
  превышение. Поле для подозрительных попыток уже логируется на уровне `auth.py`.

- [ ] **Изоляция данных по организации нереализована на уровне запросов**
  Все бизнес-роутеры требуют аутентификации через `get_current_user`, но не фильтруют данные по `org_id`.
  Суперпользователь видит все объекты, обычный пользователь в данный момент тоже. Замысел `ProjectAccess`
  в `auth.py` + `ProjectOrganization` в схеме позволяет ввести изоляцию, но роутеры не используют
  `get_project_access` — только `get_current_user`.
  **Решение:** для каждого ресурс-роутера добавить фильтр `WHERE project.id IN (org's projects)` или
  использовать `get_project_access` как зависимость для эндпоинтов, принимающих `project_id`.

- [ ] **`OrgRole` / `ProjectRole` хранятся как VARCHAR + CHECK вместо нативных PG enum'ов**
  `native_enum=False` выбран во избежание сложностей с Alembic при добавлении значений. Нативный enum
  более строг на уровне БД. При добавлении новых ролей потребуется только миграция CHECK-constraint.
  **Решение:** при стабилизации ролевой модели можно перейти на `CREATE TYPE ... AS ENUM` — отдельная
  миграция без потери данных.

- [ ] **Нет сброса пароля и верификации e-mail**
  `User.email` существует, но нет flow «забыли пароль» и нет проверки владения адресом при регистрации.
  Аккаунты создаются только через CLI или API суперпользователя, что приемлемо для закрытого B2B-продукта,
  но не масштабируется при самостоятельной регистрации.
  **Решение:** добавить `POST /api/auth/forgot-password` + `POST /api/auth/reset-password` с one-time
  token (hashed, stored in DB, TTL 1 час).

- [ ] **Письмо-приглашение при создании пользователя (обсуждается)**
  При создании пользователя через админ-консоль (`POST /api/admin/organizations/{id}/users`,
  `POST /api/orgs/users`) и при сбросе пароля (`POST /api/admin/users/{id}/reset-password`)
  суперюзер/админ сейчас вручную копирует сгенерированный пароль и передаёт его «безопасным способом».
  Хочется автоматически слать новому пользователю письмо-приглашение.
  **Контекст:** почтовой инфраструктуры в проекте нет вообще — ни SMTP-настроек в `config.py`,
  ни библиотеки отправки, ни env-ключей. `boto3` есть в зависимостях (для MinIO/S3), теоретически
  пригоден для AWS SES.
  **Развилки (решить перед реализацией):**
  1. *Содержание письма.* Слать логин+пароль в открытом виде — простой, но небезопасный паттерн
     (пароль оседает в почтовых ящиках/логах/индексах). **Предпочтительно** — ссылка-приглашение
     с one-time токеном (hashed, TTL), по которой пользователь сам задаёт пароль; пароль никогда
     не летит по почте. Это пересекается с задачей «сброс пароля и верификация e-mail» выше —
     стоит делать общий механизм one-time токенов (новая таблица `password_tokens` или подобная)
     и публичную страницу «задать пароль».
  2. *Транспорт.* SMTP через stdlib `smtplib` (без новых зависимостей, работает с любым провайдером:
     Yandex/Mailgun/свой сервер) против AWS SES через `boto3` (нужен настроенный SES + верифицированный
     домен).
  3. *Доставляемость и фоновость.* Отправку нельзя делать синхронно в request-хендлере (таймауты,
     ретраи) — нужен фоновый воркер/очередь или хотя бы `BackgroundTasks` с обработкой сбоев.
  **Триггер:** переход от ручного онбординга к самостоятельному приглашению пользователей.

- [ ] **Нет ротации `SECRET_KEY` без инвалидации всех сессий**
  При компрометации `SECRET_KEY` все access-токены надо считать недействительными и перегенерировать.
  Нет механизма версионирования ключей (kid) в JWT-заголовке.
  **Решение:** добавить `kid` в JWT header, поддерживать словарь ключей — позволит плавно ротировать
  SECRET_KEY без мгновенного логаута всех пользователей.

- [ ] **`admin.py` и `orgs.py` роутеры без `response_model=`**
  Эндпоинты возвращают raw dict без Pydantic response_model — нет OpenAPI-схемы, нет автоматической
  сериализации/валидации ответов. Несоответствие принятому стилю других роутеров.
  **Решение:** определить Pydantic-схемы (`OrgOut`, `UserOut`) в соответствующих файлах роутеров и
  добавить `response_model=` к декораторам.

---

## Инфраструктура / общее

- [ ] **auto_calculate не идемпотентен при частичном сбое**
  Если транзакция прерывается на середине цикла, часть месяцев будет рассчитана,
  часть — нет. Нет механизма retry или rollback-маркера.

- [ ] **Нет ограничения размера загружаемого PDF**
  `POST /api/invoices/upload` принимает файл без проверки max-size на уровне FastAPI.
  Сейчас защиту обеспечивает только Nginx/прокси (если настроен).

---

## Units-refactoring (Spec §2 backlog + долг реализации)

### Spec §2 — отложено на следующий этап

- [ ] **Кросс-размерностная конвертация через плотность** (пог.м→т для арматуры)
  Перевод между `mass` и `length` требует коэффициента плотности, специфичного для марки материала. Сейчас такие строки получают `dimension_mismatch=True` и выпадают из расчёта.
  **Решение:** добавить таблицу `density_factors(material_class_id, kg_per_unit)` и обрабатывать cross-dimension conversion в `normalize_item`.

- [ ] **Self-learning aliases** — автоматически добавлять `unit_aliases` из новых документов
  Сейчас неизвестная единица даёт `normalized_unit_id=NULL` и флаг «проблема». Новые алиасы добавляются только вручную (через миграцию или API).
  **Решение:** после парсинга предлагать пользователю сопоставить неизвестную строку с существующей единицей и сохранять в `unit_aliases`.

- [ ] **Lazy reprocess endpoint** — перенормализовать исторические инвойсы без реразбора PDF
  Добавление нового алиаса не ретроактивно обновляет уже сохранённые `InvoiceItem`.
  **Решение:** `POST /api/invoices/renormalize?project_id=` — перезапустить `normalize_item` для всех позиций с `normalized_unit_id IS NULL`, используя обновлённый alias map.

### Чистки после завершения frontend-плана

- [ ] **Удалить legacy `unit` OUTPUT key** из `_serialize_document` и dashboard serializer, а также `InvoiceItemEdit.unit` INPUT alias (`AliasChoices`) в схемах Pydantic — после того как фронтенд перейдёт на `raw_unit` и ни один клиент не читает/пишет `unit`.

### Долг, выявленный при code-review реализации

- [ ] **VAT-amount SQL expression дублируется ~6×** в `crud/calculations.py` (compute_calculations base/delivery/additive + compute_export_rows) и `crud/suppliers.py` — паттерн `coalesce(vat_amount, amount*coalesce(vat_rate, 20.0)/100)`. Расхождения при правке неизбежны.
  **Решение:** вынести в shared `_sql_vat_amount()` — SQLAlchemy-выражение без аргументов, переиспользуемое во всех трёх модулях.

- [ ] **`compute_export_rows`: ключи результирующего dict названы `*_per_m3`** (`mat_per_m3`, `delivery_per_m3` и т.д.), хотя расчёт теперь размерностно-агностичен (может быть per-ton, per-piece).
  **Решение:** переименовать в `*_per_unit` одновременно в `crud/calculations.py` (producer) и `routers/export.py` (consumer) — косметика, но вводит в заблуждение при ревью.

- [ ] **`func.max(InvoiceItem.raw_unit)` в `compute_export_rows`** — произвольный выбор, когда группа (invoice, class) содержит несколько разных `raw_unit`. Колонка «Ед. изм. по документу» может показывать не ту единицу для такой строки.
  **Решение:** рассмотреть distinct-aware логику (напр. `string_agg(DISTINCT raw_unit, '/')`) или явное предупреждение при неоднородной группе.

- [ ] **Supplier deviation не имеет dimension guard** — `crud/suppliers.py::_compute_supplier_project_deviation` не читает `contrib["dimensions"]` и может агрегировать отклонение по смешанным размерностям (например, м³ + т в одном классе). На странице проекта такие строки получили бы `dimension_mismatch=True`, на карточке поставщика — нет. Предшествует рефакторингу (старый код суммировал сырое `quantity`), не введён рефакторингом.
  **Решение:** добавить тот же intra-class dimension guard в `_compute_supplier_project_deviation` + написать `test_supplier_deviation_dimension_mismatch`.
