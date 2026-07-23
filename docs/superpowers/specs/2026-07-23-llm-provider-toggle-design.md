# Переключаемый LLM-провайдер: OpenRouter ↔ корпоративный gateway

**Статус:** дизайн одобрен (2026-07-23, четыре раунда ревью двумя ревьюерами: [1] граница интерфейса — доменный парсинг не переезжает, токен-жизненный-цикл, спайк+eval как приёмка; [2] `LLMProviderError` с биллингом, `cost_usd` без `None`, DI-цепочка → module-level seam, capabilities в Settings, приоритет алиасов, RP-0 не существует; [3] `cost_available` из ответа убран, смена семантики битого envelope в detect зафиксирована, два контрактных теста, readiness — новый скоуп; [4] инварианты service locator, условное правило 401, нормализация URL, определение `paid_calls`, спайк-параметры модели, вопрос IT о source-level запрете URL).

**Контекст:** корпоративная инструкция по LLM-gateway (файл в корне репо, gitignored — секреты не коммитим) требует: в контуре МР приложение ходит к внешним LLM только через внутренний OpenAI-совместимый gateway с Keycloak-авторизацией. Текущий код завязан на OpenRouter-проприетарные механизмы и напрямую несовместим с gateway.

---

## Цель

Deploy-time переключатель `LLM_PROVIDER`:

- **`openrouter`** (дефолт) — поведение приложения идентично текущему: OpenRouter + Claude + серверный OCR (`plugins: file-parser`, engine mistral-ocr). «Как задумано».
- **`gateway`** (контурный режим) — весь LLM-egress идёт через корпоративный gateway. Цель режима — **комплаенс** (политика «только через gateway»), не data-residency.

### Non-goals

- **Data-residency не обеспечивается:** gateway не маскирует изображения/бинарные вложения — содержимое СФ уходит upstream-провайдеру незамаскированным (через корп-креды gateway). Зона ответственности — IT-договоры с провайдерами.
- S3, БД, прочий egress — вне охвата; только LLM-интеграция.
- Gateway-вариант дев-скрипта `snapshot_ai_responses.py` не делается (YAGNI).

---

## 1. Конфигурация (deploy-time env)

```env
LLM_PROVIDER=openrouter | gateway     # enum, дефолт openrouter

# namespace openrouter
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1   # оканчивается на /api/v1
OPENROUTER_MODEL=anthropic/claude-sonnet-4.6
OPENROUTER_PDF_ENGINE=mistral-ocr

# namespace gateway
GATEWAY_BASE_URL=                     # БЕЗ /v1 — код добавляет /v1 ровно один раз
GATEWAY_MODEL=
# auth-переменные — финализируются по результату спайка (§7.6)
```

- **Fail-fast на старте:** валидируются обязательные поля только выбранного провайдера.
- **Алиасы (обратная совместимость), детерминированный приоритет:**
  `OPENROUTER_MODEL` → deprecated `AI_MODEL` (warning в лог, без вывода значений) → дефолт;
  `OPENROUTER_PDF_ENGINE` → deprecated `PDF_ENGINE` → дефолт.
  В gateway-режиме `AI_MODEL`/`PDF_ENGINE` не читаются вовсе.
- **Нормализация URL:** trailing slash безопасно срезается в обоих base URL; `/v1` для gateway добавляется ровно один раз; конструкция `/v1/v1/...` невозможна (закреплено тестом).
- Режим неизменяем из работающего приложения (только env/CI при деплое).

## 2. Архитектура — adapter (Strategy)

### 2.1 Интерфейс

```python
class LLMProvider(Protocol):
    async def vision_completion(
        self, *,
        system: str | None,          # detect_rotations работает без system
        user_text: str,
        attachment: PdfAttachment | ImagesAttachment,
        max_tokens: int,             # парсер 64000, детект 200
    ) -> LLMResponse: ...

@dataclass
class LLMResponse:
    content: str
    finish_reason: str | None
    cost_usd: Decimal          # ВСЕГДА Decimal; gateway → Decimal(0)
    completion_tokens: int | None
    paid_calls: int

class LLMProviderError(Exception):
    retryable: bool            # → Transient/Permanent на доменной стороне
    cost_usd: Decimal          # биллинг платного 200 с битым envelope НЕ теряется
    paid_calls: int
    correlation_id: str | None
```

