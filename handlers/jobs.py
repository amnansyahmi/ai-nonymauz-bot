"""Job search commands: /jobs (guided), /watchjob, /unwatchjob, /myjobs."""

from __future__ import annotations

import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
)
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from services.cloud_client import CloudClientError, ai_nonymauz_cloud
from services.jobs_api import format_postings, format_postings_page, jsearch
from services.storage import add_job_watch, list_job_watches, remove_job_watch
from utils.rate_limit import message_limiter
from utils.telegram_send import send_formatted_reply, typing_action

logger = logging.getLogger(__name__)

# Guided /jobs conversation states.
ASK_TITLE, ASK_LOCATION, ASK_LOCATION_TEXT, ASK_SALARY = range(4)
_SKIP_WORDS = {"any", "skip", "no", "none", "-"}


def _location_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Kuala Lumpur", callback_data="loc:Kuala Lumpur"),
         InlineKeyboardButton("Selangor", callback_data="loc:Selangor")],
        [InlineKeyboardButton("Penang", callback_data="loc:Penang"),
         InlineKeyboardButton("Johor", callback_data="loc:Johor")],
        [InlineKeyboardButton("🌐 Anywhere", callback_data="loc:__any__"),
         InlineKeyboardButton("✍️ Type it", callback_data="loc:__type__")],
    ])


def _salary_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("< RM3k", callback_data="sal:below 3000"),
         InlineKeyboardButton("RM3k–5k", callback_data="sal:3000-5000")],
        [InlineKeyboardButton("RM5k+", callback_data="sal:above 5000"),
         InlineKeyboardButton("Skip", callback_data="sal:__skip__")],
    ])


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


PAGE_SIZE = 5


async def _fetch_jobs(chat_id: int, query: str):
    """Returns (postings, fallback_text). postings is a list when JSearch is
    used (enabling pagination); None when we fell back to the cloud web search."""
    if jsearch.is_enabled():
        try:
            return await jsearch.search(query), ""
        except Exception:  # noqa: BLE001 - never let a jobs-API issue break the reply
            logger.warning("JSearch failed for %r; falling back to cloud search", query, exc_info=True)
    text = await ai_nonymauz_cloud.send_message(session_id=chat_id, text=_job_search_prompt(query))
    return None, text


async def job_results_text(chat_id: int, query: str) -> str:
    """Full results as a text block — used by the scheduled watch notifier."""
    postings, text = await _fetch_jobs(chat_id, query)
    return format_postings(query, postings) if postings is not None else text


def _results_keyboard(has_more: bool) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton("🔁 Search again", callback_data="act:jobs_again"),
        InlineKeyboardButton("⭐ Save watch", callback_data="act:jobs_save"),
    ]]
    if has_more:
        rows.append([InlineKeyboardButton("➡️ Show more", callback_data="act:jobs_more")])
    return InlineKeyboardMarkup(rows)


