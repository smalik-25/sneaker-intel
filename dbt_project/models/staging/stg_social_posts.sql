-- Staging: Reddit posts with a normalized subreddit and a derived post date.
with source as (
    select * from {{ source('raw', 'fact_social_posts') }}
)

select
    post_key,
    shoe_key,
    source_post_id,
    lower(subreddit) as subreddit,
    title,
    score,
    num_comments,
    created_utc,
    created_utc::date as created_date
from source
