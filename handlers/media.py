"""Media/tool commands: /image, /weather."""

from __future__ import annotations

import io
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from services.cloud_client import CloudClientError, ai_nonymauz_cloud
from utils.rate_limit import message_limiter
from utils.telegram_send import send_formatted_reply, typing_action

logger = logging.getLogger(__name__)


async def image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = " ".join(context.args).strip() if context.args else ""
    if not prompt:
        await update.message.reply_text("Usage: /image <description>\nExample: /image a cat astronaut on the moon")
        return

    chat_id = update.effective_chat.id
    if not message_limiter.allow(chat_id):
        await update.message.reply_text("⏳ You're generating a bit fast. Please wait a few seconds and try again.")
        return

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
        image_bytes, _mime = await ai_nonymauz_cloud.generate_image(prompt)
    except CloudClientError as exc:
        logger.exception("Image generation failed for chat %s", chat_id)
        await update.message.reply_text(f"⚠️ {exc}")
        return

    await update.message.reply_photo(photo=io.BytesIO(image_bytes), caption=prompt)


async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    location = " ".join(context.args).strip() if context.args else ""
    chat_id = update.effective_chat.id
    if not message_limiter.allow(chat_id):
        await update.message.reply_text("⏳ Please wait a few seconds and try again.")
        return

    question = (
        f"What's the current weather in {location}?" if location
        else "What's the current weather where I am?"
    )

    try:
        async with typing_action(context, chat_id):
            reply = await ai_nonymauz_cloud.send_message(session_id=chat_id, text=question)
    except CloudClientError:
        logger.exception("Weather lookup failed for chat %s", chat_id)
        await update.message.reply_text("⚠️ Sorry, I couldn't get the weather right now. Please try again shortly.")
        return

    await send_formatted_reply(update.message, reply)
