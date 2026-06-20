# A thin dashboard and CI that runs the whole pipeline

The last build phase had two halves: a dashboard someone can actually read, and the plumbing that makes the project trustworthy.

The dashboard is Streamlit, and the rule I held to is that it stays thin. Every number it shows is a query against a dbt mart, not pandas transformation done in the app. The modeling stays in dbt where it's tested; the app queries and presents. A market overview ranks shoes by premium with a date-window filter. A shoe deep dive shows the premium trajectory, the size breakdown, and Google Trends search interest. A drop calendar pairs each release with the premium it actually went on to command. The size breakdown is the page I open first, because resale premium is rarely flat across sizes. The tails, the very small and very large, behave differently from the middle of the curve, and seeing that per shoe is the kind of thing screenshots never tell you.

The half I care about more is CI. On every push, GitHub Actions stands up a Postgres service, applies the schema and seeds, runs ingestion, loads the raw data, and runs `dbt build`, models and tests, alongside ruff and pytest. It's self-contained: no secrets, because the whole thing runs in stub mode against a throwaway database. That's the strongest signal I can give that the project works. Not "the tests pass," but "the entire pipeline, ingestion through transformation, runs clean from nothing on a machine that isn't mine."

The Dockerfile packages the dashboard with dependency-layer caching, a non-root user, and a bind to the platform's `$PORT` so the same image runs locally and on a host without edits. I wrote a deploy guide instead of rushing a live URL, since a live dashboard needs a cloud Postgres seeded with the marts, and that's worth doing deliberately.

One honest detail: the whole project ran on a "prepare files locally, run git myself" workflow because of a quirk in my setup. Not glamorous, but writing it down in the DEVLOG meant I always knew what was committed.

That closes the core build: ingestion, warehouse, transforms, dashboard, CI. Five phases, each with its own commit trail and DEVLOG entry. The decision that shaped the project most, though, wasn't in the original plan. It was where the real data came from. That's the next post.
