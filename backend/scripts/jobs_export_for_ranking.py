"""Print JSON {profile, jobs[]} for the /rank-jobs slash command.

Only includes top-scored active jobs without an ai_summary_md yet.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import desc, select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import JobPosting, UserJobProfile  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    db = SessionLocal()
    try:
        p = db.get(UserJobProfile, 1)
        profile = {
            "target_titles": json.loads((p and p.target_titles_json) or "[]"),
            "target_companies": json.loads((p and p.target_companies_json) or "[]"),
            "stack": json.loads((p and p.stack_json) or "[]"),
            "seniority": p.seniority if p else None,
            "target_min_comp": p.target_min_comp if p else None,
            "preferred_remote": p.preferred_remote if p else None,
            "weaknesses_md": (p.weaknesses_md if p else None),
        }
        rows = db.execute(
            select(JobPosting).where(
                JobPosting.is_active == True,  # noqa: E712
                JobPosting.ai_summary_md.is_(None),
                JobPosting.duplicate_of.is_(None),
            ).order_by(desc(JobPosting.job_score)).limit(args.limit)
        ).scalars().all()

        out = []
        for j in rows:
            out.append({
                "id": j.id,
                "title": j.title,
                "company_name": j.company_name,
                "location": j.location,
                "remote": j.remote,
                "seniority": j.seniority,
                "salary_min": j.salary_min,
                "salary_max": j.salary_max,
                "salary_currency": j.salary_currency,
                "stack": json.loads(j.stack_json or "[]"),
                "interview_style": j.interview_style,
                "score_breakdown": json.loads(j.score_breakdown_json or "{}"),
                "description_excerpt": (j.description_md or "")[:600],
                "url": j.url,
            })
        print(json.dumps({"profile": profile, "jobs": out}, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
