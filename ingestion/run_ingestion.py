"""Ingestion entrypoint.

Runs all three source clients (eBay, Reddit, Google Trends) across the
configured watchlist and lands one timestamped JSON file per source/term in
``data/raw/``. This module is deliberately decoupled from any database: it
only fetches and writes raw files. Loading into Postgres happens separately in
Phase 2.

Run with: ``python -m ingestion.run_ingestion`` (or ``make ingest``).
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .config import Settings
from .ebay import SOURCE as EBAY_SOURCE
from .ebay import EbayClient
from .reddit import SOURCE as REDDIT_SOURCE
from .reddit import RedditClient
from .storage import write_raw
from .trends import SOURCE as TRENDS_SOURCE
from .trends import TrendsClient

logger = logging.getLogger(__name__)


def run(settings: Settings, *, stub_trends: bool = False) -> list[Path]:
    """Run ingestion for every term in the watchlist; return files written."""
    ebay = EbayClient.from_settings(settings)
    reddit = RedditClient.from_settings(settings)
    trends = TrendsClient.from_settings(settings, stub=stub_trends)

    written: list[Path] = []
    for term in settings.watchlist:
        logger.info("Ingesting %r", term)

        ebay_records = list(ebay.fetch_sold_listings(term))
        written.append(
            write_raw(EBAY_SOURCE, term, ebay_records, raw_dir=settings.raw_dir)
        )

        reddit_records = list(reddit.fetch_posts(term))
        written.append(
            write_raw(REDDIT_SOURCE, term, reddit_records, raw_dir=settings.raw_dir)
        )

        trend_records = list(trends.fetch_interest_over_time(term))
        written.append(
            write_raw(TRENDS_SOURCE, term, trend_records, raw_dir=settings.raw_dir)
        )

    logger.info("Ingestion complete: %d files written.", len(written))
    return written


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Run sneaker-intel ingestion.")
    parser.add_argument(
        "--stub-trends",
        action="store_true",
        help="Force Google Trends into stub mode (useful offline).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ...).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    run(Settings.from_env(), stub_trends=args.stub_trends)


if __name__ == "__main__":
    main()
