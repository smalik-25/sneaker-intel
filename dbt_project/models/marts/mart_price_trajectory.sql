-- Mart: one row per sale with rolling and ranked premium context.
-- Question answered: how does a shoe's resale premium move sale-over-sale,
-- and where does each sale rank within that shoe's history?
-- Uses window functions: AVG() OVER (rolling 7-day), RANK() OVER, LAG().
with enriched as (
    select * from {{ ref('int_sales_enriched') }}
)

select
    sale_key,
    shoe_key,
    search_term,
    brand,
    silhouette,
    size,
    sold_date,
    sold_price,
    pct_premium,

    -- Rolling 7-day average premium (current day + 6 prior calendar days).
    round(
        avg(pct_premium) over (
            partition by shoe_key
            order by sold_date
            range between interval '6 days' preceding and current row
        ),
        4
    ) as rolling_7d_avg_pct_premium,

    -- Where this sale's premium ranks within the shoe (1 = highest).
    rank() over (
        partition by shoe_key
        order by pct_premium desc
    ) as premium_rank_in_shoe,

    -- Change in premium versus this shoe's previous sale by date.
    round(
        pct_premium - lag(pct_premium) over (
            partition by shoe_key
            order by sold_date
        ),
        4
    ) as premium_delta_vs_prev_sale
from enriched
