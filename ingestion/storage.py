"""Raw landing-zone helpers.

The ingestion layer writes untransformed source records to ``data/raw/`` as
timestamped JSON. Keeping this separate from the clients means the database
loader (Phase 2) reads from disk and never talks to the source APIs directly.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _slugify(value: str) -> str:
    """Turn a search term into a filename-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled"


def _json_default(value: Any) -> str:
    """Serialize types json doesn't handle natively (dates, datetimes)."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_raw(
    source: str,
    search_term: str,
    records: list[Any],
    *,
    raw_dir: Path,
    now: datetime | None = None,
) -> Path:
    """Write a batch of dataclass records to a timestamped JSON file.

    Returns the path written. ``records`` are expected to be dataclass
    instances; they are converted to dicts before serialization.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{source}_{_slugify(search_term)}_{stamp}.json"
    path = raw_dir / filename

    payload = {
        "source": source,
        "search_term": search_term,
        "ingested_at": (now or datetime.now(timezone.utc)).isoformat(),
        "record_count": len(records),
        "records": [dataclasses.asdict(r) for r in records],
    }

    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=_json_default)

    logger.info("Wrote %d %s records to %s", len(records), source, path.name)
    return path
