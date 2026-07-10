"""Inline keyboard menu for quick, tappable navigation.

Gives users tappable buttons instead of remembering slash commands.
Shown by /menu and attached to /start.
"""

from __future__ import annotations

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

from handlers.commands import ABOUT_MESSAGE, HELP_MESSAGE, render_history
from services.storage import get_recent_messages
from utils.telegram_send import send_formatted_message

MENU_PROMPT = "What would you like to do? 👇"

# Persistent bottom button bar labels (also matched by the router below).
BTN_JOBS = "💼 Jobs"
BTN_IMAGE = "🎨 Image"
BTN_WEATHER = "🌦 Weather"
BTN_MENU = "☰ Menu"


def persistent_keyboard() -> ReplyKeyboardMarkup:
    """Always-visible button bar at the bottom of the chat."""
    return ReplyKeyboardMarkup(
        [[BTN_JOBS, BTN_IMAGE], [BTN_WEATHER, BTN_MENU]],
        resize_keyboard=True,
        is_persistent=True,
    )


async def button_bar_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle taps on the persistent button bar (the Jobs button is routed by
    the jobs conversation's entry point instead)."""
    text = update.message.text
    if text == BTN_MENU:
        await update.message.reply_text(MENU_PROMPT, reply_markup=main_menu_keyboard())
    elif text == BTN_IMAGE:
        await update.message.reply_text("🎨 Send /image followed by a description, e.g. `/image a sunset over Kuala Lumpur`", parse_mode="Markdown")
    elif text == BTN_WEATHER:
        await update.message.reply_text("🌦 Send /weather followed by a city, e.g. `/weather Kuala Lumpur`", parse_mode="Markdown")


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💼 Jobs", callback_data="menu:jobs"),
             InlineKeyboardButton("🎨 Image", callback_data="menu:image")],
            [InlineKeyboardButton("🌦 Weather", callback_data="menu:weather"),
             InlineKeyboardButton("📜 History", callback_data="menu:history")],
            [InlineKeyboardButton("❓ Help", callback_data="menu:help"),
             InlineKeyboardButton("ℹ️ About", callback_data="menu:about")],
        ]
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(MENU_PROMPT, reply_markup=main_menu_keyboard())


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # stop the button's loading spinner
    action = (query.data or "").split(":", 1)[-1]
    bot = context.bot
    chat_id = query.message.chat_id

    if action == "help":
        await bot.send_message(chat_id, HELP_MESSAGE, parse_mode="Markdown")
    elif action == "about":
        await bot.send_message(chat_id, ABOUT_MESSAGE, parse_mode="Markdown")
    elif action == "history":
        messages = await get_recent_messages(chat_id)
        if messages:
            await send_formatted_message(bot, chat_id, render_history(messages))
        else:
            await bot.send_message(chat_id, "No conversation history yet. Send me a message to get started!")
    elif action == "jobs":
        await bot.send_message(chat_id, "💼 Send /jobs to start a guided job search — I'll ask for the role, location, and salary.")
    elif action == "image":
        await bot.send_message(chat_id, "🎨 Send /image followed by a description, e.g. `/image a sunset over Kuala Lumpur`", parse_mode="Markdown")
    elif action == "weather":
        await bot.send_message(chat_id, "🌦 Send /weather followed by a city, e.g. `/weather Kuala Lumpur`", parse_mode="Markdown")
