"""Create all tables fresh. Use for first-time setup; afterwards prefer alembic."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base, engine
from app import models  # noqa: F401
from app.services.jobs._migrate import migrate_jobs

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    added = migrate_jobs(engine)
    if added:
        print(f"Migrated job_postings: added columns {added}")
    print(f"Created tables in {engine.url}")
