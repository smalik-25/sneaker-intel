-- Staging: clean eBay sold listings; drop non-positive prices and
-- default a missing condition.
with source as (
    select * from {{ source('raw', 'fact_sales') }}
)

select
    sale_key,
    shoe_key,
    source_item_id,
    title,
    sold_price,
    currency,
    sold_date,
    coalesce(condition, 'Unknown') as condition,
    size,
    ingested_at
from source
where sold_price > 0
