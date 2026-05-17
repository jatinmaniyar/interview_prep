"""Scrape algo.monster for problems flagged is_premium in the DB.

Idempotent: skips problems with non-empty description_md unless --force is set.

Run:
    python -m scripts.scrape_premium_problems --limit 10
    python -m scripts.scrape_premium_problems --ids 271,1244,1268
    python -m scripts.scrape_premium_problems --all-premium
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.dialects.sqlite import insert as sqlite_insert  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Problem, Solution  # noqa: E402
from app.services.algomonster_scraper import scrape  # noqa: E402


def upsert(db, scraped) -> None:
    p = db.get(Problem, scraped.id)
    if not p:
        # algo.monster covers problems that may not be in our LeetCode meta yet —
        # create a stub so the foreign keys work.
        p = Problem(
            id=scraped.id,
            title=scraped.title,
            slug=scraped.title.lower().replace(" ", "-"),
            difficulty="Unknown",
            is_premium=True,
        )
        db.add(p)
    p.title = scraped.title or p.title
    p.description_md = scraped.description_md
    p.examples_json = scraped.to_dict()["examples_json"]
    p.constraints_md = scraped.constraints_md
    p.scraped_at = datetime.now(timezone.utc)

    # method_signature + boilerplate: extract from python solution if we can
    py = scraped.solutions.get("python", "")
    if py:
        import re
        m = re.search(r"def\s+(?!__\w+__)(\w+)\s*\(self", py)
        if m:
            p.method_signature = m.group(1)
        sig_m = re.search(r"(def\s+\w+\s*\(self[^)]*\)(?:\s*->[^:{\n]+)?)\s*:", py)
        if sig_m and not p.boilerplate_python:
            sig = sig_m.group(1).rstrip()
            p.boilerplate_python = f"class Solution:\n    {sig}:\n        # your code here\n        pass\n"

    for lang, code in scraped.solutions.items():
        stmt = sqlite_insert(Solution).values(
            problem_id=scraped.id,
            language=lang,
            code=code,
            walkthrough_md=scraped.walkthrough_md,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Solution.problem_id, Solution.language],
            set_={"code": stmt.excluded.code, "walkthrough_md": stmt.excluded.walkthrough_md},
        )
        db.execute(stmt)


def select_ids(db, args) -> list[int]:
    if args.ids:
        return [int(x) for x in args.ids.split(",")]
    q = select(Problem.id).where(Problem.is_premium == True)  # noqa: E712
    if not args.force:
        q = q.where(
            (Problem.description_md.is_(None)) | (Problem.description_md == "")
        )
    if args.limit:
        q = q.limit(args.limit)
    return [r[0] for r in db.execute(q).all()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--ids", type=str, default=None, help="Comma-separated ids")
    ap.add_argument("--all-premium", action="store_true")
    ap.add_argument("--force", action="store_true", help="Re-scrape even if already populated")
    ap.add_argument("--rate", type=float, default=1.0)
    args = ap.parse_args()

    cache_dir = settings.data_dir / "raw_html"
    db = SessionLocal()
    try:
        ids = select_ids(db, args)
        if not ids:
            print("No problems to scrape.")
            return
        print(f"Scraping {len(ids)} problems")
        for i, pid in enumerate(ids, 1):
            try:
                scraped = scrape(pid, cache_dir=cache_dir, rate_limit_s=args.rate)
                if not scraped.description_md and not scraped.solutions:
                    print(f"  [{i}/{len(ids)}] #{pid}: empty page (skipped)")
                    continue
                upsert(db, scraped)
                db.commit()
                print(
                    f"  [{i}/{len(ids)}] #{pid} {scraped.title}: "
                    f"desc={len(scraped.description_md)}c, langs={list(scraped.solutions)}"
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    print(f"  [{i}/{len(ids)}] #{pid}: not on algo.monster (skipped)")
                else:
                    print(f"  [{i}/{len(ids)}] #{pid}: HTTP {e.response.status_code} (skipped)")
                db.rollback()
            except Exception as e:
                print(f"  [{i}/{len(ids)}] #{pid}: ERROR {e}")
                db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
