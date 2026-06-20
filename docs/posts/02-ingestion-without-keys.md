# Ingestion that runs before you have any API keys

Resale data is scattered across places that don't want to hand it to you cleanly: marketplaces behind API approval, social platforms behind OAuth, search-trend endpoints that rate-limit. The usual result is an ingestion layer that sits half-finished because you're waiting on access. I wanted the opposite. A pipeline that runs end to end on day one, then gets more real as keys and datasets show up.

Every source follows the same shape. A small dataclass that defines the record I'm pulling, and a client class whose public method is a generator that yields those records, with the HTTP and parsing work in private helpers. Generators instead of returning lists, because streaming keeps memory flat and lets the caller decide when to materialize. That matters the moment these turn into real paginated calls over tens of thousands of listings.

The trick that makes it runnable without access is stub mode. If a client has no credentials, it logs a warning and yields deterministic synthetic records instead of failing. Seeded per search term, so they're reproducible, which means the tests can assert on them. The third-party libraries get imported lazily inside the real-path helpers, so stub mode and the test suite need none of them installed.

Error handling is deliberately narrow. One bad listing or one unparseable row shouldn't take down a run, so I catch at the per-item and per-request boundary, log it, and keep going. Everything else uses specific exceptions. No bare `except` quietly eating real bugs.

The other rule: ingestion only writes files. It fetches and lands timestamped raw JSON, and that's the whole job. It never touches the database. Keeping the landing zone on disk means the loader reads from files, and the two layers stay independently testable. If ingestion breaks, I still have yesterday's pulls. If loading breaks, I haven't lost the fetch. For data that's expensive or rate-limited to collect, that separation isn't optional.

When I wired it together it produced a stack of raw JSON without a single key configured, and the tests passed in well under a second.

That "runs without keys" property mattered more than I expected. It's what later let me lean on a real public dataset as the backbone and treat the keyed APIs as optional. More on that decision in a later post. Next: the warehouse.
