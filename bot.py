"""Entry point for the AI Nonymauz Telegram bot (long polling)."""

from __future__ import annotations

import logging

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import settings
from handlers.commands import about, help_command, reset, start
from handlers.errors import handle_error
from handlers.jobs import jobs, myjobs, unwatchjob, watchjob
from handlers.messages import handle_text
from services.storage import init_db

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=settings.log_level,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def _post_init(application: Application) -> None:
    await init_db()


def build_application() -> Application:
    application = Application.builder().token(settings.telegram_bot_token).post_init(_post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("jobs", jobs))
    application.add_handler(CommandHandler("watchjob", watchjob))
    application.add_handler(CommandHandler("unwatchjob", unwatchjob))
    application.add_handler(CommandHandler("myjobs", myjobs))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.add_error_handler(handle_error)

    return application


def main() -> None:
    application = build_application()

    if settings.webhook_url:
        import uvicorn

        from server import build_server

        logger.info("Starting AI Nonymauz bot (webhook mode) on port %s", settings.port)
        app = build_server(application)
        uvicorn.run(app, host="0.0.0.0", port=settings.port, log_level=settings.log_level.lower())
    else:
        logger.info("Starting AI Nonymauz bot (long polling)")
        application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
