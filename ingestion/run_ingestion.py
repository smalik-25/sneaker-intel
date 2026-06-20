"""Ingestion entrypoint.

The current pipeline has two sources: the **StockX dataset** (real resale
sales, the backbone of fact_sales + dim_drops) and **Google Trends** (live
search-demand signal per shoe). It lands one timestamped JSON file per
source/term in ``data/raw``; loading into Postgres happens separately.

The eBay and Reddit clients (``ingestion/ebay.py``, ``ingestion/reddit.py``)
are implemented and tested but parked as future extensions: they need API
keys, so they are intentionally not part of the default run. The loader and
schema already support them, so enabling them later is additive.

Run with: ``python -m ingestion.run_ingestion`` (or ``make ingest``).
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .config import Settings
from .stockx import SOURCE as STOCKX_SOURCE
from .stockx import StockXClient, top_shoe_names
from .storage import write_raw
from .trends import SOURCE as TRENDS_SOURCE
from .trends import TrendsClient

logger = logging.getLogger(__name__)


def run(settings: Settings, *, stub_trends: bool = False) -> list[Path]:
    """Run the current pipeline (StockX + Google Trends); return files written."""
    trends = TrendsClient.from_settings(settings, stub=stub_trends)

    # StockX is a whole-dataset source (not per-term); fetch it once up front.
    # When the real CSV is present, its top-N shoes also drive the Trends
    # watchlist, so search signals join to the same dim_shoes rows.
    stockx = StockXClient.from_settings(settings)
    stockx_records = list(stockx.fetch_sales())
    if stockx_records and not stockx.is_stub:
        watchlist = top_shoe_names(stockx_records, settings.watchlist_size)
        logger.info("Derived watchlist of %d shoes from the StockX dataset.", len(watchlist))
    else:
        watchlist = settings.watchlist

    written: list[Path] = []
    for term in watchlist:
        logger.info("Ingesting Google Trends for %r", term)
        trend_records = list(trends.fetch_interest_over_time(term))
        written.append(
            write_raw(TRENDS_SOURCE, term, trend_records, raw_dir=settings.raw_dir)
        )

    written.append(
        write_raw(STOCKX_SOURCE, "dataset", stockx_records, raw_dir=settings.raw_dir)
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
