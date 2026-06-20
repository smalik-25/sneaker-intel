-- Intermediate: each sale joined to its shoe and primary release, with the
-- core resale economics (days since release, absolute and percentage premium).
with sales as (
    select * from {{ ref('stg_sales') }}
),

shoes as (
    select * from {{ ref('stg_shoes') }}
),

-- A shoe can have multiple drops; use the earliest as the reference release.
primary_drop as (
    select distinct on (shoe_key)
        shoe_key,
        release_date,
        retail_price,
        release_type
    from {{ ref('stg_drops') }}
    order by shoe_key, release_date asc
)

select
    s.sale_key,
    s.shoe_key,
    sh.search_term,
    sh.brand,
    sh.silhouette,
    sh.model_name,
    s.size,
    s.condition,
    s.sold_price,
    s.sold_date,
    d.release_date,
    d.retail_price,
    d.release_type,
    (s.sold_date - d.release_date) as days_since_release,
    (s.sold_price - d.retail_price) as absolute_premium,
    round((s.sold_price - d.retail_price) / nullif(d.retail_price, 0), 4) as pct_premium
from sales s
inner join shoes sh on sh.shoe_key = s.shoe_key
left join primary_drop d on d.shoe_key = s.shoe_key
