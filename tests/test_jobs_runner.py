from services.jobs_runner import run_job_watches
from services.storage import add_job_watch


async def test_notifies_on_first_run_and_dedups_identical(fresh_db):
    await add_job_watch(1, "python dev")
    await add_job_watch(2, "data analyst")
    sent = []

    async def notify(chat_id, text):
        sent.append(chat_id)

    async def search(watch):
        return f"results for {watch.query}"

    s1 = await run_job_watches(search, notify)
    assert s1 == {"checked": 2, "notified": 2, "failed": 0}

    sent.clear()
    s2 = await run_job_watches(search, notify)
    assert s2["notified"] == 0
    assert sent == []


async def test_notifies_again_when_results_change(fresh_db):
    await add_job_watch(1, "python dev")

    async def notify(chat_id, text):
        pass

    async def search_v1(watch):
        return "v1"

    async def search_v2(watch):
        return "v2 changed"

    await run_job_watches(search_v1, notify)
    s = await run_job_watches(search_v2, notify)
    assert s["notified"] == 1


async def test_empty_results_do_not_notify(fresh_db):
    await add_job_watch(1, "python dev")
    sent = []

    async def notify(chat_id, text):
        sent.append(chat_id)

    async def search(watch):
        return "   "

    s = await run_job_watches(search, notify)
    assert s["notified"] == 0
    assert sent == []


async def test_one_failing_search_does_not_abort_others(fresh_db):
    await add_job_watch(1, "boom")
    await add_job_watch(2, "ok")
    notified = []

    async def notify(chat_id, text):
        notified.append(chat_id)

    async def search(watch):
        if watch.query == "boom":
            raise RuntimeError("search exploded")
        return "good results"

    s = await run_job_watches(search, notify)
    assert s == {"checked": 2, "notified": 1, "failed": 1}
    assert notified == [2]
