# Building a data engineering project in public

I've spent a lot of time staring at sneaker resale prices, trying to understand why a pair that retailed at $220 trades at $900 eighteen months later, and why the premium on the next colorway behaves completely differently. The honest answer is that you can't reason about it from screenshots. You need the data in one place, modeled properly, so you can actually ask questions of it. That's what sneaker-intel is.

So I'm building it in public, one phase at a time, and writing down the reasoning as I go. The plan is straightforward to say and less straightforward to do well: pull resale and demand signals, model them in a warehouse, transform them with dbt, and put a dashboard on top. The sneakers are the fun part. The point is the data engineering underneath: ingestion that doesn't fall over, a schema I can defend, transforms that are tested, and a pipeline that runs the same on my laptop and in CI.

Two habits carry the "in public" side. The first is a running DEVLOG, one entry per session, written in first person, where I explain what I built and why I made each call. It's the raw material for these posts and for talking through the project later. The second is commit discipline: Conventional Commits, one logical change each, so the history reads like a sequence of decisions instead of one Friday-afternoon dump.

This first session was just scaffolding. Package layout (ingestion, db, dbt, dashboard), a README with a phase checklist, the DEVLOG template, and the usual config. First commit: `chore: scaffold project structure`. One small thing I already like: I documented how to create the virtualenv in the README instead of committing one. Environments are machine-specific and don't belong in version control.

One decision up front: no machine learning yet. Predicting resale premium is the obvious place to want to jump, and it's where I'll eventually go. But a forecast is only as good as the warehouse under it, and most of the hard, unglamorous work is in that warehouse. Build that first, then model on top of something you trust.

Next post: the ingestion layer, and why I made the whole thing run before registering a single API key.
