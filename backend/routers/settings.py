import os

from dotenv import load_dotenv, set_key
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")


def _ensure_env():
    if not os.path.exists(ENV_PATH):
        with open(ENV_PATH, "w") as f:
            f.write("")
    load_dotenv(ENV_PATH, override=True)


class SettingsUpdate(BaseModel):
    api_key: str | None = None
    model: str | None = None
    confidence_threshold: float | None = None


@router.get("")
def get_settings():
    _ensure_env()
    return {
        "api_key_set": bool(os.getenv("OPENROUTER_API_KEY", "").startswith("sk-")),
        "model": os.getenv("AI_MODEL", "anthropic/claude-sonnet-4.6"),
        "confidence_threshold": float(os.getenv("CONFIDENCE_THRESHOLD", "0.7")),
    }


@router.put("")
def update_settings(data: SettingsUpdate):
    _ensure_env()
    if data.api_key is not None:
        set_key(ENV_PATH, "OPENROUTER_API_KEY", data.api_key)
        os.environ["OPENROUTER_API_KEY"] = data.api_key
    if data.model is not None:
        set_key(ENV_PATH, "AI_MODEL", data.model)
        os.environ["AI_MODEL"] = data.model
    if data.confidence_threshold is not None:
        set_key(ENV_PATH, "CONFIDENCE_THRESHOLD", str(data.confidence_threshold))
        os.environ["CONFIDENCE_THRESHOLD"] = str(data.confidence_threshold)
    return {"message": "Настройки сохранены"}