Провайдер: собрать provider-specific payload → отправить → разобрать HTTP/envelope → нормализовать usage и ошибки → вернуть текст+метаданные. Всё.

**Доменный парсинг НЕ переезжает:** JSON УПД, markdown-fence, `doc_type`, сверка сумм, `ParsedInvoice`, разбор массива поворотов остаются в `pdf_parser.py` / `pdf_orientation.py`. Инвариант учёта платного 200 (§2.3 async-спеки) держится на `LLMProviderError.cost_usd`/`paid_calls`: провайдерское исключение всегда несёт накопленный биллинг, доменный код конвертирует его в `TransientError`/`PermanentError` с `cost_usd`.

`cost_available` в `LLMResponse` отсутствует намеренно: недоступность стоимости — свойство провайдера (deploy-time), а не ответа; единственный источник истины — `capabilities.cost_available` в Settings API (§5). Начнёт gateway отдавать cost — меняется фабрика capabilities, не контракт ответа.

### 2.2 Реализации

- **`OpenRouterProvider`** — текущий код 1:1: PDF целиком (`type: "file"`, base64), `plugins: [{id: "file-parser", pdf: {engine: ...}}]`, `usage: {include: true}`, чтение `usage.cost`. Защищён двумя контрактными тестами (§9 AC-1).
- **`GatewayProvider`** — OpenAI-совместимый запрос: `Authorization: Bearer <access_token>`, явный `stream: false`, стандартный usage (без `cost`). Способ подачи `PdfAttachment` (нативный file-парт vs рендер в изображения на нашей стороне) — **решается по результату спайка §7** и инкапсулирован внутри провайдера; если конфигурация подачу PDF не поддерживает — провайдер заранее рендерит страницы (pypdfium2 уже в зависимостях, машинерия в `render_pages_for_detect`) либо fail-fast с внятной ошибкой конфигурации.

### 2.3 Шов инжекции — module-level service locator

Новый модуль `llm.py`: `init_provider(settings)` вызывается из lifespan, `get_provider()` — из `parse_pdf` / `detect_rotations`. Это **service locator** (осознанно; НЕ «паттерн F6» — F6 в кодовой базе означает локальный импорт для monkeypatch). Выбран вместо протаскивания `llm_provider=` через цепочку `process_document → run_processing_attempt → parse_pdf/deskew_pdf → detect_rotations`, потому что тесты уже стоят на module-level monkeypatch (`processing.py:393`), а BackgroundTasks не требуют протаскивания параметра через 4 сигнатуры.

**Инварианты:**
- фабрика не выполняет сетевых запросов (только конструирование);
- провайдер неизменяем после инициализации;
- `get_provider()` до lifespan → понятный `RuntimeError`;
- lifespan teardown очищает состояние;
- тесты получают scoped override/reset (fixture); повторные `TestClient` в одном процессе работают корректно.

Import-time константа `OPENROUTER_URL` удаляется (вместе с импортом в `pdf_orientation.py:19`).

### 2.4 Security-заголовки

`GatewayProvider` **не отправляет никаких `X-Security-*` заголовков**: prompt-injection-проверка шлюза остаётся включённой (её `403` обработан в §3), `X-Security-Body-Metadata` не запрашивается никогда (возвращает демаскирующие mappings, запрещённые к логированию). Зафиксировано явно: проверочные примеры корп-инструкции содержат `X-Security-Prompt-Injection: false` — копировать их в код нельзя.

### 2.5 Смена семантики битого envelope в detect_rotations

Текущее поведение: при HTTP 200 деградация в нулевые повороты покрывает и непарсящийся контент, и битый envelope (отсутствие `choices` ловится тем же `except`, `pdf_orientation.py:184-190`). Новое поведение: **envelope цел, массив поворотов не распарсился → нули (тихая деградация); envelope битый → `LLMProviderError(retryable=False, cost_usd, paid_calls=1)` → ошибка.** Это осознанное изменение, консистентное с принятым ранее «не-2xx не деградируем в нули, иначе переразберём оригинал под видом исправленного». Тесты `test_pdf_orientation.py` на битый envelope обновляются под новую семантику (помечено, чтобы красный тест не «чинился» непредсказуемо).

## 3. Классификация ошибок gateway (по `error.code`)

