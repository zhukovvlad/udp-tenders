"""Централизованная конфигурация через pydantic-settings.

Основной способ читать переменные окружения в коде приложения — через объект
settings, а не через os.getenv() напрямую. Для инфраструктурных модулей
(alembic/env.py, tooling-скрипты) допустимы исключения.
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # JWT / безопасность
    SECRET_KEY: str = Field(min_length=32)  # обязательное поле — при отсутствии в .env запуск упадёт
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # Куки
    COOKIE_SECURE: bool = False  # True в проде (HTTPS)
    COOKIE_DOMAIN: str | None = None

    # Количество доверенных reverse-proxy в цепочке (0 = прямое соединение; X-Forwarded-For игнорируется)
    TRUSTED_PROXIES: int = 0

    # CORS — wildcard "*" несовместим с credentials=True в браузере
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    # База данных
    DATABASE_URL: str = "postgresql+psycopg://udp_app:CHANGE_ME@localhost:5432/udp"

    # MinIO / S3
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "invoices"

    # OpenRouter
    OPENROUTER_API_KEY: str = ""
    AI_MODEL: str = "anthropic/claude-sonnet-4.6"
    AI_MAX_TOKENS: int = 64000  # верхний предел вывода claude-sonnet-4.6 (~64K); prompt от mistral-ocr на 8-страничных СФ съедает ~24K, оставляя на ответ всё что есть
    CONFIDENCE_THRESHOLD: float = 0.7
    PDF_ENGINE: str = "mistral-ocr"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Логирование
    LOG_LEVEL: str = "INFO"


settings = Settings()
