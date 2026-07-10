"""Structured job listings via the JSearch API (RapidAPI).

Generic web search only returns job-board landing pages, not individual
postings. JSearch aggregates Google-for-Jobs data (real Malaysia coverage)
and returns structured listings with title, company, location, and an apply
link, so /jobs and job watches can show actual openings.

Requires JSEARCH_API_KEY (or RAPIDAPI_KEY). When unset, is_enabled() is False
and callers fall back to the ai-nonymauz-cloud web search.
Docs: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from config import settings

logger = logging.getLogger(__name__)

_HOST = "jsearch.p.rapidapi.com"
_URL = f"https://{_HOST}/search"


class JobsApiError(Exception):
    """Raised when the jobs API can't be reached or returns an error."""


@dataclass(frozen=True)
class JobPosting:
    title: str
    company: str
    location: str
    url: str
    employment_type: str | None


class JSearchClient:
    def __init__(self, api_key: str | None, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def is_enabled(self) -> bool:
        return bool(self._api_key)

    async def search(self, query: str, limit: int = 5) -> list[JobPosting]:
        if not self._api_key:
            raise JobsApiError("JSEARCH_API_KEY is not configured")

        headers = {
            "X-RapidAPI-Key": self._api_key,
            "X-RapidAPI-Host": _HOST,
        }
        params = {"query": query, "page": "1", "num_pages": "1"}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(_URL, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise JobsApiError(f"Failed to reach jobs API: {exc}") from exc

        results = data.get("data") or []
        postings = []
        for item in results[:limit]:
            city = item.get("job_city") or ""
            country = item.get("job_country") or ""
            location = ", ".join(p for p in (city, country) if p) or "Location not specified"
            postings.append(
                JobPosting(
                    title=item.get("job_title") or "Untitled role",
                    company=item.get("employer_name") or "Unknown company",
                    location=location,
                    url=item.get("job_apply_link") or "",
                    employment_type=item.get("job_employment_type"),
                )
            )
        return postings


def format_postings(query: str, postings: list[JobPosting]) -> str:
    if not postings:
        return f"No current openings found for \"{query}\". Try a broader search or a different location."

    lines = [f"Found {len(postings)} opening(s) for \"{query}\":\n"]
    for p in postings:
        line = f"**{p.title}** — {p.company}"
        meta = " · ".join(x for x in (p.location, p.employment_type) if x)
        if meta:
            line += f"\n📍 {meta}"
        if p.url:
            line += f"\n🔗 {p.url}"
        lines.append(line)
    return "\n\n".join(lines)


jsearch = JSearchClient(api_key=settings.jsearch_api_key)
