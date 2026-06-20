# sneaker-intel

**Sneaker Resale Intelligence Platform** — an end-to-end data engineering project that ingests sneaker resale and demand signals, models them in a warehouse, transforms them with dbt, and surfaces them in a dashboard.

This is a personal portfolio project, built in public. Every phase is documented through Conventional Commits and a running [DEVLOG](DEVLOG.md). Predictive modeling / ML is a deliberate **Phase 2** extension and is intentionally out of scope for this build — the focus here is the data engineering foundation.

## Tech stack

| Layer | Tooling |
|---|---|
| Ingestion | Python (dataclasses, type hints), `requests`, `praw`, `pytrends` |
| Storage | PostgreSQL (hand-written star schema, no ORM), `psycopg2` |
| Transformation | dbt-core + dbt-postgres (staging / intermediate / marts) |
| Dashboard | Streamlit + pandas |
| Deployment | Docker, Makefile, GitHub Actions (CI), Railway/Render |

## Architecture (high level)

```
sources (eBay, Reddit, Google Trends)
        │  ingestion/  → raw JSON in data/raw/
        ▼
   PostgreSQL  (db/schema.sql — star schema)
        │  load_raw.py (bulk load)
        ▼
       dbt   (staging → intermediate → marts)
        │
        ▼
   Streamlit dashboard
```

## Progress

- [x] **Phase 0** — Project scaffold
- [x] **Phase 1** — Python ingestion layer (eBay / Reddit / Google Trends)
- [x] **Phase 2** — Database schema + raw loader (Postgres star schema)
- [x] **Phase 3** — dbt transformation layer (staging / intermediate / marts + tests)
- [ ] **Phase 4** — Streamlit dashboard (Market Overview / Shoe Deep Dive / Drop Calendar)
- [ ] **Phase 5** — Deployment & polish (Docker, Makefile, CI, live URL, README finalize)

## Run locally

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run ingestion (writes timestamped raw JSON to data/raw/)
make ingest
#   ...or force Google Trends offline:  python -m ingestion.run_ingestion --stub-trends

# Later phases:
make transform   # dbt build
make dashboard   # Streamlit app
```

## API credentials

Ingestion runs out of the box in **stub mode** — each source yields synthetic
records so the pipeline is testable before any keys exist. To pull real data,
copy `.env.example` to `.env` and fill in the keys below. Any client whose keys
are missing automatically falls back to stub mode (logged as a warning).

| Source | What to register | Where | Env vars |
|---|---|---|---|
| eBay | Join the eBay Developer Program, create an app, and use its production **App ID (Client ID)** keyset for the Finding API. | https://developer.ebay.com/ | `EBAY_APP_ID` |
| Reddit | Create a **script**-type app to get a client ID + secret. | https://www.reddit.com/prefs/apps | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` |
| Google Trends | No key required (pytrends scrapes the public endpoint). | — | — |

> Note: eBay is steering new integrations toward the **Browse API**; the Finding
> API still serves sold-listing data but may need migration later. `.env` is
> gitignored — never commit real keys.

## Repo layout

```
sneaker-intel/
├── ingestion/        # source clients + run_ingestion entrypoint
├── db/               # hand-written schema.sql
├── dbt_project/      # dbt models (staging / intermediate / marts)
├── dashboard/        # Streamlit app
├── data/raw/         # landed raw JSON (gitignored)
├── docs/             # erd.md, build-in-public posts
├── tests/            # pytest suite
├── .github/workflows # CI
├── DEVLOG.md         # append-only build log
├── Makefile  Dockerfile  requirements.txt  pyproject.toml
```
