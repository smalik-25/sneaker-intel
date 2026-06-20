# A thin dashboard and CI that runs the whole pipeline

The last build phase had two halves: a dashboard people can actually look at, and
the deployment plumbing that makes the project trustworthy.

The dashboard is Streamlit, and the rule I held to is that it stays *thin*. Every
number it shows is a query against a dbt mart — not pandas transformation done in
the app. The modeling logic stays in dbt where it's tested; the app queries and
presents. There are a few pages: a market overview that ranks shoes by premium
with a date-window filter, a shoe deep dive with a premium trajectory line, a
size breakdown and Google Trends search interest, and a drop calendar pairing
each release with its realized premium. The database connection and schema come
from the same environment variables the loader and dbt use, so there's one source
of truth for where the data lives.

The half I care about more is CI. On every push, GitHub Actions spins up a
Postgres service, applies the schema and seeds, runs ingestion, loads the raw
data, and runs `dbt build` — models and tests — alongside ruff and pytest. It's
completely self-contained: no secrets, because the whole pipeline runs in stub
mode against a throwaway database. That's the strongest signal I can give that
the project actually works. It's not "the tests pass"; it's "the entire pipeline,
ingestion through transformation, runs clean from scratch on a machine that isn't
mine."

The Dockerfile packages the dashboard with dependency-layer caching, a non-root
user, and a bind to the platform's `$PORT` so the same image runs locally and on
a host like Railway or Render without edits. I wrote a deploy guide rather than
rushing a live URL — a live dashboard needs a cloud Postgres seeded with the
marts, and that's worth doing deliberately.

A small thing worth mentioning: the whole project ran on a "prepare files
locally, run git myself" workflow because of a quirk in my environment. Not
glamorous, but writing it down in the DEVLOG meant I never lost track of what was
committed.

That wraps the core build: ingestion, warehouse, transformations, dashboard, CI.
Five phases, each its own commit trail and DEVLOG entry. The one decision that
changed the project most, though, wasn't in this plan at all — it was where the
real data came from. That's the next post.
