"""Robust reply sending for Telegram.

Telegram rejects a message that exceeds 4096 characters or contains malformed
HTML — and on rejection the user gets *nothing*. This module splits long
replies on line boundaries (our formatter keeps every HTML tag balanced within
a single line, so line-splitting never breaks a tag) and falls back to plain
text if an HTML send is rejected, so a formatting glitch never eats the answer.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re

from telegram import Bot, Message
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from utils.formatting import markdown_to_telegram_html

logger = logging.getLogger(__name__)

# Telegram's hard limit is 4096; leave headroom.
MAX_MESSAGE_LEN = 3900
_TAG_RE = re.compile(r"<[^>]+>")


def chunk_text(text: str, limit: int = MAX_MESSAGE_LEN) -> list[str]:
    """Split text into <=limit pieces, preferring line boundaries."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        # A single line longer than the limit must be hard-split.
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]

        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate

    if current:
        chunks.append(current)
    return chunks


async def _send_chunks(send_html, send_plain, raw_text: str, reply_markup=None) -> None:
    html = markdown_to_telegram_html(raw_text)
    chunks = chunk_text(html)
    for i, chunk in enumerate(chunks):
        # Attach any buttons only to the final chunk.
        markup = reply_markup if i == len(chunks) - 1 else None
        try:
            await send_html(chunk, markup)
        except BadRequest:
            # Malformed HTML for this chunk — strip tags and send as plain text
            # so the user still gets the content.
            logger.warning("HTML send rejected; falling back to plain text")
            await send_plain(_TAG_RE.sub("", chunk), markup)


async def send_formatted_reply(message: Message, raw_text: str, reply_markup=None) -> None:
    """Reply to a message, splitting and degrading to plain text on HTML errors."""
    await _send_chunks(
        lambda c, m: message.reply_text(c, parse_mode="HTML", reply_markup=m),
        lambda c, m: message.reply_text(c, reply_markup=m),
        raw_text,
        reply_markup,
    )


async def send_formatted_message(bot: Bot, chat_id: int, raw_text: str, reply_markup=None) -> None:
    """Send to a chat by id (for out-of-band pushes), same splitting/fallback."""
    await _send_chunks(
        lambda c, m: bot.send_message(chat_id=chat_id, text=c, parse_mode="HTML", reply_markup=m),
        lambda c, m: bot.send_message(chat_id=chat_id, text=c, reply_markup=m),
        raw_text,
        reply_markup,
    )


@contextlib.asynccontextmanager
async def typing_action(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Keep the 'typing…' indicator alive for slow (30-60s) backend calls.
    Telegram's action lasts ~5s, so re-send it periodically until done."""

    async def _loop() -> None:
        try:
            while True:
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
