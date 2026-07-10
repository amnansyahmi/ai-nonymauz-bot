"""Persistence for job watches.

Uses SQLite via aiosqlite. Note: on Render's free tier, the filesystem is
not guaranteed to survive a redeploy (it does survive plain restarts), so
watches may be lost when the service is redeployed. Fine for now; move to
a hosted database (e.g. Render Postgres) if that becomes a problem.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite

DB_PATH = os.getenv("DB_PATH", "data/bot.db")

# How many past messages (user + assistant combined) to send as context on
# each turn. Bounds token usage/cost; older turns just drop off.
MAX_HISTORY_MESSAGES = 20


@dataclass(frozen=True)
class JobWatch:
    id: int
    chat_id: int
    query: str
    created_at: str


async def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS job_watches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                query TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        await db.commit()


async def add_message(chat_id: int, role: str, content: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversation_messages (chat_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, role, content, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()


async def get_recent_messages(chat_id: int, limit: int = MAX_HISTORY_MESSAGES) -> list[dict[str, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT role, content FROM conversation_messages WHERE chat_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        )
        rows = await cursor.fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


async def clear_history(chat_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM conversation_messages WHERE chat_id = ?", (chat_id,))
        await db.commit()


async def add_job_watch(chat_id: int, query: str) -> JobWatch:
    created_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO job_watches (chat_id, query, created_at) VALUES (?, ?, ?)",
            (chat_id, query, created_at),
        )
        await db.commit()
        return JobWatch(id=cursor.lastrowid, chat_id=chat_id, query=query, created_at=created_at)


async def list_job_watches(chat_id: int) -> list[JobWatch]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, chat_id, query, created_at FROM job_watches WHERE chat_id = ? ORDER BY id",
            (chat_id,),
        )
        rows = await cursor.fetchall()
        return [JobWatch(**dict(row)) for row in rows]


async def remove_job_watch(chat_id: int, watch_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM job_watches WHERE id = ? AND chat_id = ?",
            (watch_id, chat_id),
        )
        await db.commit()
        return cursor.rowcount > 0
