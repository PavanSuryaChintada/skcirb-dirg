# Build phases

Progress tracker for SPEC-2 §8. Each phase stops at its own check before the next starts.

- [x] **Phase 0 — Recon.** Elexon endpoints curled, fixtures saved, shapes pinned in `ASSUMPTIONS.md`.
- [x] **Phase 1 — Skeleton.** Repo, Docker Compose, FastAPI `/api/health`, React placeholder, DB via `DATABASE_URL`.
  Verified from a clean state (no-cache images, `.env.example`, all containers healthy).
- [x] **Phase 2 — Ingestion.** Both datasets in Supabase, idempotent (three runs, identical counts and checksums).
- [x] **Phase 3 — Core logic.** `selection.py`, `alignment.py`, `metrics.py`, tests first; hand check matches to 6 dp.
- [x] **Phase 4 — API.** All SPEC-1 §6 endpoints + by-cutoff, by-tercile, scatter; every endpoint executed against Supabase.
- [x] **Phase 5 — Dashboard.** Verdict headline, four stat cards, forecast vs actual with P5–P95 band, shared-axis error bars, provenance; defaults to the worst day (28 Jan).
- [x] **Phase 6 — Accuracy screen.** Bias-led headline, metric table, by-hour, cut-off lever, lead time (all vintages), histogram with P5/P50/P95, 45° scatter, terciles; figures match the API.
- [x] **Phase 7 — Detail + export.** Sortable, filterable 48-row table and CSV download; missing forecasts are blank in both.
- [ ] **Phase 8 — Deploy**
- [ ] **Phase 9 — Docs**

Run phases 4 through 9 back to back. After each phase print a one-line PHASE N DONE
summary and continue. Only stop early if a phase fails its own check or hits a decision
not covered here. Commit after each phase. No co-author line.

## Phase 4 — API

All endpoints in SPEC-1 §6 plus `GET /api/metrics/by-cutoff`.
- Metrics computed server-side only. Pydantic response models.
- Every metrics response includes `cutoff_hour` and `n_observations`.
- Clear 4xx with a useful message for dates outside the loaded range.
- `/api/day/{date}` returns the 48-period step-expanded view, flagged as expanded;
  `/api/metrics/*` return hourly-based figures.

Check: open `/docs`, execute every endpoint, paste one real response.

## Phase 5 — Dashboard

SPEC-1 Screen 1. Date picker + cut-off-hour selector, four stat cards,
forecast-vs-actual chart with the P5–P95 band, error bar chart below sharing the X
axis, provenance line showing the selected publishTime.
- X axis is clock time, not period index. All axes labelled with units.
- Caption the chart: forecast is hourly, held constant across both settlement periods.
- Default the date to a day with a large error, not 1 January.
- Loading and error states on every data fetch.

Check: screenshot the dashboard.

## Phase 6 — Accuracy screen

SPEC-1 Screen 2: metric table, error by hour of day, error by horizon (all vintages,
labelled as such), distribution histogram with P5/P50/P95 lines, forecast-vs-actual
scatter with 45-degree line, persistence skill score, and the MAE/RMSE vs cut-off-hour
chart.

Check: screenshot, and confirm the headline figures match the API.

## Phase 7 — Detail + export

SPEC-1 Screen 3: sortable table, one row per settlement period, columns per spec, CSV
export. Missing forecasts render as blank, never 0.

## Phase 8 — Deploy

Frontend to Vercel (root `frontend/`, `VITE_API_BASE_URL` set). Backend Docker image to
the Heroku container registry, bind to `$PORT`, `DATABASE_URL` config var.
CORS: explicit Vercel domain + `localhost:3000`. No wildcard.
Seed the deployed DB, or commit the January snapshot and load it there.

Check: paste both live URLs and confirm each loads data.

## Phase 9 — Docs

README with all ten items in SPEC-2 §9, including the AI tool disclosure.
`docs/ARCHITECTURE.md` with a Mermaid diagram. Finalise `ASSUMPTIONS.md`.
Run the SPEC-2 §11 pre-submission checklist and report pass/fail per line.
Confirm: repo public, random name, no secrets in `git log -p`, pytest passes with no
network.

Final output: live URLs, pytest summary, checklist results, anything still outstanding.
