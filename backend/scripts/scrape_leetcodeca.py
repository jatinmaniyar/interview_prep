"""Scrape leetcode.ca for problem descriptions + solutions.

Enumerates all problem URLs from the sitemap, then fetches only the problems
that exist in the DB (premium by default, --all for everything).

Run:
    python -m scripts.scrape_leetcodeca                  # premium problems
    python -m scripts.scrape_leetcodeca --all            # all problems in DB
    python -m scripts.scrape_leetcodeca --ids 156,158
    python -m scripts.scrape_leetcodeca --clean          # wipe then re-scrape premium
    python -m scripts.scrape_leetcodeca --all --clean    # wipe then re-scrape all
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select, update  # noqa: E402
from sqlalchemy.dialects.sqlite import insert as sqlite_insert  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Problem, Solution  # noqa: E402
from app.services.leetcodeca_scraper import fetch_id_url_map, scrape  # noqa: E402


def clean_db(db) -> None:
    """Wipe all scraped content so everything is re-populated from leetcode.ca."""
    db.execute(delete(Solution))
    db.execute(
        update(Problem).values(
            description_md=None,
            constraints_md=None,
            examples_json=None,
            method_signature=None,
            boilerplate_python=None,
            boilerplate_cpp=None,
            scraped_at=None,
        )
    )
    db.commit()
    print("Cleaned: solutions deleted, description/boilerplate fields reset on all problems.")


def upsert(db, scraped, problem: Problem) -> None:
    problem.title = scraped.title or problem.title
    problem.description_md = scraped.description_md or problem.description_md
    problem.constraints_md = scraped.constraints_md or problem.constraints_md
    problem.scraped_at = datetime.now(timezone.utc)

    py = scraped.solutions.get("python", "")
    if py:
        m = re.search(r"def\s+(?!__\w+__)(\w+)\s*\(self", py)
        if m:
            problem.method_signature = m.group(1)
        sig_m = re.search(r"(def\s+\w+\s*\(self[^)]*\)(?:\s*->[^:{\n]+)?)\s*:", py)
        if sig_m:
            sig = sig_m.group(1).rstrip()
            problem.boilerplate_python = (
                f"class Solution:\n    {sig}:\n        # your code here\n        pass\n"
            )

    cpp = scraped.solutions.get("cpp", "")
    if cpp:
        sig_m = re.search(r"public:\s*\n\s*(.+\([^)]*\))\s*\{", cpp)
        if sig_m:
            sig = sig_m.group(1).strip()
            problem.boilerplate_cpp = (
                f"class Solution {{\n public:\n  {sig} {{\n    // your code here\n  }}\n}};\n"
            )

    for lang, code in scraped.solutions.items():
        stmt = sqlite_insert(Solution).values(
            problem_id=scraped.id,
            language=lang,
            code=code,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Solution.problem_id, Solution.language],
            set_={"code": stmt.excluded.code},
        )
        db.execute(stmt)


def select_ids(db, args) -> list[int]:
    if args.ids:
        return [int(x) for x in args.ids.split(",")]
    q = select(Problem.id).order_by(Problem.id)
    if not args.all_:
        q = q.where(Problem.is_premium == True)  # noqa: E712
    if args.limit:
        q = q.limit(args.limit)
    return [r[0] for r in db.execute(q).all()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--ids", type=str, default=None, help="Comma-separated problem IDs")
    ap.add_argument("--all", action="store_true", dest="all_", help="Scrape all problems (default: premium only)")
    ap.add_argument("--clean", action="store_true", help="Wipe all scraped data before scraping")
    ap.add_argument("--rate", type=float, default=0.5, help="Seconds between requests")
    ap.add_argument("--no-cache", action="store_true", help="Skip HTML cache")
    args = ap.parse_args()

    cache_dir = None if args.no_cache else settings.data_dir / "raw_html"
    sitemap_cache = None if args.no_cache else settings.data_dir / "leetcodeca_sitemap.xml"

    db = SessionLocal()
    try:
        if args.clean:
            clean_db(db)

        print("Fetching sitemap from leetcode.ca …")
        id_url_map = fetch_id_url_map(cache_path=sitemap_cache)
        print(f"Sitemap has {len(id_url_map)} problem URLs")

        ids = select_ids(db, args)
        if not ids:
            print("No problems found in DB.")
            return

        # Only scrape problems that leetcode.ca actually covers
        covered = [(pid, id_url_map[pid]) for pid in ids if pid in id_url_map]
        missing = len(ids) - len(covered)
        print(f"Scraping {len(covered)} problems ({missing} not on leetcode.ca)")

        ok = skipped = errors = 0
        for i, (pid, url) in enumerate(covered, 1):
            problem = db.get(Problem, pid)
            if not problem:
                continue
            try:
                scraped = scrape(pid, url, cache_dir=cache_dir, rate_limit_s=args.rate)
                if not scraped.description_md and not scraped.solutions:
                    print(f"  [{i}/{len(covered)}] #{pid}: empty page (skipped)")
                    skipped += 1
                    continue
                upsert(db, scraped, problem)
                db.commit()
                langs = list(scraped.solutions)
                print(f"  [{i}/{len(covered)}] #{pid} {scraped.title}: langs={langs}")
                ok += 1
            except httpx.HTTPStatusError as e:
                label = "not found" if e.response.status_code == 404 else f"HTTP {e.response.status_code}"
                print(f"  [{i}/{len(covered)}] #{pid}: {label} (skipped)")
                skipped += 1
                db.rollback()
            except Exception as e:
                print(f"  [{i}/{len(covered)}] #{pid}: ERROR {e}")
                errors += 1
                db.rollback()

        print(f"\nDone: {ok} scraped, {skipped} skipped, {errors} errors")
    finally:
        db.close()


if __name__ == "__main__":
    main()
