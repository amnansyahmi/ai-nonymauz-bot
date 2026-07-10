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
from handlers.messages import handle_text

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=settings.log_level,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def build_application() -> Application:
    application = Application.builder().token(settings.telegram_bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.add_error_handler(handle_error)

    return application


def main() -> None:
    application = build_application()

    if settings.webhook_url:
        # The bot token doubles as a secret URL path so the webhook endpoint
        # isn't guessable without it.
        url_path = settings.telegram_bot_token
        webhook_url = f"{settings.webhook_url.rstrip('/')}/{url_path}"
        logger.info("Starting AI Nonymauz bot (webhook mode) on port %s", settings.port)
        application.run_webhook(
            listen="0.0.0.0",
            port=settings.port,
            url_path=url_path,
            webhook_url=webhook_url,
            secret_token=settings.webhook_secret_token,
            allowed_updates=["message"],
        )
    else:
        logger.info("Starting AI Nonymauz bot (long polling)")
        application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
