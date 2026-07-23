# Переключаемый LLM-провайдер — план реализации (фаза 1: без gateway-спайка)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ввести deploy-time переключатель `LLM_PROVIDER` с абстракцией провайдера так, что режим `openrouter` работает 1:1 как сейчас (закреплено контрактными тестами), а всё, что не зависит от gateway-спайка, готово к появлению `GatewayProvider`.

**Architecture:** Strategy/adapter по спеке `docs/superpowers/specs/2026-07-23-llm-provider-toggle-design.md`: новый модуль `llm.py` (типы интерфейса + service locator), `llm_openrouter.py` (текущий транспорт/envelope, вынесенный из `pdf_parser`/`pdf_orientation`), доменный парсинг не переезжает. `GatewayProvider` и `gateway_client/` — В ЭТОТ ПЛАН НЕ ВХОДЯТ (заблокированы спайком §7 спеки; отдельный план после спайка). Golden eval (§6) — отдельный план.

**Tech Stack:** Python 3.12, FastAPI, pydantic-settings, httpx, respx (тесты); React 19 + TS + TanStack Query + MSW/vitest (фронт).

## Global Constraints

- Спека — единственный источник требований: `docs/superpowers/specs/2026-07-23-llm-provider-toggle-design.md`; при расхождении план проигрывает спеке.
- Ветка: `feature/llm-provider-gateway`. Коммиты — после каждой задачи.
- Докстринги на каждую новую функцию/метод/тест (правило репо, порог ≥80%).
- Тесты гонять готовыми рецептами: `just test-backend-unit`, `just test-int-local` (integration на локальном PG), `just test-frontend`; точечно — `cd backend && uv run pytest <path> -v`. Финально — `just lint` и `just test`.
- Тексты пользовательских ошибок НЕ меняются (стабильные строки: «Таймаут запроса к OpenRouter (180с)», «Сетевая ошибка запроса к сервису распознавания», «OpenRouter API ошибка: {code}», «Ответ модели без содержимого», «Сервис распознавания ориентации недоступен/отклонил запрос»).
- Инвариант §2.3 (биллинг платного 200) сохраняется: любая ошибка после HTTP 200 несёт `cost_usd`/`paid_calls=1`.
- `.env`/`.env.test` не трогать. Новые зависимости не добавлять.
- `LLM_PROVIDER=gateway` в этой фазе валиден в конфиге, но фабрика даёт понятный `RuntimeError` («после спайка»).

---

### Task 1: Конфиг §1 — enum, namespaced-переменные, алиасы

**Files:**
- Modify: `backend/config.py`
- Test: `backend/tests/unit/test_config_llm.py` (создать)

**Interfaces:**
- Produces: поля `Settings`: `LLM_PROVIDER: Literal["openrouter","gateway"]`, `OPENROUTER_MODEL: str`, `OPENROUTER_PDF_ENGINE: str`, `OPENROUTER_MAX_TOKENS: int | None`, `GATEWAY_BASE_URL: str`, `GATEWAY_MODEL: str`; функции `resolved_openrouter_model(s) -> str`, `resolved_openrouter_pdf_engine(s) -> str`, `resolved_openrouter_max_tokens(s) -> int`, `validate_llm_settings(s) -> None`.
- Consumes: существующие deprecated-поля `AI_MODEL`, `PDF_ENGINE`, `AI_MAX_TOKENS`, `OPENROUTER_BASE_URL`, `OPENROUTER_API_KEY`.

- [ ] **Step 1: Написать падающие тесты**

Файл `backend/tests/unit/test_config_llm.py`:

```python
"""Тесты конфигурации LLM-провайдера: алиасы, дефолты, fail-fast (§1 спеки)."""
import pytest

from config import (
    Settings,
    resolved_openrouter_max_tokens,
    resolved_openrouter_model,
    resolved_openrouter_pdf_engine,
    validate_llm_settings,
)


def _mk(**kw) -> Settings:
    """Собрать Settings без чтения .env (важно: чистые дефолты + переданные поля)."""
    base = {"SECRET_KEY": "x" * 32}
    base.update(kw)
    return Settings(_env_file=None, **base)


def test_default_provider_is_openrouter():
    """Без LLM_PROVIDER действует режим openrouter (обратная совместимость)."""
    assert _mk().LLM_PROVIDER == "openrouter"


def test_model_alias_priority():
    """OPENROUTER_MODEL побеждает deprecated AI_MODEL; пустой — падаем на алиас, затем дефолт."""
    assert resolved_openrouter_model(_mk(OPENROUTER_MODEL="m1", AI_MODEL="m2")) == "m1"
    assert resolved_openrouter_model(_mk(AI_MODEL="m2")) == "m2"
    assert resolved_openrouter_model(_mk()) == "anthropic/claude-sonnet-4.6"


def test_pdf_engine_alias_priority():
    """OPENROUTER_PDF_ENGINE → PDF_ENGINE → 'mistral-ocr' (код-дефолт, §1)."""
    assert resolved_openrouter_pdf_engine(_mk(OPENROUTER_PDF_ENGINE="native")) == "native"
    assert resolved_openrouter_pdf_engine(_mk(PDF_ENGINE="native")) == "native"
    assert resolved_openrouter_pdf_engine(_mk()) == "mistral-ocr"


def test_max_tokens_alias_priority():
    """OPENROUTER_MAX_TOKENS → AI_MAX_TOKENS → 64000 (AC-1 спеки)."""
    assert resolved_openrouter_max_tokens(_mk(OPENROUTER_MAX_TOKENS=1000)) == 1000
    assert resolved_openrouter_max_tokens(_mk(AI_MAX_TOKENS=2000)) == 2000
    assert resolved_openrouter_max_tokens(_mk(AI_MAX_TOKENS=64000)) == 64000


def test_validate_openrouter_without_key_ok():
    """openrouter без ключа валиден на старте — ошибка только при вызове (§1)."""
    validate_llm_settings(_mk())  # не бросает


def test_validate_gateway_requires_base_url_and_model():
    """gateway без GATEWAY_BASE_URL/GATEWAY_MODEL — fail-fast с понятным текстом."""
    with pytest.raises(RuntimeError, match="GATEWAY_BASE_URL"):
        validate_llm_settings(_mk(LLM_PROVIDER="gateway", GATEWAY_MODEL="m"))
    with pytest.raises(RuntimeError, match="GATEWAY_MODEL"):
        validate_llm_settings(_mk(LLM_PROVIDER="gateway", GATEWAY_BASE_URL="http://gw"))


def test_empty_base_url_is_absence():
    """Пустая строка OPENROUTER_BASE_URL = отсутствие значения → дефолт (guard §1)."""
    s = _mk(OPENROUTER_BASE_URL="")
    validate_llm_settings(s)  # не бросает: пустота openrouter-URL лечится дефолтом
```

- [ ] **Step 2: Прогнать — убедиться, что падают**

Run: `cd backend && uv run pytest tests/unit/test_config_llm.py -v`
Expected: FAIL — `ImportError: cannot import name 'resolved_openrouter_model'`.

- [ ] **Step 3: Реализация в `config.py`**

