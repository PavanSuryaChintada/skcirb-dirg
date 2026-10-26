# Assumptions and verified facts

Each entry is numbered and dated. "Verified" means checked against a live Elexon
response on that date, not taken from the spec. Raw responses are in
`backend/tests/fixtures/`. Decisions taken on the Phase 0 findings are in the
**Decisions** section (D1–D9); questions still open are listed after them and are
**not** settled here.

---

## Endpoints

**A1. (2026-10-26, verified) Base URL and auth.**
`https://data.elexon.co.uk/bmrs/api/v1`. Public, no API key. Responses come back as
`200`, `Content-Type: application/json; charset=utf-8`.

**A2. (2026-10-26, verified) `/stream` returns a bare JSON array.**
Both FUELHH and WINDFOR return `[ {...}, {...} ]`. There is no `{"data": [...]}`
wrapper.

**A3. (2026-10-26, verified) FUELHH accepts both window styles.**
- `publishDateTimeFrom` / `publishDateTimeTo` worked first time (format
  `YYYY-MM-DDTHH:MMZ`). This is the one SPEC-2 §3.1 names.
- `settlementDateFrom` / `settlementDateTo` also work (format `YYYY-MM-DD`).
  `From=To=2026-01-15` returned exactly 960 rows (48 periods x 20 fuel types), all
  with `settlementDate` 2026-01-15.

**A4. (2026-10-26, verified) FUELHH publish window includes both ends.**
For `From=2026-01-15T00:00Z&To=2026-01-16T00:00Z`, rows with `publishTime`
`2026-01-15T00:00:00Z` **and** `2026-01-16T00:00:00Z` both came back. So weekly
chunks with shared boundaries overlap by one publish (20 rows). They are exact
duplicates, so an upsert on the primary key absorbs them. WINDFOR never publishes on
a chunk boundary in this window, so its boundary behaviour was not observed.

## Pinned shapes

**A5. (2026-10-26, verified) FUELHH row shape.** All 980 rows in the fixture have
exactly these keys, in this order:

| field | JSON type | example |
|---|---|---|
| `dataset` | string | `"FUELHH"` |
| `publishTime` | string | `"2026-01-15T00:00:00Z"` |
| `startTime` | string | `"2026-01-14T23:30:00Z"` |
| `settlementDate` | string | `"2026-01-14"` |
| `settlementPeriod` | integer | `48` |
| `fuelType` | string | `"WIND"` |
| `generation` | integer | `14482` |

```json
{"dataset":"FUELHH","publishTime":"2026-01-15T00:00:00Z","startTime":"2026-01-14T23:30:00Z","settlementDate":"2026-01-14","settlementPeriod":48,"fuelType":"WIND","generation":14482}
```

**A6. (2026-10-26, verified) WINDFOR row shape.** All 584 rows in the fixture have
exactly these keys:

| field | JSON type | example |
|---|---|---|
| `dataset` | string | `"WINDFOR"` |
| `publishTime` | string | `"2026-01-15T22:30:00Z"` |
| `startTime` | string | `"2026-01-14T21:00:00Z"` |
| `generation` | integer | `16732` |

```json
{"dataset":"WINDFOR","publishTime":"2026-01-15T22:30:00Z","startTime":"2026-01-14T21:00:00Z","generation":16732}
```

WINDFOR has **no** `settlementDate` or `settlementPeriod`. Those columns in the
SPEC-2 §3.2 `forecasts` table would have to be derived from `startTime`.

**A7. (2026-10-26, verified) Timestamp format.** Every `publishTime` and `startTime`
in both datasets is exactly 20 characters, `YYYY-MM-DDTHH:MM:SSZ`: UTC `Z` suffix, no
offset, no fractional seconds. `settlementDate` is `YYYY-MM-DD`.

**A8. (2026-10-26) Units.** The payload carries no unit field. `generation` is taken
as MW, per SPEC-1 §3.1. Both datasets return integers.

## FUELHH (actuals)

**A9. (2026-10-26, verified) Wind is `fuelType == "WIND"`, uppercase, exact.**
The 20 fuel types present are: BIOMASS, CCGT, COAL, INTELEC, INTEW, INTFR, INTGRNL,
INTIFA2, INTIRL, INTNED, INTNEM, INTNSL, INTVKL, NPSHYD, NUCLEAR, OCGT, OIL, OTHER,
PS, WIND.

