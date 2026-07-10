"""Shared test setup.

Sets required env vars and an isolated DB path BEFORE any app module is
imported (config.py and services.storage read the environment at import time).
"""

import os
import tempfile

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
_tmp_db = os.path.join(tempfile.mkdtemp(prefix="ai-nonymauz-bot-tests-"), "bot.db")
os.environ["DB_PATH"] = _tmp_db

import pytest

from services.storage import init_db


@pytest.fixture
async def fresh_db():
    """A clean database for each test that needs one."""
    if os.path.exists(_tmp_db):
        os.remove(_tmp_db)
    await init_db()
    yield