В класс `Settings` добавить (после блока «# OpenRouter», сохранив существующие поля как deprecated-источники):

```python
    # LLM-провайдер (спека 2026-07-23): deploy-time enum + namespaced-настройки.
    LLM_PROVIDER: Literal["openrouter", "gateway"] = "openrouter"
    # namespaced openrouter; пустое значение → алиас-цепочка (resolved_* ниже)
    OPENROUTER_MODEL: str = ""
    OPENROUTER_PDF_ENGINE: str = ""
    OPENROUTER_MAX_TOKENS: int | None = None
    # namespaced gateway; auth-переменные финализируются после спайка (§7 спеки)
    GATEWAY_BASE_URL: str = ""
    GATEWAY_MODEL: str = ""
```

(`from typing import Literal` — в импорты.) После класса — резолверы и fail-fast:

```python
def resolved_openrouter_model(s: "Settings") -> str:
    """OPENROUTER_MODEL → deprecated AI_MODEL (warning) → дефолт (§1 спеки)."""
    if s.OPENROUTER_MODEL:
        return s.OPENROUTER_MODEL
    if s.AI_MODEL != "anthropic/claude-sonnet-4.6":
        logging.getLogger(__name__).warning(
            "AI_MODEL устарел — используйте OPENROUTER_MODEL")
    return s.AI_MODEL


def resolved_openrouter_pdf_engine(s: "Settings") -> str:
    """OPENROUTER_PDF_ENGINE → deprecated PDF_ENGINE → код-дефолт mistral-ocr."""
    if s.OPENROUTER_PDF_ENGINE:
        return s.OPENROUTER_PDF_ENGINE
    if s.PDF_ENGINE != "mistral-ocr":
        logging.getLogger(__name__).warning(
            "PDF_ENGINE устарел — используйте OPENROUTER_PDF_ENGINE")
    return s.PDF_ENGINE


def resolved_openrouter_max_tokens(s: "Settings") -> int:
    """OPENROUTER_MAX_TOKENS → deprecated AI_MAX_TOKENS → 64000 (AC-1)."""
    return s.OPENROUTER_MAX_TOKENS if s.OPENROUTER_MAX_TOKENS is not None else s.AI_MAX_TOKENS


def validate_llm_settings(s: "Settings") -> None:
    """Fail-fast §1: обязательные поля ВЫБРАННОГО провайдера; openrouter-ключ НЕ проверяется.

    Пустая строка base URL = отсутствие значения: openrouter лечится дефолтом,
    gateway — обязан быть задан (дефолта нет).
    """
    if s.LLM_PROVIDER == "gateway":
        if not s.GATEWAY_BASE_URL:
            raise RuntimeError("LLM_PROVIDER=gateway: не задан GATEWAY_BASE_URL")
        if not s.GATEWAY_MODEL:
            raise RuntimeError("LLM_PROVIDER=gateway: не задан GATEWAY_MODEL")
```

(`import logging` — в импорты config.py.)

- [ ] **Step 4: Прогнать тесты**

Run: `cd backend && uv run pytest tests/unit/test_config_llm.py -v`
Expected: PASS (8 тестов). Затем smoke: `uv run pytest tests/unit -q` — без регрессий.

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/tests/unit/test_config_llm.py
git commit -m "feat(config): LLM_PROVIDER enum, namespaced-переменные и алиас-цепочки (§1)"
```

---

### Task 2: `llm.py` — типы интерфейса и service locator

**Files:**
- Create: `backend/llm.py`
- Test: `backend/tests/unit/test_llm_locator.py` (создать)

**Interfaces:**
- Produces: `PdfAttachment(data: bytes, filename: str = "document.pdf")`, `ImagesAttachment(images: tuple[bytes, ...])`, `LLMResponse(content, finish_reason, cost_usd: Decimal, completion_tokens, paid_calls)`, `LLMProviderError(message, *, retryable, code=None, cost_usd=Decimal(0), paid_calls=0, correlation_id=None)`, `LLMProvider` (Protocol c `vision_completion`), `init_provider(settings)`, `get_provider()`, `reset_provider()`.
- Consumes: `validate_llm_settings` из Task 1; `OpenRouterProvider.from_settings` из Task 3 (до Task 3 фабрика для openrouter бросает `RuntimeError` — тест это фиксирует и будет обновлён в Task 3).

- [ ] **Step 1: Написать падающие тесты**

Файл `backend/tests/unit/test_llm_locator.py`:

```python
"""Тесты service locator LLM-провайдера: инварианты §2.3 спеки."""
import pytest

import llm
from config import Settings


def _settings(**kw) -> Settings:
    """Settings без .env для изоляции теста."""
    base = {"SECRET_KEY": "x" * 32}
    base.update(kw)
    return Settings(_env_file=None, **base)


@pytest.fixture(autouse=True)
def _clean_locator():
    """Каждый тест стартует и заканчивает с пустым локатором (scoped reset)."""
    llm.reset_provider()
    yield
    llm.reset_provider()


def test_get_before_init_raises_runtime_error():
    """До init_provider() — понятный RuntimeError (инвариант §2.3)."""
    with pytest.raises(RuntimeError, match="не инициализирован"):
        llm.get_provider()


def test_gateway_not_implemented_yet():
    """LLM_PROVIDER=gateway до спайка — понятная ошибка фабрики, не тихий сбой."""
    with pytest.raises(RuntimeError, match="спайк"):
        llm.init_provider(_settings(
            LLM_PROVIDER="gateway", GATEWAY_BASE_URL="http://gw", GATEWAY_MODEL="m"))


def test_reset_clears_provider():
    """reset_provider() возвращает локатор в неинициализированное состояние."""
    llm.reset_provider()
    with pytest.raises(RuntimeError):
        llm.get_provider()


def test_provider_error_carries_billing():
    """LLMProviderError несёт cost/paid/code/correlation_id (инвариант §2.3)."""
    from decimal import Decimal
    e = llm.LLMProviderError("boom", retryable=False, code="x",
                             cost_usd=Decimal("0.1"), paid_calls=1, correlation_id="cid")
    assert (e.retryable, e.code, e.cost_usd, e.paid_calls, e.correlation_id) == \
        (False, "x", Decimal("0.1"), 1, "cid")
```

- [ ] **Step 2: Прогнать — падают**

Run: `cd backend && uv run pytest tests/unit/test_llm_locator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'llm'`.

- [ ] **Step 3: Реализация `backend/llm.py`**

```python
"""Абстракция LLM-провайдера: типы интерфейса + service locator.

Спека: docs/superpowers/specs/2026-07-23-llm-provider-toggle-design.md (§2).
Доменный парсинг (JSON УПД, повороты) сюда НЕ заходит. ЗАПРЕЩЁН импорт из
pdf_orientation (цикл, §2.2). Локатор — осознанный service locator: тесты
кодовой базы стоят на module-level monkeypatch, BackgroundTasks не требуют
протаскивания параметра (§2.3).
"""
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

import httpx

from config import Settings, validate_llm_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PdfAttachment:
    """PDF целиком; способ подачи выбирает провайдер."""
    data: bytes
    filename: str = "document.pdf"


@dataclass(frozen=True)
class ImagesAttachment:
    """Постраничные JPEG-рендеры (detect_rotations)."""
    images: tuple[bytes, ...]


Attachment = PdfAttachment | ImagesAttachment


@dataclass
class LLMResponse:
    """Нормализованный успешный ответ провайдера (§2.1)."""
    content: str
    finish_reason: str | None
    cost_usd: Decimal          # всегда Decimal; gateway → Decimal(0)
    completion_tokens: int | None
    paid_calls: int


class LLMProviderError(Exception):
    """Нормализованная ошибка провайдера; несёт биллинг платного 200 (§2.3).

    str(exc) — безопасное сообщение без содержимого ответа/токенов.
    """

    def __init__(self, message: str, *, retryable: bool, code: str | None = None,
                 cost_usd: Decimal = Decimal(0), paid_calls: int = 0,
                 correlation_id: str | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.code = code
        self.cost_usd = cost_usd
        self.paid_calls = paid_calls
        self.correlation_id = correlation_id


class LLMProvider(Protocol):
    """Единственный метод провайдера: промпт + вложение → текст и метаданные."""

    async def vision_completion(self, *, system: str | None, user_text: str,
                                attachment: Attachment, max_tokens: int,
                                timeout: httpx.Timeout) -> LLMResponse: ...


_provider: LLMProvider | None = None


def _build(settings: Settings) -> LLMProvider:
    """Собрать провайдер по LLM_PROVIDER. Без сетевых запросов (инвариант §2.3)."""
    validate_llm_settings(settings)
    if settings.LLM_PROVIDER == "openrouter":
        raise RuntimeError("OpenRouterProvider появится в Task 3 этого плана")
    raise RuntimeError(
        "LLM_PROVIDER=gateway: GatewayProvider будет реализован после gateway-спайка (спека §7)")


def init_provider(settings: Settings) -> None:
    """Собрать и АТОМАРНО заменить ссылку локатора (lifespan и PUT /settings)."""
    global _provider
    _provider = _build(settings)


def get_provider() -> LLMProvider:
    """Текущий провайдер; до init_provider() — понятный RuntimeError."""
    if _provider is None:
        raise RuntimeError(
            "LLM-провайдер не инициализирован: init_provider() вызывается в lifespan")
    return _provider


def reset_provider() -> None:
    """Очистить локатор (lifespan teardown, scoped reset в тестах)."""
    global _provider
    _provider = None
```

- [ ] **Step 4: Прогнать тесты**

Run: `cd backend && uv run pytest tests/unit/test_llm_locator.py tests/unit/test_config_llm.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/llm.py backend/tests/unit/test_llm_locator.py
git commit -m "feat(llm): типы интерфейса провайдера и service locator (§2.1, §2.3)"
```

---

### Task 3: `OpenRouterProvider` + два контрактных теста (AC-1)

**Files:**
- Create: `backend/llm_openrouter.py`
- Modify: `backend/llm.py` (ветка openrouter в `_build`)
- Test: `backend/tests/unit/test_openrouter_contract.py` (создать); обновить один тест в `backend/tests/unit/test_llm_locator.py`

**Interfaces:**
- Consumes: `LLMResponse`, `LLMProviderError`, `PdfAttachment`, `ImagesAttachment` из Task 2; `resolved_openrouter_*` из Task 1.
- Produces: `OpenRouterProvider.from_settings(settings) -> OpenRouterProvider`; `vision_completion(...)` по Protocol. Поведение envelope 1:1 с текущим `pdf_parser.parse_pdf`/`pdf_orientation.detect_rotations` (транспортный слой).

- [ ] **Step 1: Контрактные тесты (падающие)**

Файл `backend/tests/unit/test_openrouter_contract.py`:

```python
"""Контрактные тесты payload OpenRouter (AC-1 спеки): форма запроса = текущая, 1:1.

Порядок частей content — часть контракта. Плюс envelope-поведение:
биллинг платного 200 при битом теле (инвариант §2.3).
"""
import json
from decimal import Decimal

import httpx
import pytest
import respx

import llm
from config import Settings
from llm_openrouter import OpenRouterProvider

URL = "https://openrouter.ai/api/v1/chat/completions"
OK_BODY = {
    "choices": [{"message": {"content": "ответ"}, "finish_reason": "stop"}],
    "usage": {"cost": 0.01, "completion_tokens": 5},
}


def _provider(**kw) -> OpenRouterProvider:
    """Провайдер из чистых Settings (без .env) с тестовым ключом."""
    base = {"SECRET_KEY": "x" * 32, "OPENROUTER_API_KEY": "sk-test"}
    base.update(kw)
    return OpenRouterProvider.from_settings(Settings(_env_file=None, **base))


@pytest.mark.anyio
@respx.mock
async def test_parse_form_contract():
    """parse-форма: system+file первым+текст, plugins с engine, usage.include, max_tokens, auth."""
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    p = _provider(OPENROUTER_MODEL="test/model", OPENROUTER_PDF_ENGINE="native",
                  OPENROUTER_MAX_TOKENS=64000)
    resp = await p.vision_completion(
        system="SYS", user_text="извлеки",
        attachment=llm.PdfAttachment(data=b"%PDF-1.4"), max_tokens=64000,
        timeout=httpx.Timeout(180))
    req = route.calls[0].request
    assert req.headers["Authorization"] == "Bearer sk-test"
    body = json.loads(req.content)
    assert body["model"] == "test/model"
    assert body["max_tokens"] == 64000
    assert body["usage"] == {"include": True}
    assert body["plugins"] == [{"id": "file-parser", "pdf": {"engine": "native"}}]
    assert body["messages"][0] == {"role": "system", "content": "SYS"}
    parts = body["messages"][1]["content"]
    assert parts[0]["type"] == "file" and parts[1]["type"] == "text"
    assert resp.cost_usd == Decimal("0.01") and resp.paid_calls == 1
    assert resp.finish_reason == "stop" and resp.content == "ответ"


@pytest.mark.anyio
@respx.mock
async def test_detect_form_contract():
    """detect-форма: без system, текст первым + image_url, БЕЗ plugins, max_tokens=200."""
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    p = _provider(OPENROUTER_MODEL="test/model")
    await p.vision_completion(
        system=None, user_text="повороты?",
        attachment=llm.ImagesAttachment(images=(b"\xff\xd8jpeg",)), max_tokens=200,
        timeout=httpx.Timeout(30, connect=5.0))
    body = json.loads(route.calls[0].request.content)
    assert "plugins" not in body
    assert body["max_tokens"] == 200
    assert body["messages"][0]["role"] == "user"  # system отсутствует
    parts = body["messages"][0]["content"]
    assert parts[0]["type"] == "text" and parts[1]["type"] == "image_url"


@pytest.mark.anyio
@respx.mock
async def test_missing_key_is_permanent_error():
    """Без ключа — нерetryable ошибка с текущим текстом (поведение 1:1)."""
    p = _provider(OPENROUTER_API_KEY="")
    with pytest.raises(llm.LLMProviderError, match="API-ключ OpenRouter не настроен") as ei:
        await p.vision_completion(system=None, user_text="x",
                                  attachment=llm.ImagesAttachment(images=(b"j",)),
                                  max_tokens=200, timeout=httpx.Timeout(30))
    assert ei.value.retryable is False and ei.value.paid_calls == 0


@pytest.mark.anyio
@respx.mock
async def test_http_status_classification():
    """5xx/408/429 → retryable; прочие — нет (симметрично текущему parse_pdf)."""
    for status, retryable in [(500, True), (429, True), (408, True), (403, False)]:
        respx.post(URL).mock(return_value=httpx.Response(status, json={}))
        p = _provider()
        with pytest.raises(llm.LLMProviderError, match=f"OpenRouter API ошибка: {status}") as ei:
            await p.vision_completion(system=None, user_text="x",
                                      attachment=llm.ImagesAttachment(images=(b"j",)),
                                      max_tokens=200, timeout=httpx.Timeout(30))
        assert ei.value.retryable is retryable and ei.value.paid_calls == 0


@pytest.mark.anyio
@respx.mock
async def test_broken_envelope_keeps_billing():
    """HTTP 200 без choices → LLMProviderError(retryable=False, paid_calls=1, cost)."""
    respx.post(URL).mock(return_value=httpx.Response(200, json={"usage": {"cost": 0.02}}))
    p = _provider()
    with pytest.raises(llm.LLMProviderError, match="Ответ модели без содержимого") as ei:
        await p.vision_completion(system=None, user_text="x",
                                  attachment=llm.ImagesAttachment(images=(b"j",)),
                                  max_tokens=200, timeout=httpx.Timeout(30))
    assert ei.value.paid_calls == 1 and ei.value.cost_usd == Decimal("0.02")
    assert ei.value.retryable is False


@pytest.mark.anyio
@respx.mock
async def test_cost_clamp_nan_negative():
    """NaN/отрицательный usage.cost клэмпится в 0 (FIX B, поведение 1:1)."""
    respx.post(URL).mock(return_value=httpx.Response(
        200, json={"choices": [{"message": {"content": "t"}, "finish_reason": "stop"}],
                   "usage": {"cost": -5}}))
    p = _provider()
    resp = await p.vision_completion(system=None, user_text="x",
                                     attachment=llm.ImagesAttachment(images=(b"j",)),
                                     max_tokens=200, timeout=httpx.Timeout(30))
    assert resp.cost_usd == Decimal(0) and resp.paid_calls == 1
```

Примечание: если в юнит-тестах не настроен anyio-маркер, проверить `backend/pyproject.toml`/`conftest` — в репо уже есть async-тесты (`test_pdf_orientation.py`), использовать тот же механизм (например, существующий `pytest-asyncio`/`anyio` маркер; скопировать декоратор из соседнего файла).

- [ ] **Step 2: Прогнать — падают**

Run: `cd backend && uv run pytest tests/unit/test_openrouter_contract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'llm_openrouter'`.

- [ ] **Step 3: Реализация `backend/llm_openrouter.py`**

Код — перенос текущей транспортной логики `pdf_parser.parse_pdf` (строки ~157-260 до извлечения `response_text` включительно) и сборки detect-payload из `pdf_orientation.detect_rotations`:

```python
"""OpenRouterProvider: транспорт/envelope OpenRouter, вынесенный из pdf_parser (1:1).

Payload защищён контрактными тестами (AC-1). Доменного парсинга здесь нет.
"""
import base64
import logging
from dataclasses import dataclass
from decimal import Decimal

import httpx

from config import (Settings, resolved_openrouter_max_tokens,
                    resolved_openrouter_model, resolved_openrouter_pdf_engine)
from llm import (Attachment, ImagesAttachment, LLMProviderError, LLMResponse,
                 PdfAttachment)

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class OpenRouterProvider:
    """Неизменяемый экземпляр (инвариант §2.3); ссылка меняется только локатором."""

    api_key: str
    completions_url: str
    model: str
    pdf_engine: str

    @classmethod
    def from_settings(cls, s: Settings) -> "OpenRouterProvider":
        """Собрать из Settings; пустой base URL = отсутствие → дефолт (guard §1)."""
        base = (s.OPENROUTER_BASE_URL or _DEFAULT_BASE_URL).rstrip("/")
        return cls(api_key=s.OPENROUTER_API_KEY,
                   completions_url=f"{base}/chat/completions",
                   model=resolved_openrouter_model(s),
                   pdf_engine=resolved_openrouter_pdf_engine(s))

    def _payload(self, *, system: str | None, user_text: str,
                 attachment: Attachment, max_tokens: int) -> dict:
        """Собрать OpenRouter-payload; порядок частей — контракт (AC-1)."""
        if isinstance(attachment, PdfAttachment):
            pdf_b64 = base64.b64encode(attachment.data).decode("utf-8")
            content: list[dict] = [
                {"type": "file", "file": {"filename": attachment.filename,
                 "file_data": f"data:application/pdf;base64,{pdf_b64}"}},
                {"type": "text", "text": user_text},
            ]
            plugins = [{"id": "file-parser", "pdf": {"engine": self.pdf_engine}}]
        else:
            content = [{"type": "text", "text": user_text}]
            for img in attachment.images:
                b64 = base64.b64encode(img).decode()
                content.append({"type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
            plugins = None
        messages: list[dict] = []
        if system is not None:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": content})
        payload = {"model": self.model, "max_tokens": max_tokens,
                   "usage": {"include": True}, "messages": messages}
        if plugins is not None:
            payload["plugins"] = plugins
        return payload

    async def vision_completion(self, *, system: str | None, user_text: str,
                                attachment: Attachment, max_tokens: int,
                                timeout: httpx.Timeout) -> LLMResponse:
        """Отправить запрос и разобрать envelope; ошибки — LLMProviderError с биллингом."""
        if not self.api_key:
            raise LLMProviderError("API-ключ OpenRouter не настроен", retryable=False)
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}
        payload = self._payload(system=system, user_text=user_text,
                                attachment=attachment, max_tokens=max_tokens)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self.completions_url,
                                             headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise LLMProviderError("Таймаут запроса к OpenRouter (180с)",
                                   retryable=True) from exc
        except httpx.RequestError as exc:
            # транспортный сбой без ответа сервера → платного вызова не было (F12)
            logger.warning(f"OpenRouter: сетевая ошибка запроса: {exc!r}")
            raise LLMProviderError("Сетевая ошибка запроса к сервису распознавания",
                                   retryable=True) from exc

        if response.status_code != 200:
            retryable = response.status_code >= 500 or response.status_code in (408, 429)
            raise LLMProviderError(f"OpenRouter API ошибка: {response.status_code}",
                                   retryable=retryable)

        # HTTP 200 ⇒ платный вызов состоялся: ВСЁ ниже несёт paid_calls=1 (§2.3)
        cost = Decimal(0)
        try:
            data = response.json()
            raw_cost = Decimal(str((data.get("usage") or {}).get("cost") or 0))
            if raw_cost.is_finite() and raw_cost >= 0:
                cost = raw_cost
            else:
                logger.warning(f"OpenRouter: usage.cost вне допустимых значений "
                               f"({raw_cost!r}) — клэмп в 0")
            usage = data.get("usage") or {}
            completion_tokens = usage.get("completion_tokens")
            finish_reason = (data.get("choices") or [{}])[0].get("finish_reason")
            content_text = data["choices"][0]["message"]["content"]
        except LLMProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 — битый envelope платного 200
            raise LLMProviderError("Ответ модели без содержимого", retryable=False,
                                   cost_usd=cost, paid_calls=1) from exc
        return LLMResponse(content=content_text, finish_reason=finish_reason,
                           cost_usd=cost, completion_tokens=completion_tokens,
                           paid_calls=1)
```

В `llm.py::_build` заменить openrouter-ветку:

```python
    if settings.LLM_PROVIDER == "openrouter":
        from llm_openrouter import OpenRouterProvider  # локальный импорт против цикла
        return OpenRouterProvider.from_settings(settings)
```

В `test_llm_locator.py` заменить тест-заглушку Task 2 (если добавлялся тест на «Task 3») на позитивный:

```python
def test_init_openrouter_and_get():
    """init_provider(openrouter) устанавливает OpenRouterProvider."""
    llm.init_provider(_settings(OPENROUTER_API_KEY="sk-t"))
    from llm_openrouter import OpenRouterProvider
    assert isinstance(llm.get_provider(), OpenRouterProvider)
```

- [ ] **Step 4: Прогнать**

Run: `cd backend && uv run pytest tests/unit/test_openrouter_contract.py tests/unit/test_llm_locator.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/llm_openrouter.py backend/llm.py backend/tests/unit/
git commit -m "feat(llm): OpenRouterProvider + контрактные тесты обеих форм payload (AC-1)"
```

---

### Task 4: Рефактор `pdf_parser.parse_pdf` на провайдер (домен остаётся)

**Files:**
- Modify: `backend/pdf_parser.py` (строки ~157-260: транспорт → провайдер; домен 262+ не трогать)
- Modify: `backend/main.py` (lifespan: `init_provider` + teardown)
- Modify: `backend/tests/conftest.py` (autouse-fixture инициализации локатора)
- Test: существующие `backend/tests/integration/test_pdf_parser_phase_a.py`, `test_process_document.py` — должны остаться зелёными БЕЗ правок.

**Interfaces:**
- Consumes: `llm.get_provider()`, `llm.LLMProviderError`, `llm.PdfAttachment`, `resolved_openrouter_max_tokens`.
- Produces: `parse_pdf` с прежней сигнатурой и прежним поведением/текстами ошибок; `OPENROUTER_URL` в `pdf_parser` пока ОСТАЁТСЯ (его импортирует `pdf_orientation` — удаление в Task 5).

- [ ] **Step 1: Заготовить фикстуру локатора в `tests/conftest.py`**

После существующих фикстур добавить:

```python
@pytest.fixture(autouse=True)
def _llm_provider_initialized():
    """Инициализировать LLM-локатор на каждый тест (scoped reset, инвариант §2.3).

    Ключ тестовый: unit/integration перехватывают HTTP respx-моками, наружу
    запросы не уходят. reset в teardown — повторные TestClient корректны.
    """
    import llm
    from config import settings
    from llm_openrouter import OpenRouterProvider
    llm._provider = OpenRouterProvider.from_settings(settings)
    if not llm._provider.api_key:
        llm._provider = dataclasses.replace(llm._provider, api_key="sk-test")
    yield
    llm.reset_provider()
```

(`import dataclasses` — в шапку conftest. Прямое присваивание `llm._provider` вместо `init_provider` — чтобы не зависеть от валидации env в тестовом окружении.)

- [ ] **Step 2: Рефактор `parse_pdf`**

В `pdf_parser.py`: импорты дополнить `import llm` и `from config import resolved_openrouter_max_tokens`; блок от `api_key = settings.OPENROUTER_API_KEY` до `response_text = data["choices"][0]["message"]["content"]` (строки ~175-260) заменить на:

```python
    max_tokens = resolved_openrouter_max_tokens(settings)
    try:
        resp = await llm.get_provider().vision_completion(
            system=SYSTEM_PROMPT,
            user_text=("Определи тип документа и извлеки данные. ВАЖНО: каждая строка "
                       "из табличной части — это отдельная позиция в items. "
                       "Не объединяй и не суммируй строки, даже если они выглядят одинаково."),
            attachment=llm.PdfAttachment(data=file_data),
            max_tokens=max_tokens,
            timeout=httpx.Timeout(180),
        )
    except llm.LLMProviderError as exc:
        # Маппинг ошибки провайдера в доменную с сохранением биллинга (§2.3).
        cls = TransientError if exc.retryable else PermanentError
        raise cls(str(exc), cost_usd=exc.cost_usd, paid_calls=exc.paid_calls) from exc

    cost = resp.cost_usd
    paid_calls = resp.paid_calls
    logger.info(f"[doc={document_id}] Фаза A: cost=${cost}, finish_reason={resp.finish_reason}")

    if resp.finish_reason == "length":
        raise PermanentError(
            "Ответ модели обрезан по лимиту токенов — часть позиций счёта потеряна. "
            "Попробуйте повторить разбор.",
            cost_usd=cost, paid_calls=paid_calls,
        )
    if resp.completion_tokens and resp.completion_tokens >= max_tokens:
        logger.error(f"[doc={document_id}] completion_tokens={resp.completion_tokens} == max — ответ обрезан")

    response_text = resp.content
    try:
        # ниже — существующий доменный код БЕЗ изменений (fence, json.loads,
        # doc_type, цикл по СФ); он остаётся внутри прежнего try-guard
```

ВНИМАНИЕ: существующий доменный try-блок (markdown-fence → `json.loads` → `doc_type` → цикл) сохранить как есть, включая `PermanentError(..., cost_usd=cost, paid_calls=paid_calls)` во всех ветках. Логи `Фаза A: старт парсинга` и структура функции не меняются. Константы `OPENROUTER_BASE_URL`/`OPENROUTER_URL` в модуле оставить (их пока импортирует `pdf_orientation` — Task 5 удалит).

- [ ] **Step 3: lifespan в `main.py`**

В `lifespan` после `_sweep_stuck_documents()` добавить:

```python
    # LLM-провайдер: fail-fast конфигурации выбранного провайдера (§1 спеки),
    # инициализация локатора ДО приёма трафика. Позднее связывание модуля —
    # тестовые monkeypatch-и llm должны действовать (паттерн как у s3 выше).
    llm.init_provider(settings)
    logger.info(f"LLM-провайдер инициализирован: {settings.LLM_PROVIDER}")

    yield

    llm.reset_provider()
```

(`import llm` — в импорты main.py; `yield` существующий заменяется на `yield` + teardown.)

- [ ] **Step 4: Прогнать интеграционные тесты парсера — зелёные без правок**

Run: `cd backend && uv run pytest tests/integration/test_pdf_parser_phase_a.py tests/integration/test_process_document.py -v` (через `just test-int-local`, если локальный PG поднят)
Expected: PASS все — тексты ошибок и биллинг не изменились; MockAI из conftest перехватывает тот же URL.

- [ ] **Step 5: Полный smoke юнитов**

Run: `cd backend && uv run pytest tests/unit -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/pdf_parser.py backend/main.py backend/tests/conftest.py
git commit -m "refactor(parser): parse_pdf через LLM-локатор; транспорт — в провайдере (§2.2)"
```

---

### Task 5: Рефактор `detect_rotations` + семантика битого envelope (§2.5)

**Files:**
- Modify: `backend/pdf_orientation.py` (детект через провайдер; удалить `from pdf_parser import OPENROUTER_URL`)
- Modify: `backend/pdf_parser.py` (удалить module-level `OPENROUTER_BASE_URL`/`OPENROUTER_URL`)
- Modify: `backend/scripts/snapshot_ai_responses.py` (локально построить URL вместо импорта)
- Modify: `backend/processing.py` (ТОЛЬКО комментарий у `deskew_pdf`, §8)
- Test: обновить `backend/tests/unit/test_pdf_orientation.py` (битый envelope: нули → ошибка)

**Interfaces:**
- Consumes: `llm.get_provider()`, `llm.ImagesAttachment`, `llm.LLMProviderError`.
- Produces: `detect_rotations(images) -> tuple[list[int], Decimal]` — сигнатура прежняя; новое поведение: битый envelope при 200 → `PermanentError` (раньше — тихие нули).

- [ ] **Step 1: Обновить тесты ориентации под §2.5**

В `tests/unit/test_pdf_orientation.py` найти тесты деградации на битом envelope при 200 (мокают 200 без `choices`/с кривым JSON и ждут нулевых поворотов). Их ожидание меняется на ошибку:

```python
@respx.mock  # тот же стиль, что у существующих тестов файла
@pytest.mark.anyio
async def test_broken_envelope_raises_permanent():
    """§2.5: битый envelope платного 200 → PermanentError с cost, НЕ тихие нули."""
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"usage": {"cost": 0.01}}))
    with pytest.raises(PermanentError, match="отклонил запрос") as ei:
        await po.detect_rotations([b"jpeg1"])
    assert ei.value.cost_usd == Decimal("0.01")
