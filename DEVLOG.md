# DEVLOG

An append-only build log for sneaker-intel. One entry per work session, newest at the top. Written in first person — what got built, and *why* the decisions were made. This is the raw material for interview prep and the eventual project writeup.

## Entry template

```
## YYYY-MM-DD — <short title>

**What I built**
- ...

**Why I made these decisions**
- ...

**What I learned / got stuck on**
- ...

**Next up**
- ...
```

---

## 2026-06-19 — Phase 2: database schema + raw loader

**What I built**
- `db/schema.sql` — a hand-written star schema: `dim_shoes` (conformed dimension), `dim_drops` (release reference), and three facts, one per source: `fact_sales` (eBay), `fact_social_posts` (Reddit), `fact_search_interest` (Trends). FKs, natural-key unique constraints, check constraints, and indexes on every FK + time column.
- `db/seeds.sql` — upserts brand/silhouette/colorway onto the watchlist shoes and seeds representative release data into `dim_drops`.
- `db/load_raw.py` — reads `data/raw/`, upserts `dim_shoes` from the search terms it finds, then bulk-loads each source with `execute_values` and `ON CONFLICT DO NOTHING`. Idempotent by construction.
- `docker-compose.yml` (Postgres 16), Makefile targets (`db-up`, `db-down`, `db-init`, `load`), `DATABASE_URL` in `.env.example`, and `docs/erd.md` with a mermaid ERD plus the design reasoning.
- `tests/test_load_raw.py` — three tests covering the full read→transform→insert wiring against a faked cursor (row counts, column widths, empty-dir).

**Why I made these decisions**
- **Two social fact tables, not one.** Reddit is per-post and Trends is per-day — different grains. Splitting into `fact_social_posts` and `fact_search_interest` keeps every row meaningful instead of unioning mismatched grains with a column of NULLs.
- **`search_term` as the natural key on `dim_shoes`, surrogate `shoe_key` as the FK.** Raw records only know their ingestion term, so that's the reliable join key; the serial surrogate lets descriptive attributes change without rewriting fact rows.
- **Idempotency lives in the schema, not the loader.** Each fact has a natural-key unique constraint (`source_item_id`, `source_post_id`, `(shoe_key, point_date, geo)`), so `ON CONFLICT DO NOTHING` makes re-running the loader a no-op. That's the property I'd want before ever scheduling ingestion.
- **`execute_values` over row-by-row inserts** — one round trip per source instead of N, the standard psycopg2 bulk pattern.
- **`dim_drops` seeded by hand** because no drops source exists yet; `release_type` is constrained to `general/limited/collab` so Phase 3 has a real `accepted_values` test to run.

**What I learned / got stuck on**
- Couldn't stand up a real Postgres in this environment (aarch64, no root), so I validated the loader's Python wiring against a fake cursor and will run the live load via Docker. The 10-test suite passes and ruff is clean.

**Next up**
- Run the real load locally (`make db-up && make db-init && make load`) and confirm row counts, then start Phase 3: dbt staging/intermediate/mart models with window functions and tests.

## 2026-06-19 — Phase 1: Python ingestion layer

**What I built**
- Three source clients in `ingestion/`, all following one shared shape: a frozen dataclass for the record (`SoldListing`, `SocialSignal`, `TrendPoint`) plus a client class whose public method is a generator, with private `_request`/`_parse` helpers doing the actual work.
  - `ebay.py` — sold listings via the eBay Finding API (`findCompletedItems`), including title-based US size parsing.
  - `reddit.py` — per-post engagement (score, comments) across the sneaker subreddits via PRAW.
  - `trends.py` — search-interest-over-time via pytrends.
- `config.py` — a `Settings` dataclass holding the watchlist, subreddits, and credentials read from env (with optional `.env` support via python-dotenv).
- `storage.py` — `write_raw()` lands each batch as timestamped JSON in `data/raw/`.
- `run_ingestion.py` — entrypoint that loops the watchlist, runs all three clients, and writes one file per source/term. A small CLI (`--stub-trends`, `--log-level`).
- `tests/test_ingestion.py` — 7 pytest cases covering stub output, determinism, size parsing, JSON round-trip, and the full run. Added `.env.example` and an "API credentials" table to the README.

**Why I made these decisions**
- **Stub mode by default.** Any client missing credentials logs a warning and yields deterministic synthetic records, so the whole pipeline runs end-to-end before I've registered a single key. The stubs are seeded per search term, which makes tests reproducible.
- **Generators, not lists, as the public API.** Streaming records keeps memory flat and lets the entrypoint decide whether to materialize — a habit that matters once these are real paginated API calls.
- **Lazy imports of `requests`/`praw`/`pytrends`** inside the real-path helpers means stub mode (and the test suite) needs zero third-party deps installed.
- **Ingestion writes files only — no database.** Keeping the landing zone on disk means Phase 2's loader reads from `data/raw/` and the two layers stay independently testable.
- Caught broad `Exception` only at the per-term / per-subreddit boundary (with `logger.exception`) so one bad request can't abort a whole run; everything else uses narrow excepts.

**What I learned / got stuck on**
- eBay is nudging new integrations toward the Browse API; the Finding API still returns sold-listing data but may need migrating later. Noted in the README so future-me isn't surprised.
- Nothing blocking — ran the entrypoint in stub mode (15 files landed), ruff is clean, and the 7 tests pass.

**Next up**
- Phase 2: hand-write the Postgres star schema (`dim_shoes`, `fact_sales`, `fact_social_signals`, `dim_drops`) and a `load_raw.py` that bulk-loads the JSON in `data/raw/` with `execute_values`.

## 2026-06-19 — Phase 0: project scaffold

**What I built**
- Scaffolded the full `sneaker-intel` repo: ingestion/, db/, dbt_project/, dashboard/, data/raw/, docs/, tests/, and .github/workflows/.
- Added README (description, tech stack, architecture sketch, phase checklist, run instructions), this DEVLOG, and starter config: .gitignore, requirements.txt, pyproject.toml, Makefile, Dockerfile.
- Initialized the git repo and made the first commit.

**Why I made these decisions**
- Kept the structure flat and conventional so it reads quickly to anyone reviewing the repo. The star-schema / dbt-layered approach is signposted in the README up front rather than buried.
- Chose to *document* the virtualenv setup in the README rather than commit a `.venv` — environments are machine-specific and don't belong in version control.
- requirements.txt and pyproject.toml both present: requirements for a reproducible pinned install, pyproject for tooling config (ruff/black/pytest) and project metadata.

**What I learned / got stuck on**
- Nothing blocking — this was setup. Deferred actual API keys and Postgres setup to their respective phases so the scaffold stays runnable as-is.

**Next up**
- Phase 1: build the three ingestion modules (eBay, Reddit, Google Trends) following a shared dataclass + client pattern, with stubs until API keys are registered.
