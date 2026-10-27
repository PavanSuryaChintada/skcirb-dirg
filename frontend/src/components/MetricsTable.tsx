import type { Metrics } from "../api/client";
import { gwh, num2, plainPct, signedMw, mw, stamp } from "../format";

export default function MetricsTable({ m, cutoffLabel }: { m: Metrics; cutoffLabel: string }) {
  const rows: [string, string, string][] = [
    ["Bias (mean error)", signedMw(m.me_mw), "Systematic lean. Positive means the forecast runs high, so you start short."],
    ["MAE", mw(m.mae_mw), "Size of a typical hourly miss."],
    ["RMSE", mw(m.rmse_mw), "Like MAE, but big misses count more. RMSE well above MAE means occasional large failures."],
    ["nMAE", plainPct(m.nmae_pct), "MAE as a share of average actual wind. The headline percentage."],
    ["P5 of error", signedMw(m.p5_mw), "Only 5% of hours had the forecast lower than this against actual."],
    ["P50 of error", signedMw(m.p50_mw), "The median hour."],
    ["P95 of error", signedMw(m.p95_mw), "95% of hours, the forecast was no more than this too high."],
    ["Largest miss", `${mw(m.max_abs_error_mw)}`, `At ${stamp(m.max_abs_error_at)}.`],
    ["Energy error", gwh(m.energy_error_mwh == null ? null : m.energy_error_mwh / 1000), "Cumulative over- or under-procurement across the window."],
    ["Skill vs persistence", num2(m.skill_score), "1 − RMSE ÷ RMSE of “tomorrow looks like today”. Above 0 beats the naive baseline."],
  ];
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-rule text-left text-muted">
            <th className="py-2 pr-6 font-medium">Metric</th>
            <th className="py-2 pr-6 text-right font-medium">Value</th>
            <th className="py-2 font-medium">How to read it</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([name, value, read]) => (
            <tr key={name} className="border-b border-rule/60 last:border-0">
              <td className="py-2 pr-6 font-medium">{name}</td>
              <td className="py-2 pr-6 text-right font-cond text-base font-semibold whitespace-nowrap">{value}</td>
              <td className="py-2 text-muted">{read}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-xs text-muted">
        Hourly frame, n = {m.n} hours, decision-time forecast at the {cutoffLabel} cut-off. MAPE is left out on purpose: it
        explodes on calm hours when actual wind is near zero.
      </p>
    </div>
  );
}