```

(Декоратор async-тестов скопировать из соседних тестов этого же файла — там уже есть работающая связка respx + async. Существующие `monkeypatch.setattr(po.settings, "OPENROUTER_API_KEY", ...)` в переписываемых тестах больше не нужны: ключ идёт из conftest-фикстуры локатора Task 4.)

Тесты «контент не распарсился при ЦЕЛОМ envelope» (есть `choices`, но текст без массива) — остаются на нулях. Точечный разбор существующих тестов файла — по месту: какие мокают отсутствие `choices` → переписать на ошибку; какие мокают мусорный текст в `choices[0].message.content` → оставить нули.

- [ ] **Step 2: Прогнать — новые ожидания падают**

Run: `cd backend && uv run pytest tests/unit/test_pdf_orientation.py -v`
Expected: FAIL на обновлённых тестах (пока старое поведение).

- [ ] **Step 3: Рефактор `detect_rotations`**

В `pdf_orientation.py`: удалить `from pdf_parser import OPENROUTER_URL`, добавить `import llm`. Блок сборки payload/HTTP (строки ~137-167) и разбора (169-193) заменить на:

```python
    content_text: str = ""
    try:
        resp = await llm.get_provider().vision_completion(
            system=None, user_text=_DETECT_PROMPT,
            attachment=llm.ImagesAttachment(images=tuple(images)),
            max_tokens=200,
            timeout=httpx.Timeout(DETECT_TIMEOUT, connect=5.0),
        )
    except llm.LLMProviderError as e:
        # НЕ деградируем в нули (иначе переразберём оригинал под видом исправленного).
        # §2.5: битый envelope платного 200 — тоже ошибка (retryable=False, cost, paid=1),
        # а не тихие нули; биллинг доезжает через cost_usd/paid_calls исключения.
        logger.warning(f"detect_rotations: vision-запрос упал: {e}")
        if e.retryable:
            raise TransientError("Сервис распознавания ориентации недоступен",
                                 http_status=502, cost_usd=e.cost_usd,
                                 paid_calls=e.paid_calls) from e
        raise PermanentError("Сервис распознавания ориентации отклонил запрос",
                             http_status=502, cost_usd=e.cost_usd,
                             paid_calls=e.paid_calls) from e

    cost = resp.cost_usd
    content_text = resp.content
    # envelope цел: непарсящееся СОДЕРЖИМОЕ → нули (деградация уровня контента)
    try:
        m = re.search(r"\[[\d,\s]*\]", content_text)
        nums = json.loads(m.group(0)) if m else []
        allowed = {0, 90, 180, 270}
        rots = [v % 360 if (v % 360) in allowed else 0 for v in nums[:n]]
    except Exception:  # noqa: BLE001 — кривое содержимое не должно ронять вызывающего
        rots = []
    rots += [0] * (n - len(rots))
    logger.info(f"detect_rotations: n={n}, rotations={rots}, cost=${cost}, raw={content_text[:300]!r}")
    return rots, cost
