# Ingestion that runs before you have any API keys

The ingestion layer is where a data project usually gets stuck waiting on access:
you can't test anything until the API keys show up. I wanted the opposite — a
pipeline that runs end to end on day one, then gets *more* real as credentials
and datasets arrive.

Every source follows the same shape: a small dataclass that defines the record
I'm extracting, and a client class whose public method is a generator yielding
those records, with the actual HTTP/parsing work tucked into private helpers.
Generators instead of returning lists, because streaming keeps memory flat and
lets the caller decide whether to materialize — a habit that pays off the moment
these become real paginated API calls.

The trick that makes it runnable without access is **stub mode**. If a client has
no credentials, it logs a warning and yields deterministic synthetic records
instead of failing. The records are seeded per search term, so they're
reproducible — which means the test suite can assert on them. The third-party
libraries (`requests`, `praw`, `pytrends`) are imported lazily inside the
real-path helpers, so stub mode and the tests need zero of them installed.

Error handling is deliberately narrow. One bad request or one unparseable row
shouldn't take down a whole run, so I catch at the per-item and per-request
boundary, log it, and keep going. Everything else uses specific exceptions — no
bare `except` swallowing real bugs.

The other principle: ingestion writes files, full stop. It fetches and lands
timestamped raw JSON in `data/raw/`, and that's the entire job. It never touches
the database. Keeping the landing zone on disk means the database loader (a later
phase) reads from files, and the two layers stay independently testable. If
ingestion breaks, I still have yesterday's raw files. If loading breaks, I
haven't lost the fetch.

When I wired it together and ran it, the whole thing produced a stack of raw JSON
files without a single key configured. Then I wrote the tests against the stub
output and the entrypoint, and they passed in well under a second.

That "runs without keys" property turned out to matter more than I expected —
it's what later let me lean on a real public dataset as the backbone and treat
the keyed APIs as optional. More on that in a later post. Next: designing the
warehouse.
