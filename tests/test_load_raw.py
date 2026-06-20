"""Tests for the raw loader's read -> transform -> insert wiring.

A real Postgres run happens via Docker (`make db-up && make db-init && make
load`). These tests validate everything up to the database driver by faking the
psycopg2 connection/cursor and `execute_values`, so the row-shaping logic and
source wiring are covered without a server.
"""

from __future__ import annotations

import db.load_raw as lr
from ingestion.config import Settings
from ingestion.run_ingestion import run

# Stub record counts per term: ebay=12, reddit=15, trends=13 (see ingestion).
_EBAY_PER_TERM = 12
_REDDIT_PER_TERM = 15
_TRENDS_PER_TERM = 13
_STOCKX_STUB_ROWS = 40  # StockXClient stub default (run() calls fetch_sales())


class FakeCursor:
    def __init__(self) -> None:
        self.ev_calls: list[tuple[str, list]] = []
        self.rowcount = 0
        self._shoes: list[str] = []

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def execute(self, sql: str, params=None) -> None:
        self._last_sql = sql

    def fetchall(self) -> list[tuple[str, int]]:
        return [(term, i + 1) for i, term in enumerate(self._shoes)]


class FakeConn:
    def __init__(self, cur: FakeCursor) -> None:
        self._cur = cur
        self.committed = False

    def __enter__(self) -> FakeConn:
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def cursor(self) -> FakeCursor:
        return self._cur

    def commit(self) -> None:
        self.committed = True


def _patch_db(monkeypatch) -> FakeCursor:
    cur = FakeCursor()

    def fake_execute_values(cursor, sql, rows):
        cursor.ev_calls.append((sql, list(rows)))
        cursor.rowcount = len(rows)
        if "dim_shoes" in sql:
            cursor._shoes = sorted({r[0] for r in rows})

    monkeypatch.setattr(lr, "execute_values", fake_execute_values)
    monkeypatch.setattr(lr.psycopg2, "connect", lambda dsn: FakeConn(cur))
    return cur


def test_load_all_inserts_every_record(tmp_path, monkeypatch) -> None:
    settings = Settings(
        watchlist=["Air Jordan 1", "Yeezy 350"],
        subreddits=["sneakers"],
        raw_dir=tmp_path,
        stockx_csv_path=tmp_path / "missing.csv",  # force StockX stub mode
    )
    run(settings, stub_trends=True)  # land raw JSON in tmp_path

    _patch_db(monkeypatch)
    inserted = lr.load_all("postgresql://fake", raw_dir=tmp_path)

    # Current pipeline produces Trends + StockX only; eBay/Reddit are future
    # extensions, so their fact loads are present-but-empty.
    assert inserted["fact_search_interest"] == _TRENDS_PER_TERM * 2
    assert inserted["fact_sales_stockx"] == _STOCKX_STUB_ROWS
    assert inserted["fact_sales_ebay"] == 0
    assert inserted["fact_social_posts"] == 0
    # StockX stub spans 4 distinct shoes, each with one release date.
    assert inserted["dim_drops"] == 4


def test_load_all_builds_correct_row_widths(tmp_path, monkeypatch) -> None:
    settings = Settings(
        watchlist=["Air Jordan 1"],
        subreddits=["sneakers"],
        raw_dir=tmp_path,
        stockx_csv_path=tmp_path / "missing.csv",  # force StockX stub mode
    )
    run(settings, stub_trends=True)

    cur = _patch_db(monkeypatch)
    lr.load_all("postgresql://fake", raw_dir=tmp_path)

    widths = {}
    for sql, rows in cur.ev_calls:
        if "fact_sales" in sql:
            widths["sales"] = len(rows[0])
        elif "fact_social_posts" in sql:
            widths["posts"] = len(rows[0])
        elif "fact_search_interest" in sql:
            widths["interest"] = len(rows[0])
        elif "dim_drops" in sql:
            widths["drops"] = len(rows[0])
    # Current run inserts StockX sales, Trends interest, and derived drops.
    # Column counts must match the INSERT column lists.
    assert widths == {"sales": 9, "interest": 4, "drops": 4}


def test_load_all_handles_empty_raw_dir(tmp_path, monkeypatch) -> None:
    _patch_db(monkeypatch)
    inserted = lr.load_all("postgresql://fake", raw_dir=tmp_path)
    assert set(inserted) == {
        "dim_drops",
        "fact_sales_ebay",
        "fact_sales_stockx",
        "fact_social_posts",
        "fact_search_interest",
    }
    assert all(v == 0 for v in inserted.values())
