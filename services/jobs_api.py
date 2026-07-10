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
# JSearch retired the old /search endpoint (returns 404); /search-v2 is current.
_URL = f"https://{_HOST}/search-v2"


class JobsApiError(Exception):
    """Raised when the jobs API can't be reached or returns an error."""


@dataclass(frozen=True)
class JobPosting:
    title: str
    company: str
    location: str
    url: str
    employment_type: str | None
    salary: str | None = None


# JSearch returns ~10 results per page and charges one request per page, so
# num_pages is derived from the desired result count to avoid wasting quota.
_RESULTS_PER_PAGE = 10


class JSearchClient:
    def __init__(
        self,
        api_key: str | None,
        country: str = "my",
        max_results: int = 10,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._country = country
        self._max_results = max_results
        self._timeout = timeout

    def is_enabled(self) -> bool:
        return bool(self._api_key)

    async def search(self, query: str, limit: int | None = None) -> list[JobPosting]:
        if not self._api_key:
            raise JobsApiError("JSEARCH_API_KEY is not configured")

        limit = limit or self._max_results
        num_pages = max(1, -(-limit // _RESULTS_PER_PAGE))  # ceil division

        headers = {
            "X-RapidAPI-Key": self._api_key,
            "X-RapidAPI-Host": _HOST,
        }
        # country defaults the search region — without it JSearch assumes "us",
        # so Malaysian-location queries return nothing. Params match the
        # /search-v2 contract (query, num_pages, country, date_posted).
        params = {
            "query": query,
            "num_pages": str(num_pages),
            "country": self._country,
            "date_posted": "all",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(_URL, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            # Include the response body so 403 "not subscribed" / 401 "invalid
            # key" style errors are actionable instead of just a status code.
            body = (exc.response.text or "").strip()[:200]
            raise JobsApiError(f"Jobs API returned HTTP {exc.response.status_code}: {body}") from exc
        except httpx.HTTPError as exc:
            raise JobsApiError(f"Failed to reach jobs API: {exc}") from exc

        results = data.get("data")
        # /search-v2 may nest the job list under data instead of making data
        # the list directly — handle the common variants.
        if isinstance(results, dict):
            for key in ("jobs", "results", "items", "data"):
                if isinstance(results.get(key), list):
                    results = results[key]
                    break
        if not isinstance(results, list):
            raw = data.get("data")
            raise JobsApiError(
                f"Unexpected 'data' shape: {type(raw).__name__} -> {repr(raw)[:300]}"
            )

        postings = []
        for item in results[:limit]:
            if not isinstance(item, dict):
                continue
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
                    salary=_format_salary(item),
                )
            )
        return postings


def _format_salary(item: dict) -> str | None:
    lo = item.get("job_min_salary")
    hi = item.get("job_max_salary")
    period = (item.get("job_salary_period") or "").lower()
    if not lo and not hi:
        return None
    if lo and hi:
        amount = f"{int(lo):,}–{int(hi):,}"
    else:
        amount = f"{int(lo or hi):,}"
    return f"{amount}/{period}" if period else amount


def format_postings(query: str, postings: list[JobPosting]) -> str:
    if not postings:
        return f"No current openings found for \"{query}\". Try a broader search or a different location."

    lines = [f"Found {len(postings)} opening(s) for \"{query}\":\n"]
    for p in postings:
        line = f"**{p.title}** — {p.company}"
        meta = " · ".join(x for x in (p.location, p.employment_type) if x)
        if meta:
            line += f"\n📍 {meta}"
        if p.salary:
            line += f"\n💰 {p.salary}"
        if p.url:
            line += f"\n🔗 {p.url}"
        lines.append(line)
    return "\n\n".join(lines)


jsearch = JSearchClient(
    api_key=settings.jsearch_api_key,
    country=settings.jsearch_country,
    max_results=settings.jsearch_max_results,
)