**A10. (2026-10-26, verified) Settlement period matches UTC start time.**
For all 32,660 unique rows in the window,
`settlementPeriod == (startTime - settlementDate 00:00Z) / 30 min + 1`. This is
consistent with UTC == UK local time across the study window (SPEC-1 §3.1).

**A11. (2026-10-26, verified) Publish lag.** FUELHH is normally published at
`startTime + 30 min`, i.e. at the end of the period. Only 4 WIND rows in the whole
window were late, all on 2026-01-15, which is the fixture day:

| SP | startTime | publishTime | lag |
|---|---|---|---|
| 21 | 2026-01-15T10:00Z | 2026-01-15T12:25Z | 2:25 |
| 22 | 2026-01-15T10:30Z | 2026-01-15T12:26Z | 1:56 |
| 23 | 2026-01-15T11:00Z | 2026-01-15T12:26Z | 1:26 |
| 24 | 2026-01-15T11:30Z | 2026-01-15T12:26Z | 0:56 |

On the same day the usual 11:30 WINDFOR publish came out at 12:25 instead (A15).
The likely cause is a publishing delay at Elexon. That is inferred, not confirmed.
Selection keys on `publishTime`, so a late publish is correctly excluded from any
cut-off earlier than when it actually appeared. A Phase 3 test must prove this on the
real case (D6).

**A12. (2026-10-26, verified) No revisions.** No WIND `startTime` has more than one
`publishTime` in the fetched window. One actual per period.

**A13. (2026-10-26, verified) Negatives exist, but not for wind.** WIND has 0
negatives and 0 zeros (range 1,695 to 17,805 MW over the window). Negative
`generation` does occur for interconnectors (INTGRNL, INTIRL, INTEW, INTNEM, INTVKL)
and pumped storage (PS). Those are exports and pumping, not bad data. **Decided:** the
reject-negative rule applies to `fuelType = "WIND"` rows only (D7).

## WINDFOR (forecasts)

**A14. (2026-10-26, verified) WINDFOR is hourly.** Every `startTime` in the window
falls on the hour (`HH:00:00Z`; 19,856 of 19,856 rows), with 1-hour steps inside
each publish. Settlement periods are half-hourly. See open question Q1.

**A15. (2026-10-26, verified) Publish cadence: 8 per day.** Usual times (UTC):
02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30. All 34 publish dates in the
window have exactly 8 publishes. The one irregularity: on 2026-01-15 the 11:30
publish appeared at 12:25. Gaps between consecutive publishes range from 2 h to 4 h.

**A16. (2026-10-26, verified) Every publish covers the same fixed 73-hour block.**
All 272 publishes have exactly 73 hourly rows, running from **21:00Z the day before
the publish date** to **21:00Z two days after it**. The block does not depend on the
publish hour. As a result:
- Furthest reach ahead (`last startTime - publishTime`): 66.5 h for the 02:30 publish
  down to 46.5 h for the 22:30 publish.
- **Every publish also includes hours that are already past** (`startTime <
  publishTime`), back to -5.5 h (02:30 publish) and -25.5 h (22:30 publish). Under
  SPEC-1 §3.4 these rows have negative `horizon_hours`. See Q3.

**A17. (2026-10-26, verified) Which publishes cover a delivery day D.**
For every January day, 32 distinct `publishTime`s contain at least one hour of D:
- 8 from D-2: cover D 00:00 to 21:00 only (22 of 24 hours)
- 8 from D-1: cover all of D
- 8 from D: cover all of D
- 8 from D+1: cover D 21:00 to 23:00 only

Of these, 11 have `publishTime <= cutoff(D)` at the 09:00 default: the 8 from D-2,
plus D-1 at 02:30, 04:30 and 07:30.

**A18. (2026-10-26, verified) What the 09:00 cut-off selects.** For all 31 January
days, the decision-time forecast (SPEC-1 §3.3, latest `publishTime <= cutoff`) is the
**D-1 07:30Z publish** for all 24 hours. Selected horizons run from 16.5 h to 39.5 h.
The D-1 09:30 publish lands 30 minutes after the default cut-off, so a 10:00 cut-off
would pick a different publish.

