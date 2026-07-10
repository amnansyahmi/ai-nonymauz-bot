"""Handler for plain text messages."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from services.cloud_client import CloudClientError, ai_nonymauz_cloud

logger = logging.getLogger(__name__)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None or not message.text:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else "unknown"
    logger.info("Received message from user %s: %s", user_id, message.text)

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        reply = await ai_nonymauz_cloud.send_message(session_id=chat_id, text=message.text)
    except CloudClientError:
        logger.exception("ai-nonymauz-cloud request failed for user %s", user_id)
        reply = "⚠️ Sorry, I couldn't reach the AI service right now. Please try again shortly."

    await message.reply_text(reply)
