"""Reddit social-signal ingestion client.

Pulls post volume and engagement (score, comment count) for a search term
across the sneaker subreddits using PRAW. Until Reddit API credentials are
configured the client runs in stub mode, yielding synthetic signals so the
rest of the pipeline is testable. The public method is a generator.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .config import Settings

logger = logging.getLogger(__name__)

SOURCE = "reddit"


@dataclass(frozen=True)
class SocialSignal:
    """Engagement signal for one Reddit post matching a search term."""

    source_post_id: str
    search_term: str
    subreddit: str
    title: str
    score: int
    num_comments: int
    created_utc: datetime


class RedditClient:
    """Fetches post-level engagement signals from Reddit via PRAW."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str = "sneaker-intel/0.1",
        *,
        subreddits: list[str] | None = None,
        stub: bool | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._user_agent = user_agent
        self._subreddits = subreddits or ["sneakers"]
        has_creds = bool(client_id and client_secret)
        self._stub = (not has_creds) if stub is None else stub
        if self._stub:
            logger.warning("RedditClient running in STUB mode (no Reddit credentials).")

    @classmethod
    def from_settings(cls, settings: Settings) -> RedditClient:
        return cls(
            settings.reddit_client_id,
            settings.reddit_client_secret,
            settings.reddit_user_agent,
            subreddits=settings.subreddits,
        )

    def fetch_posts(
        self, search_term: str, *, limit: int = 100
    ) -> Iterator[SocialSignal]:
        """Yield engagement signals for posts matching ``search_term``."""
        if self._stub:
            yield from self._stub_signals(search_term, limit)
            return

        reddit = self._client()
        for subreddit in self._subreddits:
            try:
                yield from self._search_subreddit(reddit, subreddit, search_term, limit)
            except Exception:  # noqa: BLE001 - one subreddit failing must not abort
                logger.exception(
                    "Reddit search failed for r/%s %r; skipping", subreddit, search_term
                )

    # -- private helpers ---------------------------------------------------

    def _client(self):
        """Build a read-only PRAW client. Imported lazily for stub mode."""
        import praw

        return praw.Reddit(
            client_id=self._client_id,
            client_secret=self._client_secret,
            user_agent=self._user_agent,
            check_for_async=False,
        )

    def _search_subreddit(
        self, reddit, subreddit: str, search_term: str, limit: int
    ) -> Iterator[SocialSignal]:
        """Yield signals for one subreddit's search results."""
        for post in reddit.subreddit(subreddit).search(search_term, limit=limit):
            yield SocialSignal(
                source_post_id=str(post.id),
                search_term=search_term,
                subreddit=subreddit,
                title=str(post.title),
                score=int(post.score),
                num_comments=int(post.num_comments),
                created_utc=datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
            )

    def _stub_signals(self, search_term: str, limit: int) -> Iterator[SocialSignal]:
        """Yield deterministic synthetic signals for development/testing."""
        rng = random.Random(f"reddit::{search_term}")
        topics = ["legit check", "on feet", "cop or drop", "restock?"]
        count = min(limit, 15)
        for i in range(count):
            subreddit = rng.choice(self._subreddits)
            created = datetime.now(timezone.utc) - timedelta(days=rng.randint(0, 90))
            yield SocialSignal(
                source_post_id=f"stub-rdt-{abs(hash((search_term, i))) % 10**8:08x}",
                search_term=search_term,
                subreddit=subreddit,
                title=f"[{search_term}] {rng.choice(topics)}",
                score=rng.randint(0, 2500),
                num_comments=rng.randint(0, 400),
                created_utc=created,
            )
