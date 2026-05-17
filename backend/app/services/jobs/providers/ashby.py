"""Ashby public job-board provider.

Endpoint: https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true
No API key required.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

BASE = "https://api.ashbyhq.com/posting-api/job-board/{org}"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _get(org: str) -> dict:
    url = BASE.format(org=org)
    with httpx.Client(timeout=20.0, headers={"User-Agent": "interview-prep/0.1"}) as c:
        r = c.get(url, params={"includeCompensation": "true"})
        r.raise_for_status()
        return r.json()


def fetch(external_org: str) -> Iterable[dict]:
    data = _get(external_org)
    for j in data.get("jobs", []):
        published = j.get("publishedAt") or j.get("updatedAt")
        try:
            posted_at = datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None
            if posted_at and posted_at.tzinfo:
                posted_at = posted_at.replace(tzinfo=None)
        except Exception:
            posted_at = None

        comp = j.get("compensation") or {}
        salary_min = salary_max = None
        currency = None
        try:
            summary = comp.get("compensationTierSummary") or ""
            # ashby returns e.g. "$150K – $200K • Offers Equity"; we'll parse cheap.
            from .._normalize import parse_salary_range
            salary_min, salary_max, currency = parse_salary_range(summary)
        except Exception:
            pass

        yield {
            "source": "ashby",
            "external_id": str(j.get("id") or j.get("jobUrl") or ""),
            "external_org": external_org,
            "title": j.get("title") or "",
            "company_name": None,
            "location": j.get("locationName") or j.get("location"),
            "url": j.get("jobUrl") or j.get("applyUrl"),
            "description_html": j.get("descriptionHtml") or j.get("descriptionPlain"),
            "posted_at": posted_at,
            "departments": [j.get("department")] if j.get("department") else [],
            "workplace": j.get("workplaceType") or j.get("employmentType"),
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_currency": currency,
            "raw": j,
        }
