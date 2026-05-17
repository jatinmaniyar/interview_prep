"""Emit JSON for problems that still need test cases.

Used by Claude Code's /generate-tests slash command — the main agent reads this
output, then dispatches one `testcase-generator` sub-agent per problem.

Output: JSON array of {id, title, description_md, constraints_md, ref_code, method}.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Problem, Solution, TestCase  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--ids", type=str, default=None)
    ap.add_argument("--min-count", type=int, default=30, help="Skip problems already at >= this many validated tests")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        if args.ids:
            ids = [int(x) for x in args.ids.split(",")]
            q = select(Problem).where(Problem.id.in_(ids))
        else:
            tc_counts = (
                select(TestCase.problem_id, func.count().label("n"))
                .where(TestCase.validated == True)  # noqa: E712
                .group_by(TestCase.problem_id)
                .subquery()
            )
            q = (
                select(Problem)
                .outerjoin(tc_counts, tc_counts.c.problem_id == Problem.id)
                .where(
                    Problem.description_md.is_not(None),
                    Problem.description_md != "",
                    (tc_counts.c.n.is_(None)) | (tc_counts.c.n < args.min_count),
                )
                .limit(args.limit)
            )

        out = []
        for p in db.execute(q).scalars().all():
            ref = db.execute(
                select(Solution).where(
                    Solution.problem_id == p.id, Solution.language == "python"
                )
            ).scalar_one_or_none()
            if not ref:
                continue
            out.append(
                {
                    "id": p.id,
                    "title": p.title,
                    "description_md": p.description_md or "",
                    "constraints_md": p.constraints_md or "",
                    "ref_code": ref.code,
                    "method": p.method_signature or "solve",
                }
            )
        print(json.dumps(out, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
