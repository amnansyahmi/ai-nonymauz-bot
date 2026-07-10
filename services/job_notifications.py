"""Production search/notify wiring for the scheduled job-watch runner.

Kept separate from jobs_runner.py so the runner core stays free of Telegram
and cloud-client imports and remains easily unit-testable.
"""

from __future__ import annotations

from telegram import Bot

from handlers.jobs import _job_search_prompt
from services.cloud_client import ai_nonymauz_cloud
from services.storage import JobWatch
from utils.telegram_send import send_formatted_message


async def search_for_watch(watch: JobWatch) -> str:
    return await ai_nonymauz_cloud.send_message(
        session_id=watch.chat_id,
        text=_job_search_prompt(watch.query),
    )


def make_notifier(bot: Bot):
    async def notify(chat_id: int, text: str) -> None:
        await send_formatted_message(bot, chat_id, text)

    return notify