| Условие | Классификация |
|---|---|
| транспорт/таймаут, `502 upstream_error`, `429 quota_exceeded` | **Transient** |
| `401 authentication_error` | см. правило 401 ниже |
| `403 authorization_error`, `403 model_access_denied`, `422 validation_error` | **Permanent** |
| `403 prompt_injection_blocked` | **Permanent, отдельное сообщение** («документ отклонён security-фильтром шлюза») |
| прочие 4xx | **Permanent** |
| прочие 5xx и всё нераспознанное | **Transient** |

Default-ветки повторяют текущее поведение `parse_pdf` (5xx/408/429 → Transient, прочее → Permanent) — тесты симметричны.

**Правило 401 (условное):** один refresh-retry выполняется **только если** сконфигурированный `GatewayTokenProvider` поддерживает безопасное обновление токена; без refresh-механизма (статический токен) первый `401` сразу Permanent. Повторный `401` после refresh → Permanent. Сбои token endpoint: транспорт/5xx → Transient; 400/401 гранта → Permanent (ошибка конфигурации). Конкурентное обновление — под lock'ом с re-check («не обновил ли токен уже другой запрос»). Механизм гранта (client_credentials vs refresh-token flow) — по результату спайка §7.6; password-grant в прод не закладывается.

`correlation_id` из `error.details` — в лог. Bearer token, `_security`, `X-AISG-Masking-Map` — **никогда не логируются** (закреплено тестом, AC-4).

## 4. Стоимость и paid_calls

- Gateway не возвращает `usage.cost` → `cost_usd = Decimal(0)`. Доменная арифметика (`processing.py:424`, слияние detect+parse §2.5 async-спеки) не меняется — `None` в неё не попадает.
- **Определение `paid_calls`:** `1` за каждый полученный HTTP 200 от completion endpoint независимо от валидности envelope; транспортная ошибка и non-200 → `0`; `401`, предшествовавший успешному refresh-retry, платным вызовом не считается.
- UI по `capabilities.cost_available=false` показывает «стоимость недоступна», а не `$0` (ноль означал бы «бесплатно», что неизвестно).

## 5. Settings API/UI

- **PUT** в gateway-режиме запрещает `api_key` **и** `model` (403); `confidence_threshold` разрешён (бизнес-настройка, не деплой-конфиг).
- **GET** отдаёт capabilities:

  ```json
  { "provider": "gateway", "can_edit_credentials": false, "can_edit_model": false, "cost_available": false }
  ```

  В gateway-режиме `api_key_set` не вычисляется по `sk-`-префиксу (иначе UI покажет ложный призыв «введите ключ»); `model` в GET читается через алиас-цепочку §1, не напрямую из `os.getenv("AI_MODEL")` (`routers/settings.py:30`).
- Frontend скрывает поля по capabilities; backend enforce'ит запрет независимо от фронта. Gateway-токен на frontend не передаётся ни в каком виде.
- Полный режим — без изменений (дев-удобство «вставь ключ в UI» сохраняется).

## 6. Golden eval — зависимость приёмки

Eval-артефакта в репозитории нет — он **строится до приёмки контурного режима** (можно параллельно спайку):

- golden-набор реальных документов + правила хранения (PDF не в git — паттерн `tests/fixtures/pdf/real/`);
- **baseline снимается на текущем OpenRouter-режиме до начала миграции**;
- числовые метрики: точность ключевых полей (цены, количества, ИНН, даты, поставщик), полнота строк (позиций), доля успешной сверки итогов;
- числовой допуск ухудшения фиксируется в eval-доке при его создании («в пределах дисперсии» без числа критерием не является);
- способ запуска (ручной/автоматический) — там же.

Приёмка gateway-режима = метрики не хуже baseline на согласованный допуск.

## 7. Gateway-спайк — precondition для внутренностей `GatewayProvider`

Прежде чем финализировать реализацию `GatewayProvider` (интерфейс §2.1 от спайка не зависит):

1. Токен → `GET /v1/models`: фактический список для роли; какие модели vision-capable.
2. Подача документа: принимает ли gateway `image_url`? принимает ли `type: file` с PDF?
3. Форма `usage` в ответе; параметры модели: `max_tokens` vs `max_completion_tokens`, максимальный output limit, тип `choices[0].message.content` (строка vs массив блоков), фактические значения `finish_reason`, поддержка system message без преобразований.
4. **Лимит размера body** + бюджет DPI/страницу под него (до 20 страниц × 300 DPI в base64 могут упереться в 413 до модели; параметр связан с качеством, которое меряет eval §6).
5. Не триггерит ли стена base64-картинок `403 prompt_injection_blocked`.
6. **Жизненный цикл токена — главная неизвестная фичи:** поддерживает ли клиент gateway client_credentials (сервис-аккаунт)? TTL access token; TTL и политика ротации refresh token → может ли backend работать unattended без оператора.

