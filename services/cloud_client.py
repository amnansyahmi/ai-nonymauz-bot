"""Client for the ai-nonymauz-cloud API.

The bot has no AI logic of its own — every user message is forwarded here
and the response is relayed back to Telegram. Until AI_NONYMAUZ_CLOUD_URL is
configured, a placeholder reply is returned instead.

Confirmed contract (verified live against https://ai-nonymauz-cloud.vercel.app):
  POST {base_url}/chat
    body: {"messages": [{"role": "user"|"assistant", "content": "..."}], "stream": false}
    response: OpenAI-style chat completion, e.g.
      {"choices": [{"message": {"content": "...", "reasoning": "..."}}], ...}

The API itself is stateless per request — it has no session/reset endpoint,
so multi-turn memory is the bot's job: the caller passes the full message
history (see services/storage.py) instead of just the latest turn.
"""

from __future__ import annotations

import logging
import re

import httpx

from config import settings

logger = logging.getLogger(__name__)

# Closed reasoning blocks. Some models inline their <think> trace into the
# reply content instead of the separate 'reasoning' field.
_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
# An *unclosed* trailing <think> — happens when the reply is truncated mid
# reasoning (finish_reason: length). Drop it so raw reasoning never reaches
# the user, even though it means we lost the real answer for that turn.
_OPEN_THINK_RE = re.compile(r"<think>.*$", re.DOTALL | re.IGNORECASE)

# Sent as the system prompt on every conversational turn. Keeps replies in the
# user's language, concise, non-repetitive on follow-ups, and free of raw
# reasoning — without this the model re-dumps the whole previous answer and
# sometimes leaks <think> traces.
SYSTEM_PROMPT = (
    "You are AI Nonymauz, a helpful assistant chatting on Telegram. "
    "Always reply in the same language the user wrote in. "
    "Be concise and conversational. When answering a follow-up question, do "
    "not repeat information you have already given — only add what is new or "
    "directly asked. Never output your internal reasoning or <think> tags."
)


def _strip_reasoning(text: str) -> str:
    text = _THINK_TAG_RE.sub("", text)
    text = _OPEN_THINK_RE.sub("", text)
    return text.strip()


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

    async def send_conversation(self, session_id: int, messages: list[dict[str, str]]) -> str:
        if not self._base_url:
            last_text = messages[-1]["content"] if messages else ""
            logger.warning("AI_NONYMAUZ_CLOUD_URL not configured; returning placeholder reply")
            return f"(Phase 1 placeholder) You said: {last_text}"

        payload = {
            "messages": messages,
            "stream": False,
            # "auto" mode routes unpredictably and often truncates
            # (finish_reason: length) before finishing tool/search-based
            # answers. "deep" mode + a higher token budget avoids that.
            "mode": "deep",
            "max_tokens": 2048,
            "system_prompt": SYSTEM_PROMPT,
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

        content = _strip_reasoning(content)
        if not content:
            # The whole reply was (truncated) reasoning with no actual answer.
            return "🤔 I got a bit tangled up thinking about that. Could you rephrase or ask again?"
        return content

    async def send_message(self, session_id: int, text: str) -> str:
        """Single-turn convenience wrapper (no history) for one-off queries."""
        return await self.send_conversation(session_id, [{"role": "user", "content": text}])


ai_nonymauz_cloud = CloudClient(
    base_url=settings.ai_nonymauz_cloud_url,
    api_key=settings.ai_nonymauz_cloud_api_key,
)
