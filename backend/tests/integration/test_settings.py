import os


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