```

Проверить сигнатуры `TransientError`/`PermanentError` в `processing.py`: если конструктор не принимает `cost_usd`/`paid_calls` вместе с `http_status` — использовать фактическую сигнатуру (`ProcessingError` в репо уже несёт `cost_usd`/`paid_calls` — см. использование в `pdf_parser`).

- [ ] **Step 4: Удалить константы из `pdf_parser.py` и починить snapshot-скрипт**

Из `pdf_parser.py` удалить блок `OPENROUTER_BASE_URL = ...` / `OPENROUTER_URL = ...` (с комментарием про пустую строку — guard переехал в `OpenRouterProvider.from_settings`). В `scripts/snapshot_ai_responses.py` заменить `from pdf_parser import OPENROUTER_URL, SYSTEM_PROMPT` на:

```python
    from pdf_parser import SYSTEM_PROMPT
    base = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").rstrip("/")
    OPENROUTER_URL = f"{base}/chat/completions"
```

(Скрипт дев-only и остаётся OpenRouter-only — §8 спеки, YAGNI.)

- [ ] **Step 5: Обновить комментарий-инвариант в `processing.py` (§8)**

Комментарий на строках ~334-335 заменить на:

```python
    # deskew_pdf бросает TransientError ДО чтения cost при транспортном сбое detect
    # (тогда detect не оплачен); при битом envelope платного 200 — ошибку С detect-cost
    # (§2.5 спеки LLM-провайдера: retryable=False, cost, paid_calls=1 — биллинг в exc);
    # при сбое apply_rotations — уже С detect-cost (см. pdf_orientation).
