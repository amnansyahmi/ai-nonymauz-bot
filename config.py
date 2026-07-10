"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    ai_nonymauz_cloud_url: str | None
    ai_nonymauz_cloud_api_key: str | None
    log_level: str


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        ai_nonymauz_cloud_url=os.getenv("AI_NONYMAUZ_CLOUD_URL"),
        ai_nonymauz_cloud_api_key=os.getenv("AI_NONYMAUZ_CLOUD_API_KEY"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


settings = load_settings()
