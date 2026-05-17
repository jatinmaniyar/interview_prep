"""Lever public postings provider.

Endpoint: https://api.lever.co/v0/postings/{org}?mode=json
No API key required.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

BASE = "https://api.lever.co/v0/postings/{org}"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _get(org: str) -> list:
    url = BASE.format(org=org)
    with httpx.Client(timeout=20.0, headers={"User-Agent": "interview-prep/0.1"}) as c:
        r = c.get(url, params={"mode": "json"})
        r.raise_for_status()
        return r.json()


def fetch(external_org: str) -> Iterable[dict]:
    for j in _get(external_org):
        cat = j.get("categories") or {}
        loc = cat.get("location")
        created = j.get("createdAt")  # ms epoch
        try:
            posted_at = datetime.utcfromtimestamp(created / 1000) if created else None
        except Exception:
            posted_at = None
        yield {
            "source": "lever",
            "external_id": j.get("id") or j.get("lever_id") or j.get("hostedUrl", ""),
            "external_org": external_org,
            "title": j.get("text") or "",
            "company_name": None,  # lever board belongs to one org; we'll fill from registry
            "location": loc,
            "url": j.get("hostedUrl") or j.get("applyUrl"),
            "description_html": j.get("descriptionPlain") or j.get("description"),
            "posted_at": posted_at,
            "departments": [cat.get("team")] if cat.get("team") else [],
            "commitment": cat.get("commitment"),
            "workplace": j.get("workplaceType"),
            "raw": j,
        }