async def _run_and_reply(message: Message, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    """Run a search and reply to `message`, paginated with action buttons."""
    chat_id = message.chat_id
    if not message_limiter.allow(chat_id):
        await message.reply_text("⏳ You're searching a bit fast. Please wait a few seconds and try again.")
        return
    try:
        async with typing_action(context, chat_id):
            postings, text = await _fetch_jobs(chat_id, query)
    except CloudClientError:
        logger.exception("Job search failed for chat %s", chat_id)
        await message.reply_text("⚠️ Sorry, job search isn't available right now. Please try again shortly.")
        return

    context.user_data["last_job_query"] = query

    if postings is None:  # cloud fallback — plain text, no pagination
        await send_formatted_reply(message, text, reply_markup=_results_keyboard(False))
        return
    if not postings:
        await send_formatted_reply(message, format_postings(query, []))
        return

    context.user_data["job_postings"] = postings
    context.user_data["job_offset"] = 0
    has_more = len(postings) > PAGE_SIZE
    await send_formatted_reply(
        message,
        format_postings_page(query, postings, 0, PAGE_SIZE),
        reply_markup=_results_keyboard(has_more),
    )


# ── Guided /jobs conversation ────────────────────────────────────────────────

async def jobs_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Power-user shortcut: `/jobs <query>` runs immediately, no questions.
    query = " ".join(context.args).strip() if context.args else ""
    if query:
        await _run_and_reply(update.message, context, query)
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
    await update.message.reply_text("📍 Which location?", reply_markup=_location_keyboard())
    return ASK_LOCATION


async def location_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    value = query.data.split(":", 1)[1]
    if value == "__type__":
        await query.message.reply_text("✍️ Type the location you want:")
        return ASK_LOCATION_TEXT
    context.user_data["job_location"] = "" if value == "__any__" else value
    await query.message.reply_text("💰 Expected monthly salary?", reply_markup=_salary_keyboard())
    return ASK_SALARY


async def location_typed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answer = update.message.text.strip()
    context.user_data["job_location"] = "" if answer.lower() in _SKIP_WORDS else answer
    await update.message.reply_text("💰 Expected monthly salary?", reply_markup=_salary_keyboard())
    return ASK_SALARY


async def salary_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    value = query.data.split(":", 1)[1]
    salary = "" if value == "__skip__" else value
    search_query = build_job_query(
        context.user_data.get("job_title", ""),
        context.user_data.get("job_location", ""),
        salary,
    )
    await _run_and_reply(query.message, context, search_query)
    return ConversationHandler.END


async def cancel_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Job search cancelled.")
    return ConversationHandler.END


async def jobs_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 🔁 Search again / ⭐ Save watch / ➡️ Show more under job results."""
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]
    last_query = context.user_data.get("last_job_query")
    if not last_query:
        await query.message.reply_text("That search has expired — run /jobs again.")
        return

    if action == "jobs_again":
        await _run_and_reply(query.message, context, last_query)
    elif action == "jobs_save":
        watch = await add_job_watch(chat_id=query.message.chat_id, query=last_query)
        await query.message.reply_text(
            f"⭐ Saved watch #{watch.id} for \"{last_query}\". "
            "I'll alert you when the results change. See /myjobs."
        )
    elif action == "jobs_more":
        postings = context.user_data.get("job_postings")
        offset = context.user_data.get("job_offset", 0) + PAGE_SIZE
        if not postings or offset >= len(postings):
            await query.message.reply_text("No more results — try /jobs for a fresh search.")
            return
        context.user_data["job_offset"] = offset
        # Retire the tapped message's Show more so it isn't re-used.
        try:
            await query.edit_message_reply_markup(reply_markup=_results_keyboard(False))
        except Exception:  # noqa: BLE001 - editing is best-effort
            pass
        has_more = len(postings) > offset + PAGE_SIZE
        await send_formatted_reply(
            query.message,
            format_postings_page(last_query, postings, offset, PAGE_SIZE),
            reply_markup=_results_keyboard(has_more),
        )


def build_jobs_conversation() -> ConversationHandler:
    from handlers.menu import BTN_JOBS

    return ConversationHandler(
        entry_points=[
            CommandHandler("jobs", jobs_entry),
            MessageHandler(filters.Text([BTN_JOBS]), jobs_entry),
        ],
        states={
            ASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_title)],
            ASK_LOCATION: [CallbackQueryHandler(location_chosen, pattern=r"^loc:")],
            ASK_LOCATION_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, location_typed)],
            ASK_SALARY: [CallbackQueryHandler(salary_chosen, pattern=r"^sal:")],
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
        f"✅ Saved watch for \"{query}\".\n\n"
        "I'll check periodically and message you when the results change. "
        "Tap /myjobs to run or remove your watches.\n\n"
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


_MYJOBS_HEADER = "📌 Your saved job watches — tap 🔁 to run one now or 🗑 to remove it:"
_MYJOBS_EMPTY = "You have no saved job watches yet. Save one with ⭐ on a search result, or /watchjob <role>."


def _watches_keyboard(watches) -> InlineKeyboardMarkup:
    rows = []
    for w in watches:
        label = w.query if len(w.query) <= 30 else w.query[:29] + "…"
        rows.append([
            InlineKeyboardButton(f"🔁 {label}", callback_data=f"watch:run:{w.id}"),
            InlineKeyboardButton("🗑", callback_data=f"watch:del:{w.id}"),
        ])
    return InlineKeyboardMarkup(rows)


async def myjobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    watches = await list_job_watches(update.effective_chat.id)
    if not watches:
        await update.message.reply_text(_MYJOBS_EMPTY)
        return
    await update.message.reply_text(_MYJOBS_HEADER, reply_markup=_watches_keyboard(watches))


async def watch_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 🔁 run / 🗑 delete buttons in /myjobs."""
    query = update.callback_query
    await query.answer()
    _, action, raw_id = query.data.split(":")
    watch_id = int(raw_id)
    chat_id = query.message.chat_id

    if action == "run":
        watch = next((w for w in await list_job_watches(chat_id) if w.id == watch_id), None)
        if watch is None:
            await query.message.reply_text("That watch no longer exists.")
            return
        await _run_and_reply(query.message, context, watch.query)
    elif action == "del":
        await remove_job_watch(chat_id=chat_id, watch_id=watch_id)
        watches = await list_job_watches(chat_id)
        if watches:
            await query.edit_message_text(_MYJOBS_HEADER, reply_markup=_watches_keyboard(watches))
        else:
            await query.edit_message_text("🗑 Removed. " + _MYJOBS_EMPTY)
