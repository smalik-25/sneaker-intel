# DEVLOG

An append-only build log for sneaker-intel. One entry per work session, newest at the top, first person: what I built and why I made each call. It's the raw material for these writeups and for talking through the project later.

## Entry template

```
## YYYY-MM-DD: <short title>

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

## 2026-06-19: Scope: two real sources, eBay/Reddit as future extensions

**What I built**
- Reframed the pipeline around two real, key-free sources: the StockX dataset (sales) and Google Trends (demand). Removed eBay and Reddit from the default `run_ingestion`. Their client modules, tests, and the schema/loader support all stay, documented under a README "Roadmap / future extensions" section.
- Added `mart_search_interest` (Trends interest per shoe over time) and put Google Trends on the dashboard: a search-interest line on the Shoe Deep Dive page, so the live source is visible instead of loaded and hidden.
- Fixed the Streamlit `use_container_width` deprecation (now `width="stretch"`). Updated tests and docs for the two-source pipeline.

**Why I made these decisions**
- I'm not going to register eBay/Reddit keys, but the clients are real evidence of API-integration work. Deleting them would throw away a genuine skill showcase. Parking them as documented, tested, schema-ready extensions is the honest framing: the current pipeline is StockX plus Trends, and those two are wired and ready pending keys.
- Trends was being ingested but never displayed. Surfacing it on the Deep Dive makes the live source actually count toward the product, and it joins on the same `dim_shoes` key as sales thanks to the normalized names.
- Keeping eBay/Reddit in the loader and schema (present but empty) means re-enabling them later is purely additive. No migration.

**What I learned / got stuck on**
- Clean reframe. The loader already returns 0 for missing sources, so dropping two needed almost no loader change. 17 tests pass, ruff clean, dbt parses.

**Next up**
- Re-run locally to see Trends on the Deep Dive, then the deferred Phase 2 ML work or the live deploy.

## 2026-06-19: Real data: the StockX dataset as the backbone

**What I built**
- `ingestion/stockx.py`, a CSV client for the Kaggle StockX 2019 dataset (real Off-White / Yeezy resale sales), following the same dataclass + generator pattern as the API clients, with tolerant money/date parsing and a synthetic stub when the CSV isn't present. It runs once over the whole dataset rather than per watchlist term.
- Made `fact_sales` multi-source: added a `source` column (schema, `stg_sales`, `int_sales_enriched`) and a shared insert helper, so eBay and StockX sales coexist with provenance.
- Extended the loader to derive `dim_drops` from StockX (release date and retail price, deduped per shoe-release), using real release data instead of hand-seeded values.
- Made the StockX source ingest every shoe in the dataset, and when the real CSV is present, derive the live-source watchlist from its top-N most-sold shoes (`SNEAKER_INTEL_WATCHLIST_SIZE`, default 15). Normalized sneaker names (slug to clean text) so StockX facts and live signals share one conformed `dim_shoes` key.
- Tests: a StockX suite (stub determinism, money/date parsing, a real-CSV round-trip) and updated loader tests for the multi-source insert shape. Gitignored `data/external/` and documented the Kaggle download in the README.

**Why I made these decisions**
- Keep the API clients, put real data underneath. The eBay/Reddit/Trends clients still demonstrate live API integration, and StockX gives a real backbone that won't break the way a StockX scraper would. The story is "multi-source ingestion with live API clients plus a real historical dataset," which is stronger than either alone.
- A `source` column rather than a separate sales table. Same grain (one sold listing), so one fact table with provenance keeps the premium logic unified while still allowing source-level filtering.
- Derive `dim_drops` from the data. With real retail prices and release dates in the dataset, hand-seeding releases is pointless. The loader builds the dimension from what it ingests, which is how I'd want it with real data.
- Stub fallback preserved, so CI and key-less/CSV-less runs still exercise the whole pipeline.

**What I learned / got stuck on**
- The dataset's price and date formatting varies across mirrors, so the parser tolerates `$1,097.00`-style money and several date formats instead of assuming one. 14 tests pass, ruff clean, and the multi-source load runs against Docker Postgres.

**Next up**
- Download the real CSV, re-run `db-init`, `load`, `transform`, and confirm the dashboard reflects real premiums. Then the Phase 2 ML work.

---

## 2026-06-19: Phase 5: deployment, CI, and polish

**What I built**
- GitHub Actions CI that runs the entire pipeline on every push and PR: stands up a Postgres service, applies schema and seeds, runs ingestion (stub), load, and `dbt build` (models and data tests), plus ruff and pytest. Self-contained, no secrets.
- A production Dockerfile for the dashboard: dependency-layer caching, a non-root user, and a bind to the platform `$PORT` so it runs on a host unchanged. Added a `.dockerignore`.
- `DEPLOY.md`, with step-by-step guides for Railway (app plus managed Postgres) and Streamlit Community Cloud plus Neon (free), including how to seed the cloud database and refresh data later.
- Finalized the README: a mermaid architecture diagram, a full local run sequence, a CI/live-demo line, and a "Decisions and tradeoffs" section pulled from this log.

**Why I made these decisions**
- Full-pipeline CI over lint-only. Running ingest, load, and dbt build against a real Postgres service is the strongest signal the project works. It exercises the SQL, the constraints, and every dbt test on each push, not just the Python.
- Deferred the live deploy behind a guide. A live dashboard needs a cloud Postgres seeded with the marts, which depends on my hosting accounts and is better done deliberately than rushed. The Dockerfile and DEPLOY.md make it a short, documented step.
- A `$PORT`-aware container so the same image runs locally and on a host without edits.

**What I learned / got stuck on**
- The whole build ran on a "prepare files locally, run git myself" workflow because the sandbox couldn't manage git locks on the mounted drive. Worth remembering.
- Validated everything reachable without a live DB: ruff clean, 10 pytests pass, the workflow and compose YAML parse, dbt parses. CI is the first place the full pipeline runs unattended.

**Next up (Phase 2 / future)**
- The deliberate ML work: forecasting resale premium from the sales, social, and search features this warehouse already models.

## 2026-06-19: Phase 4: Streamlit dashboard

**What I built**
- `dashboard/app.py`, a three-page Streamlit app reading from the marts:
  - Market Overview: headline KPIs from `mart_shoe_performance`, plus a sale-date-window slider that re-ranks shoes by average premium (with peak and volatility) from `mart_price_trajectory`.
  - Shoe Deep Dive: a per-shoe premium trajectory line chart (raw `pct_premium` against the rolling 7-day average), a recent-7-day-vs-90-day-baseline metric, and a premium-by-size bar chart.
  - Drop Calendar: release history from `dim_drops` joined to each shoe's premium context from `mart_shoe_performance`.
- Added `size`, `brand`, and `silhouette` to `mart_price_trajectory` so the dashboard reads them directly instead of doing joins itself.
- Cached the SQLAlchemy engine (`st.cache_resource`) and every query (`st.cache_data`, 5-minute TTL). Added `sqlalchemy` to requirements.

**Why I made these decisions**
- The app stays thin. Every aggregation it shows is a `GROUP BY` or window query against a mart, not pandas transformation. The heavy logic stays in dbt where it's tested. The one bit of in-app math (recent vs baseline) is presentation glue, not modeling.
- All-time KPIs plus a date-window slider rather than a hardcoded "this month": full range is the default but you can scope to any window. More useful, and the stub data is sparse month to month.
- Drop Calendar shows release history, not "upcoming." The seeded drops are past-dated, so an upcoming-only calendar would be empty. Pairing each release with the premium it realized is the more honest view of the data I have.
- Connection and schema from env (`DATABASE_URL`, `DBT_PG_SCHEMA`), matching dbt and the loader, so there's one source of truth for where data lives.

**What I learned / got stuck on**
- Validated `app.py` by import (pages register, no syntax or ruff issues) and re-ran `dbt parse` for the mart change. The live render happens via `make transform && make dashboard` against Docker Postgres. Couldn't run the Streamlit server in this environment.

**Next up**
- Phase 5: Dockerfile, GitHub Actions CI running dbt tests, deploy to a live URL, and finalize the README.

## 2026-06-19: Phase 3: dbt transformation layer

**What I built**
- A dbt project (`dbt_project/`) with the postgres adapter and an in-repo, env-var-driven `profiles.yml` (defaults to the docker-compose Postgres), so the whole thing is self-contained.
- Staging (views), one model per source table (`stg_shoes`, `stg_drops`, `stg_sales`, `stg_social_posts`, `stg_search_interest`): casting, cleaning, normalizing names, defaulting nulls.
- Intermediate `int_sales_enriched` (view): joins sales to the shoe and its primary release, computing `days_since_release`, `absolute_premium`, and `pct_premium`.
- Marts (tables): `mart_shoe_performance` (average, median via `percentile_cont`, peak premium, and volatility via `stddev_pop`, per shoe) and `mart_price_trajectory` (per-sale rolling 7-day average premium with `AVG() OVER`, `RANK() OVER` within shoe, and period-over-period delta with `LAG()`).
- Tests: `not_null` and `unique` on every key, `relationships` from each fact staging model and the trajectory mart back to `stg_shoes`, and `accepted_values` on `release_type`. Marts carry descriptions documenting the question each answers.

**Why I made these decisions**
- Staging and intermediate as views, marts as tables. Staging and intermediate are cheap pass-throughs that should always reflect current raw data. Marts are what the dashboard hits, so materializing them as tables keeps reads fast.
- `int_sales_enriched` as a separate layer. Premium is the central metric, so I compute it once, in one place, and let both marts and any future model share an identical definition instead of redefining it.
- `distinct on (shoe_key)` for the primary drop. A shoe can have multiple releases, so I pick the earliest as the reference rather than fanning sales out across every drop.
- A dedicated `analytics` schema keeps modeled tables cleanly separated from the raw `public` tables the loader writes.
- `nullif(retail_price, 0)` guards the pct_premium division so a bad or zero retail never throws.

**What I learned / got stuck on**
- Validated structurally with `dbt parse` (refs, sources, Jinja, YAML all resolve). I couldn't run `dbt build` in this environment, so the model SQL gets its real exercise against the Docker database. `make transform` runs build and tests in one shot.

**Next up**
- Run `make transform` locally to build the models and confirm tests pass, then Phase 4: the dashboard reading from these marts.

## 2026-06-19: Phase 2: database schema + raw loader

**What I built**
- `db/schema.sql`, a hand-written star schema: `dim_shoes` (conformed dimension), `dim_drops` (release reference), and three facts, one per source: `fact_sales`, `fact_social_posts`, `fact_search_interest`. Foreign keys, natural-key unique constraints, check constraints, and indexes on every FK and time column.
- `db/seeds.sql`, which upserts brand/silhouette/colorway onto the watchlist shoes and seeds representative release data into `dim_drops`.
- `db/load_raw.py`, which reads `data/raw/`, upserts `dim_shoes` from the search terms it finds, then bulk-loads each source with `execute_values` and `ON CONFLICT DO NOTHING`. Idempotent by construction.
- `docker-compose.yml` (Postgres 16), Makefile targets (`db-up`, `db-down`, `db-init`, `load`), `DATABASE_URL` in `.env.example`, and `docs/erd.md` with a mermaid ERD and the design reasoning.
- `tests/test_load_raw.py`, covering the full read, transform, and insert wiring against a faked cursor (row counts, column widths, empty dir).

**Why I made these decisions**
- Two social fact tables, not one. A Reddit post is one event; Trends is one row per day. Different grains. Splitting into `fact_social_posts` and `fact_search_interest` keeps every row meaningful instead of unioning mismatched grains behind a column of nulls.
- `search_term` as the natural key on `dim_shoes`, surrogate `shoe_key` as the FK. Raw records only know their ingestion term, so that's the reliable join key. The serial surrogate lets descriptive attributes change without rewriting fact rows.
- Idempotency lives in the schema, not the loader. Each fact has a natural-key unique constraint (`source_item_id`, `source_post_id`, `(shoe_key, point_date, geo)`), so `ON CONFLICT DO NOTHING` makes re-running the loader a no-op. That's the property I want before ever scheduling ingestion.
- `execute_values` over row-by-row inserts: one round trip per source instead of N, the standard psycopg2 bulk pattern.
- `dim_drops` seeded by hand at this stage (a real drops source comes later), with `release_type` constrained to `general`, `limited`, or `collab` so Phase 3 has a real `accepted_values` test to run.

**What I learned / got stuck on**
- Couldn't stand up a real Postgres in this environment (aarch64, no root), so I validated the loader's Python wiring against a fake cursor and ran the live load via Docker. The 10-test suite passes and ruff is clean.

**Next up**
- Run the real load locally (`make db-up && make db-init && make load`), confirm row counts, then Phase 3: dbt staging/intermediate/mart models with window functions and tests.

## 2026-06-19: Phase 1: Python ingestion layer

**What I built**
- Three source clients in `ingestion/`, all the same shape: a frozen dataclass for the record (`SoldListing`, `SocialSignal`, `TrendPoint`) and a client class whose public method is a generator, with private `_request`/`_parse` helpers doing the work.
  - `ebay.py`: sold listings via the eBay Finding API (`findCompletedItems`), including title-based US size parsing.
  - `reddit.py`: per-post engagement (score, comments) across the sneaker subreddits via PRAW.
  - `trends.py`: search interest over time via pytrends.
- `config.py`: a `Settings` dataclass holding the watchlist, subreddits, and credentials read from env (with optional `.env` support via python-dotenv).
- `storage.py`: `write_raw()` lands each batch as timestamped JSON in `data/raw/`.
- `run_ingestion.py`: the entrypoint that loops the watchlist, runs the clients, and writes one file per source/term. Small CLI (`--stub-trends`, `--log-level`).
- `tests/test_ingestion.py`: pytest cases covering stub output, determinism, size parsing, JSON round-trip, and the full run. Added `.env.example` and an API-setup table to the README.

**Why I made these decisions**
- Stub mode by default. Any client missing credentials logs a warning and yields deterministic synthetic records, so the whole pipeline runs end to end before I've registered a single key. The stubs are seeded per search term, which makes tests reproducible.
- Generators, not lists, as the public API. Streaming keeps memory flat and lets the entrypoint decide when to materialize, which matters once these are real paginated calls.
- Lazy imports of `requests`/`praw`/`pytrends` inside the real-path helpers, so stub mode and the test suite need none of them installed.
- Ingestion writes files only, no database. Keeping the landing zone on disk means the loader reads from `data/raw/` and the two layers stay independently testable.
- Caught broad `Exception` only at the per-term and per-request boundary (with `logger.exception`) so one bad request can't abort a run. Everything else uses narrow excepts.

**What I learned / got stuck on**
- eBay is nudging new integrations toward the Browse API. The Finding API still returns sold-listing data but may need migrating later. Noted in the README.
- Nothing blocking. Ran the entrypoint in stub mode (files landed), ruff clean, tests pass.

**Next up**
- Phase 2: hand-write the Postgres star schema and a `load_raw.py` that bulk-loads the JSON in `data/raw/` with `execute_values`.

## 2026-06-19: Phase 0: project scaffold

**What I built**
- Scaffolded the full `sneaker-intel` repo: ingestion/, db/, dbt_project/, dashboard/, data/raw/, docs/, tests/, and .github/workflows/.
- Added the README (description, tech stack, architecture sketch, phase checklist, run instructions), this DEVLOG, and starter config: .gitignore, requirements.txt, pyproject.toml, Makefile, Dockerfile.
- Initialized the git repo and made the first commit.

**Why I made these decisions**
- Kept the structure flat and conventional so it reads quickly to anyone reviewing the repo. The star-schema and dbt-layered approach is signposted in the README up front rather than buried.
- Documented the virtualenv setup in the README rather than committing a `.venv`. Environments are machine-specific and don't belong in version control.
- requirements.txt and pyproject.toml both present: requirements for a reproducible pinned install, pyproject for tooling config and project metadata.

**What I learned / got stuck on**
- Nothing blocking; this was setup. Deferred API keys and Postgres to their phases so the scaffold stays runnable as is.

**Next up**
- Phase 1: build the three ingestion modules following a shared dataclass + client pattern, with stubs until keys are registered.
