# Designing the warehouse: a star schema, by hand

With raw JSON landing on disk, the next job was the warehouse. I wrote the Postgres schema by hand, no ORM, because I wanted the grain, constraints, and indexes to be explicit. When someone asks why a table is shaped the way it is, "the ORM generated it" is not an answer I want to give.

It's a star schema. A conformed `dim_shoes` dimension that every fact joins to, a `dim_drops` table for release reference data, and fact tables for the events: sales, social posts, search interest. Resale questions are analytical and read-heavy. What's the average premium per shoe, how does demand track sale volume over time, which silhouettes hold value. A star schema keeps those to a single dimension join, and it's the shape dbt and BI tools expect downstream.

The decision I spent the most time on was grain, and it's where the resale domain actually shows up in the modeling. A sold listing is one event. A Reddit post is one event. But Google Trends is one row per day, an index, not a transaction. Forcing post-level and day-level data into a single "social signals" table would mean mixing grains and storing a wall of nulls. So I split them. Every row means one specific thing, and I never accidentally average a post score against a daily interest value.

For keys I used the ingestion search term as the natural key on `dim_shoes`, with a surrogate `shoe_key` as the foreign key the facts carry. The term is the only thing raw records reliably know before enrichment, and the surrogate lets descriptive attributes change without rewriting fact rows.

The property I care about most is idempotency, and I put it in the schema, not the loader. Each fact has a natural-key unique constraint: the source item id on sales, the post id on social, and (shoe, date, geo) on search interest. The loader inserts with `ON CONFLICT DO NOTHING`. Re-running ingestion is a safe no-op, which is exactly what you want before putting any of this on a schedule. Resale pulls overlap constantly; the same sold listing shows up in two windows, and you do not want it counted twice when you're measuring premium.

The loader uses `execute_values` for bulk inserts, one round trip per source, and reads only from `data/raw/`. I validated its logic against a fake cursor first, then ran it against a Dockerized Postgres. Counts came out exactly as expected, and a second run inserted zero rows.

Next: dbt, and the window functions that actually pull their weight.
