# SPEC 1 — Product & Analytics Specification
## Wind Forecast Accuracy Portal for Day-Ahead Power Procurement

**Read this document first. It defines WHAT to build and WHY.**
SPEC-2-ENGINEERING.md defines HOW. Do not start coding from this file alone.

> **Revised 2026-10-26 after Phase 0 recon.** Changes: WINDFOR is hourly, so canonical
> metrics are hourly and the 48-period view is a labelled step-expansion (§3.5); the
> horizon chart uses all forecast vintages (§3.4); the cut-off hour is a first-class
> lever (§3.6). Evidence and decisions: `docs/ASSUMPTIONS.md`.

---

## 1. The user and the decision

**User:** a day-ahead trader at a UK energy supplier.

**Their daily job:** before the GB day-ahead auction closes on day D-1, decide how much
thermal (gas) power to buy for every half hour of delivery day D.

```
Thermal power to buy  =  Consumer demand  −  Expected wind generation
```

Demand is out of scope for this challenge. Only wind matters here.

**Why forecast error is money:**

- Forecast too HIGH → they under-buy → must cover the shortfall at spot/imbalance prices (expensive)
- Forecast too LOW  → they over-buy → must dump surplus at a loss

So the product has exactly two jobs:

1. Show the **decision-time forecast** — the latest forecast that genuinely existed
   before the auction gate closed. Not a later revision.
2. **Quantify how wrong that forecast tends to be**, so the trader can add a risk
   buffer to their purchase instead of guessing.

Job 2 is where the value is. Weight the UI and the analysis accordingly.

---

## 2. Scope boundary (do not exceed)

IN scope:

- National-level GB wind only
- Elexon FUELHH (actuals) and WINDFOR (forecasts) only
- Delivery days in **January 2026** (2026-01-01 through 2026-01-31 inclusive)

OUT of scope — do not build, do not mention as "coming soon" in the UI:

- Demand forecasting, prices, solar, interconnectors, other fuel types
- User accounts, login, roles, multi-tenancy
- Live/real-time streaming or scheduled refresh
- ML models that produce a better forecast (we EVALUATE a forecast, we do not make one)

---

## 3. Domain rules — get these right, they are the substance

### 3.1 Settlement periods

- A GB day is split into **48 settlement periods** of 30 minutes. SP1 = 00:00–00:30 UK local.
- All Elexon timestamps are **UTC** (`...Z`). January has no BST, so UTC == UK local
  for the whole study window. State this assumption in the README — it is why
  January conveniently avoids the 46-period and 50-period clock-change days.
- Power is in **MW**. Energy for one settlement period = `MW × 0.5` **MWh**; for one
  hour of the hourly metric frame (§3.5) = `mean MW × 1` **MWh**. The two agree: the
  hourly mean of two half-hours × 1 h equals the sum of each × 0.5 h.

### 3.2 The decision cut-off — the single most important rule

For each delivery day D, define a cut-off timestamp on D-1. Only forecasts with
`publishTime <= cutoff` may be used to evaluate that day. Everything published after
is hindsight and must be excluded.

```
DECISION_CUTOFF_HOUR_UTC = 9   # configurable via environment variable
cutoff(D) = (D - 1 day) at 09:00 UTC
```

**Assumption to state openly in the README and in the video:** GB day-ahead auctions
close mid-morning on D-1 (EPEX SPOT and N2EX run separate auctions at slightly
different times). 09:00 UTC is a deliberately conservative default. The exact gate
closure should be confirmed with the client. Make the hour an env var so it can be
changed without a code change, and expose it as a selector in the UI — being able
to say *"here is what your accuracy looks like if you decide an hour earlier"* is a
strong demo moment.

### 3.3 Selecting the decision-time forecast

WINDFOR is published at **hourly** resolution (every `startTime` is on the hour —
verified in Phase 0). Selection therefore runs per hour.

For each `(delivery_day D, hour H)`, H = 00:00 … 23:00 UTC:

1. Take all WINDFOR rows whose `startTime` equals hour H of day D
2. Discard any row with `publishTime > cutoff(D)`, and any row with `horizon_hours < 0`
   (explicit filter — past-hour rows are stored, never used; see §3.4)
3. Of what remains, keep the row with the **latest** `publishTime`
4. That single row is the **decision-time forecast** for that hour