```

- [ ] **Step 6: Прогнать**

Run: `cd backend && uv run pytest tests/unit/test_pdf_orientation.py tests/unit -q && uv run python -c "import scripts.snapshot_ai_responses"` (последнее — smoke импорта не обязателен, скрипт с sys.argv-guard: достаточно `uv run python scripts/snapshot_ai_responses.py` → Usage-сообщение)
Expected: PASS; скрипт печатает Usage.

- [ ] **Step 7: Интеграционный прогон deskew**

Run: `just test-int-local` (или `uv run pytest tests/integration -q` при поднятом тестовом PG)
Expected: PASS (маршрут deskew-reparse жив; изменившиеся тесты — только unit ориентации).

- [ ] **Step 8: Commit**

```bash
git add backend/pdf_orientation.py backend/pdf_parser.py backend/scripts/snapshot_ai_responses.py backend/processing.py backend/tests/unit/test_pdf_orientation.py
git commit -m "refactor(orientation): detect через провайдер; битый envelope → ошибка (§2.5)"
```

---

### Task 6: Settings API — capabilities, запреты PUT, атомарная замена провайдера

**Files:**
- Modify: `backend/routers/settings.py`
- Test: `backend/tests/integration/test_settings.py` (дополнить)

**Interfaces:**
- Consumes: `llm.init_provider`, `config.Settings`, `resolved_openrouter_model`.
- Produces: GET `/api/settings` → `{provider, can_edit_model, cost_available, api_key_set, model, confidence_threshold}`; PUT — в gateway-режиме `api_key`/`model` → 403; в openrouter-режиме PUT пересобирает провайдер.

- [ ] **Step 1: Тесты (падающие) — дополнить `tests/integration/test_settings.py`**

```python
def test_get_returns_capabilities(client):
    """GET отдаёт capabilities: provider/can_edit_model/cost_available (§5 спеки)."""
    r = client.get("/api/settings")
    body = r.json()
    assert body["provider"] == "openrouter"
    assert body["can_edit_model"] is True
    assert body["cost_available"] is True