**A19. (2026-10-26, verified) Cut-off sensitivity.** Hourly slots across January (out
of 744) that have a decision-time forecast:
- cut-off 00:00 to 02:00 UTC: 682. Each day's 22:00 and 23:00 have no qualifying
  forecast, because the latest qualifying publish is from D-2 and stops at D 21:00.
- cut-off 03:00 to 23:00 UTC: 744, full coverage.

These are real gaps, not data errors. Under SPEC-1 §3.3 they must be shown as
`forecast_available = false`. **Decided:** those hours (SP45 to SP48 when
step-expanded) render as gaps, never as zero (D8).

## Data quality and coverage

**A20. (2026-10-26, verified) Quality over the full window.** Both datasets: 0 nulls
in any field, and 0 duplicate keys apart from the FUELHH chunk-boundary overlaps in
A4 (identical values). WIND and WINDFOR have 0 negatives and 0 zeros. WINDFOR ranges
from 2,250 to 21,353 MW.

**A21. (2026-10-26, verified) Coverage, 2025-12-30 to 2026-02-01.**
Fetched as `publishDateTimeFrom=2025-12-30T00:00Z` to `publishDateTimeTo=2026-02-02T00:00Z`,
in five chunks of up to 7 days each. Total wall time was about 38 s, sequential.

| dataset | raw rows | unique rows | notes |
|---|---|---|---|
| FUELHH (all fuels) | 32,740 | 32,660 | 80 boundary duplicates (4 boundaries x 20 fuels) |
| FUELHH WIND only | — | 1,633 | 2025-12-29 SP48 through 2026-02-01 SP48 |
| FUELHH WIND, January | — | **1,488** | = 31 days x 48 SPs; every day has SP1 to SP48 exactly |
| WINDFOR | 19,856 | 19,856 | 272 publishes x 73 rows; 2025-12-30 02:30Z to 2026-02-01 22:30Z |

December 30 and 31 actuals are complete, which the persistence baseline for 1 January
needs (SPEC-1 §4.2). February 1 actuals are also complete.

