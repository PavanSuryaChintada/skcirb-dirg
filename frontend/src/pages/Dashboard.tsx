import { api, type DayResponse } from "../api/client";
import ErrorBarChart from "../components/ErrorBarChart";
import ForecastActualChart, { toRows } from "../components/ForecastActualChart";
import StatCard from "../components/StatCard";
import { COLORS } from "../components/chartTheme";
import { gwh, hourLabel, longDate, pct, shortDate, signedGwh, signedInt, stamp } from "../format";
import { useApi } from "../useApi";

export default function Dashboard({ date, cutoff }: { date: string; cutoff: number }) {
  const day = useApi(() => api.day(date, cutoff), [date, cutoff]);

  if (day.status === "loading") return <p className="text-muted">Loading {longDate(date)}…</p>;
  if (day.status === "failed") return <p className="text-short">Couldn't load {date}: {day.message}</p>;
  return <DayView d={day.data} />;
}

function DayView({ d }: { d: DayResponse }) {
  const { totals, band } = d;
  const high = totals.error_gwh > 0;
  const rows = toRows(d.periods);
  const missingHours = 24 - totals.n_hours;
  const cutoffLabel = hourLabel(d.cutoff_hour);
  const prevDay = shortDate(d.cutoff_time.slice(0, 10));

  return (
    <article>
      <h1 className="max-w-[24ch] font-cond text-[40px] font-semibold leading-[1.1] tracking-tight">
        {longDate(d.date)}: the forecast you could have traded on ran {gwh(Math.abs(totals.error_gwh))}{" "}
        {high ? "high" : "low"}.
      </h1>
      <p className="mt-3 max-w-[68ch] text-muted">
        That is {pct(totals.error_pct)} against the wind that actually turned up, so a buyer relying on it would have
        been {high ? "short and buying the gap at short notice" : "long and selling surplus at a loss"}.
      </p>

      <section className="mt-8 grid grid-cols-1 border border-rule sm:grid-cols-2 lg:grid-cols-4" aria-label="Day totals">
        <StatCard label="Decision-time forecast" value={gwh(totals.forecast_gwh)} detail={`${totals.n_hours} hours with a forecast`} />
        <StatCard label="Actual wind" value={gwh(totals.actual_gwh)} detail="FUELHH outturn, same hours" />
        <StatCard
          label={high ? "Error: forecast too high" : "Error: forecast too low"}
          value={signedGwh(totals.error_gwh)}
          detail={`${pct(totals.error_pct)} of actual`}
          tone={high ? "short" : "long"}
        />
        <StatCard
          label="90% band on hourly error"
          value={`${signedInt(band.p5_mw)} to ${signedInt(band.p95_mw)} MW`}
          detail={`P5 to P95 over ${band.n_observations} hours on other January days`}
        />
      </section>

      <section className="mt-8 border border-rule bg-panel px-4 pb-4 pt-5" aria-label="Forecast against actual">
        <div className="flex flex-wrap items-baseline justify-between gap-3 px-2">
          <h2 className="font-cond text-lg font-semibold">Forecast against actual, by settlement period</h2>
          <Legend />
        </div>
        <p className="mt-1 px-2 text-sm text-muted">
          The forecast is published hourly, held constant across both settlement periods. The shaded range is where the
          actual landed on 90% of hours on other January days at this cut-off.
        </p>
        <div className="mt-3">
          <ForecastActualChart rows={rows} />
        </div>
        <h3 className="mt-4 px-2 text-sm font-medium">Forecast minus actual</h3>
        <ErrorBarChart rows={rows} />
      </section>

      <p className="mt-4 text-sm text-muted">
        {d.publish_times.length === 1
          ? `Forecast published ${stamp(d.publish_times[0])}, the latest available before the ${cutoffLabel} cut-off on ${prevDay}.`
          : `Forecasts published ${d.publish_times.map(stamp).join(" and ")}, the latest available for each hour before the ${cutoffLabel} cut-off on ${prevDay}.`}
        {missingHours > 0 &&
          ` No forecast existed for ${missingHours} hour${missingHours > 1 ? "s" : ""} by then; those periods are left blank and excluded from the totals.`}
      </p>
    </article>
  );
}

function Legend() {
  const item = "flex items-center gap-2";
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
      <li className={item}>
        <span className="inline-block h-0.5 w-5" style={{ background: COLORS.forecast }} /> Decision-time forecast
      </li>
      <li className={item}>
        <span className="inline-block h-0.5 w-5" style={{ background: COLORS.ink }} /> Actual
      </li>
      <li className={item}>
        <span className="inline-block h-3 w-5" style={{ background: COLORS.band, opacity: 0.18 }} /> 90% range
      </li>
      <li className={item}>
        <span className="inline-block h-3 w-3" style={{ background: COLORS.short }} /> Too high (short)
      </li>
      <li className={item}>
        <span className="inline-block h-3 w-3" style={{ background: COLORS.long }} /> Too low (long)
      </li>
    </ul>
  );
}
