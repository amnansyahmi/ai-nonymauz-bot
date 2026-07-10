import httpx
import pytest

from services.jobs_api import JobsApiError, JSearchClient, format_postings


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, payload):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, *a, **k):
        return _FakeResponse(self._payload)


def test_disabled_without_key():
    assert JSearchClient(api_key=None).is_enabled() is False
    assert JSearchClient(api_key="k").is_enabled() is True


async def test_search_without_key_raises():
    with pytest.raises(JobsApiError):
        await JSearchClient(api_key=None).search("dev")


async def test_search_parses_and_limits(monkeypatch):
    payload = {
        "status": "OK",
        "data": [
            {
                "job_title": "Software Engineer",
                "employer_name": "Acme",
                "job_city": "Shah Alam",
                "job_country": "Malaysia",
                "job_apply_link": "https://apply.example/1",
                "job_employment_type": "FULLTIME",
            },
            {"job_title": "Backend Dev", "employer_name": "Beta", "job_apply_link": "https://apply.example/2"},
            {"job_title": "Extra", "employer_name": "C"},
        ],
    }
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _FakeClient(payload))
    postings = await JSearchClient(api_key="k").search("software engineer", limit=2)
    assert len(postings) == 2
    assert postings[0].title == "Software Engineer"
    assert postings[0].location == "Shah Alam, Malaysia"
    assert postings[1].location == "Location not specified"


async def test_search_http_error_wrapped(monkeypatch):
    class _BoomClient(_FakeClient):
        async def get(self, *a, **k):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _BoomClient({}))
    with pytest.raises(JobsApiError):
        await JSearchClient(api_key="k").search("dev")


def test_format_postings_empty():
    out = format_postings("dev in KL", [])
    assert "No current openings" in out


def test_format_postings_renders_fields(monkeypatch):
    from services.jobs_api import JobPosting

    out = format_postings("dev", [JobPosting("Eng", "Acme", "KL", "https://x/1", "FULLTIME")])
    assert "**Eng** — Acme" in out
    assert "📍 KL · FULLTIME" in out
    assert "🔗 https://x/1" in out
