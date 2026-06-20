"""StockX sold-sales ingestion from the Kaggle StockX dataset.

Reads the StockX 2019 Data Contest CSV (real Off-White / Yeezy resale sales:
order date, brand, sneaker name, sale price, retail price, release date, shoe
size, buyer region) and yields one record per sale. This is the real-data
backbone for fact_sales and lets the loader derive dim_drops (retail price +
release date) instead of hand-seeding it.

Download the CSV from Kaggle and place it at the path in STOCKX_CSV_PATH
(default data/external/StockX-Data-Contest.csv). Until the file exists, the
client runs in stub mode and yields synthetic sales so the pipeline still runs.

Expected columns (header names matched case/space-insensitively):
    Order Date, Brand, Sneaker Name, Sale Price, Retail Price,
    Release Date, Shoe Size, Buyer Region
"""

from __future__ import annotations

import csv
import logging
import random
import re
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import Settings

logger = logging.getLogger(__name__)

SOURCE = "stockx"
_MONEY_RE = re.compile(r"[^0-9.]")
_WS_RE = re.compile(r"\s+")
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y")


def clean_name(raw: str) -> str:
    """Normalize a StockX slug into a human/search-friendly name.

    'Adidas-Yeezy-Boost-350-V2-Zebra' -> 'Adidas Yeezy Boost 350 V2 Zebra'.
    This normalized form is the conformed natural key in dim_shoes, so the
    StockX facts and the live API signals join on the same shoe.
    """
    return _WS_RE.sub(" ", raw.replace("-", " ")).strip()


def top_shoe_names(sales: Iterable[StockXSale], n: int) -> list[str]:
    """Return the N most-sold shoe names (by row count) from StockX sales."""
    counts = Counter(s.search_term for s in sales)
    return [name for name, _ in counts.most_common(n)]


@dataclass(frozen=True)
class StockXSale:
    """A single StockX resale transaction."""

    source_item_id: str
    search_term: str
    brand: str
    title: str
    sold_price: float
    retail_price: float | None
    sold_date: date
    release_date: date | None
    size: float | None
    buyer_region: str | None


class StockXClient:
    """Reads StockX resale sales from the Kaggle dataset CSV."""

    def __init__(self, csv_path: Path | None = None, *, stub: bool | None = None) -> None:
        self._csv_path = csv_path
        exists = csv_path is not None and csv_path.exists()
        self._stub = (not exists) if stub is None else stub
        if self._stub:
            logger.warning(
                "StockXClient running in STUB mode (CSV not found at %s).", csv_path
            )

    @classmethod
    def from_settings(cls, settings: Settings) -> StockXClient:
        return cls(settings.stockx_csv_path)

    @property
    def is_stub(self) -> bool:
        return self._stub

    def fetch_sales(self, *, limit: int | None = None) -> Iterator[StockXSale]:
        """Yield StockX sales, optionally capping the row count."""
        if self._stub:
            yield from self._stub_sales(limit or 40)
            return

        with self._csv_path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            normalized = {h: (h or "").strip().lower() for h in (reader.fieldnames or [])}
            for index, row in enumerate(reader):
                if limit is not None and index >= limit:
                    break
                record = self._parse_row({normalized[k]: v for k, v in row.items()}, index)
                if record is not None:
                    yield record

    # -- private helpers ---------------------------------------------------

    def _parse_row(self, row: dict[str, str], index: int) -> StockXSale | None:
        """Convert one normalized CSV row into a StockXSale."""
        try:
            raw_name = (row.get("sneaker name") or "").strip()
            name = clean_name(raw_name)
            sold_price = self._parse_money(row.get("sale price"))
            sold_date = self._parse_date(row.get("order date"))
            if not name or sold_price is None or sold_date is None:
                return None
            return StockXSale(
                source_item_id=self._row_id(raw_name, row.get("order date"), index),
                search_term=name,
                brand=(row.get("brand") or "").strip(),
                title=name,
                sold_price=sold_price,
                retail_price=self._parse_money(row.get("retail price")),
                sold_date=sold_date,
                release_date=self._parse_date(row.get("release date")),
                size=self._parse_float(row.get("shoe size")),
                buyer_region=(row.get("buyer region") or "").strip() or None,
            )
        except (KeyError, ValueError):
            logger.warning("Skipping unparseable StockX row %d", index)
            return None

    @staticmethod
    def _row_id(name: str, order_date: str | None, index: int) -> str:
        """Deterministic id for a row (no native id in the dataset)."""
        return f"stockx-{abs(hash((name, order_date, index))) % 10**12}"

    @staticmethod
    def _parse_money(value: str | None) -> float | None:
        """Parse '$1,097.00' / '220' into a float; None if blank/invalid."""
        if not value:
            return None
        cleaned = _MONEY_RE.sub("", value)
        return float(cleaned) if cleaned else None

    @staticmethod
    def _parse_float(value: str | None) -> float | None:
        if not value or not value.strip():
            return None
        try:
            return float(value)
        except ValueError:
            return None

    @staticmethod
    def _parse_date(value: str | None) -> date | None:
        """Parse a date string across the formats the dataset has shipped in."""
        if not value or not value.strip():
            return None
        text = value.strip()
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    def _stub_sales(self, limit: int) -> Iterator[StockXSale]:
        """Yield deterministic synthetic StockX sales for dev/testing/CI."""
        catalog = [
            ("Yeezy", "Adidas-Yeezy-Boost-350-V2-Zebra", 220.0, date(2017, 2, 25)),
            ("Off-White", "Nike-Air-Presto-Off-White", 160.0, date(2018, 8, 3)),
            ("Off-White", "Nike-Blazer-Mid-Off-White-Grim-Reaper", 130.0, date(2018, 10, 20)),
            ("Yeezy", "Adidas-Yeezy-Boost-350-V2-Butter", 220.0, date(2018, 6, 30)),
        ]
        rng = random.Random("stockx-stub")
        for i in range(limit):
            brand, slug, retail, release = catalog[i % len(catalog)]
            name = clean_name(slug)
            yield StockXSale(
                source_item_id=f"stockx-stub-{i:04d}",
                search_term=name,
                brand=brand,
                title=name,
                sold_price=round(retail * rng.uniform(1.1, 3.5), 2),
                retail_price=retail,
                sold_date=release + timedelta(days=rng.randint(10, 400)),
                release_date=release,
                size=rng.choice([7.0, 8.0, 8.5, 9.0, 9.5, 10.0, 10.5, 11.0, 12.0]),
                buyer_region=rng.choice(["California", "New York", "Texas", "Oregon"]),
            )
