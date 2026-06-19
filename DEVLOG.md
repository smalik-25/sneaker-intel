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
