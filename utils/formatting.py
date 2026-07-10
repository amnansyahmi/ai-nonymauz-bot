"""Converts LLM-style Markdown into Telegram-safe HTML.

Telegram doesn't render raw Markdown unless parse_mode is set, and its HTML
mode only supports a small tag subset (no tables, no headers) — so this
rewrites the common constructs models produce into something that reads
cleanly as plain chat text instead of showing literal ** and | characters.
"""

from __future__ import annotations

import html
import re

_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HR_RE = re.compile(r"^[ \t]*([*_-])\1{2,}[ \t]*$", re.MULTILINE)
_TABLE_SEPARATOR_RE = re.compile(r"^[ \t]*\|?[ \t:|-]+\|[ \t:|-]+\|?[ \t]*$", re.MULTILINE)
_TABLE_ROW_RE = re.compile(r"^[ \t]*\|(.+)\|[ \t]*$", re.MULTILINE)
_HEADER_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
_BULLET_RE = re.compile(r"^(\s*)[*-]\s+", re.MULTILINE)
_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_CODE_RE = re.compile(r"`([^`]+?)`")
_ITALIC_STAR_RE = re.compile(r"(?<!\*)\*(?!\*)([^*\n]+?)\*(?!\*)")
_ITALIC_UNDERSCORE_RE = re.compile(r"(?<!_)_(?!_)([^_\n]+?)_(?!_)")


def _flatten_table_row(match: re.Match[str]) -> str:
    cells = [cell.strip() for cell in match.group(1).split("|")]
    return " — ".join(cell for cell in cells if cell)


def markdown_to_telegram_html(text: str) -> str:
    text = _HR_RE.sub("", text)
    text = _TABLE_SEPARATOR_RE.sub("", text)
    text = _TABLE_ROW_RE.sub(_flatten_table_row, text)
    text = _BULLET_RE.sub(r"\1• ", text)
    text = _BR_RE.sub("\n", text)

    text = html.escape(text, quote=False)

    text = _LINK_RE.sub(r'<a href="\2">\1</a>', text)
    text = _HEADER_RE.sub(r"<b>\1</b>", text)
    text = _BOLD_RE.sub(r"<b>\1</b>", text)
    text = _CODE_RE.sub(r"<code>\1</code>", text)
    text = _ITALIC_STAR_RE.sub(r"<i>\1</i>", text)
    text = _ITALIC_UNDERSCORE_RE.sub(r"<i>\1</i>", text)

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
