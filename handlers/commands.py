"""Command handlers: /start, /help, /about, /reset."""

from __future__ import annotations

import logging
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from services.cloud_client import CloudClientError, ai_nonymauz_cloud
from services.storage import clear_history, get_recent_messages
from utils.rate_limit import message_limiter
from utils.telegram_send import send_formatted_reply, typing_action

logger = logging.getLogger(__name__)

START_MESSAGE = (
    "👋 Hi, I'm *AI Nonymauz* — your AI assistant on Telegram.\n\n"
    "Here's what I can do:\n"
    "💬 Chat — just send a message (I remember our conversation)\n"
    "🖼 Describe photos — send me a picture\n"
    "🎨 /image — generate images from text\n"
    "🌦 /weather — live weather\n"
    "💼 /jobs — guided job search with real listings\n\n"
    "Type /help for the full command list."
)

HELP_MESSAGE = (
    "*What I can do*\n\n"
    "💬 *Chat* — send any message; I keep track of our conversation.\n"
    "🖼 *Photos* — send a picture (with an optional question) and I'll describe it.\n\n"
    "*Commands*\n\n"
    "🤖 _AI & chat_\n"
    "/summarize - Summarize our conversation\n"
    "/reset - Forget our conversation and start fresh\n\n"
    "🎨 _Create & look up_\n"
    "/image <description> - Generate an image\n"
    "/weather <city> - Get the current weather\n\n"
    "💼 _Jobs_\n"
    "/jobs - Guided job search (title, location, salary)\n"
    "/watchjob <role> - Save a search; I'll alert you on new results\n"
    "/myjobs - Run or remove your saved watches (with buttons)\n\n"
    "ℹ️ _Other_\n"
    "/menu - Quick-action buttons\n"
    "/about - About AI Nonymauz\n"
    "/help - Show this message"
)

ABOUT_MESSAGE = (
    "*AI Nonymauz* 🤖\n\n"
    "Your AI assistant on Telegram — chat, image generation, vision, live "
    "weather, and real job listings, all in one place.\n\n"
    "Powered by the ai-nonymauz-cloud AI backend. The bot itself just connects "
    "you to it, so new capabilities can be added without changing how you chat.\n\n"
    "Type /help to see everything I can do."
)

_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo.jpg"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("User %s issued /start", update.effective_user.id if update.effective_user else "unknown")
    from handlers.menu import persistent_keyboard  # lazy import avoids a cycle

    keyboard = persistent_keyboard()
    # Send the logo with the welcome as a caption for a branded first impression;
    # fall back to a plain text welcome if the asset is missing.
    if _LOGO_PATH.exists():
        with _LOGO_PATH.open("rb") as logo:
            await update.message.reply_photo(
                photo=logo, caption=START_MESSAGE, parse_mode="Markdown", reply_markup=keyboard
            )
    else:
        await update.message.reply_text(START_MESSAGE, parse_mode="Markdown", reply_markup=keyboard)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("User %s issued /help", update.effective_user.id if update.effective_user else "unknown")
    await update.message.reply_text(HELP_MESSAGE, parse_mode="Markdown")


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("User %s issued /about", update.effective_user.id if update.effective_user else "unknown")
    await update.message.reply_text(ABOUT_MESSAGE, parse_mode="Markdown")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("User %s issued /reset", update.effective_user.id if update.effective_user else "unknown")
    context.user_data.clear()
    cleared = await clear_history(update.effective_chat.id)
    if cleared:
        await update.message.reply_text(
            f"🔄 Done — I've cleared our conversation ({cleared} message"
            f"{'s' if cleared != 1 else ''}) and forgotten the earlier context. Starting fresh!"
        )
    else:
        await update.message.reply_text("✨ Nothing to reset — we haven't talked yet. Send me anything to begin!")


def render_history(messages: list[dict[str, str]]) -> str:
    lines = []
    for m in messages:
        who = "🧑 You" if m["role"] == "user" else "🤖 AI Nonymauz"
        text = m["content"]
        if len(text) > 200:
            text = text[:200] + "…"
        lines.append(f"{who}: {text}")
    return "\n\n".join(lines)


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    messages = await get_recent_messages(chat_id)
    if not messages:
        await update.message.reply_text("No conversation history yet. Send me a message to get started!")
        return

    await send_formatted_reply(update.message, render_history(messages))


async def summarize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    messages = await get_recent_messages(chat_id)
    if not messages:
        await update.message.reply_text("Nothing to summarize yet — we haven't talked about anything.")
        return

    if not message_limiter.allow(chat_id):
        await update.message.reply_text("⏳ Please wait a few seconds and try again.")
        return

    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    prompt = (
        "Summarize the following conversation concisely in a few bullet points, "
        "in the same language it's mostly written in:\n\n" + transcript
    )

    try:
        async with typing_action(context, chat_id):
            reply = await ai_nonymauz_cloud.send_message(session_id=chat_id, text=prompt)
    except CloudClientError:
        logger.exception("Summarize failed for chat %s", chat_id)
        await update.message.reply_text("⚠️ Sorry, I couldn't summarize right now. Please try again shortly.")
        return

    await send_formatted_reply(update.message, reply)
