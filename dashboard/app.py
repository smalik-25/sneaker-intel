"""Streamlit dashboard for sneaker-intel.

A thin reader over the dbt mart tables: it queries marts and hands DataFrames to
Streamlit charts/tables. All transformation logic lives in dbt: this app does
querying and presentation only.

Pages:
  1. Market Overview : KPIs + date-windowed ranking of shoes by resale premium.
  2. Shoe Deep Dive  : price trajectory, size breakdown, recent-vs-baseline.
  3. Drop Calendar   : release history with each shoe's premium context.

Run with: ``streamlit run dashboard/app.py`` (or ``make dashboard``). Reads the
connection from DATABASE_URL and the mart schema from DBT_PG_SCHEMA (default
``analytics``).
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

def _setting(key: str, default: str | None = None) -> str | None:
    """Read a setting from the environment, falling back to Streamlit secrets.

    Locally the value comes from .env / the environment; on Streamlit Community
    Cloud it comes from the app's Secrets. Accessing st.secrets with no secrets
    file raises, so the lookup is guarded.
    """
    value = os.getenv(key)
    if value:
        return value
    try:
        return st.secrets[key]
    except Exception:
        return default


MART_SCHEMA = _setting("DBT_PG_SCHEMA", "analytics")
RAW_SCHEMA = "public"


@st.cache_resource
def get_engine() -> Engine:
    """Build a cached SQLAlchemy engine from DATABASE_URL.

    pool_pre_ping checks a pooled connection is alive before using it (and
    reconnects if not), and pool_recycle drops connections older than 5 minutes.
    Together these handle serverless Postgres (e.g. Neon) auto-suspending while
    the cached engine is idle, which otherwise errors on the first query after a
    cold start.
    """
    dsn = _setting("DATABASE_URL")
    if not dsn:
        st.error(
            "DATABASE_URL is not set. Copy .env.example to .env (and make sure "
            "the database is running and loaded)."
        )
        st.stop()
    return create_engine(dsn, pool_pre_ping=True, pool_recycle=300)


@st.cache_data(ttl=300)
def run_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Run a read-only query and return a DataFrame (cached for 5 minutes)."""
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


# ---------------------------------------------------------------------------
# Page 1: Market Overview
# ---------------------------------------------------------------------------
def market_overview() -> None:
    st.header("Market Overview")
    st.caption("Resale premium = (sold price − retail) / retail.")

    kpis = run_query(
        f"""
        select
            count(*) as shoes_tracked,
            round(avg(avg_pct_premium), 4) as mean_premium,
            round(max(peak_pct_premium), 4) as highest_peak_premium,
            sum(sales_count) as total_sales
        from {MART_SCHEMA}.mart_shoe_performance
        """
    ).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Shoes tracked", int(kpis["shoes_tracked"]))
    c2.metric("Total sales", int(kpis["total_sales"]))
    c3.metric("Avg premium", f"{kpis['mean_premium']:.0%}")
    c4.metric("Highest peak", f"{kpis['highest_peak_premium']:.0%}")

    bounds = run_query(
        f"select min(sold_date) as lo, max(sold_date) as hi "
        f"from {MART_SCHEMA}.mart_price_trajectory"
    ).iloc[0]
    lo, hi = bounds["lo"], bounds["hi"]
    if pd.isna(lo):
        st.info("No sales loaded yet. Run `make ingest && make load && make transform`.")
        return

    start, end = st.slider(
        "Sale date window",
        min_value=lo,
        max_value=hi,
        value=(lo, hi),
        format="YYYY-MM-DD",
    )

    ranked = run_query(
        f"""
        select
            search_term,
            count(*) as sales_count,
            round(avg(pct_premium) * 100, 1) as avg_premium,
            round(max(pct_premium) * 100, 1) as peak_premium,
            round(stddev_pop(pct_premium), 4) as volatility
        from {MART_SCHEMA}.mart_price_trajectory
        where sold_date between :start and :end
        group by search_term
        order by avg_premium desc
        """,
        {"start": start, "end": end},
    )

    if ranked.empty:
        st.warning("No sales in the selected window.")
        return

    st.subheader("Top shoes by average premium")
    top10 = ranked.head(10)
    st.bar_chart(top10.set_index("search_term")["avg_premium"])

    st.subheader("All shoes (sortable)")
    st.dataframe(
        ranked,
        width="stretch",
        hide_index=True,
        column_config={
            "search_term": "Shoe",
            "sales_count": "Sales",
            "avg_premium": st.column_config.NumberColumn("Avg premium", format="%.1f%%"),
            "peak_premium": st.column_config.NumberColumn("Peak premium", format="%.1f%%"),
            "volatility": st.column_config.NumberColumn("Volatility", format="%.3f"),
        },
    )


