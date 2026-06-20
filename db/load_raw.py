"""Load raw ingestion JSON from data/raw/ into Postgres.

Reads the timestamped files written by the ingestion layer and bulk-loads them
into the star schema using ``psycopg2.extras.execute_values`` (one round trip
per source, not row-by-row). The load is idempotent: every fact has a natural
-key unique constraint and inserts use ``ON CONFLICT DO NOTHING``, so re-running
against the same raw files inserts zero new rows.

Connection comes from the ``DATABASE_URL`` env var, e.g.
``postgresql://sneaker:sneaker@localhost:5432/sneaker_intel``.

Run with: ``python -m db.load_raw`` (or ``make load``).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import execute_values

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
RAW_DIR: Path = PROJECT_ROOT / "data" / "raw"


def get_dsn() -> str:
    """Return the Postgres DSN from the environment, or raise a clear error."""
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and set it, e.g. "
            "postgresql://sneaker:sneaker@localhost:5432/sneaker_intel"
        )
    return dsn


def _read_source(raw_dir: Path, source: str) -> list[dict[str, Any]]:
    """Read and parse every raw file for one source, returning record dicts."""
    records: list[dict[str, Any]] = []
    for path in sorted(raw_dir.glob(f"{source}_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        records.extend(payload.get("records", []))
    logger.info("Read %d %s records from %s", len(records), source, raw_dir)
    return records


def upsert_shoes(cur, search_terms: set[str]) -> dict[str, int]:
    """Ensure a dim_shoes row exists per search term; return term -> shoe_key."""
    if search_terms:
        execute_values(
            cur,
            "insert into dim_shoes (search_term) values %s "
            "on conflict (search_term) do nothing",
            [(term,) for term in sorted(search_terms)],
        )
    cur.execute("select search_term, shoe_key from dim_shoes")
    return {term: key for term, key in cur.fetchall()}


def load_sales(cur, records: list[dict[str, Any]], shoe_map: dict[str, int]) -> int:
    """Bulk-insert eBay sold listings; return the number of new rows."""
    rows = [
        (
            shoe_map[r["search_term"]],
            r["source_item_id"],
            r["title"],
            r["sold_price"],
            r["currency"],
            r["sold_date"],
            r["condition"],
            r["size"],
        )
        for r in records
    ]
    if not rows:
        return 0
    execute_values(
        cur,
        "insert into fact_sales "
        "(shoe_key, source_item_id, title, sold_price, currency, sold_date, "
        "condition, size) values %s on conflict (source_item_id) do nothing",
        rows,
    )
    return cur.rowcount


def load_social_posts(
    cur, records: list[dict[str, Any]], shoe_map: dict[str, int]
) -> int:
    """Bulk-insert Reddit posts; return the number of new rows."""
    rows = [
        (
            shoe_map[r["search_term"]],
            r["source_post_id"],
            r["subreddit"],
            r["title"],
            r["score"],
            r["num_comments"],
            r["created_utc"],
        )
        for r in records
    ]
    if not rows:
        return 0
    execute_values(
        cur,
        "insert into fact_social_posts "
        "(shoe_key, source_post_id, subreddit, title, score, num_comments, "
        "created_utc) values %s on conflict (source_post_id) do nothing",
        rows,
    )
    return cur.rowcount


def load_search_interest(
    cur, records: list[dict[str, Any]], shoe_map: dict[str, int]
) -> int:
    """Bulk-insert Google Trends points; return the number of new rows."""
    rows = [
        (
            shoe_map[r["search_term"]],
            r["point_date"],
            r["interest"],
            r["geo"],
        )
        for r in records
    ]
    if not rows:
        return 0
    execute_values(
        cur,
        "insert into fact_search_interest (shoe_key, point_date, interest, geo) "
        "values %s on conflict (shoe_key, point_date, geo) do nothing",
        rows,
    )
    return cur.rowcount


def load_all(dsn: str, raw_dir: Path = RAW_DIR) -> dict[str, int]:
    """Load every source from ``raw_dir`` into Postgres; return rows inserted."""
    sales = _read_source(raw_dir, "ebay")
    posts = _read_source(raw_dir, "reddit")
    interest = _read_source(raw_dir, "trends")

    search_terms = {
        r["search_term"] for batch in (sales, posts, interest) for r in batch
    }

    inserted: dict[str, int] = {}
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            shoe_map = upsert_shoes(cur, search_terms)
            inserted["fact_sales"] = load_sales(cur, sales, shoe_map)
            inserted["fact_social_posts"] = load_social_posts(cur, posts, shoe_map)
            inserted["fact_search_interest"] = load_search_interest(
                cur, interest, shoe_map
            )
        conn.commit()

    logger.info("Load complete. Rows inserted: %s", inserted)
    return inserted


def main() -> None:
    """CLI entrypoint."""
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    load_all(get_dsn())


if __name__ == "__main__":
    main()
