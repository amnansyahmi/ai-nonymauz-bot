"""Media/tool commands: /image, /weather."""

from __future__ import annotations

import io
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from services.cloud_client import CloudClientError, ai_nonymauz_cloud
from services.storage import add_message
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


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None or not message.photo:
        return

    chat_id = update.effective_chat.id
    if not message_limiter.allow(chat_id):
        await message.reply_text("⏳ Please wait a few seconds and try again.")
        return

    caption = (message.caption or "").strip()
    prompt = caption or "What's in this image? Describe it briefly."

    # photo is a list of sizes ascending; the last is the highest resolution.
    photo_file = await context.bot.get_file(message.photo[-1].file_id)
    image_bytes = bytes(await photo_file.download_as_bytearray())

    try:
        async with typing_action(context, chat_id):
            reply = await ai_nonymauz_cloud.describe_image(image_bytes, "image/jpeg", prompt)
    except CloudClientError:
        logger.exception("Vision request failed for chat %s", chat_id)
        await message.reply_text("⚠️ Sorry, I couldn't analyze that image right now. Please try again shortly.")
        return

    # Record a text trace so later text follow-ups have some context.
    await add_message(chat_id, "user", f"[sent an image] {caption}".strip())
    await add_message(chat_id, "assistant", reply)

    await send_formatted_reply(message, reply)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎙️ I can't understand voice messages yet — ai-nonymauz-cloud doesn't have "
        "speech-to-text. Please type your message, or send a photo and I'll describe it."
    )
