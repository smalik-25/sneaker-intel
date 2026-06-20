-- Seed/enrich reference data for the watchlist shoes.
--
-- Safe to run before OR after load_raw.py: the INSERT ... ON CONFLICT upserts
-- dim_shoes by its natural key (search_term), so descriptive attributes land
-- whether or not the loader has already created the shoe row. dim_drops is
-- hand-maintained until a real drops source is ingested; values here are
-- representative reference data, not authoritative pricing.

insert into dim_shoes (search_term, brand, silhouette, model_name, colorway, gender)
values
    ('Air Jordan 1 High',        'Nike',         'Air Jordan 1',   'Air Jordan 1 High',        null,                  'mens'),
    ('Nike Dunk Low Panda',      'Nike',         'Dunk Low',       'Nike Dunk Low Retro',      'Black/White (Panda)', 'mens'),
    ('Yeezy Boost 350 V2',       'adidas',       'Yeezy Boost 350','Yeezy Boost 350 V2',       null,                  'unisex'),
    ('New Balance 550',          'New Balance',  '550',            'New Balance 550',          null,                  'unisex'),
    ('Travis Scott Jordan 1 Low','Nike',         'Air Jordan 1',   'Air Jordan 1 Low OG SP',   'Travis Scott',        'mens')
on conflict (search_term) do update set
    brand      = excluded.brand,
    silhouette = excluded.silhouette,
    model_name = excluded.model_name,
    colorway   = excluded.colorway,
    gender     = excluded.gender;

-- Representative release data, keyed to dim_shoes via search_term.
insert into dim_drops (shoe_key, release_date, retail_price, release_type, region)
select s.shoe_key, d.release_date, d.retail_price, d.release_type, 'US'
from (values
    ('Air Jordan 1 High',         date '2023-09-09', 180.00, 'general'),
    ('Nike Dunk Low Panda',       date '2021-03-10', 110.00, 'general'),
    ('Yeezy Boost 350 V2',        date '2022-02-26', 230.00, 'limited'),
    ('New Balance 550',           date '2021-05-20', 120.00, 'general'),
    ('Travis Scott Jordan 1 Low', date '2019-07-20', 150.00, 'collab')
) as d (search_term, release_date, retail_price, release_type)
join dim_shoes s on s.search_term = d.search_term
on conflict (shoe_key, release_date) do nothing;
