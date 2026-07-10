"""/diag — report live configuration and job-search health into Telegram.

A diagnostic command so config/deploy issues can be checked without reading
server logs. Reveals only enabled/disabled state and error text, no secrets.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import settings
from services.jobs_api import JobsApiError, jsearch

logger = logging.getLogger(__name__)


async def diag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = [
        "🔧 Diagnostics",
        f"• ai-nonymauz-cloud URL: {'set' if settings.ai_nonymauz_cloud_url else 'UNSET'}",
        f"• JSearch enabled: {jsearch.is_enabled()}",
        f"• JSearch country: {settings.jsearch_country}",
    ]

    if jsearch.is_enabled():
        try:
            postings = await jsearch.search("software engineer in Kuala Lumpur", limit=3)
            lines.append(f"• JSearch live test: OK — {len(postings)} result(s)")
            if postings:
                lines.append(f"   e.g. {postings[0].title} @ {postings[0].company}")
        except JobsApiError as exc:
            lines.append(f"• JSearch live test: FAILED — {exc}")
    else:
        lines.append("• JSearch live test: skipped (no key)")

    await update.message.reply_text("\n".join(lines))
