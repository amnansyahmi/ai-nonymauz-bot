"""Command handlers: /start, /help, /about, /reset."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from services.cloud_client import CloudClientError, ai_nonymauz_cloud
from services.storage import clear_history, get_recent_messages
from utils.rate_limit import message_limiter
from utils.telegram_send import send_formatted_reply, typing_action

logger = logging.getLogger(__name__)

START_MESSAGE = (
    "👋 Hi, I'm *AI Nonymauz* — your AI assistant on Telegram.\n\n"
    "Send me a message and I'll get back to you.\n"
    "Type /help to see what I can do."
)

HELP_MESSAGE = (
    "*Available commands*\n\n"
    "/start - Start the bot\n"
    "/help - View available commands\n"
    "/about - About AI Nonymauz\n"
    "/reset - Reset the conversation\n"
    "/jobs - Guided job search (title, location, salary)\n"
    "/watchjob <role> - Save a job search to check later\n"
    "/myjobs - List your saved job watches\n"
    "/unwatchjob <id> - Remove a saved job watch\n"
    "/image <description> - Generate an image\n"
    "/weather <city> - Get the current weather\n"
    "/history - Show recent conversation history\n"
    "/summarize - Summarize the conversation\n\n"
    "You can also send me a normal text message, or a photo to describe."
)

ABOUT_MESSAGE = (
    "*AI Nonymauz*\n\n"
    "A Telegram frontend for the ai-nonymauz-cloud API. "
    "This bot forwards your messages to ai-nonymauz-cloud and returns the AI's response."
)

RESET_MESSAGE = "🔄 Conversation reset. Let's start fresh!"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("User %s issued /start", update.effective_user.id if update.effective_user else "unknown")
    await update.message.reply_text(START_MESSAGE, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("User %s issued /help", update.effective_user.id if update.effective_user else "unknown")
    await update.message.reply_text(HELP_MESSAGE, parse_mode="Markdown")


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("User %s issued /about", update.effective_user.id if update.effective_user else "unknown")
    await update.message.reply_text(ABOUT_MESSAGE, parse_mode="Markdown")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("User %s issued /reset", update.effective_user.id if update.effective_user else "unknown")
    context.user_data.clear()
    await clear_history(update.effective_chat.id)
    await update.message.reply_text(RESET_MESSAGE)


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    messages = await get_recent_messages(chat_id)
    if not messages:
        await update.message.reply_text("No conversation history yet. Send me a message to get started!")
        return

    lines = []
    for m in messages:
        who = "🧑 You" if m["role"] == "user" else "🤖 AI Nonymauz"
        text = m["content"]
        if len(text) > 200:
            text = text[:200] + "…"
        lines.append(f"{who}: {text}")

    await send_formatted_reply(update.message, "\n\n".join(lines))


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
