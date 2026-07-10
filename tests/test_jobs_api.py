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


async def test_search_uses_v2_endpoint_with_country(monkeypatch):
    captured = {}

    class _CapturingClient(_FakeClient):
        async def get(self, url, headers=None, params=None):
            captured["url"] = url
            captured["params"] = params
            return _FakeResponse({"status": "OK", "data": []})

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _CapturingClient({}))
    await JSearchClient(api_key="k", country="my").search("dev")
    assert captured["url"].endswith("/search-v2")
    assert captured["params"]["country"] == "my"


async def test_num_pages_derived_from_result_count(monkeypatch):
    captured = {}

    class _CapturingClient(_FakeClient):
        async def get(self, url, headers=None, params=None):
            captured["params"] = params
            return _FakeResponse({"status": "OK", "data": []})

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _CapturingClient({}))
    await JSearchClient(api_key="k", max_results=10).search("dev")
    assert captured["params"]["num_pages"] == "1"
    await JSearchClient(api_key="k", max_results=25).search("dev")
    assert captured["params"]["num_pages"] == "3"


async def test_nested_data_list_is_unwrapped(monkeypatch):
    payload = {"status": "OK", "data": {"jobs": [{"job_title": "Eng", "employer_name": "Acme"}]}}
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _FakeClient(payload))
    postings = await JSearchClient(api_key="k").search("dev")
    assert len(postings) == 1
    assert postings[0].title == "Eng"


async def test_search_http_error_wrapped(monkeypatch):
    class _BoomClient(_FakeClient):
        async def get(self, *a, **k):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _BoomClient({}))
    with pytest.raises(JobsApiError):
        await JSearchClient(api_key="k").search("dev")


async def test_salary_parsed_from_item(monkeypatch):
    payload = {
        "status": "OK",
        "data": [{
            "job_title": "Eng", "employer_name": "Acme",
            "job_min_salary": 3000, "job_max_salary": 5000, "job_salary_period": "MONTH",
        }],
    }
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _FakeClient(payload))
    postings = await JSearchClient(api_key="k").search("eng")
    assert postings[0].salary == "3,000–5,000/month"


def test_format_postings_empty():
    out = format_postings("dev in KL", [])
    assert "No current openings" in out


def test_format_postings_renders_fields(monkeypatch):
    from services.jobs_api import JobPosting

    out = format_postings("dev", [JobPosting("Eng", "Acme", "KL", "https://x/1", "FULLTIME")])
    assert "**Eng** — Acme" in out
    assert "📍 KL · FULLTIME" in out
    assert "🔗 https://x/1" in out
