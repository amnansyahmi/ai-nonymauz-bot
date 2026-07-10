"""Entry point for the AI Nonymauz Telegram bot (long polling)."""

from __future__ import annotations

import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import settings
from handlers.bot_commands import BOT_COMMANDS
from handlers.commands import about, help_command, history, reset, start, summarize
from handlers.diag import diag
from handlers.errors import handle_error
from handlers.jobs import (
    build_jobs_conversation,
    jobs_action_callback,
    myjobs,
    unwatchjob,
    watch_action_callback,
    watchjob,
)
from handlers.media import handle_photo, handle_voice, image, media_action_callback, weather
from handlers.menu import (
    BTN_IMAGE,
    BTN_MENU,
    BTN_WEATHER,
    button_bar_router,
    menu_callback,
    menu_command,
)
from handlers.messages import handle_text
from services.storage import init_db

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=settings.log_level,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def on_startup(application: Application) -> None:
    """Shared startup: runs for both polling (via post_init) and webhook (via
    the server lifespan). Idempotent."""
    await init_db()
    await application.bot.set_my_commands(BOT_COMMANDS)
    from services.jobs_api import jsearch

    logger.info(
        "Config: cloud=%s | JSearch jobs API=%s",
        "set" if settings.ai_nonymauz_cloud_url else "UNSET",
        "enabled" if jsearch.is_enabled() else "disabled (JSEARCH_API_KEY unset)",
    )


async def on_shutdown(application: Application) -> None:
    """Close the shared HTTP client. Runs for polling (post_shutdown) and
    webhook (server lifespan)."""
    from services.cloud_client import ai_nonymauz_cloud

    await ai_nonymauz_cloud.aclose()


def build_application() -> Application:
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(build_jobs_conversation())
    application.add_handler(CommandHandler("watchjob", watchjob))
    application.add_handler(CommandHandler("unwatchjob", unwatchjob))
    application.add_handler(CommandHandler("myjobs", myjobs))
    application.add_handler(CommandHandler("image", image))
    application.add_handler(CommandHandler("weather", weather))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("summarize", summarize))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("diag", diag))  # not in the public menu
    application.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:"))
    application.add_handler(CallbackQueryHandler(jobs_action_callback, pattern=r"^act:jobs_"))
    application.add_handler(CallbackQueryHandler(media_action_callback, pattern=r"^act:(image|weather)_"))
    application.add_handler(CallbackQueryHandler(watch_action_callback, pattern=r"^watch:"))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    # Persistent button-bar taps (Jobs is routed by the jobs conversation entry).
    application.add_handler(MessageHandler(filters.Text([BTN_IMAGE, BTN_WEATHER, BTN_MENU]), button_bar_router))
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
        application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