**A21a. (2026-10-26, verified) Counts under the exclusive upper bound (D4).** The
table above used Elexon's inclusive `To`. Dropping rows with `publishTime >=
2026-02-02T00:00Z` removes exactly 20 FUELHH rows, one per fuel type. The single WIND
row among them is 2026-02-01 SP48 (startTime 23:30Z, published 2026-02-02T00:00Z).
Under the window as decided:

| dataset | unique rows |
|---|---|
| FUELHH (all fuels) | 32,640 |
| FUELHH WIND only | 1,632 (2026-02-01 has 47 SPs) |
| FUELHH WIND, January | **1,488**, unchanged |
| WINDFOR | 19,856, unchanged (no publish lands on the bound) |

All 48 January 31 WIND actuals were published before the bound. January is
unaffected.

**A22. (2026-10-26) Fixtures.** Raw bytes as returned, unmodified:

| file | request |
|---|---|
| `fuelhh_stream_publish_2026-01-15.json` | `/datasets/FUELHH/stream?publishDateTimeFrom=2026-01-15T00:00Z&publishDateTimeTo=2026-01-16T00:00Z` (980 rows) |
| `fuelhh_stream_settlement_2026-01-15.json` | `/datasets/FUELHH/stream?settlementDateFrom=2026-01-15&settlementDateTo=2026-01-15` (960 rows) |
| `windfor_stream_publish_2026-01-15.json` | `/datasets/WINDFOR/stream?publishDateTimeFrom=2026-01-15T00:00Z&publishDateTimeTo=2026-01-16T00:00Z` (584 rows) |

Every fixture row matches the full-window pull exactly. Note that the WINDFOR fixture
holds publishes **from** 2026-01-15, so the decision-time forecast for delivery day
2026-01-15 (published 2026-01-14 07:30) is not in it.

---

## Decisions (2026-10-26)

Taken on the Phase 0 findings. The specs in `specs/` have been revised to match.

**D1. Hourly forecasts vs half-hourly periods (was Q1). Two frames, kept apart.**
- *Canonical metrics are hourly.* The two half-hourly WIND actuals in each hour are
  averaged to an hourly mean MW and compared with the single hourly forecast.
  n = 744 per month (31 x 24). A forecast is never duplicated across two periods to
  report n = 1,488, because that doubles the apparent sample size without adding
  information.
- *The dashboard chart is per settlement period.* Each hourly forecast is
  step-expanded across both half-hours of its hour, with MW held constant. The axis
  or caption reads "forecast is published hourly, held constant across both
  settlement periods". Step-expanded data is never presented as native half-hourly.
- Implemented in `core/alignment.py` as `to_hourly(actuals_df)` and
  `expand_to_periods(hourly_forecast_df)`. Metrics always run on the hourly frame.
  The expansion is presentation only.
- Knock-on spec changes: energy error becomes `sum(e) x 1 h` on the hourly frame;
  persistence is hourly; the "by settlement period" breakdown becomes "by hour of
  day 00-23" (endpoint `/api/metrics/by-hour`); the acceptance item now reads "24
  hourly forecast points per day, step-expanded to 48 periods for display, with the
  expansion labelled in the UI".

**D2. Horizon chart uses all forecast vintages (was Q2).** It pairs every stored row
with `horizon_hours >= 0` against the hourly actual, and is labelled "all forecast
vintages". Every headline metric stays on decision-time selection only. Headline
answers "how good was the forecast we actually had"; the horizon chart answers "how
does this forecast degrade with lead time".

**D3. Past-hour rows are stored (was Q3).** Ingestion mirrors the source. Filtering
happens at query time: `horizon_hours` is a stored column, and every forecast
analytic excludes `horizon_hours < 0` with an explicit `WHERE`. Nothing is deleted at
ingest.

**D4. Fetch window (was Q4).** Through the end of 1 February, with an **exclusive**
upper bound of `2026-02-02T00:00Z`. Elexon's `To` is inclusive (A4), so the client
drops `publishTime >= 2026-02-02T00:00Z`. Effect on counts: A21a.

**D5. Configuration.** The app needs only `DATABASE_URL`, plus non-secret settings.
The Supabase Session pooler URI with `?sslmode=require` is set in `.env` by the
project owner and is never printed. The `sbp_` management token is not stored in
`.env`.

**D6. The cut-off hour is a first-class lever.** At 09:00 the selected publish is
always D-1 07:30, and the 09:30 publish is missed by 30 minutes (A18). Add
`GET /api/metrics/by-cutoff?from=&to=`, returning the full metric set at cut-offs
02:00, 04:00, 07:00, 09:00 and 11:00. Each one makes a different publish the newest
available: D-2 22:30, then D-1 02:30, 04:30, 07:30 and 09:30. Screen 2 gets an MAE and
RMSE vs cut-off chart. The headline it supports: "moving your decision from 09:00 to
11:00 captures a fresher publish and cuts MAE by X MW". Separately, a Phase 3 test
must prove the 15 January late publish (A11, A15) behaves correctly: for delivery day
2026-01-16, a 12:00 cut-off selects 2026-01-15T09:30Z, not the 12:25 publish.

**D7. Negative MW.** Valid for interconnectors and pumped storage. The reject-negative
rule applies to `fuelType = "WIND"` rows only.

**D8. Early cut-off gaps.** Cut-offs from 00:00 to 02:00 leave 22:00 and 23:00 with no
forecast. These render as gaps, never as zero.

**D9. Repo housekeeping.** Specs moved from `spec docs/` to `specs/`, because spaces
break shell and Docker paths.

---

## Open questions (undecided; need an answer before the phase that depends on them)

**Q5. Screen 3 and CSV resolution (blocks Phase 7).** SPEC-1 §5 asks for one row per
settlement period, which means each row carries a step-expanded forecast. Undecided:
keep per-SP rows with the expansion labelled, or switch the table and CSV to hourly
rows?

**Q6. Comparability across cut-offs (blocks Phase 4).** At the 02:00 cut-off, 22:00
and 23:00 have no forecast (A19). That row of `by-cutoff` therefore has n = 682 for
January, against n = 744 for the other four, and it misses the late-evening hours
from the sample entirely. Undecided: report each row on its own n (n is shown either
way), or compare all five on the common 682 hours?

**Q7. FUELHH fuels stored (blocks Phase 2).** The SPEC-2 §3.2 `actuals` table has no
`fuel_type` column, which implies WIND only. D3 says "ingestion mirrors the source",
and D7 scopes a rule by fuel type. Undecided: store WIND only, or all 20 fuel types
with a `fuel_type` column?