def test_gateway_mode_put_model_forbidden(client, monkeypatch):
    """gateway-режим: PUT с model/api_key → 403; только confidence_threshold — 200."""
    from config import settings as cfg
    monkeypatch.setattr(cfg, "LLM_PROVIDER", "gateway")
    assert client.put("/api/settings", json={"model": "x"}).status_code == 403
    assert client.put("/api/settings", json={"api_key": "sk-x"}).status_code == 403
    assert client.put("/api/settings", json={"confidence_threshold": 0.5}).status_code == 200


def test_gateway_mode_get_capabilities(client, monkeypatch):
    """gateway-режим: can_edit_model=false, cost_available=false, api_key_set не по sk-."""
    from config import settings as cfg
    monkeypatch.setattr(cfg, "LLM_PROVIDER", "gateway")
    body = client.get("/api/settings").json()
    assert body["can_edit_model"] is False
    assert body["cost_available"] is False
    assert body["api_key_set"] is True  # ключ не нужен — UI не должен просить ввод


def test_put_rebuilds_provider(client):
    """openrouter: PUT модели атомарно пересобирает провайдер (чинит латентный баг §5)."""
    import llm
    client.put("/api/settings", json={"model": "test/rebuilt"})
    assert llm.get_provider().model == "test/rebuilt"
