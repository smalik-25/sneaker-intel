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


def test_run_writes_trends_per_term_plus_stockx(tmp_path) -> None:
    settings = Settings(
        watchlist=["Air Jordan 1", "Yeezy 350"],
        subreddits=["sneakers"],
        raw_dir=tmp_path,
    )
    written = run(settings, stub_trends=True)
    # Current pipeline: 1 Trends file per term + 1 StockX dataset file.
    assert len(written) == 2 + 1
    assert all(p.exists() for p in written)
    # eBay/Reddit are future extensions, not produced by the default run.
    assert not list(tmp_path.glob("ebay_*.json"))
    assert not list(tmp_path.glob("reddit_*.json"))


def test_run_derives_watchlist_from_real_stockx_csv(tmp_path) -> None:
    csv = tmp_path / "stockx.csv"
    csv.write_text(
        "Order Date,Brand,Sneaker Name,Sale Price,Retail Price,"
        "Release Date,Shoe Size,Buyer Region\n"
        "9/1/2017,Yeezy,Adidas-Yeezy-Boost-350-Zebra,500,220,2/25/2017,10,California\n"
        "9/2/2017,Off-White,Nike-Air-Presto-Off-White,800,160,8/3/2018,9,Texas\n",
        encoding="utf-8",
    )
    settings = Settings(
        watchlist=["Should Not Be Used"],
        subreddits=["sneakers"],
        raw_dir=tmp_path,
        stockx_csv_path=csv,
    )
    run(settings, stub_trends=True)
    # Trends files should be named for the StockX-derived shoes, not the curated term.
    trends_files = sorted(p.name for p in tmp_path.glob("trends_*.json"))
    assert any("yeezy" in f for f in trends_files)
    assert not any("should-not-be-used" in f for f in trends_files)
