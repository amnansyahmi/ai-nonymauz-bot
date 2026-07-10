"""Client for the ai-nonymauz-cloud API.

The bot has no AI logic of its own — every user message is forwarded here
and the response is relayed back to Telegram. Until AI_NONYMAUZ_CLOUD_URL is
configured, a placeholder reply is returned instead.

Confirmed contract (verified live against https://ai-nonymauz-cloud.vercel.app):
  POST {base_url}/chat
    body: {"messages": [{"role": "user", "content": "..."}], "stream": false}
    response: OpenAI-style chat completion, e.g.
      {"choices": [{"message": {"content": "...", "reasoning": "..."}}], ...}

The API is stateless per request — it has no session/reset endpoint, so the
bot only sends the latest message. Conversation history/memory is a Phase 3
feature to be added on the bot side (or once ai-nonymauz-cloud exposes one).
"""

from __future__ import annotations

import logging
import re

import httpx

from config import settings

logger = logging.getLogger(__name__)

_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class CloudClientError(Exception):
    """Raised when ai-nonymauz-cloud cannot be reached or returns an error."""


class CloudClient:
    def __init__(self, base_url: str | None, api_key: str | None, timeout: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/") if base_url else None
        self._api_key = api_key
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def send_message(self, session_id: int, text: str) -> str:
        if not self._base_url:
            logger.warning("AI_NONYMAUZ_CLOUD_URL not configured; returning placeholder reply")
            return f"(Phase 1 placeholder) You said: {text}"

        payload = {
            "messages": [{"role": "user", "content": text}],
            "stream": False,
            # "auto" mode routes unpredictably and often truncates
            # (finish_reason: length) before finishing tool/search-based
            # answers. "deep" mode + a higher token budget avoids that.
            "mode": "deep",
            "max_tokens": 2048,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/chat",
                    json=payload,
                    headers=self._headers(),
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise CloudClientError(f"Failed to reach ai-nonymauz-cloud: {exc}") from exc

        choices = data.get("choices") or []
        if not choices:
            raise CloudClientError("ai-nonymauz-cloud response missing 'choices'")

        content = choices[0].get("message", {}).get("content")
        if not content:
            raise CloudClientError("ai-nonymauz-cloud response missing message content")

        # Some reasoning models inline their <think> trace into content instead
        # of the separate 'reasoning' field — strip it before showing the user.
        content = _THINK_TAG_RE.sub("", content).strip()
        return content or "(empty response from AI Nonymauz)"


ai_nonymauz_cloud = CloudClient(
    base_url=settings.ai_nonymauz_cloud_url,
    api_key=settings.ai_nonymauz_cloud_api_key,
)
