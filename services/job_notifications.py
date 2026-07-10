"""Production search/notify wiring for the scheduled job-watch runner.

Kept separate from jobs_runner.py so the runner core stays free of Telegram
and cloud-client imports and remains easily unit-testable.
"""

from __future__ import annotations

from telegram import Bot

from handlers.jobs import job_results_text
from services.storage import JobWatch
from utils.telegram_send import send_formatted_message


async def search_for_watch(watch: JobWatch) -> str:
    return await job_results_text(watch.chat_id, watch.query)


def make_notifier(bot: Bot):
    async def notify(chat_id: int, text: str) -> None:
        await send_formatted_message(bot, chat_id, text)

    return notify
