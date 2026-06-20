# dbt, and the window functions that earn their keep

With data loaded, the transformation layer is where the warehouse starts
answering questions. I built it in dbt with three layers: staging, intermediate,
and marts.

Staging is one model per source table — cast types, clean nulls, standardize
names. Cheap views, nothing clever. The intermediate layer is where the actual
domain logic lives: `int_sales_enriched` joins each sale to its shoe and its
release, then computes the numbers everything else depends on — days since
release, absolute premium, and percentage premium over retail. I put that in one
place on purpose. The premium definition is computed once, so every mart and any
future model share an identical version of it instead of redefining it five
slightly different ways.

The marts are what the dashboard reads. `mart_shoe_performance` aggregates per
shoe: average, median, and peak premium, plus volatility as the standard
deviation of premium. `mart_price_trajectory` is one row per sale, enriched with
the windowed context — and this is where window functions earn their keep. A
rolling 7-day average premium with `AVG() OVER`, the sale's premium rank within
its shoe with `RANK() OVER`, and the change versus the previous sale with
`LAG()`. Each of those computes in a single pass over the shoe's partition. The
correlated-subquery equivalents would re-scan per row — slower and far harder to
read.

Materialization follows the layer: staging and intermediate are views (they
should always reflect current raw data), marts are tables (the dashboard hits
them, so reads should be fast). Modeled tables live in their own `analytics`
schema, kept separate from the raw `public` tables the loader writes.

The part I'd defend hardest in a review is the tests. Not-null and unique on
every key, relationship tests from each fact back to `dim_shoes`, and
accepted-values on the release type. These aren't decoration — they're the thing
that tells me a refactor didn't silently break a join. `dbt build` runs the
models and the tests together, so a broken assumption fails loudly instead of
producing quietly wrong numbers.

When I first ran it against Postgres, every model built and all 44 tests passed.
That green run is the moment the warehouse stopped being a pile of SQL files and
became something I trust.

Next: putting a dashboard on top, and wiring CI that runs the whole pipeline.
