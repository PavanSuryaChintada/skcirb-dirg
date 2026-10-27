# SPEC 2 — Engineering Build Specification

**Companion to SPEC-1-PRODUCT.md. Read that first for domain rules and metric
definitions. This document covers stack, structure, build order and delivery.**

> **Revised 2026-10-26 after Phase 0 recon.** Changes: `core/alignment.py` added
> (hourly metric frame + display expansion); fetch window has an exclusive upper bound;
> past-hour forecast rows are stored and filtered at query time; reject-negative applies
> to WIND only; `/api/metrics/by-cutoff` added. Evidence: `docs/ASSUMPTIONS.md`.

Target effort: **16 hours.** Every decision below is optimised for shipping, not
for architectural purity. Where the two conflict, shipping wins, and the trade-off
gets stated in the README rather than engineered away.

---

## 1. Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | React 18 + Vite + TypeScript | Vite for fast builds and a trivial Vercel deploy |
| Charts | Recharts | Declarative, good tooltips, fastest route to labelled axes |
| Styling | Tailwind CSS | No design system to build in 16 hours |
| Backend | **FastAPI** (Python 3.11) | Async HTTP, Pydantic validation, free OpenAPI docs at `/docs` |
| Data processing | pandas | The dataset is tiny; pandas is the clearest way to express the metrics |
| Database | **Supabase Postgres** | Managed, free tier, no infra. Used as plain Postgres only |
| DB access | SQLAlchemy 2.x + psycopg | Keeps the data layer swappable |
| Container | Docker + docker-compose | Required by the brief |
| Tests | pytest | Focused on the metric maths, not on coverage percentage |
| Deploy | Vercel (frontend) + Heroku container (backend) | Satisfies both the Docker and the hosting requirement |

### 1.1 Explicit non-choices — put this reasoning in the README

- **Not Django.** No auth, no admin, no forms, no user-generated writes. The ORM and
  admin would be unused weight on a read-only analytics API.
- **Supabase is used as a managed Postgres instance only.** No Supabase Auth, no
  `supabase-js`, no row-level security, no realtime. The frontend never talks to
  Supabase — it only talks to FastAPI. One data path, one place for logic.
- **No Celery, Redis, or scheduler.** The study window is a fixed, closed month.
  Ingestion is a one-shot idempotent command, not a recurring job.
- **Fallback if Supabase is slow to set up:** SQLite via the same SQLAlchemy layer.
  Changing `DATABASE_URL` must be the only change required. Do not let the database
  choice block progress past hour 3.

---

## 2. Repository layout

Repo name must be a random string, e.g. `kjhwr`. No "wind", "elexon" or "forecast"
in the repo name.

```
.
├── README.md
├── CLAUDE.md
├── docker-compose.yml
├── .env.example
├── .gitignore
│
├── specs/
│   ├── SPEC-1-PRODUCT.md
│   └── SPEC-2-ENGINEERING.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt     # pytest + httpx; not installed in the image
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, router registration
│   │   ├── config.py            # env-driven settings (pydantic-settings)
│   │   ├── db.py                # SQLAlchemy engine + session
│   │   ├── models.py            # ORM tables
│   │   ├── schemas.py           # Pydantic response models
│   │   ├── ingest/
│   │   │   ├── elexon_client.py # HTTP client for the two Elexon endpoints
│   │   │   └── loader.py        # fetch -> normalise -> upsert
│   │   ├── core/
│   │   │   ├── periods.py       # settlement period <-> timestamp conversion
│   │   │   ├── alignment.py     # hourly metric frame + 48-SP display expansion (SPEC-1 §3.5)
│   │   │   ├── selection.py     # decision-time forecast selection (SPEC-1 §3.3)
│   │   │   └── metrics.py       # every formula from SPEC-1 §4
│   │   └── routers/
│   │       ├── meta.py          # /api/health and /api/meta
│   │       ├── day.py
│   │       ├── metrics.py
│   │       └── export.py
│   ├── scripts/
│   │   └── ingest.py            # CLI entry point: python -m scripts.ingest
│   └── tests/
│       ├── fixtures/            # raw one-day Elexon responses from Phase 0
│       ├── test_health.py       # Phase 1 smoke test, SQLite, no network
│       ├── test_periods.py
│       ├── test_selection.py    # MOST IMPORTANT TEST FILE
│       └── test_metrics.py
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── api/client.ts        # all fetch calls, one place
│       ├── pages/
│       │   ├── Dashboard.tsx
│       │   ├── Accuracy.tsx
│       │   └── DailyDetail.tsx
│       └── components/
│           ├── StatCard.tsx
│           ├── ForecastActualChart.tsx
│           ├── ErrorBarChart.tsx
│           ├── ErrorDistribution.tsx
│           └── MetricsTable.tsx
│
└── docs/
    ├── ARCHITECTURE.md          # diagram + data flow, for the video
    └── ASSUMPTIONS.md           # every assumption, numbered
```

