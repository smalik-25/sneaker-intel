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


# Faint hauntological grain overlay (fractal noise), screen-blended on the void.
_GRAIN = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E"
    "%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E"
    "%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E"
)

_BRAND_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant:ital,wght@0,400..700;1,400..600&family=Space+Grotesk:wght@300..700&family=IBM+Plex+Mono:wght@400..600&display=swap');

:root {
  --void:#0b0b0f; --pitch:#060608; --slab:#131318; --slab-2:#1b1b22;
  --hairline:#26262e; --hairline-2:#34343e;
  --bone:#ece7d8; --bone-dim:#b6b1a4; --ash:#847f74;
  --phosphor:#c8f24a; --oxblood:#8e1c24;
}

.stApp { background-color: var(--void); }
html, body, .stApp, p, span, div, label, li, [class*="st-"] {
  font-family: 'Space Grotesk', sans-serif;
  color: var(--bone-dim);
}
h1, h2, h3, h4, h5 {
  font-family: 'Cormorant', serif !important;
  font-weight: 600; letter-spacing: -0.02em; color: var(--bone) !important;
}
h3 { font-size: 1.5rem !important; }
a, a:visited { color: var(--phosphor); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Mono brand marks */
.sm-eyebrow {
  font-family: 'IBM Plex Mono', monospace; font-size: 11px; letter-spacing: .14em;
  text-transform: uppercase; color: var(--ash); margin-bottom: .35rem;
}
.sm-title {
  font-family: 'Cormorant', serif; font-weight: 600; font-size: 3.4rem; line-height: 1.0;
  letter-spacing: -0.02em; color: var(--bone); margin: 0 0 .3rem;
}
.sm-section-title {
  font-family: 'Cormorant', serif; font-weight: 600; font-size: 2rem; line-height: 1.05;
  letter-spacing: -0.02em; color: var(--bone); margin: .2rem 0 .3rem;
}
.sm-sub { font-family: 'Space Grotesk', sans-serif; color: var(--bone-dim); font-size: 1rem; }
.sm-rule { border: 0; border-top: 1px solid var(--hairline); margin: 1rem 0 1.6rem; }

/* DataField-style metrics */
[data-testid="stMetric"] {
  background: var(--slab); border: 1px solid var(--hairline); border-radius: 0; padding: 14px 16px;
}
[data-testid="stMetricLabel"] p {
  font-family: 'IBM Plex Mono', monospace !important; text-transform: uppercase;
  letter-spacing: .12em; font-size: 11px !important; color: var(--ash) !important;
}
[data-testid="stMetricValue"] {
  font-family: 'Cormorant', serif !important; color: var(--bone) !important; font-weight: 600;
}

/* Hard gothic edges + hairlines */
.stButton > button, [data-baseweb="input"], [data-baseweb="select"] > div,
.stDataFrame, [data-testid="stTable"] { border-radius: 0 !important; }
.stButton > button {
  font-family: 'IBM Plex Mono', monospace; text-transform: uppercase; letter-spacing: .1em;
  border: 1px solid var(--hairline-2); color: var(--bone);
}
.stDataFrame thead tr th {
  font-family: 'IBM Plex Mono', monospace !important; text-transform: uppercase;
  letter-spacing: .08em; font-size: 11px !important; color: var(--ash) !important;
}

section[data-testid="stSidebar"] {
  background: var(--pitch); border-right: 1px solid var(--hairline);
}

/* Grain overlay (restrained) */
.stApp::before {
  content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 9999;
  opacity: .035; mix-blend-mode: screen; background-image: url("%GRAIN%");
}
</style>
""".replace("%GRAIN%", _GRAIN)


def _inject_brand_styles() -> None:
    """Apply the Sam Malik 'Two Currents' design system to the Streamlit app."""
    st.markdown(_BRAND_CSS, unsafe_allow_html=True)


def _section(index: str, title: str, caption: str | None = None) -> None:
    """Render a brand section header: mono eyebrow + gothic-serif title + optional caption."""
    st.markdown(
        f'<div class="sm-eyebrow">&sect; {index} &middot; {title.upper()}</div>'
        f'<div class="sm-section-title">{title}</div>',
        unsafe_allow_html=True,
    )
    if caption:
        st.markdown(
            f'<div class="sm-sub" style="margin-bottom:.6rem">{caption}</div>',
            unsafe_allow_html=True,
        )


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
    _section("0.1", "Market Overview", "Resale premium = (sold price − retail) / retail.")

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
    _section("0.2", "Shoe Deep Dive", "Premium trajectory, size curve, and search demand per shoe.")

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
    _section("0.3", "Drop Calendar", "Release history with each shoe's resale-premium context.")

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
    _section("0.4", "About", "What this is and how it's built.")
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
    _inject_brand_styles()

    st.markdown(
        '<div class="sm-eyebrow">0.0 &middot; SNEAKER RESALE INTELLIGENCE '
        '&middot; DATA PIPELINE</div>'
        '<div class="sm-title">Sneaker Resale Intelligence</div>'
        '<div class="sm-sub">Resale premiums and search demand across the sneaker market '
        '&middot; an end-to-end data engineering project</div>'
        '<hr class="sm-rule"/>',
        unsafe_allow_html=True,
    )

    st.sidebar.markdown(
        '<div class="sm-eyebrow">SAM&middot;MALIK &middot; DATA</div>'
        '<div style="font-family:Cormorant,serif;font-weight:600;font-size:1.7rem;'
        'color:#ece7d8;line-height:1;margin-bottom:.2rem">sneaker&middot;intel</div>'
        '<div class="sm-eyebrow" style="color:#555049">Resale Intelligence Platform</div>',
        unsafe_allow_html=True,
    )
    choice = st.sidebar.radio("Page", list(PAGES))
    PAGES[choice]()


if __name__ == "__main__":
    main()
