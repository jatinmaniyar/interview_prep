"""Ingest job postings from configured sources.

Usage:
    python -m scripts.ingest_jobs                  # all enabled
    python -m scripts.ingest_jobs --source greenhouse --org stripe
    python -m scripts.ingest_jobs --seed           # load content/job_sources.yaml first
    python -m scripts.ingest_jobs --rescore        # also recompute JobScore for all rows

Notes:
- Idempotent: jobs not seen this run are marked is_active=False.
- Reposted jobs (reactivated after being inactive) get repost_count++.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from app.db import SessionLocal, Base, engine  # noqa: E402
from app import models  # noqa: F401, E402  # registers tables
from app.models import JobSourceRegistry, Company  # noqa: E402
from app.services.jobs import ingest, scoring  # noqa: E402
from app.services.jobs.ingest import _ensure_company  # noqa: E402
from sqlalchemy import select  # noqa: E402


def seed_from_yaml(db, path: Path) -> int:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    n = 0
    for row in data.get("sources", []):
        co = _ensure_company(db, row.get("company_name") or row["external_org"])
        reg = db.execute(
            select(JobSourceRegistry).where(
                JobSourceRegistry.source == row["source"],
                JobSourceRegistry.external_org == row["external_org"],
            )
        ).scalar_one_or_none()
        if reg:
            reg.company_id = co.id
            reg.enabled = row.get("enabled", True)
        else:
            db.add(JobSourceRegistry(
                source=row["source"],
                external_org=row["external_org"],
                company_id=co.id,
                enabled=row.get("enabled", True),
            ))
            n += 1
    db.commit()
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source")
    ap.add_argument("--org")
    ap.add_argument("--seed", action="store_true",
                    help="Load content/job_sources.yaml into the registry before ingesting.")
    ap.add_argument("--rescore", action="store_true")
    ap.add_argument("--skip-fetch", action="store_true",
                    help="Don't fetch; only run --seed and/or --rescore.")
    args = ap.parse_args()

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if args.seed:
            seed_path = Path(__file__).resolve().parents[1] / "content" / "job_sources.yaml"
            added = seed_from_yaml(db, seed_path)
            print(f"seeded: {added} new source rows")

        results = []
        if not args.skip_fetch:
            if args.source and args.org:
                results = [ingest.ingest_source(db, args.source, args.org)]
            else:
                results = ingest.ingest_all_enabled(db)

        if args.rescore or results:
            n = scoring.rescore_all(db)
            print(f"rescored {n} jobs")

        summary = [
            {"source": r.source, "org": r.org, "fetched": r.fetched, "new": r.new,
             "deactivated": r.deactivated, "errors": r.errors[:3]}
            for r in results
        ]
        print(json.dumps(summary, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
