# Deploying the dashboard

The dashboard is a Streamlit app that reads the dbt **mart** tables from
Postgres. So deploying means three things: a **cloud Postgres**, **loading the
data** into it (ingest → load → dbt build), and **hosting the app** pointed at
that database via `DATABASE_URL`.

Two paths below. Railway is the simplest single-platform option; Streamlit
Community Cloud + Neon is a free split option.

---

## Prerequisites (both paths)

- The repo pushed to GitHub.
- A local virtualenv with `requirements.txt` installed (used to seed the cloud
  database once).

## Option A: Railway (app + managed Postgres)

1. Create an account at https://railway.app and a new project.
2. **Add a Postgres database**: New → Database → PostgreSQL. Copy its connection
   string from the database's *Connect* tab (looks like
   `postgresql://user:pass@host:port/railway`).
3. **Seed the cloud database from your machine** (one time). Point the local
   tooling at the cloud DB and run the pipeline:
   ```bash
   export DATABASE_URL="postgresql://user:pass@host:port/railway"   # the Railway URL
   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/schema.sql -f db/seeds.sql
   python -m ingestion.run_ingestion --stub-trends
   python -m db.load_raw
   ( cd dbt_project && DBT_PROFILES_DIR=. \
       DBT_PG_HOST=host DBT_PG_PORT=port DBT_PG_USER=user \
       DBT_PG_PASSWORD=pass DBT_PG_DBNAME=railway dbt build )
   ```
   (Fill the `DBT_PG_*` values from the same connection string.)
4. **Deploy the app**: New → GitHub Repo → select this repo. Railway detects the
   `Dockerfile` and builds it.
5. **Set the app's variables** (Variables tab): add `DATABASE_URL` (the same
   Railway Postgres URL) and `DBT_PG_SCHEMA=analytics`. Railway provides `PORT`
   automatically; the Dockerfile already honors it.
6. Open the generated public URL. Put it in the README's live-demo line.

## Option B: Streamlit Community Cloud + Neon (free)

1. **Create a free Postgres at https://neon.tech** and copy its connection
   string (it already ends in `?sslmode=require`).
2. **Seed it from your machine** with one command. With the venv active and the
   StockX CSV in `data/external/`:
   ```bash
   export DATABASE_URL="postgresql://...neon...?sslmode=require"
   make seed-remote
   ```
   This applies the schema and seeds, runs ingestion and the loader, and builds
   the dbt models and tests against Neon. `scripts/seed_remote.py` derives the
   `DBT_PG_*` settings from `DATABASE_URL`, so there's nothing else to set.
3. **Deploy the app at https://share.streamlit.io**: New app, pick this repo,
   main file path `dashboard/app.py`.
4. **Add secrets** (app → Settings → Secrets), in TOML:
   ```toml
   DATABASE_URL = "postgresql://...neon...?sslmode=require"
   DBT_PG_SCHEMA = "analytics"
   ```
   `app.py` reads these from the environment, falling back to Streamlit secrets.
5. Launch and copy the public URL into the README.

---

## Refreshing data later

Re-running ingestion and rebuilding the marts against the cloud `DATABASE_URL`
updates the live dashboard (the loader is idempotent, so re-runs only add new
rows):

```bash
export DATABASE_URL="<cloud url>"
python -m ingestion.run_ingestion && python -m db.load_raw
( cd dbt_project && DBT_PROFILES_DIR=. dbt build )
```

> Note: the current data is synthetic stub data. Register real eBay/Reddit keys
> (see the README "API credentials" section) before treating any numbers as real.