```

(Использовать существующий `client` из conftest; авторизация — как в соседних тестах файла `test_settings.py` — скопировать их подготовку пользователя. **ВАЖНО:** PUT пишет в `ENV_PATH` — проверить, как существующие тесты файла изолируют запись от реального `backend/.env` (monkeypatch `ENV_PATH` → tmp_path); новые тесты обязаны использовать тот же механизм, чтобы не мутировать дев-`.env`.)

- [ ] **Step 2: Прогнать — падают**

Run: `cd backend && uv run pytest tests/integration/test_settings.py -v` (нужен тестовый PG)
Expected: FAIL новые тесты.

- [ ] **Step 3: Реализация `routers/settings.py`**

Заменить содержимое GET/PUT:

```python
import os

from dotenv import load_dotenv, set_key
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import llm
from config import Settings, resolved_openrouter_model, settings

router = APIRouter()

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")


def _ensure_env():
    """Создать .env при отсутствии и подгрузить его в os.environ."""
    if not os.path.exists(ENV_PATH):
        with open(ENV_PATH, "w") as f:
            f.write("")
    load_dotenv(ENV_PATH, override=True)


class SettingsUpdate(BaseModel):
    """Частичный PUT: присылаются ТОЛЬКО изменённые поля (§5 спеки)."""
    api_key: str | None = None
    model: str | None = None
    confidence_threshold: float | None = None


@router.get("")
def get_settings():
    """Настройки + capabilities (§5): фронт скрывает поля, backend enforce'ит."""
    _ensure_env()
    is_gateway = settings.LLM_PROVIDER == "gateway"
    return {
        "provider": settings.LLM_PROVIDER,
        "can_edit_model": not is_gateway,
        "cost_available": not is_gateway,
        # gateway: ключ не нужен → true, чтобы UI не показывал призыв ввода (§5)
        "api_key_set": True if is_gateway
        else bool(os.getenv("OPENROUTER_API_KEY", "").startswith("sk-")),
        "model": settings.GATEWAY_MODEL if is_gateway
        else (os.getenv("OPENROUTER_MODEL") or os.getenv("AI_MODEL")
              or "anthropic/claude-sonnet-4.6"),
        "confidence_threshold": float(os.getenv("CONFIDENCE_THRESHOLD", "0.7")),
    }


@router.put("")
def update_settings(data: SettingsUpdate):
    """PUT: в gateway-режиме api_key/model запрещены (403); openrouter — пересборка провайдера."""
    _ensure_env()
    if settings.LLM_PROVIDER == "gateway" and (data.api_key is not None or data.model is not None):
        raise HTTPException(status_code=403,
                            detail="В контурном режиме ключ и модель задаются при деплое")
    llm_changed = False
    if data.api_key is not None:
        set_key(ENV_PATH, "OPENROUTER_API_KEY", data.api_key)
        os.environ["OPENROUTER_API_KEY"] = data.api_key
        llm_changed = True
    if data.model is not None:
        set_key(ENV_PATH, "AI_MODEL", data.model)
        os.environ["AI_MODEL"] = data.model
        llm_changed = True
    if data.confidence_threshold is not None:
        set_key(ENV_PATH, "CONFIDENCE_THRESHOLD", str(data.confidence_threshold))
        os.environ["CONFIDENCE_THRESHOLD"] = str(data.confidence_threshold)
    if llm_changed:
        # Атомарная замена провайдера (§5): свежие Settings() перечитывают
        # обновлённый os.environ — латентный баг «ключ не действует до рестарта» закрыт.
        # Синглтон config.settings обновляем точечно, чтобы GET видел актуальный ключ.
        fresh = Settings()
        settings.OPENROUTER_API_KEY = fresh.OPENROUTER_API_KEY
        settings.AI_MODEL = fresh.AI_MODEL
        llm.init_provider(fresh)
    return {"message": "Настройки сохранены"}
```

Примечание: `set_key(..., "AI_MODEL", ...)` сохраняется (существующие `.env` живут на `AI_MODEL`; писать новый ключ `OPENROUTER_MODEL` = два источника в одном файле). Резолвер Task 1 читает `AI_MODEL` алиасом — поведение корректно.

- [ ] **Step 4: Прогнать**

Run: `cd backend && uv run pytest tests/integration/test_settings.py -v`
Expected: PASS (новые + существующие).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/settings.py backend/tests/integration/test_settings.py
git commit -m "feat(settings): capabilities, запреты PUT в контуре, атомарная пересборка провайдера (§5)"
```

---

### Task 7: Frontend — частичный PUT, capabilities, «стоимость недоступна»

