"""Empty all application tables in a disposable database (used before end-to-end runs).

Refuses to run unless the database name ends in _e2e or _test, so it cannot be pointed
at a development or production database by mistake.

Usage: DATABASE_URL=... python scripts/reset_test_database.py
"""

import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TABLES = "audit_events, review_decisions, proposed_actions, assumptions, agent_runs, tasks"


def main() -> int:
    url = os.environ.get("DATABASE_URL", "")
    database = make_url(url).database or "" if url else ""
    if not database.endswith(("_e2e", "_test")):
        print(f"Refusing to reset database {database!r}: name must end in _e2e or _test", file=sys.stderr)
        return 1
    engine = create_engine(url.replace("postgresql://", "postgresql+psycopg://", 1))
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    print(f"Reset {database}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
