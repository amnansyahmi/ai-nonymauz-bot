"""Job search commands: /jobs, /watchjob, /unwatchjob, /myjobs."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from services.cloud_client import CloudClientError, ai_nonymauz_cloud
from services.jobs_api import format_postings, jsearch
from services.storage import add_job_watch, list_job_watches, remove_job_watch
from utils.rate_limit import message_limiter
from utils.telegram_send import send_formatted_reply, typing_action

logger = logging.getLogger(__name__)


def _job_search_prompt(query: str) -> str:
    return (
        f"Search for current job vacancy / hiring listings for: {query}. "
        "List up to 5 openings with job title, company, location, and a link "
        "if available. If you can't find real postings, say so plainly."
    )


async def job_results_text(chat_id: int, query: str) -> str:
    """Get job results for a query as a text block.

    Prefers the JSearch API (real structured listings). Falls back to the
    ai-nonymauz-cloud web search when JSearch isn't configured or errors out.
    Shared by the /jobs command and the scheduled watch runner.
    """
    if jsearch.is_enabled():
        try:
            postings = await jsearch.search(query)
            return format_postings(query, postings)
        except Exception:  # noqa: BLE001 - never let a jobs-API issue break the reply
            logger.warning("JSearch failed for %r; falling back to cloud search", query, exc_info=True)

    return await ai_nonymauz_cloud.send_message(session_id=chat_id, text=_job_search_prompt(query))


async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        await update.message.reply_text("Usage: /jobs <role or keyword>\nExample: /jobs software engineer in Johor Bahru")
        return

    chat_id = update.effective_chat.id
    if not message_limiter.allow(chat_id):
        await update.message.reply_text("⏳ You're searching a bit fast. Please wait a few seconds and try again.")
        return

    try:
        async with typing_action(context, chat_id):
            reply = await job_results_text(chat_id, query)
    except CloudClientError:
        logger.exception("Job search failed for chat %s", chat_id)
        await update.message.reply_text("⚠️ Sorry, job search isn't available right now. Please try again shortly.")
        return

    await send_formatted_reply(update.message, reply)


async def watchjob(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        await update.message.reply_text("Usage: /watchjob <role or keyword>\nExample: /watchjob data analyst in Johor Bahru")
        return

    chat_id = update.effective_chat.id
    watch = await add_job_watch(chat_id=chat_id, query=query)
    await update.message.reply_text(
        f"✅ Saved watch #{watch.id} for \"{query}\".\n\n"
        "I'll check periodically and message you when the results change. "
        "Use /myjobs to see your watches, /unwatchjob <id> to stop one, or "
        "/jobs to search right now.\n\n"
        "(Automatic checks run only when the deployment's scheduler is "
        "configured — see the README.)"
    )


async def unwatchjob(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /unwatchjob <watch id>\nSee /myjobs for the id.")
        return

    watch_id = int(context.args[0])
    removed = await remove_job_watch(chat_id=chat_id, watch_id=watch_id)
    if removed:
        await update.message.reply_text(f"🗑️ Removed watch #{watch_id}.")
    else:
        await update.message.reply_text(f"No watch #{watch_id} found for you.")


async def myjobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    watches = await list_job_watches(chat_id)
    if not watches:
        await update.message.reply_text("You have no saved job watches. Add one with /watchjob <role or keyword>.")
        return

    lines = [f"#{w.id} — {w.query}" for w in watches]
    await update.message.reply_text("Your saved job watches:\n" + "\n".join(lines))
