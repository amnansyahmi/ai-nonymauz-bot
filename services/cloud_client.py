"""Client for the ai-nonymauz-cloud API.

The bot has no AI logic of its own — every user message is forwarded here
and the response is relayed back to Telegram. Until AI_NONYMAUZ_CLOUD_URL is
configured, a placeholder reply is returned instead.

Contract (adjust here if the real ai-nonymauz-cloud API differs):
  POST   {base_url}/api/v1/chat            {"session_id": ..., "message": ...} -> {"reply": ...}
  DELETE {base_url}/api/v1/chat/{session_id}   clears server-side conversation history

The Telegram chat_id is used as the session_id, so ai-nonymauz-cloud owns
conversation history and the bot only ever sends the latest message.
"""

from __future__ import annotations

import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


class CloudClientError(Exception):
    """Raised when ai-nonymauz-cloud cannot be reached or returns an error."""


class CloudClient:
    def __init__(self, base_url: str | None, api_key: str | None, timeout: float = 30.0) -> None:
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

        payload = {"session_id": session_id, "message": text}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/v1/chat",
                    json=payload,
                    headers=self._headers(),
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise CloudClientError(f"Failed to reach ai-nonymauz-cloud: {exc}") from exc

        reply = data.get("reply")
        if not reply:
            raise CloudClientError("ai-nonymauz-cloud response missing 'reply' field")
        return reply

    async def reset_session(self, session_id: int) -> None:
        if not self._base_url:
            return

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.delete(
                    f"{self._base_url}/api/v1/chat/{session_id}",
                    headers=self._headers(),
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Failed to reset ai-nonymauz-cloud session %s: %s", session_id, exc)


ai_nonymauz_cloud = CloudClient(
    base_url=settings.ai_nonymauz_cloud_url,
    api_key=settings.ai_nonymauz_cloud_api_key,
)
