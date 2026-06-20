# Building a data engineering project in public

I wanted a portfolio project that showed how I actually work, not just a finished
repo that appears fully formed. So I'm building sneaker-intel — a sneaker resale
intelligence platform — in public, one phase at a time, with the reasoning
written down as I go.

The idea is simple: pull sneaker resale and demand signals, model them properly
in a warehouse, transform them with dbt, and put a dashboard on top. The
interesting part isn't the sneakers. It's the data engineering: ingestion that
doesn't fall over, a schema I can defend, transformations that are tested, and a
pipeline that runs the same way on my machine and in CI.

Two habits are doing the heavy lifting for the "in public" part. The first is a
running DEVLOG — one entry per work session, written in first person, explaining
what I built and *why* I made the calls I did. It's the raw material for these
posts and, honestly, for talking through the project in an interview later. The
second is commit discipline: Conventional Commits, one logical change per commit,
so the git history reads like a story rather than a single end-of-week dump.

For the first session I just scaffolded the repo: the package layout (ingestion,
db, dbt, dashboard), a README with a phase checklist, the DEVLOG template, and
the usual config — gitignore, requirements, a Makefile, a Dockerfile. First
commit: `chore: scaffold project structure`.

One small decision I'm already glad about: I documented how to create the
virtualenv in the README rather than committing one. Environments are
machine-specific and don't belong in version control. It's a tiny thing, but
those tiny things are what separate a repo that looks tidy from one that's
actually pleasant to clone.

One deliberate scope decision up front: no machine learning. Predictive modeling
is a tempting place to jump straight to, but it's a Phase 2 extension here. The
whole point of this build is the foundation underneath any forecasting — reliable
ingestion, a clean warehouse, tests. Get that right first.

Next up: the ingestion layer, and a pattern I'm fond of — making the whole
pipeline runnable before I've registered a single API key.
