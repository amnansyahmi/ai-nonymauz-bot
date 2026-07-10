"""Job search commands: /jobs (guided), /watchjob, /unwatchjob, /myjobs."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from services.cloud_client import CloudClientError, ai_nonymauz_cloud
from services.jobs_api import format_postings, jsearch
from services.storage import add_job_watch, list_job_watches, remove_job_watch
from utils.rate_limit import message_limiter
from utils.telegram_send import send_formatted_reply, typing_action

logger = logging.getLogger(__name__)

# Guided /jobs conversation states.
ASK_TITLE, ASK_LOCATION, ASK_SALARY = range(3)
_SKIP_WORDS = {"any", "skip", "no", "none", "-"}


def _job_search_prompt(query: str) -> str:
    return (
        f"Search for current job vacancy / hiring listings for: {query}. "
        "List up to 5 openings with job title, company, location, and a link "
        "if available. If you can't find real postings, say so plainly."
    )


def build_job_query(title: str, location: str = "", salary: str = "") -> str:
    """Assemble a search query from the guided answers."""
    query = title.strip()
    if location.strip():
        query += f" in {location.strip()}"
    if salary.strip():
        query += f" salary {salary.strip()}"
    return query


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


async def _run_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
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


# ── Guided /jobs conversation ────────────────────────────────────────────────

async def jobs_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Power-user shortcut: `/jobs <query>` runs immediately, no questions.
    query = " ".join(context.args).strip() if context.args else ""
    if query:
        await _run_and_reply(update, context, query)
        return ConversationHandler.END

    context.user_data.pop("job_title", None)
    context.user_data.pop("job_location", None)
    await update.message.reply_text(
        "Let's find some jobs! 🔎\n\n"
        "What job title or role are you looking for? (e.g. software engineer)\n"
        "Send /cancel any time to stop."
    )
    return ASK_TITLE


async def received_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["job_title"] = update.message.text.strip()
    await update.message.reply_text("📍 Which location? (e.g. Selangor, Kuala Lumpur — or type 'any')")
    return ASK_LOCATION


async def received_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answer = update.message.text.strip()
    context.user_data["job_location"] = "" if answer.lower() in _SKIP_WORDS else answer
    await update.message.reply_text("💰 Minimum expected monthly salary? (e.g. 3000 — or type 'skip')")
    return ASK_SALARY


async def received_salary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answer = update.message.text.strip()
    salary = "" if answer.lower() in _SKIP_WORDS else answer
    query = build_job_query(
        context.user_data.get("job_title", ""),
        context.user_data.get("job_location", ""),
        salary,
    )
    await _run_and_reply(update, context, query)
    return ConversationHandler.END


async def cancel_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Job search cancelled.")
    return ConversationHandler.END


def build_jobs_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("jobs", jobs_entry)],
        states={
            ASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_title)],
            ASK_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_location)],
            ASK_SALARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_salary)],
        },
        fallbacks=[CommandHandler("cancel", cancel_jobs)],
    )


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
