"""Configuration for the ingestion layer.

Holds the watchlist of shoe models we track, the subreddits we scan, and the
API credentials read from the environment. Credentials are optional: when one
is missing, the corresponding client falls back to stub mode so the pipeline
stays runnable end to end before any keys are registered.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    # Optional convenience: load a local .env if python-dotenv is installed.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional; real env vars still work without it.
    pass

# Project root is the parent of the ingestion package.
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
RAW_DIR: Path = PROJECT_ROOT / "data" / "raw"
STOCKX_CSV: Path = PROJECT_ROOT / "data" / "external" / "StockX-Data-Contest.csv"

# Default models to track. Override with the SNEAKER_INTEL_WATCHLIST env var
# (comma-separated) without touching code.
DEFAULT_WATCHLIST: tuple[str, ...] = (
    "Air Jordan 1 High",
    "Nike Dunk Low Panda",
    "Yeezy Boost 350 V2",
    "New Balance 550",
    "Travis Scott Jordan 1 Low",
)

DEFAULT_SUBREDDITS: tuple[str, ...] = ("sneakers", "Sneakers", "SneakerMarket")


def _split_env(name: str, default: tuple[str, ...]) -> list[str]:
    """Read a comma-separated env var into a list, falling back to a default."""
    raw = os.getenv(name)
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """Runtime settings for an ingestion run."""

    watchlist: list[str] = field(default_factory=lambda: list(DEFAULT_WATCHLIST))
    subreddits: list[str] = field(default_factory=lambda: list(DEFAULT_SUBREDDITS))
    raw_dir: Path = RAW_DIR
    stockx_csv_path: Path = STOCKX_CSV
    # When the real StockX CSV is present, the live-source watchlist is derived
    # from its top-N most-sold shoes (capped here) instead of DEFAULT_WATCHLIST.
    watchlist_size: int = 15

    # Credentials (None when unset -> the client runs in stub mode).
    ebay_app_id: str | None = None
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str = "sneaker-intel/0.1 by u/sneaker-intel"

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from environment variables."""
        return cls(
            watchlist=_split_env("SNEAKER_INTEL_WATCHLIST", DEFAULT_WATCHLIST),
            subreddits=_split_env("SNEAKER_INTEL_SUBREDDITS", DEFAULT_SUBREDDITS),
            stockx_csv_path=Path(os.getenv("STOCKX_CSV_PATH", str(STOCKX_CSV))),
            watchlist_size=int(os.getenv("SNEAKER_INTEL_WATCHLIST_SIZE", "15")),
            ebay_app_id=os.getenv("EBAY_APP_ID"),
            reddit_client_id=os.getenv("REDDIT_CLIENT_ID"),
            reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            reddit_user_agent=os.getenv(
                "REDDIT_USER_AGENT", "sneaker-intel/0.1 by u/sneaker-intel"
            ),
        )
