-- Mart: one row per shoe summarizing its resale economics.
-- Question answered: which shoes carry the highest — and most volatile —
-- resale premium over retail?
with enriched as (
    select * from {{ ref('int_sales_enriched') }}
)

select
    shoe_key,
    search_term,
    brand,
    model_name,
    count(*) as sales_count,
    round(avg(sold_price), 2) as avg_sold_price,
    round(avg(absolute_premium), 2) as avg_absolute_premium,
    round(avg(pct_premium), 4) as avg_pct_premium,
    round(
        percentile_cont(0.5) within group (order by pct_premium)::numeric, 4
    ) as median_pct_premium,
    round(max(pct_premium), 4) as peak_pct_premium,
    round(stddev_pop(pct_premium), 4) as premium_volatility
from enriched
group by shoe_key, search_term, brand, model_name
