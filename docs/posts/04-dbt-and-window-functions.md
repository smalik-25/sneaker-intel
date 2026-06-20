# dbt, and the window functions that pull their weight

With data loaded, the transformation layer is where the warehouse starts answering the questions I actually care about. I built it in dbt across three layers: staging, intermediate, marts.

Staging is one model per source table. Cast types, clean nulls, standardize names. Cheap views, nothing clever. The intermediate layer is where the resale logic lives. `int_sales_enriched` joins each sale to its shoe and its release, then computes the numbers everything downstream depends on: days since release, absolute premium, and percentage premium over retail. I defined those once, on purpose. Premium is the central metric of this whole project, and I don't want it computed five slightly different ways across five models.

The marts are what the dashboard reads. `mart_shoe_performance` aggregates per shoe: average, median, and peak premium, plus volatility as the standard deviation of premium. That volatility column is the one I find most interesting. A shoe averaging a 200% premium with low volatility is a different asset from one averaging 200% with wild swings, and resale traders price that difference even when they don't name it.

`mart_price_trajectory` is one row per sale with windowed context, and this is where window functions pull their weight. A rolling 7-day average premium with `AVG() OVER`, the sale's premium rank within its shoe with `RANK() OVER`, and the change from the previous sale with `LAG()`. Each computes in a single pass over the shoe's partition. The correlated-subquery versions would re-scan per row, slower and harder to read. Premium decay after a drop, the slow bleed as hype fades, only shows up if you can see each sale in the context of the ones around it. That's what these give me.

Materialization follows the layer. Staging and intermediate are views, since they should always reflect current raw data. Marts are tables, because the dashboard hits them and reads should be fast. Modeled tables sit in their own `analytics` schema, separate from the raw `public` tables.

The part I'd defend hardest in review is the tests. Not-null and unique on every key, relationship tests from each fact back to `dim_shoes`, accepted-values on release type. They're what tells me a refactor didn't silently break a join. `dbt build` runs models and tests together, so a broken assumption fails loudly instead of producing quietly wrong premiums.

First real run against Postgres: every model built, all 44 tests passed.

Next: the dashboard, and CI that runs the whole pipeline from scratch.