If no forecast survives step 2, mark the hour `forecast_available = false`.
Do not interpolate, do not fall back to a later publish. Show the gap honestly —
a missing forecast is itself a finding worth reporting to the client.

Selection uses `publishTime`, so a publish that arrives late (e.g. the 11:30 WINDFOR
publish on 2026-01-15 that appeared at 12:25) is correctly excluded from any cut-off
earlier than its actual `publishTime`.

Known real gap: cut-offs from 00:00 to 02:00 UTC leave hours 22:00 and 23:00 of D
(SP45–SP48) with no qualifying forecast, because the newest publish is then from D-2
and only reaches D 21:00. These must render as gaps, never as zero.

### 3.4 Forecast horizon

```
horizon_hours = (startTime − publishTime) / 3600
```

Error grows with horizon. A chart of error vs horizon is one of the most
commercially interesting outputs in the whole app. Include it.

**The horizon chart uses ALL forecast vintages, not just decision-time selections.**
At a 09:00 cut-off every decision-time horizon falls between 16.5 h and 39.5 h, which
cannot show degradation with lead time. So the horizon analysis pairs every stored
WINDFOR row with `horizon_hours >= 0` against the hourly actual, and is labelled
**"all forecast vintages"** wherever it appears.

These are two different questions and the UI must not blur them:

- **Headline metrics** (everything except the horizon chart) = decision-time selection
  only. *"How good was the forecast we actually had?"*
- **Horizon chart** = all vintages. *"How does this forecast degrade with lead time?"*

Every WINDFOR publish also contains hours already in the past (`startTime <
publishTime`, negative horizon). These rows are stored as the source published them
and excluded from all forecast analytics by an explicit `horizon_hours >= 0` filter.

### 3.5 Resolution: hourly forecasts, half-hourly actuals

WINDFOR is hourly; FUELHH actuals are half-hourly. Two frames, clearly separated:

- **Canonical metrics are hourly.** The two half-hourly WIND actuals in each hour are
  averaged to an hourly mean MW and compared with the single hourly forecast.
  n = 744 per month (31 × 24). Never duplicate a forecast across two periods and report
  n = 1488 — that doubles the apparent sample size without adding information.
- **The dashboard chart is per settlement period.** Each hourly forecast is
  step-expanded across both half-hours of its hour (MW held constant), so the 48-period
  view has no artificial gaps. The chart axis or caption must say:
  **"forecast is published hourly, held constant across both settlement periods"**.
  Never present step-expanded data as if it were native half-hourly resolution.

Metrics ALWAYS run on the hourly frame. The expansion is presentation only.

### 3.6 The cut-off hour is a lever

Recon showed that at a 09:00 cut-off the decision-time forecast is always the D-1
07:30 publish; the 09:30 publish is missed by 30 minutes. The client's gate-closure
time therefore decides which publish they trade on. Treat this as a first-class
finding: compute the full metric set at each candidate cut-off hour

| cut-off (D-1, UTC) | newest qualifying publish |
|---|---|
| 02:00 | D-2 22:30 |
| 04:00 | D-1 02:30 |
| 07:00 | D-1 04:30 |
| 09:00 | D-1 07:30 |
| 11:00 | D-1 09:30 |

so each row corresponds to a different publish being the newest available. The
headline it supports: *"moving your decision from 09:00 to 11:00 captures a fresher
publish and cuts MAE by X MW."* This is a recommendation the client can act on
without buying anything.

---

## 4. Metric definitions — implement exactly as written

All metrics run on the **hourly frame** (§3.5): one observation per hour, `f` = the
hourly forecast, `a` = the hourly mean of the two half-hourly actuals. A full month is
N = 744. For a set of N paired observations where `f` = forecast MW and `a` = actual MW:

| Metric | Formula | Unit | How to read it |
|---|---|---|---|
| Error | `e = f − a` | MW | Positive = forecast over-predicted wind |
| **ME (Bias)** | `mean(e)` | MW | Systematic lean. Non-zero bias is correctable — flag it loudly |
| **MAE** | `mean(abs(e))` | MW | Typical miss size |
| **RMSE** | `sqrt(mean(e²))` | MW | Like MAE but punishes large misses. RMSE >> MAE means occasional big failures |
| **nMAE** | `MAE / mean(a)` | % | MAE as a share of average actual wind |
| **P5 / P50 / P95 of e** | quantiles | MW | The risk band. "95% of the time we are no more than X MW short" |
| **Max absolute error** | `max(abs(e))` | MW | Worst case, with its timestamp |
| **Energy error** | `sum(e) × 1 h` (hourly frame) | MWh | Cumulative over/under procurement across the month |

