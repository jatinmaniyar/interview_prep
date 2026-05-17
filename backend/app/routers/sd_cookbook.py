"""SD Cookbook router — problem inventory (names only) + curated reference sections.

No problem detail / solution endpoints. The inventory comes from the DB
(`sd_problems` + `sd_company_tags`, seeded by `scripts/seed_sd_cookbook.py`);
the curated sections come from YAML files under `backend/content/sd_cookbook/`
and are loaded once at import time.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import SDCompanyTag, SDProblem

router = APIRouter(tags=["sd-cookbook"])


CONTENT_DIR = Path(__file__).resolve().parents[2] / "content" / "sd_cookbook"

# Section files served by /sd-cookbook. Order matches the left-nav order.
COOKBOOK_FILES = [
    "framework.yaml",
    "patterns.yaml",
    "building_blocks.yaml",
    "tradeoffs.yaml",
    "numbers.yaml",
    "consistency.yaml",
    "solid.yaml",
    "concurrency.yaml",
    "tips.yaml",
    "companies.yaml",
]


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


@lru_cache(maxsize=1)
def _load_cookbook_sections() -> list[dict]:
    """Read and cache the 10 cookbook YAML files. Restart the server to refresh."""
    sections: list[dict] = []
    for name in COOKBOOK_FILES:
        path = CONTENT_DIR / name
        with path.open(encoding="utf-8") as f:
            sections.append(yaml.safe_load(f))
    return sections


@router.get("/sd-problems")
def list_sd_problems(
    type: str | None = None,
    company: list[str] | None = Query(default=None),
    topic: str | None = None,
    difficulty: list[str] | None = Query(default=None),
    q: str | None = None,
    limit: int = 500,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List the problem inventory. Names + tags only — no solutions."""
    stmt = select(SDProblem)
    if type:
        stmt = stmt.where(SDProblem.type == type)
    if topic:
        stmt = stmt.where(SDProblem.topic == topic)
    if difficulty:
        stmt = stmt.where(SDProblem.difficulty.in_(difficulty))
    if q:
        stmt = stmt.where(SDProblem.title.ilike(f"%{q}%"))
    if company:
        stmt = (
            stmt.join(SDCompanyTag, SDCompanyTag.sd_problem_id == SDProblem.id)
            .where(SDCompanyTag.company.in_(company))
            .distinct()
        )
    stmt = stmt.order_by(SDProblem.type, SDProblem.title).limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()

    ids = [r.id for r in rows]
    company_map: dict[int, list[str]] = {i: [] for i in ids}
    if ids:
        tag_rows = db.execute(
            select(SDCompanyTag.sd_problem_id, SDCompanyTag.company)
            .where(SDCompanyTag.sd_problem_id.in_(ids))
            .order_by(SDCompanyTag.company)
        ).all()
        for pid, c in tag_rows:
            company_map[pid].append(c)

    return [
        {
            "id": r.id,
            "title": r.title,
            "type": r.type,
            "topic": r.topic,
            "difficulty": r.difficulty,
            "summary": r.summary,
            "tags": _parse_tags(r.tags_json),
            "companies": company_map[r.id],
        }
        for r in rows
    ]


@router.get("/sd-companies")
def list_sd_companies(db: Session = Depends(get_db)):
    """Distinct companies + counts for the inventory filter dropdown."""
    rows = db.execute(
        select(
            SDCompanyTag.company,
            func.count(func.distinct(SDCompanyTag.sd_problem_id)).label("count"),
        )
        .group_by(SDCompanyTag.company)
        .order_by(func.count(func.distinct(SDCompanyTag.sd_problem_id)).desc())
    ).all()
    return [{"company": c, "count": n} for c, n in rows]


@router.get("/sd-topics")
def list_sd_topics(db: Session = Depends(get_db)):
    """Distinct topics + counts for the inventory filter dropdown."""
    rows = db.execute(
        select(SDProblem.topic, func.count())
        .where(SDProblem.topic.isnot(None))
        .group_by(SDProblem.topic)
        .order_by(func.count().desc())
    ).all()
    return [{"topic": t, "count": n} for t, n in rows if t]


@router.get("/sd-cookbook")
def get_cookbook():
    """Return all 10 curated sections in display order. Loaded once at startup."""
    return {"sections": _load_cookbook_sections()}
