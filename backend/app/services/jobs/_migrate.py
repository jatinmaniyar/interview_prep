"""Idempotent SQLite migration for the persona-relevance columns.

We don't run alembic in this project yet, so this is a tiny self-contained
ALTER-TABLE-ADD-COLUMN pass. Safe to call every startup; it inspects
PRAGMA table_info and only adds what's missing.

When alembic is wired up properly, delete this and replace with a real
migration. The columns added here have defaults so they survive any
ordering against `Base.metadata.create_all()`.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

# (column_name, SQLite type + default clause)
_JOB_POSTING_ADDITIONS: list[tuple[str, str]] = [
    ("role_family",         "VARCHAR(24)"),
    ("yoe_min",             "INTEGER"),
    ("yoe_max",             "INTEGER"),
    ("is_low_signal",       "BOOLEAN DEFAULT 0"),
    ("has_system_design",   "BOOLEAN DEFAULT 0"),
    ("role_relevance",      "FLOAT DEFAULT 0.0"),
    ("engineering_quality", "FLOAT DEFAULT 0.0"),
    ("career_leverage",     "FLOAT DEFAULT 0.0"),
]


def migrate_jobs(engine: Engine) -> list[str]:
    """Add any missing columns to job_postings. Returns names of columns added."""
    added: list[str] = []
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(job_postings)"))}
        if not existing:
            return added  # table doesn't exist yet; create_all will handle it
        for col, decl in _JOB_POSTING_ADDITIONS:
            if col not in existing:
                conn.execute(text(f"ALTER TABLE job_postings ADD COLUMN {col} {decl}"))
                added.append(col)
        # Indexes — SQLite is happy with IF NOT EXISTS
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_postings_role_family ON job_postings(role_family)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_postings_is_low_signal ON job_postings(is_low_signal)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_postings_role_relevance ON job_postings(role_relevance)"))
    return added