### 4.1 Do NOT use raw MAPE as a headline

`MAPE = mean(abs(e)/a)` explodes when actual wind is near zero (calm nights), which
happens in January. If you show MAPE at all, show it only for periods where
`a >= 500 MW` and label that filter on the chart. Use **nMAE** as the headline
percentage instead. If the tech lead asks why, this is the answer — know it.

### 4.2 Baseline comparison — include this, it is a differentiator

Compare the Elexon forecast against a naive **persistence baseline**:

```
persistence_forecast(D, H) = hourly_mean_actual(D − 1 day, H)
```

Then report **Forecast Skill Score**:

```
skill = 1 − (RMSE_elexon / RMSE_persistence)
```

A positive skill score means the forecast beats "assume tomorrow looks like today".
This proves the forecast has real value and shows the client you understand
forecast evaluation, not just arithmetic. It costs about 20 lines of code.

### 4.3 Required breakdowns

Compute the metric set over each of these groupings:

- Whole month (headline numbers)
- By hour of day 00–23 (reveals time-of-day patterns; hour H = SP 2H+1 and 2H+2).
  This replaces "by settlement period 1–48", because metrics run on the hourly frame
- By delivery day (reveals which days blew up)
- By forecast horizon bucket (0–6h, 6–12h, 12–18h, 18–24h, 24h+), over **all
  forecast vintages** (§3.4), labelled as such
- By actual wind level tercile (low / medium / high wind conditions)
- By cut-off hour (02:00, 04:00, 07:00, 09:00, 11:00), decision-time selection at
  each (§3.6)

---

## 5. Screens

Three screens. No more. Build them in this order.

### Screen 1 — Procurement Dashboard (the landing page)

This is what the trader opens every morning. Date picker defaults to a day with
interesting error, not 1 January.

- **Date selector** for the delivery day, plus a cut-off hour selector
- **Headline strip** — four large stat cards:
  - Decision-time forecast total for the day (GWh)
  - Actual total (GWh)
  - Error (GWh and %)
  - 90% confidence band on the error, from historical P5/P95
- **Main chart** — forecast vs actual across all 48 settlement periods
  - Two lines, clearly labelled, X axis showing clock time not period index
  - The forecast line is the hourly forecast step-expanded across both half-hours
    (§3.5). Axis or caption reads: *"forecast is published hourly, held constant
    across both settlement periods"*. Draw it as a step line, not a smooth line
  - Hours with no decision-time forecast are gaps in the line, never zero
  - A shaded band around the forecast line = the historical P5–P95 error band.
    **This band is the product.** It converts a point forecast into a risk range.
  - Hovering a point shows: SP number, clock time, forecast, actual, error, publishTime
- **Error bar chart** below, sharing the X axis, bars coloured by sign
- **Data provenance line**, small text: *"Forecast published YYYY-MM-DD HH:MM UTC,
  the latest available before the 09:00 cut-off on D-1."* Traders trust tools that
  show their sources.

### Screen 2 — Accuracy Analysis

The quantified-error screen. This is where job 2 lives.

- Metric table for the full month: ME, MAE, RMSE, nMAE, P5/P50/P95, max error, skill score
- **Error by hour of day** — line or bar chart, 00 to 23 (hourly frame, §3.5). Call out
  the worst hours.
- **Error by forecast horizon** — shows degradation with lead time. Titled or captioned
  **"all forecast vintages"** (§3.4) so it is never read as a headline metric
- **MAE and RMSE vs cut-off hour** — small chart, one point per candidate cut-off
  (02, 04, 07, 09, 11). Supports the gate-closure recommendation in §3.6
- **Error distribution histogram** with the P5/P50/P95 lines drawn on it
- **Scatter: forecast vs actual** with a 45° reference line. Points below the line
  = over-forecast. Instantly readable.
- Every chart must have axis labels with units, a title, and a legend. Unlabelled
  axes are the fastest way to lose a technical reviewer.

### Screen 3 — Daily Detail Table

