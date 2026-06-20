"""One-time seeder for a remote (managed) Postgres such as Neon.

Reads `DATABASE_URL`, applies the schema and seeds, runs ingestion and the
loader, then runs `dbt build` against the same database. Use this to populate a
cloud database before deploying the dashboard.

Usage:
    export DATABASE_URL="postgresql://user:pass@host/db?sslmode=require"
    python scripts/seed_remote.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg2

ROOT = Path(__file__).resolve().parent.parent


def _apply_sql(dsn: str, *sql_files: str) -> None:
    """Execute each SQL file against the database."""
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for name in sql_files:
                sql = (ROOT / name).read_text(encoding="utf-8")
                cur.execute(sql)
                print(f"applied {name}")
    finally:
        conn.close()


def _dbt_env(dsn: str) -> dict[str, str]:
    """Translate a DATABASE_URL into the DBT_PG_* env vars the profile reads."""
    u = urlparse(dsn)
    env = dict(os.environ)
    env.update(
        DBT_PG_HOST=u.hostname or "localhost",
        DBT_PG_PORT=str(u.port or 5432),
        DBT_PG_USER=u.username or "",
        DBT_PG_PASSWORD=u.password or "",
        DBT_PG_DBNAME=(u.path or "/").lstrip("/") or "postgres",
        DBT_PG_SCHEMA=os.getenv("DBT_PG_SCHEMA", "analytics"),
        DBT_PG_SSLMODE=os.getenv("DBT_PG_SSLMODE", "require"),
        DBT_PROFILES_DIR=".",
    )
    return env


def main() -> int:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set. Export your Neon connection string first.")
        return 1

    print("1/4  applying schema + seeds ...")
    _apply_sql(dsn, "db/schema.sql", "db/seeds.sql")

    print("2/4  running ingestion ...")
    subprocess.run([sys.executable, "-m", "ingestion.run_ingestion"], cwd=ROOT, check=True)

    print("3/4  loading raw data ...")
    subprocess.run([sys.executable, "-m", "db.load_raw"], cwd=ROOT, check=True)

    print("4/4  building dbt models + tests ...")
    subprocess.run(
        ["dbt", "build"], cwd=ROOT / "dbt_project", env=_dbt_env(dsn), check=True
    )

    print("Done. The remote database is seeded and the marts are built.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
