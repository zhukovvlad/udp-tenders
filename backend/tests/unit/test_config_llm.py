"""Тесты конфигурации LLM-провайдера: алиасы, дефолты, fail-fast (§1 спеки)."""
import pytest

from config import (
    Settings,
    resolved_openrouter_max_tokens,
    resolved_openrouter_model,
    resolved_openrouter_pdf_engine,
    validate_llm_settings,
)


@pytest.fixture(autouse=True)
def _clean_llm_env(monkeypatch):
    """Гермет: Settings(_env_file=None) отсекает файл, но НЕ os.environ, куда
    pytest уже загрузил .env.test (env_files в pyproject) — чистим LLM-семейства."""
    for var in ("LLM_PROVIDER", "OPENROUTER_MODEL", "OPENROUTER_PDF_ENGINE",
                "OPENROUTER_MAX_TOKENS", "OPENROUTER_BASE_URL", "OPENROUTER_API_KEY",
                "GATEWAY_BASE_URL", "GATEWAY_MODEL",
                "AI_MODEL", "AI_MAX_TOKENS", "PDF_ENGINE"):
        monkeypatch.delenv(var, raising=False)


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
    assert resolved_openrouter_model(_mk(AI_MODEL="   ")) == "anthropic/claude-sonnet-4.6"


def test_pdf_engine_alias_priority():
    """OPENROUTER_PDF_ENGINE → PDF_ENGINE → 'mistral-ocr' (код-дефолт, §1)."""
    assert resolved_openrouter_pdf_engine(_mk(OPENROUTER_PDF_ENGINE="native")) == "native"
    assert resolved_openrouter_pdf_engine(_mk(PDF_ENGINE="native")) == "native"
    assert resolved_openrouter_pdf_engine(_mk()) == "mistral-ocr"
    assert resolved_openrouter_pdf_engine(_mk(OPENROUTER_PDF_ENGINE="   ")) == "mistral-ocr"
    assert resolved_openrouter_pdf_engine(_mk(PDF_ENGINE="   ")) == "mistral-ocr"


def test_base_url_resolver():
    """OPENROUTER_BASE_URL: пробельная строка = отсутствие → дефолт (guard §1)."""
    from config import resolved_openrouter_base_url
    assert resolved_openrouter_base_url(_mk()) == "https://openrouter.ai/api/v1"
    assert resolved_openrouter_base_url(_mk(OPENROUTER_BASE_URL="   ")) == "https://openrouter.ai/api/v1"
    assert resolved_openrouter_base_url(_mk(OPENROUTER_BASE_URL="http://x/api/v1")) == "http://x/api/v1"


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
    """Пустая/пробельная строка base URL = отсутствие значения (guard §1)."""
    validate_llm_settings(_mk(OPENROUTER_BASE_URL=""))   # openrouter лечится дефолтом
    with pytest.raises(RuntimeError, match="GATEWAY_BASE_URL"):
        validate_llm_settings(_mk(LLM_PROVIDER="gateway",
                                  GATEWAY_BASE_URL="   ", GATEWAY_MODEL="m"))


def test_parse_max_tokens_neutral_resolver():
    """Нейтральный резолвер: openrouter-цепочка; gateway до спайка — понятная ошибка."""
    from config import resolved_llm_parse_max_tokens
    assert resolved_llm_parse_max_tokens(_mk(AI_MAX_TOKENS=2000)) == 2000
    with pytest.raises(RuntimeError, match="спайк"):
        resolved_llm_parse_max_tokens(_mk(LLM_PROVIDER="gateway",
                                          GATEWAY_BASE_URL="http://gw", GATEWAY_MODEL="m"))
