"""Populate the `problems` table with metadata from LeetCode's public GraphQL.

Idempotent: existing rows are upserted on every run.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.dialects.sqlite import insert as sqlite_insert  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Problem  # noqa: E402
from app.services.leetcode_meta import fetch_all  # noqa: E402


def main() -> None:
    db = SessionLocal()
    count = 0
    try:
        for q in fetch_all():
            stmt = sqlite_insert(Problem).values(
                id=q["id"],
                title=q["title"],
                slug=q["slug"],
                difficulty=q["difficulty"],
                is_premium=q["is_premium"],
                acceptance_pct=q["acceptance_pct"],
                topics_json=json.dumps(q["topics"]),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[Problem.id],
                set_={
                    "title": stmt.excluded.title,
                    "slug": stmt.excluded.slug,
                    "difficulty": stmt.excluded.difficulty,
                    "is_premium": stmt.excluded.is_premium,
                    "acceptance_pct": stmt.excluded.acceptance_pct,
                    "topics_json": stmt.excluded.topics_json,
                },
            )
            db.execute(stmt)
            count += 1
            if count % 100 == 0:
                db.commit()
                print(f"  ...{count} problems")
        db.commit()
        print(f"Done. Upserted {count} problems.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
