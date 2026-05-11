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

    response = client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "anthropic/claude-sonnet-4.6"
    assert body["confidence_threshold"] == 0.7
    assert "api_key_set" in body


def test_update_settings_writes_to_env(client, monkeypatch, tmp_path):
    """update_settings пишет в .env. Подменяем путь на временный файл."""
    fake_env = tmp_path / ".env"
    fake_env.write_text("")
    monkeypatch.setattr("routers.settings.ENV_PATH", str(fake_env))

    response = client.put(
        "/api/settings",
        json={"model": "test-model", "confidence_threshold": 0.85},
    )
    assert response.status_code == 200
    content = fake_env.read_text()
    assert "test-model" in content
    assert "0.85" in content
