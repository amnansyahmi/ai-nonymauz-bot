"""Media/tool commands: /image, /weather."""

from __future__ import annotations

import io
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from services.cloud_client import CloudClientError, ai_nonymauz_cloud
from services.storage import add_message
from utils.rate_limit import message_limiter
from utils.telegram_send import send_formatted_reply, typing_action

logger = logging.getLogger(__name__)

_IMAGE_ACTIONS = InlineKeyboardMarkup([[InlineKeyboardButton("🎨 Another", callback_data="act:image_again")]])
_WEATHER_ACTIONS = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="act:weather_refresh")]])


async def _generate_image(message: Message, context: ContextTypes.DEFAULT_TYPE, prompt: str) -> None:
    chat_id = message.chat_id
    if not message_limiter.allow(chat_id):
        await message.reply_text("⏳ You're generating a bit fast. Please wait a few seconds and try again.")
        return
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
        image_bytes, _mime = await ai_nonymauz_cloud.generate_image(prompt)
    except CloudClientError as exc:
        logger.exception("Image generation failed for chat %s", chat_id)
        await message.reply_text(f"⚠️ {exc}")
        return
    context.user_data["last_image_prompt"] = prompt
    await message.reply_photo(photo=io.BytesIO(image_bytes), caption=prompt, reply_markup=_IMAGE_ACTIONS)


async def _fetch_weather(message: Message, context: ContextTypes.DEFAULT_TYPE, location: str) -> None:
    chat_id = message.chat_id
    if not message_limiter.allow(chat_id):
        await message.reply_text("⏳ Please wait a few seconds and try again.")
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
        await message.reply_text("⚠️ Sorry, I couldn't get the weather right now. Please try again shortly.")
        return
    context.user_data["last_weather_location"] = location
    await send_formatted_reply(message, reply, reply_markup=_WEATHER_ACTIONS)


async def image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = " ".join(context.args).strip() if context.args else ""
    if not prompt:
        await update.message.reply_text("Usage: /image <description>\nExample: /image a cat astronaut on the moon")
        return
    await _generate_image(update.message, context, prompt)


async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    location = " ".join(context.args).strip() if context.args else ""
    await _fetch_weather(update.message, context, location)


async def media_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 🎨 Another / 🔄 Refresh buttons under image and weather replies."""
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]
    if action == "image_again":
        prompt = context.user_data.get("last_image_prompt")
        if prompt:
            await _generate_image(query.message, context, prompt)
        else:
            await query.message.reply_text("That prompt has expired — use /image again.")
    elif action == "weather_refresh":
        location = context.user_data.get("last_weather_location", "")
        await _fetch_weather(query.message, context, location)


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
