"""Tests for the ingestion layer, exercised entirely in stub mode.

These run without API keys or network access: each client's stub path yields
synthetic records, and the entrypoint lands them as JSON.
"""

from __future__ import annotations

import json
from datetime import date, datetime

from ingestion.config import Settings
from ingestion.ebay import EbayClient, SoldListing
from ingestion.reddit import RedditClient, SocialSignal
from ingestion.run_ingestion import run
from ingestion.storage import write_raw
from ingestion.trends import TrendPoint, TrendsClient


def test_ebay_stub_yields_valid_listings() -> None:
    client = EbayClient(stub=True)
    listings = list(client.fetch_sold_listings("Air Jordan 1", limit=5))
    assert listings, "stub should yield listings"
    assert all(isinstance(x, SoldListing) for x in listings)
    assert all(x.sold_price > 0 for x in listings)
    assert all(x.search_term == "Air Jordan 1" for x in listings)


def test_ebay_stub_is_deterministic() -> None:
    a = list(EbayClient(stub=True).fetch_sold_listings("Yeezy 350"))
    b = list(EbayClient(stub=True).fetch_sold_listings("Yeezy 350"))
    assert [x.source_item_id for x in a] == [x.source_item_id for x in b]


def test_ebay_size_parsing() -> None:
    assert EbayClient._parse_size("Nike Dunk Low Panda US 10.5 New") == 10.5
    assert EbayClient._parse_size("Air Jordan 1 no size here") is None
    assert EbayClient._parse_size("Lot of 99 laces") is None  # out of size range


def test_reddit_stub_yields_valid_signals() -> None:
    client = RedditClient(subreddits=["sneakers", "Sneakers"], stub=True)
    signals = list(client.fetch_posts("New Balance 550"))
    assert signals
    assert all(isinstance(x, SocialSignal) for x in signals)
    assert all(x.score >= 0 and x.num_comments >= 0 for x in signals)
    assert all(isinstance(x.created_utc, datetime) for x in signals)


def test_trends_stub_yields_points() -> None:
    points = list(TrendsClient(stub=True).fetch_interest_over_time("Travis Scott"))
    assert points
    assert all(isinstance(x, TrendPoint) for x in points)
    assert all(0 <= x.interest <= 100 for x in points)
    assert all(isinstance(x.point_date, date) for x in points)


def test_write_raw_roundtrips(tmp_path) -> None:
    records = list(EbayClient(stub=True).fetch_sold_listings("Air Jordan 1", limit=3))
    path = write_raw("ebay", "Air Jordan 1", records, raw_dir=tmp_path)
    assert path.exists()
    payload = json.loads(path.read_text())
    assert payload["source"] == "ebay"
    assert payload["record_count"] == len(records)
    assert len(payload["records"]) == len(records)
    # Dates serialized as ISO strings.
    assert isinstance(payload["records"][0]["sold_date"], str)


def test_run_writes_three_files_per_term(tmp_path) -> None:
    settings = Settings(
        watchlist=["Air Jordan 1", "Yeezy 350"],
        subreddits=["sneakers"],
        raw_dir=tmp_path,
        # No credentials -> eBay & Reddit auto-stub.
    )
    written = run(settings, stub_trends=True)
    assert len(written) == 2 * 3  # 2 terms x (ebay, reddit, trends)
    assert all(p.exists() for p in written)
