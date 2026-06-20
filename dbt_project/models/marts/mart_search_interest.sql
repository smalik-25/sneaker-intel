-- Mart: Google Trends search interest per shoe over time.
-- Question answered: how does search demand for a shoe move over time, and how
-- does it line up with resale activity?
with interest as (
    select * from {{ ref('stg_search_interest') }}
),

shoes as (
    select * from {{ ref('stg_shoes') }}
)

select
    i.shoe_key,
    sh.search_term,
    i.point_date,
    i.interest,
    i.geo
from interest i
inner join shoes sh on sh.shoe_key = i.shoe_key
