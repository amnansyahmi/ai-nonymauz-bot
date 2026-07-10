from unittest.mock import AsyncMock

from telegram.error import BadRequest

from utils.telegram_send import MAX_MESSAGE_LEN, chunk_text, send_formatted_reply


def test_short_text_single_chunk():
    assert chunk_text("hello") == ["hello"]


def test_splits_on_line_boundaries_within_limit():
    text = "\n".join("line %d %s" % (i, "x" * 60) for i in range(300))
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert all(len(c) <= MAX_MESSAGE_LEN for c in chunks)


def test_single_giant_line_hard_split():
    giant = "z" * (MAX_MESSAGE_LEN * 2 + 500)
    chunks = chunk_text(giant)
    assert all(len(c) <= MAX_MESSAGE_LEN for c in chunks)
    assert "".join(chunks) == giant


async def test_send_falls_back_to_plain_text_on_bad_html():
    message = AsyncMock()
    # First (HTML) send fails, plain-text retry should be attempted.
    message.reply_text.side_effect = [BadRequest("bad entities"), None]
    await send_formatted_reply(message, "**bold** text")
    assert message.reply_text.await_count == 2
    # The retry call must not carry parse_mode.
    plain_call = message.reply_text.await_args_list[1]
    assert "parse_mode" not in plain_call.kwargs


async def test_send_html_when_valid():
    message = AsyncMock()
    message.reply_text.return_value = None
    await send_formatted_reply(message, "hello")
    assert message.reply_text.await_count == 1
    assert message.reply_text.await_args.kwargs.get("parse_mode") == "HTML"
