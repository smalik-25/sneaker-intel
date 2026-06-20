-- sneaker-intel warehouse schema (star schema, hand-written, no ORM).
--
-- Two conformed dimensions (dim_shoes, dim_drops) and three facts, one per
-- ingestion source:
--   fact_sales            <- eBay sold listings        (grain: one sold listing)
--   fact_social_posts     <- Reddit posts              (grain: one post)
--   fact_search_interest  <- Google Trends             (grain: one shoe-day)
--
-- dim_shoes is the conformed dimension every fact joins to. Natural key is the
-- ingestion search_term, which is how raw records reference a shoe before any
-- enrichment exists. Re-running the loader is idempotent: every fact has a
-- natural-key unique constraint and the loader inserts ON CONFLICT DO NOTHING.

-- Idempotent (re)creation for local dev. CASCADE also clears any dbt views
-- (analytics.stg_*) built on top of these tables; rebuild them with
-- `make transform`.
drop table if exists fact_search_interest cascade;
drop table if exists fact_social_posts cascade;
drop table if exists fact_sales cascade;
drop table if exists dim_drops cascade;
drop table if exists dim_shoes cascade;

-- ---------------------------------------------------------------------------
-- Dimensions
-- ---------------------------------------------------------------------------

-- One row per tracked shoe model. search_term is the natural key linking back
-- to raw ingestion files; descriptive attributes are enriched via seeds.sql.
create table dim_shoes (
    shoe_key      serial primary key,
    search_term   text not null unique,
    brand         text,
    silhouette    text,
    model_name    text,
    colorway      text,
    gender        text,
    created_at    timestamptz not null default now()
);

-- Release/"drop" reference data per shoe. Manually seeded for now (no drops
-- source ingested yet). Enables days-since-release and premium math in dbt.
create table dim_drops (
    drop_key      serial primary key,
    shoe_key      integer not null references dim_shoes (shoe_key),
    release_date  date not null,
    retail_price  numeric(10, 2) check (retail_price >= 0),
    release_type  text not null default 'general',
    region        text not null default 'US',
    constraint dim_drops_release_type_chk
        check (release_type in ('general', 'limited', 'collab')),
    constraint dim_drops_shoe_release_uq unique (shoe_key, release_date)
);

-- ---------------------------------------------------------------------------
-- Facts
-- ---------------------------------------------------------------------------

-- One row per sold listing, across sources (eBay, StockX). source_item_id is
-- unique so repeated ingestion of the same sale never double-counts, and the
-- `source` column records provenance.
create table fact_sales (
    sale_key        bigserial primary key,
    shoe_key        integer not null references dim_shoes (shoe_key),
    source          text not null default 'ebay',
    source_item_id  text not null unique,
    title           text,
    sold_price      numeric(10, 2) not null check (sold_price >= 0),
    currency        char(3) not null default 'USD',
    sold_date       date not null,
    condition       text,
    size            numeric(4, 1),
    ingested_at     timestamptz not null default now()
);

create index ix_fact_sales_shoe on fact_sales (shoe_key);
create index ix_fact_sales_sold_date on fact_sales (sold_date);
create index ix_fact_sales_source on fact_sales (source);

-- One row per Reddit post matching a tracked shoe. source_post_id deduplicates.
create table fact_social_posts (
    post_key        bigserial primary key,
    shoe_key        integer not null references dim_shoes (shoe_key),
    source_post_id  text not null unique,
    subreddit       text,
    title           text,
    score           integer not null default 0,
    num_comments    integer not null default 0,
    created_utc     timestamptz not null,
    ingested_at     timestamptz not null default now()
);

create index ix_fact_social_posts_shoe on fact_social_posts (shoe_key);
create index ix_fact_social_posts_created on fact_social_posts (created_utc);

-- One row per shoe per day of Google Trends interest. The (shoe, date, geo)
-- natural key deduplicates overlapping pulls.
create table fact_search_interest (
    interest_key  bigserial primary key,
    shoe_key      integer not null references dim_shoes (shoe_key),
    point_date    date not null,
    interest      smallint not null check (interest between 0 and 100),
    geo           text not null default 'US',
    ingested_at   timestamptz not null default now(),
    constraint fact_search_interest_uq unique (shoe_key, point_date, geo)
);

create index ix_fact_search_interest_shoe on fact_search_interest (shoe_key);
create index ix_fact_search_interest_date on fact_search_interest (point_date);