**Files:**
- Modify: `frontend/src/services/api/settings.ts`
- Modify: `frontend/src/pages/Settings.tsx`
- Modify: `frontend/src/pages/Review.tsx` (строка ~330-335)
- Modify: `frontend/src/test/handlers.ts` (дефолтный мок `/settings`)
- Test: `frontend/src/pages/Settings.test.tsx` (если нет — создать), обновить `frontend/src/pages/Review.test.tsx`

**Interfaces:**
- Consumes: GET-форма Task 6 (`provider`, `can_edit_model`, `cost_available`).
- Produces: PUT отправляет только изменённые разрешённые поля; UI скрывает выбор модели по `can_edit_model=false`; `Review` показывает «стоимость недоступна» при `cost_available=false`.

- [ ] **Step 1: Типы `settings.ts`**

```typescript
export interface AppSettings {
  provider: "openrouter" | "gateway";
  can_edit_model: boolean;
  cost_available: boolean;
  api_key_set: boolean;
  model: string;
  confidence_threshold: number;
  [key: string]: unknown;
}
```

(Метод `update` уже принимает `Partial<AppSettings>` — не трогать.)

- [ ] **Step 2: Обновить дефолтный мок в `test/handlers.ts`**

В хэндлере `/settings` (строка ~105) дополнить тело ответа:

```typescript
      provider: "openrouter",
      can_edit_model: true,
      cost_available: true,
```

- [ ] **Step 3: Тесты (падающие)**

В `Review.test.tsx` добавить кейс:

```typescript
it("показывает «стоимость недоступна» при cost_available=false", async () => {
  server.use(
    http.get("*/api/settings", () =>
      HttpResponse.json({
        provider: "gateway", can_edit_model: false, cost_available: false,
        api_key_set: true, model: "m", confidence_threshold: 0.7,
      })
    )
  );
  renderReview(); // существующий хелпер файла
  expect(await screen.findByText(/стоимость недоступна/i)).toBeInTheDocument();
  expect(screen.queryByText(/\$\d/)).not.toBeInTheDocument();
});
```

Для `Settings.tsx` — новый файл `Settings.test.tsx` (по образцу соседних page-тестов: провайдеры/роутер из существующего test-utils):

```typescript
it("отправляет только изменённые поля", async () => {
  let putBody: unknown;
  server.use(
    http.put("*/api/settings", async ({ request }) => {
      putBody = await request.json();
      return HttpResponse.json({ message: "ok" });
    })
  );
  renderSettingsPage();
  await userEvent.click(screen.getByRole("button", { name: "Парсинг" }));
  const threshold = screen.getByRole("spinbutton");
  await userEvent.clear(threshold);
  await userEvent.type(threshold, "0.9");
  await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
  await waitFor(() => expect(putBody).toEqual({ confidence_threshold: 0.9 }));
});

it("скрывает поле модели при can_edit_model=false", async () => {
  server.use(
    http.get("*/api/settings", () =>
      HttpResponse.json({
        provider: "gateway", can_edit_model: false, cost_available: false,
        api_key_set: true, model: "m", confidence_threshold: 0.7,
      })
    )
  );
  renderSettingsPage();
  await userEvent.click(await screen.findByRole("button", { name: "Парсинг" }));
  expect(screen.queryByPlaceholderText(/anthropic/)).not.toBeInTheDocument();
});
```

- [ ] **Step 4: Реализация**

`Settings.tsx`:
- обёртку поля «Модель» (строки ~151-164) обернуть в `{draft.can_edit_model && ( ... )}`;
- кнопку «Сохранить» (строка ~220): вместо `update.mutate(draft)`:

```typescript
onClick={() => {
  if (!settingsQ.data) return;
  const changed: Record<string, unknown> = {};
  const editable: Array<keyof AppSettings> = draft.can_edit_model
    ? ["model", "confidence_threshold"]
    : ["confidence_threshold"];
  for (const k of editable) {
    if (draft[k] !== settingsQ.data[k]) changed[k as string] = draft[k];
  }
  update.mutate(changed);
}}
```

`Review.tsx` (строки ~330-335): компонент уже имеет доступ к настройкам (см. существующий запрос настроек в этом дереве — тесты файла мокают `/settings`; если хук не подключён в самом Review — добавить `const settingsQ = useSettings();`):

```tsx
{doc.parse_count > 0 && (
  <span title={`${doc.parse_count} разбор${pluralRu(doc.parse_count)}`}>
    {settingsQ.data?.cost_available === false
      ? "ИИ-разбор: стоимость недоступна"
      : `ИИ-разбор: ${formatUsd(doc.parse_cost_usd)}`}
    {doc.parse_count > 1 ? ` · ${doc.parse_count}×` : ""}
  </span>
)}
```

Обновить OpenRouter-специфичные комментарии в `frontend/src/types/invoice.ts` (строки ~82-84): «стоимость ИИ-разбора, USD (usage-репорт провайдера; в контурном режиме недоступна — см. capabilities)».

- [ ] **Step 5: Прогнать**

Run: `just test-frontend` и `just typecheck-frontend`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): частичный PUT настроек, capabilities, «стоимость недоступна» (§5, AC-5/6)"
```

---

### Task 8: Гигиена — `.gitignore`, `.env.example`, финальный прогон

**Files:**
- Modify: `.gitignore`, `backend/.env.example`

**Interfaces:** нет (файлы конфигурации).

- [ ] **Step 1: `.gitignore` — секреты gateway (§8)**

После строки `/CLAUDE_CODE_GATEWAY_INSTRUCTION.md` добавить:

```
.gateway.env
.access_token
.refresh_token
```

- [ ] **Step 2: `.env.example` — namespaced-переменные §1**

Заменить строки `AI_MODEL=...` и `PDF_ENGINE=native` на:

```
# LLM-провайдер: openrouter (дефолт) | gateway (контур МР; после спайка)
LLM_PROVIDER=openrouter
OPENROUTER_MODEL=anthropic/claude-sonnet-4.6
OPENROUTER_PDF_ENGINE=native
# GATEWAY_BASE_URL=
# GATEWAY_MODEL=
```

(Теперь переменные существуют в коде — обещание §8 выполняется.)

- [ ] **Step 3: Полный прогон**

Run: `just lint` затем `just test` (напрямую, без пайпов — Windows-грабля из памяти проекта)
Expected: оба зелёные.

- [ ] **Step 4: Commit**

```bash
git add .gitignore backend/.env.example
git commit -m "chore: gitignore токенов gateway, namespaced-переменные в .env.example (§8)"
```

---

## Вне этого плана (следующие фазы)

1. **Gateway-спайк** (§7 спеки) — ручной, нужен Keycloak-токен; client_credentials уже проверен (выключен — вопрос IT §10.2).
2. **План 2: `gateway_client/` + `GatewayProvider`** — после спайка (auth-механизм, подача PDF, `GATEWAY_MAX_TOKENS`, замена временного AC-3).
3. **План 3: golden eval + baseline** (§6) — baseline снимать ДО мержа изменений модели/движка.
4. IT-вопросы §10 (source-level URL, сервис-аккаунт, комплаенс картинок).
