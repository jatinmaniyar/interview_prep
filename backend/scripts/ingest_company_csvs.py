"""Ingest company-tagged LeetCode questions from public GitHub CSVs.

Source: https://github.com/liquidslr/interview-company-wise-problems
Layout : <root>/<Company>/<period>.csv

CSV columns (typical): Difficulty, Title, Frequency, Acceptance Rate, Link, Topics

Run:
    python -m scripts.ingest_company_csvs --root data/external/interview-company-wise-problems

If the root doesn't exist, the script clones the repo automatically.
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.dialects.sqlite import insert as sqlite_insert  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import CompanyTag, Problem  # noqa: E402

REPO_URL = "https://github.com/liquidslr/interview-company-wise-problems.git"

PERIOD_MAP = {
    "thirty days": "30d",
    "three months": "90d",
    "six months": "6m",
    "more than six months": "1y",
    "all time": "alltime",
    "all": "alltime",
}


def parse_period(filename: str) -> str | None:
    name = Path(filename).stem.lower()
    name = re.sub(r"^\d+\.\s*", "", name)
    return PERIOD_MAP.get(name.strip())


def parse_id_from_link(link: str) -> int | None:
    """Slugs alone aren't enough — we look up the slug in the DB to find the id."""
    m = re.search(r"/problems/([^/]+)/?", link or "")
    return None if not m else m.group(1)  # returns slug, not int


def slug_to_id_map(db) -> dict[str, int]:
    rows = db.execute(select(Problem.id, Problem.slug)).all()
    return {slug: pid for pid, slug in rows}


def parse_freq(raw: str) -> float:
    if not raw:
        return 0.0
    raw = raw.strip().rstrip("%")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def ingest_csv(db, csv_path: Path, company: str, period: str, slug_map: dict[str, int]) -> int:
    n = 0
    with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            link = row.get("Link") or row.get("Leetcode Link") or ""
            slug = parse_id_from_link(link)
            if not slug or slug not in slug_map:
                continue
            problem_id = slug_map[slug]
            freq = parse_freq(row.get("Frequency") or row.get("Frequency (%)") or "")
            stmt = sqlite_insert(CompanyTag).values(
                problem_id=problem_id,
                company=company,
                frequency=freq,
                period=period,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[CompanyTag.problem_id, CompanyTag.company, CompanyTag.period],
                set_={"frequency": stmt.excluded.frequency},
            )
            db.execute(stmt)
            n += 1
    return n


def ensure_repo(root: Path) -> None:
    if root.exists():
        return
    root.parent.mkdir(parents=True, exist_ok=True)
    print(f"Cloning {REPO_URL} -> {root}")
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(root)], check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--root",
        default="data/external/interview-company-wise-problems",
        help="Path to the cloned repo (will clone if missing).",
    )
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    root = (project_root / args.root).resolve()
    ensure_repo(root)

    db = SessionLocal()
    try:
        slug_map = slug_to_id_map(db)
        if not slug_map:
            print("No problems found in DB — run ingest_leetcode_meta.py first.")
            return
        total = 0
        for company_dir in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
            company = company_dir.name
            for csv_path in company_dir.glob("*.csv"):
                period = parse_period(csv_path.name)
                if not period:
                    continue
                n = ingest_csv(db, csv_path, company, period, slug_map)
                total += n
                if n:
                    print(f"  {company}/{csv_path.name} -> {n} rows")
            db.commit()
        print(f"Done. Upserted {total} company tags.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
