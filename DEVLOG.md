# DEVLOG

An append-only build log for sneaker-intel. One entry per work session, newest at the top. Written in first person — what got built, and *why* the decisions were made. This is the raw material for interview prep and the eventual project writeup.

## Entry template

```
## YYYY-MM-DD — <short title>

**What I built**
- ...

**Why I made these decisions**
- ...

**What I learned / got stuck on**
- ...

**Next up**
- ...
```

---

## 2026-06-19 — Phase 0: project scaffold

**What I built**
- Scaffolded the full `sneaker-intel` repo: ingestion/, db/, dbt_project/, dashboard/, data/raw/, docs/, tests/, and .github/workflows/.
- Added README (description, tech stack, architecture sketch, phase checklist, run instructions), this DEVLOG, and starter config: .gitignore, requirements.txt, pyproject.toml, Makefile, Dockerfile.
- Initialized the git repo and made the first commit.

**Why I made these decisions**
- Kept the structure flat and conventional so it reads quickly to anyone reviewing the repo. The star-schema / dbt-layered approach is signposted in the README up front rather than buried.
- Chose to *document* the virtualenv setup in the README rather than commit a `.venv` — environments are machine-specific and don't belong in version control.
- requirements.txt and pyproject.toml both present: requirements for a reproducible pinned install, pyproject for tooling config (ruff/black/pytest) and project metadata.

**What I learned / got stuck on**
- Nothing blocking — this was setup. Deferred actual API keys and Postgres setup to their respective phases so the scaffold stays runnable as-is.

**Next up**
- Phase 1: build the three ingestion modules (eBay, Reddit, Google Trends) following a shared dataclass + client pattern, with stubs until API keys are registered.