---

## 3. Data layer

### 3.1 Elexon endpoints

Base URL: `https://data.elexon.co.uk/bmrs/api/v1` — public, no API key.

```
GET /datasets/FUELHH/stream?publishDateTimeFrom={iso}&publishDateTimeTo={iso}
GET /datasets/WINDFOR/stream?publishDateTimeFrom={iso}&publishDateTimeTo={iso}
```

**TASK 0, before writing any other code:** curl one day from each endpoint, save the
raw JSON into `backend/tests/fixtures/`, and inspect it. Confirm:

- whether the `/stream` response is a bare JSON array or wrapped in `{"data": [...]}`
- the exact field names and casing
- whether `settlementDateFrom`/`settlementDateTo` are accepted as an alternative
  window parameter for FUELHH
- the publication cadence of WINDFOR and how far ahead each publish reaches

Write the real shape into `docs/ASSUMPTIONS.md`. **Do not guess the schema from this
spec** — pin it against the live API, then code to what you saw. Those fixtures then
become the test data, so the test suite runs with no network access.

Fetch window: pull from **2025-12-30** through the end of **2026-02-01** so that D-1
forecasts for 1 January and late-publishing actuals for 31 January are both captured.
The window is `[2025-12-30T00:00Z, 2026-02-02T00:00Z)` — **exclusive upper bound**.

Elexon's `publishDateTimeTo` is *inclusive* (verified, ASSUMPTIONS A4), so the client
must enforce the exclusive bound itself: drop rows with `publishTime >= 2026-02-02T00:00Z`
after fetching. Chunk boundaries overlap by one publish for the same reason; the
upsert absorbs those identical rows.

Verified shapes (pinned in ASSUMPTIONS.md): both `/stream` endpoints return a bare
JSON array; WINDFOR rows carry only `dataset, publishTime, startTime, generation`, so
`settlement_date` / `settlement_period` for forecasts are derived from `startTime`.

### 3.2 Schema

```sql
CREATE TABLE actuals (
    start_time        TIMESTAMPTZ NOT NULL,
    settlement_date   DATE        NOT NULL,
    settlement_period SMALLINT    NOT NULL,
    generation_mw     DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (start_time)
);

CREATE TABLE forecasts (
    start_time        TIMESTAMPTZ NOT NULL,
    publish_time      TIMESTAMPTZ NOT NULL,
    settlement_date   DATE        NOT NULL,
    settlement_period SMALLINT    NOT NULL,
    generation_mw     DOUBLE PRECISION NOT NULL,
    horizon_hours     DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (start_time, publish_time)
);

CREATE INDEX idx_fc_start_publish ON forecasts (start_time, publish_time DESC);
CREATE INDEX idx_fc_date          ON forecasts (settlement_date);
CREATE INDEX idx_ac_date          ON actuals   (settlement_date);
```

- Composite PK on forecasts makes ingestion idempotent — rerunning never duplicates.
- Store `horizon_hours` at write time. Cheap, and it keeps query code simple.
  It **can be negative**: every WINDFOR publish includes past hours. Those rows are
  stored as published; analytics exclude them with an explicit
  `WHERE horizon_hours >= 0`. Never delete them at ingest.
- WINDFOR is hourly, so `forecasts.settlement_period` is always the first SP of its
  hour (odd numbers 1, 3, … 47).
- Use `ON CONFLICT DO UPDATE` for upserts.

