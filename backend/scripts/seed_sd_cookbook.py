"""Wipe sd_problems + sd_company_tags and reseed from the curated cookbook YAML.

Reads `backend/content/sd_cookbook/problems.yaml` (curated inventory of HLD/LLD
problem names + company tags + topic/difficulty/summary), drops both tables,
recreates them from the current ORM schema, and inserts a row per problem
plus per-(problem, company) company tag.

Idempotent: re-running with the same YAML reproduces the same DB state.

The non-inventory cookbook sections live as YAML on disk and are served
directly by the router — they're not stored in the DB.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import SDCompanyTag, SDProblem  # noqa: E402

CONTENT_DIR = Path(__file__).resolve().parents[1] / "content" / "sd_cookbook"


def _reset_tables() -> None:
    """Drop+recreate sd_problems and sd_company_tags. Other tables untouched."""
    SDCompanyTag.__table__.drop(engine, checkfirst=True)
    SDProblem.__table__.drop(engine, checkfirst=True)
    Base.metadata.create_all(engine, tables=[SDProblem.__table__, SDCompanyTag.__table__])


def _load_problems() -> list[dict]:
    path = CONTENT_DIR / "problems.yaml"
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    items = data.get("problems") or []
    if not items:
        raise RuntimeError(f"no problems found in {path}")
    return items


def main() -> None:
    print(f"loading inventory from {CONTENT_DIR / 'problems.yaml'}")
    problems = _load_problems()
    print(f"  {len(problems)} entries")

    print("wiping sd_problems + sd_company_tags")
    _reset_tables()

    db = SessionLocal()
    try:
        company_rows = 0
        for p in problems:
            tags = p.get("tags") or []
            row = SDProblem(
                title=p["title"],
                type=p["type"],
                topic=p.get("topic"),
                difficulty=p.get("difficulty"),
                summary=p.get("summary"),
                tags_json=json.dumps(tags) if tags else None,
            )
            db.add(row)
            db.flush()  # populate row.id for the company tags below
            for company in p.get("companies") or []:
                db.add(
                    SDCompanyTag(
                        sd_problem_id=row.id,
                        company=company,
                        confidence=1.0,
                        source="seed",
                    )
                )
                company_rows += 1
        db.commit()
        print(f"  inserted {len(problems)} problems, {company_rows} company tags")
    finally:
        db.close()


if __name__ == "__main__":
    main()
