"""Persist an AI-generated summary onto a JobPosting row.

Used by the /rank-jobs slash command. One row at a time; idempotent.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal  # noqa: E402
from app.models import JobPosting  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--md", required=True)
    args = ap.parse_args()

    db = SessionLocal()
    try:
        j = db.get(JobPosting, args.id)
        if not j:
            print(json.dumps({"ok": False, "error": "not found"}))
            return 1
        j.ai_summary_md = args.md
        db.commit()
        print(json.dumps({"ok": True, "id": j.id}))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
