-- Staging: one clean row per tracked shoe, with a normalized gender.
with source as (
    select * from {{ source('raw', 'dim_shoes') }}
)

select
    shoe_key,
    search_term,
    brand,
    silhouette,
    model_name,
    colorway,
    coalesce(gender, 'unknown') as gender
from source
