"""eBay sold-listings ingestion client.

Pulls completed/sold sneaker listings via the eBay Finding API
(``findCompletedItems``). Until an ``EBAY_APP_ID`` is configured the client
runs in stub mode, yielding synthetic listings so the rest of the pipeline is
testable. The public method is a generator so callers can stream results
without holding an entire response in memory.
"""

from __future__ import annotations

import logging
import random
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from .config import Settings

logger = logging.getLogger(__name__)

SOURCE = "ebay"
_FINDING_API_URL = "https://svcs.ebay.com/services/search/FindingService/v1"
_SIZE_RE = re.compile(r"\b(?:size\s*)?(\d{1,2}(?:\.5)?)\b", re.IGNORECASE)


@dataclass(frozen=True)
class SoldListing:
    """A single sold sneaker listing extracted from eBay."""

    source_item_id: str
    search_term: str
    title: str
    sold_price: float
    currency: str
    sold_date: date
    condition: str | None
    size: float | None


class EbayClient:
    """Fetches sold sneaker listings from eBay."""

    def __init__(self, app_id: str | None = None, *, stub: bool | None = None) -> None:
        # Stub unless explicitly told otherwise and we actually have a key.
        self._app_id = app_id
        self._stub = (app_id is None) if stub is None else stub
        if self._stub:
            logger.warning("EbayClient running in STUB mode (no EBAY_APP_ID set).")

    @classmethod
    def from_settings(cls, settings: Settings) -> EbayClient:
        return cls(settings.ebay_app_id)

    def fetch_sold_listings(
        self, search_term: str, *, limit: int = 50
    ) -> Iterator[SoldListing]:
        """Yield sold listings matching ``search_term``."""
        if self._stub:
            yield from self._stub_listings(search_term, limit)
            return

        try:
            items = self._request(search_term, limit)
        except Exception:  # noqa: BLE001 - one failed term must not kill the run
            logger.exception("eBay request failed for %r; skipping", search_term)
            return

        for item in items:
            listing = self._parse_listing(item, search_term)
            if listing is not None:
                yield listing

    # -- private helpers ---------------------------------------------------

    def _request(self, search_term: str, limit: int) -> list[dict[str, Any]]:
        """Call the Finding API and return the raw item dicts.

        Imported lazily so stub mode has no third-party dependency.
        """
        import requests

        params = {
            "OPERATION-NAME": "findCompletedItems",
            "SERVICE-VERSION": "1.13.0",
            "SECURITY-APPNAME": self._app_id,
            "RESPONSE-DATA-FORMAT": "JSON",
            "REST-PAYLOAD": "",
            "keywords": search_term,
            "categoryId": "15709",  # Athletic Shoes
            "itemFilter(0).name": "SoldItemsOnly",
            "itemFilter(0).value": "true",
            "paginationInput.entriesPerPage": str(limit),
        }
        response = requests.get(_FINDING_API_URL, params=params, timeout=30)
        response.raise_for_status()
        body = response.json()
        try:
            search_result = body["findCompletedItemsResponse"][0]["searchResult"][0]
            return search_result.get("item", [])
        except (KeyError, IndexError):
            logger.warning("Unexpected eBay response shape for %r", search_term)
            return []

    def _parse_listing(
        self, item: dict[str, Any], search_term: str
    ) -> SoldListing | None:
        """Convert one raw eBay item dict into a ``SoldListing``."""
        try:
            item_id = item["itemId"][0]
            title = item["title"][0]
            selling = item["sellingStatus"][0]
            price_node = selling["currentPrice"][0]
            sold_price = float(price_node["__value__"])
            currency = price_node.get("@currencyId", "USD")
            end_time = item["listingInfo"][0]["endTime"][0]
            sold_date = date.fromisoformat(end_time[:10])
            condition = (
                item.get("condition", [{}])[0].get("conditionDisplayName", [None])[0]
            )
        except (KeyError, IndexError, ValueError):
            logger.warning("Skipping unparseable eBay item in %r", search_term)
            return None

        return SoldListing(
            source_item_id=str(item_id),
            search_term=search_term,
            title=title,
            sold_price=sold_price,
            currency=currency,
            sold_date=sold_date,
            condition=condition,
            size=self._parse_size(title),
        )

    @staticmethod
    def _parse_size(title: str) -> float | None:
        """Best-effort parse of a US shoe size from a listing title."""
        match = _SIZE_RE.search(title)
        if not match:
            return None
        size = float(match.group(1))
        # Sneaker sizes realistically fall in this range; ignore stray numbers.
        return size if 3.0 <= size <= 18.0 else None

    def _stub_listings(self, search_term: str, limit: int) -> Iterator[SoldListing]:
        """Yield deterministic synthetic listings for development/testing."""
        rng = random.Random(f"ebay::{search_term}")
        conditions = ["New with box", "New without box", "Pre-owned"]
        base_price = rng.uniform(150, 450)
        count = min(limit, 12)
        for i in range(count):
            price = round(base_price * rng.uniform(0.8, 1.6), 2)
            size = rng.choice([7, 8, 8.5, 9, 9.5, 10, 10.5, 11, 12])
            yield SoldListing(
                source_item_id=f"stub-ebay-{abs(hash((search_term, i))) % 10**10}",
                search_term=search_term,
                title=f"{search_term} US {size} {rng.choice(conditions)}",
                sold_price=price,
                currency="USD",
                sold_date=date.today() - timedelta(days=rng.randint(0, 60)),
                condition=rng.choice(conditions),
                size=float(size),
            )