# ---------------------------------------------------------------------------
# Page 2: Shoe Deep Dive
# ---------------------------------------------------------------------------
def shoe_deep_dive() -> None:
    st.header("Shoe Deep Dive")

    shoes = run_query(
        f"select distinct search_term from {MART_SCHEMA}.mart_shoe_performance "
        f"order by search_term"
    )["search_term"].tolist()
    if not shoes:
        st.info("No shoes available. Build the marts with `make transform`.")
        return

    shoe = st.selectbox("Shoe", shoes)

    traj = run_query(
        f"""
        select sold_date, sold_price, pct_premium, rolling_7d_avg_pct_premium, size
        from {MART_SCHEMA}.mart_price_trajectory
        where search_term = :shoe
        order by sold_date
        """,
        {"shoe": shoe},
    )
    if traj.empty:
        st.warning("No sales for this shoe.")
        return

    st.subheader("Premium trajectory")
    line = traj.set_index("sold_date")[["pct_premium", "rolling_7d_avg_pct_premium"]]
    st.line_chart(line)

    # Recent 7-day premium vs the prior 90-day baseline.
    latest = traj["sold_date"].max()
    recent_cut = latest - pd.Timedelta(days=7)
    base_cut = latest - pd.Timedelta(days=90)
    recent = traj.loc[traj["sold_date"] > recent_cut, "pct_premium"].mean()
    baseline = traj.loc[
        (traj["sold_date"] <= recent_cut) & (traj["sold_date"] > base_cut),
        "pct_premium",
    ].mean()

    c1, c2 = st.columns(2)
    c1.metric("Last 7 days avg premium", _fmt_pct(recent))
    if pd.notna(recent) and pd.notna(baseline):
        c2.metric(
            "vs 90-day baseline",
            _fmt_pct(baseline),
            delta=f"{(recent - baseline) * 100:.1f} pts",
        )
    else:
        c2.metric("vs 90-day baseline", _fmt_pct(baseline))

    st.subheader("Premium by size")
    by_size = (
        traj.dropna(subset=["size"])
        .groupby("size")["pct_premium"]
        .mean()
        .sort_index()
    )
    if by_size.empty:
        st.caption("No size data parsed for this shoe.")
    else:
        st.bar_chart(by_size)

    st.subheader("Search interest (Google Trends)")
    interest = run_query(
        f"""
        select point_date, interest
        from {MART_SCHEMA}.mart_search_interest
        where search_term = :shoe
        order by point_date
        """,
        {"shoe": shoe},
    )
    if interest.empty:
        st.caption("No Google Trends data for this shoe (not in the live watchlist).")
    else:
        st.line_chart(interest.set_index("point_date")["interest"])


