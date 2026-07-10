"""Handler for plain text messages."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from services.cloud_client import CloudClientError, ai_nonymauz_cloud
from services.storage import add_message, get_recent_messages
from utils.telegram_send import send_formatted_reply, typing_action

logger = logging.getLogger(__name__)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None or not message.text:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else "unknown"
    logger.info("Received message from user %s: %s", user_id, message.text)

    history = await get_recent_messages(chat_id)
    conversation = history + [{"role": "user", "content": message.text}]

    try:
        async with typing_action(context, chat_id):
            reply = await ai_nonymauz_cloud.send_conversation(session_id=chat_id, messages=conversation)
    except CloudClientError:
        logger.exception("ai-nonymauz-cloud request failed for user %s", user_id)
        await add_message(chat_id, "user", message.text)
        await message.reply_text("⚠️ Sorry, I couldn't reach the AI service right now. Please try again shortly.")
        return

    await add_message(chat_id, "user", message.text)
    await add_message(chat_id, "assistant", reply)

    await send_formatted_reply(message, reply)
