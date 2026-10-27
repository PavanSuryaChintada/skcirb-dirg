import { useMemo, useState } from "react";
import { api, type Period } from "../api/client";
import { errorColor } from "../components/chartTheme";
import { clock, hourLabel, int, longDate, num1, signedInt, stamp } from "../format";
import { useApi } from "../useApi";

type Key = "settlement_period" | "publish_time" | "horizon_hours" | "forecast_mw" | "actual_mw" | "error_mw" | "abs_error_mw";

const COLUMNS: { key: Key; label: string; render: (p: Period) => string; numeric: boolean }[] = [
  { key: "settlement_period", label: "SP", render: (p) => String(p.settlement_period), numeric: true },
  { key: "settlement_period", label: "Time (UK)", render: (p) => clock(p.start_time), numeric: false },
  { key: "publish_time", label: "Published", render: (p) => (p.publish_time ? stamp(p.publish_time) : ""), numeric: false },
  { key: "horizon_hours", label: "Lead time (h)", render: (p) => (p.horizon_hours == null ? "" : num1(p.horizon_hours)), numeric: true },
  { key: "forecast_mw", label: "Forecast (MW)", render: (p) => (p.forecast_mw == null ? "" : int(p.forecast_mw)), numeric: true },
  { key: "actual_mw", label: "Actual (MW)", render: (p) => (p.actual_mw == null ? "" : int(p.actual_mw)), numeric: true },
  { key: "error_mw", label: "Error (MW)", render: (p) => (p.error_mw == null ? "" : signedInt(p.error_mw)), numeric: true },
  { key: "abs_error_mw", label: "Abs error (MW)", render: (p) => (p.abs_error_mw == null ? "" : int(p.abs_error_mw)), numeric: true },
];

export default function DailyDetail({ date, cutoff }: { date: string; cutoff: number }) {
  const day = useApi(() => api.day(date, cutoff), [date, cutoff]);
  const [sort, setSort] = useState<{ key: Key; desc: boolean }>({ key: "settlement_period", desc: false });
  const [minAbs, setMinAbs] = useState("");
  const [forecastOnly, setForecastOnly] = useState(false);

  const rows = useMemo(() => {
    if (day.status !== "ready") return [];
    const threshold = Number(minAbs) || 0;
    const kept = day.data.periods.filter(
      (p) => (!forecastOnly || p.forecast_available) && (threshold === 0 || (p.abs_error_mw ?? -1) >= threshold),
    );
    const value = (p: Period) => p[sort.key];
    // missing values always sort to the bottom, whatever the direction
    return [...kept].sort((a, b) => {
      const va = value(a);
      const vb = value(b);
      if (va == null) return vb == null ? 0 : 1;
      if (vb == null) return -1;
      const order = va < vb ? -1 : va > vb ? 1 : 0;
      return sort.desc ? -order : order;
    });
  }, [day, sort, minAbs, forecastOnly]);

  if (day.status === "loading") return <p className="text-muted">Loading {longDate(date)}…</p>;
  if (day.status === "failed") return <p className="text-short">Couldn't load {date}: {day.message}</p>;

  const toggle = (key: Key) => setSort((s) => ({ key, desc: s.key === key ? !s.desc : false }));

  return (
    <article>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-cond text-[32px] font-semibold leading-tight">{longDate(date)}, period by period</h1>
          <p className="mt-1 max-w-[72ch] text-sm text-muted">
            Decision-time forecast at the {hourLabel(cutoff)} cut-off. The forecast is published hourly, held constant across
            both settlement periods. A blank forecast means none had been published by the cut-off.
          </p>
        </div>
        <a
          href={api.csvUrl(date, cutoff)}
          download
          className="rounded-[3px] bg-forecast px-4 py-2 text-sm font-medium text-white hover:bg-ink"
        >
          Download CSV
        </a>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-6 text-sm">
        <label className="flex items-center gap-2">
          Show periods with absolute error of at least
          <input
            type="number"
            min={0}
            step={250}
            value={minAbs}
            onChange={(e) => setMinAbs(e.target.value)}
            placeholder="0"
            className="w-24 rounded-[3px] border border-rule bg-panel px-2 py-1 text-right"
          />
          MW
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={forecastOnly} onChange={(e) => setForecastOnly(e.target.checked)} />
          Only periods with a forecast
        </label>
        <span className="text-muted">
          Showing {rows.length} of {day.data.periods.length} periods
        </span>
      </div>

      <div className="mt-4 overflow-x-auto border border-rule bg-panel">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-rule text-muted">
              {COLUMNS.map((c) => (
                <th key={c.label} className={`px-3 py-2 font-medium ${c.numeric ? "text-right" : "text-left"}`}>
                  <button type="button" onClick={() => toggle(c.key)} className="hover:text-ink">
                    {c.label}
                    {sort.key === c.key && c.label !== "Time (UK)" ? (sort.desc ? " ↓" : " ↑") : ""}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.settlement_period} className="border-b border-rule/60 last:border-0 hover:bg-paper">
                {COLUMNS.map((c) => (
                  <td
                    key={c.label}
                    className={`px-3 py-1.5 ${c.numeric ? "text-right" : "text-left"}`}
                    style={c.key === "error_mw" ? { color: errorColor(p.error_mw) } : undefined}
                  >
                    {c.render(p)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}
