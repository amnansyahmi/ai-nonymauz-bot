import httpx
import pytest

from services.cloud_client import CloudClient, CloudClientError, _strip_reasoning


def test_strip_closed_think():
    assert _strip_reasoning("<think>reasoning</think>Answer") == "Answer"


def test_strip_unclosed_trailing_think():
    assert _strip_reasoning("Answer here <think>truncated reasoning") == "Answer here"


def test_all_think_becomes_empty():
    assert _strip_reasoning("<think>only reasoning, truncated") == ""


def test_plain_text_untouched():
    assert _strip_reasoning("just an answer") == "just an answer"


async def test_placeholder_when_no_base_url():
    client = CloudClient(base_url=None, api_key=None)
    reply = await client.send_message(session_id=1, text="hi")
    assert "hi" in reply


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

    async def post(self, *a, **k):
        return _FakeResponse(self._payload)


async def test_parses_choices_content(monkeypatch):
    payload = {"choices": [{"message": {"content": "Hello world"}}]}
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _FakeClient(payload))
    client = CloudClient(base_url="https://cloud.example", api_key=None)
    reply = await client.send_message(session_id=1, text="hi")
    assert reply == "Hello world"


async def test_strips_reasoning_from_content(monkeypatch):
    payload = {"choices": [{"message": {"content": "<think>hmm</think>Real answer"}}]}
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _FakeClient(payload))
    client = CloudClient(base_url="https://cloud.example", api_key=None)
    reply = await client.send_message(session_id=1, text="hi")
    assert reply == "Real answer"


async def test_missing_choices_raises(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _FakeClient({}))
    client = CloudClient(base_url="https://cloud.example", api_key=None)
    with pytest.raises(CloudClientError):
        await client.send_message(session_id=1, text="hi")


async def test_describe_image_parses_content(monkeypatch):
    payload = {"choices": [{"message": {"content": "A red square"}}]}
    captured = {}

    class _CapturingClient(_FakeClient):
        async def post(self, url, json=None, headers=None):
            captured["json"] = json
            return _FakeResponse(payload)

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _CapturingClient(payload))
    client = CloudClient(base_url="https://cloud.example", api_key=None)
    reply = await client.describe_image(b"\x89PNG...", "image/png", "what is this?")
    assert reply == "A red square"
    # Sent as a vision request with an image_url content part.
    assert captured["json"]["mode"] == "vision"
    parts = captured["json"]["messages"][0]["content"]
    assert any(p["type"] == "image_url" and p["image_url"]["url"].startswith("data:image/png;base64,") for p in parts)
