-- Staging: Google Trends interest points, one row per shoe-day.
with source as (
    select * from {{ source('raw', 'fact_search_interest') }}
)

select
    interest_key,
    shoe_key,
    point_date,
    interest,
    geo
from source
