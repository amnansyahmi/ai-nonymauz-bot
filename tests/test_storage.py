from services.storage import (
    add_job_watch,
    add_message,
    clear_history,
    get_recent_messages,
    list_all_job_watches,
    list_job_watches,
    remove_job_watch,
    set_job_watch_result_hash,
)


async def test_conversation_history_roundtrip(fresh_db):
    await add_message(1, "user", "hello")
    await add_message(1, "assistant", "hi there")
    msgs = await get_recent_messages(1)
    assert msgs == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]


async def test_history_is_per_chat(fresh_db):
    await add_message(1, "user", "chat one")
    await add_message(2, "user", "chat two")
    assert len(await get_recent_messages(1)) == 1
    assert len(await get_recent_messages(2)) == 1


async def test_clear_history(fresh_db):
    await add_message(1, "user", "hello")
    await clear_history(1)
    assert await get_recent_messages(1) == []


async def test_recent_messages_limit_keeps_latest(fresh_db):
    for i in range(30):
        await add_message(1, "user", f"m{i}")
    msgs = await get_recent_messages(1, limit=5)
    assert [m["content"] for m in msgs] == ["m25", "m26", "m27", "m28", "m29"]


async def test_job_watch_crud(fresh_db):
    w = await add_job_watch(7, "python dev")
    assert (await list_job_watches(7))[0].query == "python dev"
    assert len(await list_all_job_watches()) == 1
    await set_job_watch_result_hash(w.id, "abc123")
    assert (await list_job_watches(7))[0].last_result_hash == "abc123"
    assert await remove_job_watch(7, w.id) is True
    assert await list_job_watches(7) == []


async def test_remove_other_users_watch_fails(fresh_db):
    w = await add_job_watch(7, "python dev")
    assert await remove_job_watch(999, w.id) is False
