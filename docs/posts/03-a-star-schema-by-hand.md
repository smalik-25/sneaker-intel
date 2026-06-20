# Designing the warehouse: a star schema, by hand

With raw JSON landing on disk, the next phase was the warehouse. I wrote the
Postgres schema by hand — no ORM — because I wanted the constraints, indexes, and
grain to be explicit and something I could talk through, not generated behind a
framework.

It's a star schema. A conformed `dim_shoes` dimension that every fact joins to, a
`dim_drops` table for release reference data, and fact tables for the events:
sales, social posts, search interest. The data is read-heavy and analytical —
the questions are "average premium per shoe," "demand versus sale volume over
time" — and a star schema keeps those to a single dimension join. It's also the
shape dbt and BI tools expect downstream.

The decision I spent the most time on was grain. Reddit posts are one row per
post; Google Trends is one row per day. Those are genuinely different grains, so
forcing them into a single "social signals" table would mean mixing grains and
storing a pile of NULLs. I split them into separate fact tables instead. Every
row stays meaningful, and I never accidentally average a post score against a
daily interest index.

For keys, I used the ingestion search term as the natural key on `dim_shoes` —
it's the only thing raw records reliably know before any enrichment — with a
surrogate `shoe_key` as the foreign key the facts actually carry. That way
descriptive attributes can change without rewriting fact rows.

The property I care about most is idempotency, and I put it in the schema rather
than the loader. Each fact has a natural-key unique constraint — the source
item id on sales, the post id on social, and (shoe, date, geo) on search
interest. The loader inserts with `ON CONFLICT DO NOTHING`. So re-running
ingestion is a safe no-op: overlapping pulls never double-count. That's the
property I'd want before ever putting ingestion on a schedule.

The loader itself uses `execute_values` for bulk inserts — one round trip per
source instead of a row-by-row crawl — and it reads from `data/raw/`, never from
the source APIs. Clean separation, again.

I couldn't spin up Postgres in every environment I worked in, so I validated the
loader's logic against a fake database cursor first, then ran it for real against
a Dockerized Postgres. The row counts came out exactly as expected, and a second
run inserted zero rows — idempotency, confirmed.

Next: dbt, and the window functions that actually earn their place.
