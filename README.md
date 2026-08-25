# BoxBox

Pit-stop strategy advisor for Formula 1. Given the state of a race at lap *N*, recommend
**BOX** or **SEGUIR**, the compound to fit, and the net time it is worth.

Built for the *Inteligencia Artificial Avanzada* Trabajo Práctico Integral (UTN FRBA), which
follows the **IDEAL** methodology. The conceptualización — static and dynamic models,
pseudo-rules, decision tables — lives in [`docs/tp/`](docs/tp/).

> Status: **scaffold + validated data pipeline.** The backend is generated and green, the
> FastF1 ingest and feature pipeline run end-to-end on real races, and the frontend is an
> untouched Vite scaffold. No model has been trained yet.

## Layout

A plain-folder monorepo, same shape as [Margen](https://github.com/tomasanchez/margen):

```text
boxbox/
  apps/
    api/    # FastAPI backend (scaffolded from cosmic-fastapi)
    ml/     # FastF1 ingest, feature engineering, models
    web/    # React + Vite + TypeScript frontend
  docs/
    research/   # verified findings — read fastf1.md before touching the data layer
    tp/         # the academic deliverables (conceptualización, entregas)
  Makefile
```

## The system, in two layers

The recommendation is deliberately **not** one end-to-end model. A race engineer will not act
on a recommendation they cannot interrogate, so the architecture splits:

| Layer | What it does | Why |
|---|---|---|
| **Learned** | Regression over tyre degradation: how much time is this compound losing per lap, at this circuit, at this track temperature | Degradation genuinely varies by circuit, compound and temperature; no fixed threshold survives contact with the data |
| **Symbolic** | Rules and decision tables consuming those numbers to produce BOX / SEGUIR | Every recommendation arrives with the rules that fired. This is the auditable half |

A supervised classifier trained on what teams actually did runs alongside as a control and a
baseline — not as the source of truth, because the real decision was not always the right one.

## Quick start

Requires [uv](https://docs.astral.sh/uv/), Node 22 with Corepack (`corepack enable`),
Docker, and `make`.

```powershell
make install     # uv sync (api, ml) + pnpm install (web)
make smoke       # verify the FastF1 pipeline on two known races
make db          # start local PostgreSQL
make migrate     # apply backend migrations
```

Then, in separate terminals:

```powershell
make api         # FastAPI on http://localhost:8000
make web         # Vite on http://localhost:5173
```

`make help` lists every target.

## Working with the data

```powershell
make ingest SEASONS="2023 2024"   # -> apps/ml/data/laps.parquet
make ml                            # JupyterLab against the ML workspace
```

The first ingest downloads from the F1 live-timing API and is slow. Everything after hits the
local cache in `apps/ml/data/` — gitignored, large, and fully re-derivable.

**Read [`docs/research/fastf1.md`](docs/research/fastf1.md) before touching the data layer.**
It records what was measured rather than what the docs claim, including three traps that
silently corrupt results: `TyreLife` is not laps-into-stint, `TrackStatus` is a concatenated
string, and the positive class is only ~3% of laps.

## Backend scaffold reproducibility

`apps/api` was generated from the [`cosmic-fastapi`](https://github.com/tomasanchez/cosmic-fastapi)
Copier template on the `main` ref:

```powershell
uvx copier copy --trust --vcs-ref main --defaults `
  --data project_name="BoxBox API" --data project_slug="boxbox-api" `
  --data package_name="boxbox_api" --data database="postgres" `
  --data include_user_example=false `
  gh:tomasanchez/cosmic-fastapi apps/api
```

| Question | Value |
|---|---|
| project_name | `BoxBox API` |
| project_slug | `boxbox-api` |
| package_name | `boxbox_api` |
| author_name | `Tomas Sanchez` |
| author_email | `info@tomsanchez.com` |
| github_owner | `tomasanchez` |
| license | `MIT` |
| python_version | `3.13` |
| database | `postgres` (asyncpg) |
| include_user_example | `false` |

## Decisions

Architecture decisions are recorded as ADRs under `decisions/boxbox/`.