### 3.3 Ingestion

`python -m scripts.ingest --from 2025-12-30 --to 2026-02-01`

Requirements:

- Idempotent — safe to run repeatedly
- Chunk the date range (one week per request) to avoid oversized responses
- Retry with exponential backoff on 5xx and timeouts
- Log row counts in and out, and reject obviously bad rows (null times; negative MW
  **for `fuelType = "WIND"` rows only** — negative MW is valid for interconnectors
  and pumped storage, which are exports and pumping, not bad data)
- Mirror the source faithfully: past-hour WINDFOR rows are stored, not filtered
- Print a summary: rows fetched, rows written, date coverage, any gaps found
- Must complete in under 3 minutes for the full window. Measured 122–154 s against a
  Tokyo-region Supabase pooler; network-bound, not code-bound. The original 2-minute
  target assumed a same-region database, which an EU-region project would likely
  meet (ASSUMPTIONS D12)

**Commit the ingested data as a seed file** (`backend/seed/january_2026.sql.gz` or a
parquet pair). Reason: if Elexon is down or slow during your demo recording or
during their evaluation, the app still works. State in the README that the seed is a
convenience snapshot and `scripts/ingest.py` is the source of truth.

---

## 4. Core logic — the four files that matter

Everything else is plumbing. These four carry the assignment.

### 4.1 `core/periods.py`

- `settlement_period(ts) -> int` (1–48)
- `period_start(date, sp) -> datetime`
- Assert 48 periods per day across the whole January window and fail loudly otherwise.
  January has no clock change — the assertion documents that and protects the code if
  it is ever pointed at a different month.

### 4.2 `core/selection.py` — implement SPEC-1 §3.3 exactly

```python
def cutoff_for(delivery_date: date, cutoff_hour: int) -> datetime:
    """Latest moment a forecast could have been used for delivery_date."""

def decision_time_forecasts(
    delivery_date: date,
    cutoff_hour: int,
    session: Session,
) -> list[ForecastRow]:
    """
    Latest forecast per hourly start_time with publish_time <= cutoff and
    horizon_hours >= 0. Hours with no qualifying forecast are returned with
    forecast_mw = None.
    Never interpolate. Never fall back to a later publish.
    """
```

SQL approach: `DISTINCT ON (start_time) ... WHERE publish_time <= :cutoff
AND horizon_hours >= 0 ORDER BY start_time, publish_time DESC`.

Selection is per **hourly** `start_time` (24 per day). The returned rows feed the
hourly metric frame directly; they are step-expanded only for display (§4.4).

### 4.3 `core/metrics.py`

Pure functions on a DataFrame with `forecast_mw` and `actual_mw`:

```python
def error_series(df) -> pd.Series            # f - a
def compute_metrics(df) -> MetricSet         # ME, MAE, RMSE, nMAE, P5/P50/P95, max, energy
def persistence_baseline(df, actuals) -> pd.Series
def skill_score(rmse_model, rmse_baseline) -> float
def group_metrics(df, by) -> list[MetricSet] # by hour / day / horizon bucket / wind tercile / cut-off
```

The input frame is always the hourly frame from `alignment.to_hourly`. The horizon
grouping takes all vintages with `horizon_hours >= 0` (SPEC-1 §3.4); every other
grouping takes decision-time selections only. `by-cutoff` runs selection once per
candidate hour (02, 04, 07, 09, 11) and computes the full metric set for each.

Rules:

- Drop rows where either side is null **before** computing, and return the surviving
  `n` alongside every metric
- No MAPE in headline outputs (SPEC-1 §4.1)
- Pure functions, no DB access, no FastAPI imports — that is what makes them testable

### 4.4 `core/alignment.py` — implement SPEC-1 §3.5 exactly

```python
def to_hourly(actuals_df) -> pd.DataFrame:
    """Mean MW of the two half-hourly actuals in each hour. One row per hour."""

def expand_to_periods(hourly_forecast_df) -> pd.DataFrame:
    """48-row per-SP frame. Each hourly forecast held constant across both
    half-hours of its hour. Presentation only — never fed to metrics.py."""
```

Rules:

