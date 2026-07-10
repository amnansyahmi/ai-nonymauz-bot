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
    port: int
    webhook_url: str | None
    webhook_secret_token: str | None
    cron_secret: str | None
    jsearch_api_key: str | None


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_settings() -> Settings:
    # WEBHOOK_URL can be set explicitly, or picked up automatically from
    # RENDER_EXTERNAL_URL, which Render injects for every web service.
    # Leaving both unset (e.g. local development) falls back to long polling.
    webhook_url = os.getenv("WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL")

    return Settings(
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        ai_nonymauz_cloud_url=os.getenv("AI_NONYMAUZ_CLOUD_URL"),
        ai_nonymauz_cloud_api_key=os.getenv("AI_NONYMAUZ_CLOUD_API_KEY"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        port=int(os.getenv("PORT", "8080")),
        webhook_url=webhook_url,
        webhook_secret_token=os.getenv("WEBHOOK_SECRET_TOKEN"),
        cron_secret=os.getenv("CRON_SECRET"),
        jsearch_api_key=os.getenv("JSEARCH_API_KEY") or os.getenv("RAPIDAPI_KEY"),
    )


settings = load_settings()
