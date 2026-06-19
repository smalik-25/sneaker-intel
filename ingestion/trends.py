"""Google Trends ingestion client.

Pulls search-interest-over-time for a shoe model using pytrends. Google Trends
needs no API key, so this client hits the live service by default but still
supports an explicit stub mode for offline/testing runs. The public method is
a generator yielding one point per time bucket.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta

from .config import Settings

logger = logging.getLogger(__name__)

SOURCE = "trends"


@dataclass(frozen=True)
class TrendPoint:
    """Search interest for a term in a single time bucket."""

    search_term: str
    point_date: date
    interest: int
    geo: str


class TrendsClient:
    """Fetches Google Trends search interest via pytrends."""

    def __init__(
        self,
        *,
        geo: str = "US",
        timeframe: str = "today 3-m",
        stub: bool = False,
    ) -> None:
        self._geo = geo
        self._timeframe = timeframe
        self._stub = stub
        if self._stub:
            logger.warning("TrendsClient running in STUB mode.")

    @classmethod
    def from_settings(cls, settings: Settings, *, stub: bool = False) -> TrendsClient:
        return cls(stub=stub)

    def fetch_interest_over_time(self, search_term: str) -> Iterator[TrendPoint]:
        """Yield search-interest points for ``search_term``."""
        if self._stub:
            yield from self._stub_points(search_term)
            return

        try:
            rows = self._request(search_term)
        except Exception:  # noqa: BLE001 - one term failing must not abort the run
            logger.exception("Google Trends request failed for %r; skipping", search_term)
            return

        for point_date, interest in rows:
            yield TrendPoint(
                search_term=search_term,
                point_date=point_date,
                interest=int(interest),
                geo=self._geo,
            )

    # -- private helpers ---------------------------------------------------

    def _request(self, search_term: str) -> list[tuple[date, int]]:
        """Query pytrends and return (date, interest) rows. Imported lazily."""
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=0)
        pytrends.build_payload([search_term], timeframe=self._timeframe, geo=self._geo)
        frame = pytrends.interest_over_time()
        if frame.empty:
            logger.warning("Google Trends returned no data for %r", search_term)
            return []
        return [
            (idx.date(), int(row[search_term]))
            for idx, row in frame.iterrows()
            if not row.get("isPartial", False)
        ]

    def _stub_points(self, search_term: str) -> Iterator[TrendPoint]:
        """Yield deterministic synthetic interest points for development/testing."""
        rng = random.Random(f"trends::{search_term}")
        today = date.today()
        for weeks_ago in range(12, -1, -1):
            yield TrendPoint(
                search_term=search_term,
                point_date=today - timedelta(weeks=weeks_ago),
                interest=rng.randint(20, 100),
                geo=self._geo,
            )
