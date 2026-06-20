-- Staging: release reference data, one row per shoe-release.
with source as (
    select * from {{ source('raw', 'dim_drops') }}
)

select
    drop_key,
    shoe_key,
    release_date,
    retail_price,
    release_type,
    region
from source
