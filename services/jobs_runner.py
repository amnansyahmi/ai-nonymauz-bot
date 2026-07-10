"""Scheduled job-watch runner.

Invoked out-of-band (by the /tasks/run-job-watches endpoint, triggered by a
GitHub Actions cron) rather than on a Telegram message. For each saved watch
it re-runs the job search, and if the result differs from what the user was
last notified about, pushes an update to their chat.

Dedup is coarse by design: we hash the search result text and only notify when
that hash changes. It means any change re-sends the whole result, but it
reliably avoids spamming identical results every run.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Awaitable, Callable

from services.storage import (
    JobWatch,
    list_all_job_watches,
    set_job_watch_result_hash,
)

logger = logging.getLogger(__name__)

# Callables injected so the runner stays unit-testable without a live API or bot.
SearchFn = Callable[[JobWatch], Awaitable[str]]
NotifyFn = Callable[[int, str], Awaitable[None]]


def _hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


async def run_job_watches(search: SearchFn, notify: NotifyFn) -> dict[str, int]:
    """Run every saved watch. Returns a small summary for logging/HTTP response."""
    watches = await list_all_job_watches()
    checked = 0
    notified = 0
    failed = 0

    for watch in watches:
        checked += 1
        try:
            result = await search(watch)
        except Exception:  # noqa: BLE001 - one bad watch shouldn't kill the run
            logger.exception("Search failed for watch %s (chat %s)", watch.id, watch.chat_id)
            failed += 1
            continue

        if not result.strip():
            continue

        new_hash = _hash(result)
        if new_hash == watch.last_result_hash:
            continue  # nothing new since last notification

        try:
            await notify(watch.chat_id, f"🔔 Update for your job watch \"{watch.query}\":\n\n{result}")
        except Exception:  # noqa: BLE001
            logger.exception("Notify failed for watch %s (chat %s)", watch.id, watch.chat_id)
            failed += 1
            continue

        await set_job_watch_result_hash(watch.id, new_hash)
        notified += 1

    summary = {"checked": checked, "notified": notified, "failed": failed}
    logger.info("Job watch run complete: %s", summary)
    return summary
