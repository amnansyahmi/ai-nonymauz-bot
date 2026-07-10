"""FastAPI server for webhook mode.

Runs our own web server (instead of python-telegram-bot's built-in webhook
server) so we can expose extra routes alongside the Telegram endpoint —
specifically the cron-triggered /tasks/run-job-watches endpoint that powers
job-watch notifications. This is the PTB "custom webhook" integration pattern:
the Application runs without its own Updater, and we feed it updates parsed
from incoming HTTP requests.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request, Response
from telegram import Update
from telegram.ext import Application

from config import settings
from services.job_notifications import make_notifier, search_for_watch
from services.jobs_runner import run_job_watches
from services.storage import init_db

logger = logging.getLogger(__name__)


def build_server(application: Application) -> FastAPI:
    webhook_path = f"/{settings.telegram_bot_token}"
    webhook_url = f"{settings.webhook_url.rstrip('/')}{webhook_path}"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await init_db()
        await application.initialize()
        await application.start()
        await application.bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret_token,
            allowed_updates=["message"],
        )
        logger.info("Webhook registered at %s", webhook_url)
        try:
            yield
        finally:
            await application.stop()
            await application.shutdown()

    app = FastAPI(lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(webhook_path)
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> Response:
        if settings.webhook_secret_token and x_telegram_bot_api_secret_token != settings.webhook_secret_token:
            raise HTTPException(status_code=403, detail="invalid secret token")
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return Response(status_code=200)

    @app.post("/tasks/run-job-watches")
    async def run_watches(x_cron_secret: str | None = Header(default=None)) -> dict:
        if not settings.cron_secret:
            raise HTTPException(status_code=503, detail="cron secret not configured")
        if x_cron_secret != settings.cron_secret:
            raise HTTPException(status_code=403, detail="invalid cron secret")
        summary = await run_job_watches(
            search=search_for_watch,
            notify=make_notifier(application.bot),
        )
        return summary

    return app
