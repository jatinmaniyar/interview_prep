"""Greenhouse public job-board provider.

Docs: https://developers.greenhouse.io/job-board.html
Endpoint: https://boards-api.greenhouse.io/v1/boards/{org}/jobs?content=true
No API key required.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

BASE = "https://boards-api.greenhouse.io/v1/boards/{org}/jobs"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _get(org: str) -> dict:
    url = BASE.format(org=org)
    with httpx.Client(timeout=20.0, headers={"User-Agent": "interview-prep/0.1"}) as c:
        r = c.get(url, params={"content": "true"})
        r.raise_for_status()
        return r.json()


def fetch(external_org: str) -> Iterable[dict]:
    """Yield RawJob dicts for a Greenhouse board token (e.g. "stripe")."""
    data = _get(external_org)
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name")
        updated = j.get("updated_at") or j.get("first_published")
        try:
            posted_at = datetime.fromisoformat(updated.replace("Z", "+00:00")) if updated else None
            if posted_at and posted_at.tzinfo:
                posted_at = posted_at.replace(tzinfo=None)
        except Exception:
            posted_at = None
        yield {
            "source": "greenhouse",
            "external_id": str(j["id"]),
            "external_org": external_org,
            "title": j.get("title") or "",
            "company_name": (j.get("company_name") or "").strip() or None,
            "location": loc,
            "url": j.get("absolute_url"),
            "description_html": j.get("content"),
            "posted_at": posted_at,
            "departments": [d.get("name") for d in j.get("departments") or [] if d.get("name")],
            "offices": [o.get("name") for o in j.get("offices") or [] if o.get("name")],
            "raw": j,
        }