## 8. Blast radius / сопутствующие изменения

- `pdf_parser.py` — payload/HTTP/envelope уезжают в `OpenRouterProvider`; доменная часть (fence → JSON → валидация → `ParsedInvoice`) остаётся.
- `pdf_orientation.py:19` — импорт `OPENROUTER_URL` умирает; `detect_rotations` → `get_provider()`; семантика битого envelope — §2.5.
- `processing.py` — не меняется (module-level seam сохраняет цепочку вызовов).
- `scripts/snapshot_ai_responses.py` — дев-only, остаётся OpenRouter-only; чинится только импорт.
- `routers/settings.py` — §5 (PUT-запреты, capabilities, алиас модели в GET).
- `config.py` — §1 (enum, namespacing, алиасы, fail-fast).
- **Новый скоуп:** `/readyz` (или параметр к существующему `/api/health`, `main.py:177`) с проверкой `GET /healthz` шлюза в gateway-режиме; в openrouter-режиме внешней проверки нет. Существующий `/api/health` внешних проверок не имеет — это добавление, а не переиспользование.
- `.gitignore` — добавить `.gateway.env`, `.access_token`, `.refresh_token`; запись `/CLAUDE_CODE_GATEWAY_INSTRUCTION.md` сохраняется.
- Тесты: полный режим остаётся зелёным; провайдеры тестируются изолированно respx-моками; `test_pdf_orientation.py` — обновление по §2.5.

## 9. Acceptance criteria

1. `LLM_PROVIDER=openrouter` (и unset) → поведение идентично текущему. **Два контрактных теста payload'а** (порядок частей `content` — часть контракта):
   - *parse*: system + file-парт первым, затем текст; `plugins`; `max_tokens=64000`;
   - *detect*: без system; текст первым, затем массив `image_url`; без `plugins`; `max_tokens=200`.
2. `LLM_PROVIDER=gateway` → ни одного запроса к `openrouter.ai` или прямым LLM-провайдерам.
3. Gateway-запрос: не содержит `plugins`, `usage:{include}`, `type:file` (до подтверждения спайком); содержит явный `stream: false`; не содержит `X-Security-*`; URL без `/v1/v1` (тест конструкции).
4. Ошибки — по таблице §3; `correlation_id` в логе; bearer/`_security`/masking-map в логах отсутствуют (тест).
5. Учёт: `paid_calls` по определению §4 в обоих режимах; gateway → `cost_usd=0`, UI показывает «недоступна».
6. Settings: PUT `api_key`/`model` в gateway-режиме → 403; GET отдаёт корректные capabilities; фронт скрывает поля.
7. Fail-fast конфигурации выбранного провайдера на старте; доступность gateway — в readiness, не в startup.
8. Инварианты service locator (§2.3): `RuntimeError` до init, teardown, scoped override в тестах.
9. Eval §6 построен, baseline снят, метрики gateway-режима в допуске.

## 10. Открытые вопросы (к IT; блокеры деплоя в контур, не реализации)

1. **Source-level запрет URL:** инструкция требует «нет прямых URL внешних LLM providers» — подтвердить, что запрет про runtime-egress, а не про наличие дефолта `openrouter.ai/api/v1` в исходниках dual-mode артефакта. Если буквальный — дефолт убирается, `OPENROUTER_BASE_URL` становится обязательной env в OpenRouter-деплое (или раздельные артефакты).
2. Сервис-аккаунт (client_credentials) для headless backend — §7.6.
3. Комплаенс отправки изображений СФ upstream (retention/training/юрисдикция) — вопрос поднят ранее, вне охвата этой фичи (non-goal), но ответ влияет на допустимость контурного деплоя как такового.

## 11. Гигиена секретов этой спеки

Корп-инструкция содержит живой `CLIENT_SECRET` — её содержимое в коммитимые документы не переносится (файл gitignored). Эта спека ссылается на gateway только по возможностям (OpenAI-совместимый API, Keycloak bearer, коды ошибок), без хостнеймов и кредов.
