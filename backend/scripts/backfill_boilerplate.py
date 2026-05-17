"""Backfill boilerplate_python from existing scraped Python solutions.

Reads Problem + Solution rows already in the DB — no network calls.
Only updates problems where boilerplate_python is currently NULL.

Usage:
    python -m scripts.backfill_boilerplate
    python -m scripts.backfill_boilerplate --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Problem, Solution  # noqa: E402

METHOD_RE = re.compile(r"(def\s+(?!__init__)(\w+)\s*\(self[^)]*\)(?:\s*->[^:{\n]+)?)\s*:")


def extract_boilerplate(code: str) -> str | None:
    # Find the Solution class block, then extract its first non-dunder method.
    sol_match = re.search(r"class Solution.*?(?=\nclass |\Z)", code, re.S)
    search_in = sol_match.group(0) if sol_match else code
    m = METHOD_RE.search(search_in)
    if not m:
        return None
    sig = m.group(1).rstrip()
    return f"class Solution:\n    {sig}:\n        # your code here\n        pass\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        problems = db.execute(
            select(Problem).where(Problem.boilerplate_python.is_(None))
        ).scalars().all()

        solutions = {
            s.problem_id: s.code
            for s in db.execute(
                select(Solution).where(Solution.language == "python")
            ).scalars().all()
        }

        updated = skipped = 0
        for p in problems:
            code = solutions.get(p.id)
            if not code:
                skipped += 1
                continue
            boilerplate = extract_boilerplate(code)
            if not boilerplate:
                skipped += 1
                continue
            if args.dry_run:
                print(f"  [{p.id}] {p.title}")
                print(f"    {boilerplate.splitlines()[1].strip()}")
            else:
                p.boilerplate_python = boilerplate
                updated += 1

        if not args.dry_run:
            db.commit()
            print(f"Updated {updated} problems, skipped {skipped} (no Python solution).")
        else:
            print(f"\nDry run: would update {len(problems) - skipped}, skip {skipped}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
