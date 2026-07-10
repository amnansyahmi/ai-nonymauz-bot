"""Command handlers: /start, /help, /about, /reset."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from services.storage import clear_history

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
    "/jobs <role> - Search for job vacancies now\n"
    "/watchjob <role> - Save a job search to check later\n"
    "/myjobs - List your saved job watches\n"
    "/unwatchjob <id> - Remove a saved job watch\n"
    "/image <description> - Generate an image\n"
    "/weather <city> - Get the current weather\n\n"
    "You can also just send me a normal text message."
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
