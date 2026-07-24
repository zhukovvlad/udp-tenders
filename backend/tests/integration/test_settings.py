import os

import pytest


@pytest.fixture(autouse=True)
def _tmp_env_path(tmp_path, monkeypatch):
    """Подменить ENV_PATH на временный .env: PUT-тесты не трогают backend/.env."""
    import routers.settings as settings_router
    env_file = tmp_path / ".env"
    env_file.write_text("")
    monkeypatch.setattr(settings_router, "ENV_PATH", str(env_file))


def test_get_settings(client, monkeypatch, tmp_path):
    """Smoke — settings возвращает текущие значения env."""
    # ВАЖНО: settings._ensure_env() делает load_dotenv(ENV_PATH, override=True),
    # что перезапишет наши monkeypatch.setenv значениями из реального .env.
    # Подменяем ENV_PATH на пустой временный файл, чтобы load_dotenv ничего
    # не загрузил, и наши setenv остались видны для os.getenv в роутере.
    fake_env = tmp_path / ".env"
    fake_env.write_text("")
    monkeypatch.setattr("routers.settings.ENV_PATH", str(fake_env))

    monkeypatch.setenv("AI_MODEL", "anthropic/claude-sonnet-4.6")
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "0.7")
    # OPENROUTER_API_KEY в .env.test = "mock-key-not-used" (не начинается на "sk-"),
    # поэтому api_key_set должен быть False.
    monkeypatch.setenv("OPENROUTER_API_KEY", "mock-key-not-used")

    response = client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "anthropic/claude-sonnet-4.6"
    assert body["confidence_threshold"] == 0.7
    assert body["api_key_set"] is False


def test_update_settings_writes_to_env(client, monkeypatch, tmp_path):
    """update_settings пишет в .env. Подменяем путь на временный файл.

    Роутер также пишет в os.environ (помимо файла) — monkeypatch.setenv до PUT
    гарантирует, что эти изменения откатятся pytest'ом после теста и не
    утекут в последующие тесты процесса.
    """
    fake_env = tmp_path / ".env"
    fake_env.write_text("")
    monkeypatch.setattr("routers.settings.ENV_PATH", str(fake_env))
    # Регистрируем в monkeypatch текущие значения, чтобы pytest откатил
    # перезапись os.environ внутри update_settings после завершения теста.
    monkeypatch.setenv("AI_MODEL", os.environ.get("AI_MODEL", ""))
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", os.environ.get("CONFIDENCE_THRESHOLD", ""))

    response = client.put(
        "/api/settings",
        json={"model": "test-model", "confidence_threshold": 0.85},
    )
    assert response.status_code == 200
    content = fake_env.read_text()
    assert "test-model" in content
    assert "0.85" in content


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


def test_put_model_wins_over_legacy_alias(client, monkeypatch):
    """PUT пишет namespaced OPENROUTER_MODEL: легаси AI_MODEL в env не перекрывает.

    Регресс на приоритет алиасов: если бы PUT писал AI_MODEL, заданный в env
    OPENROUTER_MODEL победил бы по цепочке §1 и PUT молча не действовал бы.
    """
    import llm
    monkeypatch.setenv("AI_MODEL", "legacy/model")
    monkeypatch.setenv("OPENROUTER_MODEL", "before/model")
    client.put("/api/settings", json={"model": "after/model"})
    assert llm.get_provider().model == "after/model"
    assert client.get("/api/settings").json()["model"] == "after/model"