- Metrics ALWAYS run on the hourly frame. n = 744 for the full month.
- A missing hourly forecast expands to two missing periods (None), never 0.
- Any response that carries step-expanded values says so (a field or label the UI
  renders as "forecast is published hourly, held constant across both settlement
  periods").
- Pure functions, no DB access, same as `metrics.py`.

---

## 5. Testing — small, targeted, and demonstrable

Do not chase coverage. A handful of test files, roughly 20–25 tests total, all
runnable offline against the saved fixtures.

**`test_selection.py` — the highest-value tests in the project:**

- Given forecasts published at 06:00, 08:00 and 10:00 on D-1 for the same period and
  a 09:00 cut-off, the 08:00 one is selected
- A forecast published after the cut-off is never selected, even when it is the only one
- A period with no pre-cut-off forecast returns None, not 0 and not the next available
- Changing `cutoff_hour` changes the selected row
- **The real 2026-01-15 late publish** (11:30 slot, published 12:25), from the Phase 0
  WINDFOR fixture: for delivery day 2026-01-16, a 12:00 cut-off selects the
  2026-01-15T09:30Z publish, and a 13:00 cut-off selects the 12:25 one
- Cut-offs 00:00–02:00 return None for hours 22:00 and 23:00, never 0
- A row with `horizon_hours < 0` is never selected

**`test_alignment.py`:**

- `to_hourly` averages the two half-hours of each hour; 48 SPs in → 24 hours out
- `expand_to_periods` gives 48 rows, each hourly value on both of its SPs
- A missing hourly forecast expands to two None periods, never 0

**`test_metrics.py`:**

- Hand-computed MAE/RMSE/bias on a 5-row fixture match to 6 decimal places
- Perfect forecast gives MAE = RMSE = bias = 0 and skill score = 1 vs a worse baseline
- Null handling: nulls excluded, `n` reported correctly

**`test_periods.py`:**

- Midnight UTC → SP1, 23:30 → SP48, round-trip conversions hold for all 48

In the Part 2 video, run `pytest -v` on camera. Twenty passing, well-named tests on
the logic that matters reads far better than a coverage badge.

---

## 6. Docker

**`backend/Dockerfile`** — multi-stage, non-root user, `python:3.11-slim`, healthcheck
hitting `/api/health`.

**`frontend/Dockerfile`** — Node build stage, nginx serve stage.

**`docker-compose.yml`** — three services: `db` (postgres:16, local dev only),
`backend` (depends on db health), `frontend`. Named volume for pg data.

Single-command start is a hard requirement of the README:

```bash
cp .env.example .env
docker compose up --build
# frontend http://localhost:3000, API docs http://localhost:8000/docs
docker compose exec backend python -m scripts.ingest --from 2025-12-30 --to 2026-02-01
```

Verify this works from a fresh clone before recording. A failed `docker compose up`
during evaluation is fatal and completely avoidable.

---

## 7. Deployment

**Frontend → Vercel**
- Root directory `frontend/`, framework preset Vite
- Env var `VITE_API_BASE_URL` pointing at the Heroku backend
- Check the deployed build in incognito

> **Revised 2026-10-27:** the backend is deployed to **Render** (`render.yaml`, Docker,
> free plan, Singapore region) instead of Heroku, which no longer has a free tier
> (ASSUMPTIONS D13). The Heroku steps below are kept for reference.

**Backend → Heroku container**
```bash
heroku container:login
heroku create <random-name>
heroku container:push web -a <random-name>
heroku container:release web -a <random-name>
heroku config:set DATABASE_URL=<supabase-connection-string> -a <random-name>
```
- Bind to `$PORT` — Heroku injects it and ignores a hardcoded port
- Use the Supabase **connection pooler** URI, not the direct one, and add `?sslmode=require`

**CORS:** allow the Vercel domain and `localhost:3000` explicitly. Do not ship `*`;
the tech lead will notice.

**Cold starts:** Heroku free dynos sleep. Hit the app once before recording the video
and once before submitting the form.

---

## 8. Build order — 16 hours

Hard rule: **nothing from a later phase before the current phase works end to end.**

| Phase | Hours | Deliverable |
|---|---|---|
| **0. Recon** | 0.5 | Curl both endpoints, save fixtures, confirm schema, write ASSUMPTIONS.md |
| **1. Skeleton** | 1.5 | Repo, Docker Compose, FastAPI `/api/health` green, React renders, DB connected |
| **2. Ingestion** | 2.0 | Both datasets in Postgres, idempotent, row counts verified |
| **3. Core logic** | 3.0 | selection.py + alignment.py + metrics.py + tests passing. **The heart of the assignment** |
| **4. API** | 1.5 | All endpoints in SPEC-1 §6 including `/api/metrics/by-cutoff`, visible and working in `/docs` |
| **5. Dashboard** | 2.5 | Screen 1 complete with the P5–P95 error band and the step-expansion label |
| **6. Accuracy** | 2.0 | Screen 2 complete, every metric displayed, MAE/RMSE vs cut-off chart |
| **7. Detail + CSV** | 1.0 | Screen 3 and export |
| **8. Deploy** | 1.0 | Vercel + Heroku live, verified in incognito |
| **9. Docs + polish** | 1.0 | README, ARCHITECTURE.md, labelled axes, loading and error states |

Running behind? Cut in this order: wind-tercile breakdown, then the scatter plot,
then Screen 3. **Never cut:** the cut-off logic, the P5–P95 band, the metric tests,
or the deployment. Those four are what is actually being assessed.

---

## 9. README — required contents

The brief names three mandatory items. Include all of them plus the rest below.

1. **One-paragraph overview** of what the app does and for whom
2. **Live links** — Vercel frontend, Heroku API, `/docs`
3. **File and directory guide** — the tree from §2 with one line per directory
4. **How to start** — the Docker commands from §6, copy-pasteable, tested from a fresh clone
5. **Architecture diagram** — a Mermaid block is enough
6. **Key assumptions** — the 09:00 UTC cut-off, UTC == UK local in January, national
   level only, January 2026 only
7. **Metric definitions** — copy SPEC-1 §4 verbatim so reviewers need not dig
8. **Testing** — how to run, what is covered and what deliberately is not
9. **AI tool disclosure — REQUIRED BY THE BRIEF.** State plainly which AI tools were
   used and for what. Omitting this breaks an explicit instruction.
10. **Known limitations and next steps** — one month of data, no price data so error
    is not monetised, no automated refresh, national level masks regional error

---

## 10. Part 2 of the video — tech walkthrough, 5 minutes

Reviewers want to know the code is navigable, not that it is clever.

1. **40s — architecture.** The diagram. React → FastAPI → Postgres, one data path,
   all logic server-side. Say why not Django in one sentence.
2. **60s — the data problem.** Open `selection.py`. This is the intellectual core:
   excluding hindsight forecasts. Show the SQL and the test proving a post-cut-off
   forecast is never chosen.
3. **60s — the metrics.** Open `metrics.py`. Show the pure functions. Explain the
   MAPE decision and the persistence baseline in one sentence each.
4. **45s — tests.** Run `pytest -v` live.
5. **45s — API.** Open `/docs`, execute one endpoint, show the real response.
6. **40s — practices.** Typed Pydantic schemas, idempotent ingestion, multi-stage
   Docker, non-root container user, env-driven config, no secrets in the repo.
7. **30s — what I would do next with more time.** Monetise the error with day-ahead
   prices; add regional breakdown; add a scheduled refresh; probabilistic rather than
   point forecasts. This answers "do they know what good looks like" better than
   anything else you can say.

---

## 11. Pre-submission checklist

- [ ] Repo is **public** and the name is a random string
- [ ] Fresh clone + `docker compose up --build` works with no manual fixes
- [ ] Vercel URL opens in **incognito** and loads data from the live backend
- [ ] Heroku API and `/docs` both open in **incognito**
- [ ] YouTube video is **unlisted**, under 10:00, both parts present, audio audible
- [ ] README has all ten items from §9, including the AI disclosure
- [ ] No `.env`, no secrets, no connection strings committed. Check `git log -p`.
- [ ] `pytest` passes on a clean checkout with no network access
- [ ] Every URL in the submission form opened in incognito and verified