- Sortable, filterable table, one row per settlement period for the selected day
- Columns: SP, clock time, publishTime, horizon_h, forecast MW, actual MW, error MW, abs error MW
- Per-SP rows carry the step-expanded hourly forecast, labelled on screen and in a
  `forecast_step_expanded` CSV column. Missing forecasts are blank, never 0
  (ASSUMPTIONS D14).
- CSV export button. Energy traders live in Excel. This takes ten minutes to build
  and always lands well in a demo.

---

## 6. Backend API contract

All responses JSON. All timestamps ISO-8601 UTC with `Z`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | `{"status":"ok","db":"connected","rows":{...}}` |
| GET | `/api/meta` | Available date range, cut-off config, last ingest timestamp, row counts |
| GET | `/api/day/{date}?cutoff_hour=9` | 48 periods for one delivery day: forecast (step-expanded from hourly, flagged as such), actual, error, publishTime, horizon |
| GET | `/api/metrics?from=&to=&cutoff_hour=9` | Full metric set for the whole window (hourly frame, decision-time) |
| GET | `/api/metrics/by-hour?...` | Metrics grouped by hour of day 00–23 (replaces `by-period`, §4.3) |
| GET | `/api/metrics/by-day?...` | Metrics grouped by delivery day |
| GET | `/api/metrics/by-horizon?...` | Metrics grouped by horizon bucket, **all forecast vintages** (§3.4) |
| GET | `/api/metrics/by-cutoff?from=&to=` | Full metric set at each candidate cut-off hour 02, 04, 07, 09, 11 (§3.6) |
| GET | `/api/distribution?...` | Histogram bins plus P5/P50/P95 |
| GET | `/api/export/day/{date}.csv` | CSV for Screen 3 |

Rules:

- The API does the maths. React renders what it is given. **No metric computation in
  JavaScript** — the tech lead will ask where the logic lives and there must be
  exactly one answer.
- Every metrics response includes the `cutoff_hour` and `n_observations` it used.
  Numbers without their sample size are not credible.
- Return a clear 4xx with a useful message for a date outside the loaded range.

---

## 7. What "impressing the client" means in Part 1 of the video

Do not demo features. Demo the decision.

Suggested 5-minute arc:

1. **30s — the problem in money terms.** "On 12 January the forecast was 1.8 GW high.
   At day-ahead prices that is roughly £X of power you had to buy at short notice."
   (Say *roughly*, and say you have not been given price data — do not invent a price.)
2. **90s — the dashboard.** Pick a real day with a big miss. Walk the forecast line,
   the actual line, the error band. Point at the provenance line showing you used
   only what they actually had before gate closure.
3. **120s — the accuracy screen.** Lead with bias: "the forecast leans high by X MW
   on average, which means your default position is systematically short." Then the
   time-of-day pattern, then the horizon decay.
4. **60s — the so-what.** "Apply the P95 band as a procurement buffer in these specific
   settlement periods." Then the gate-closure lever (§3.6): "moving your decision from
   09:00 to 11:00 captures a fresher publish and cuts MAE by X MW." A recommendation,
   not a feature list.
5. **Limitations, briefly and confidently.** One month of data, national level only,
   cut-off assumed at 09:00. Stating limits builds trust; hiding them loses it when
   they find out.

---

## 8. Acceptance checklist

Feature complete when all of these are true:

- [ ] All 31 January delivery days load: 24 hourly forecast points per day,
      step-expanded to 48 periods for display, with the expansion labelled in the UI
- [ ] Headline metrics run on the hourly frame and report n = 744 for the full month
- [ ] Forecast selection provably excludes any `publishTime` after the cut-off
- [ ] The 2026-01-15 late publish (11:30 slot, published 12:25) is excluded from a
      12:00 cut-off for delivery day 2026-01-16, proven by a test
- [ ] Changing the cut-off hour visibly changes the numbers
- [ ] `/api/metrics/by-cutoff` and the MAE/RMSE vs cut-off chart are live
- [ ] The horizon chart is labelled "all forecast vintages"; headline metrics are
      decision-time only
- [ ] Cut-offs 00:00–02:00 show 22:00 and 23:00 as gaps, never zero
- [ ] Every metric in section 4 appears somewhere in the UI
- [ ] Persistence baseline and skill score are computed and displayed
- [ ] Every chart has labelled axes with units
- [ ] CSV export opens cleanly in Excel
- [ ] Missing-forecast periods are shown as gaps, never as zero
- [ ] A metric computed by hand in a notebook matches the API to 2 decimal places