# ---------------------------------------------------------------------------
# Page 3: Drop Calendar
# ---------------------------------------------------------------------------
def drop_calendar() -> None:
    st.header("Drop Calendar")
    st.caption("Release history with each shoe's resale-premium context.")

    drops = run_query(
        f"""
        select
            d.release_date,
            p.brand,
            p.model_name,
            d.release_type,
            d.retail_price,
            p.sales_count,
            round(p.avg_pct_premium * 100, 1) as avg_pct_premium,
            round(p.peak_pct_premium * 100, 1) as peak_pct_premium
        from {RAW_SCHEMA}.dim_drops d
        join {MART_SCHEMA}.mart_shoe_performance p on p.shoe_key = d.shoe_key
        order by d.release_date desc
        """
    )
    if drops.empty:
        st.info("No drops seeded. Run `make db-init`.")
        return

    st.dataframe(
        drops,
        width="stretch",
        hide_index=True,
        column_config={
            "release_date": "Released",
            "brand": "Brand",
            "model_name": "Model",
            "release_type": "Type",
            "retail_price": st.column_config.NumberColumn("Retail", format="$%.0f"),
            "sales_count": "Sales",
            "avg_pct_premium": st.column_config.NumberColumn("Avg premium", format="%.1f%%"),
            "peak_pct_premium": st.column_config.NumberColumn("Peak premium", format="%.1f%%"),
        },
    )


# ---------------------------------------------------------------------------
# Page 4: About
# ---------------------------------------------------------------------------
def about() -> None:
    st.header("About this project")
    st.markdown(
        """
I built **Sneaker Resale Intelligence** because resale price behavior is hard to
reason about from screenshots. Why a pair that retailed at $220 trades at
multiples of that, how the premium decays after a drop, why two colorways of the
same silhouette diverge. To see any of that clearly you need the data in one
place, modeled properly. This is that, end to end, built in public as a data
engineering portfolio project.

#### How it works

```
sources  ->  raw JSON  ->  PostgreSQL (star schema)  ->  dbt  ->  marts  ->  this dashboard
```

The pipeline pulls two real, key-free sources: the **StockX 2019 dataset** for
actual resale sales, and **Google Trends** for live search demand. Typed Python
clients land raw JSON, an idempotent loader bulk-loads it into a hand-written
**star schema** in PostgreSQL, and **dbt** transforms it across staging,
intermediate, and mart layers. The premium economics (premium over retail,
rolling averages, rank within a shoe) are computed with SQL window functions and
covered by dbt tests. This dashboard is a thin reader over the marts: every
number on it is a query against a modeled table, not math done in the app.

The eBay and Reddit API clients are built and tested but parked as future
extensions, since they need keys. The schema and loader already support them.

#### The three views

- **Market Overview** ranks shoes by resale premium, with a date-window filter.
- **Shoe Deep Dive** shows a shoe's premium trajectory, how premium varies across
  sizes, and its Google Trends interest over time.
- **Drop Calendar** pairs each release with the premium it went on to command.

#### Notes

The sales are the StockX 2019 dataset, so the figures reflect that era and its
Off-White / Yeezy heavy catalog. Without the dataset or a database connection,
the app falls back to synthetic stub data. Forecasting resale premium is the
deliberate next phase, not part of this build.
"""
    )


def _fmt_pct(value: float | None) -> str:
    """Format a fractional premium as a percentage, tolerating NaN/None."""
    return "n/a" if value is None or pd.isna(value) else f"{value:.0%}"


PAGES = {
    "Market Overview": market_overview,
    "Shoe Deep Dive": shoe_deep_dive,
    "Drop Calendar": drop_calendar,
    "About": about,
}


def main() -> None:
    st.set_page_config(page_title="Sneaker Resale Intelligence", layout="wide")

    st.title("Sneaker Resale Intelligence")
    st.caption(
        "Resale premiums and search demand across the sneaker market. "
        "An end-to-end data engineering project."
    )
    st.divider()

    st.sidebar.title("sneaker-intel")
    st.sidebar.caption("Resale Intelligence Platform")
    choice = st.sidebar.radio("Page", list(PAGES))
    PAGES[choice]()


if __name__ == "__main__":
    main()
