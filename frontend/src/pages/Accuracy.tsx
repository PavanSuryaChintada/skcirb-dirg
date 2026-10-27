import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type ByCutoffResponse, type GroupedResponse, type Metrics, type ScatterResponse } from "../api/client";
import { AXIS, AXIS_LABEL, COLORS, errorColor } from "../components/chartTheme";
import ErrorDistribution, { histogramCaption } from "../components/ErrorDistribution";
import MetricsTable from "../components/MetricsTable";
import { Legend, LegendItem, Loaded, Panel } from "../components/Panel";
import { hourLabel, int, mw, num2, plainPct, signedInt, signedMw } from "../format";
import { useApi } from "../useApi";

export default function Accuracy({ cutoff }: { cutoff: number }) {
  const metrics = useApi(() => api.metrics(cutoff), [cutoff]);
  const byHour = useApi(() => api.byHour(cutoff), [cutoff]);
  const terciles = useApi(() => api.byTercile(cutoff), [cutoff]);
  const distribution = useApi(() => api.distribution(cutoff), [cutoff]);
  const scatter = useApi(() => api.scatter(cutoff), [cutoff]);
  const byHorizon = useApi(api.byHorizon, []);
  const byCutoff = useApi(api.byCutoff, []);
  const cutoffLabel = hourLabel(cutoff);

  return (
    <article>
      <Loaded load={metrics}>{(r) => <Headline m={r.metrics} cutoffLabel={cutoffLabel} />}</Loaded>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.15fr_1fr]">
        <Panel title="January in numbers" caption="Decision-time forecast against hourly actual, whole month.">
          <Loaded load={metrics}>{(r) => <MetricsTable m={r.metrics} cutoffLabel={cutoffLabel} />}</Loaded>
        </Panel>
        <Panel
          title="What a later decision buys you"
          caption="Each cut-off makes a different publish the newest you could use. Compared on the hours every cut-off covers."
          legend={
            <Legend>
              <LegendItem color={COLORS.forecast} label="MAE" />
              <LegendItem color={COLORS.ink} label="RMSE" />
            </Legend>
          }
        >
          <Loaded load={byCutoff}>{(r) => <CutoffChart r={r} />}</Loaded>
        </Panel>
      </div>

      <Panel
        className="mt-6"
        title="Error by hour of day"
        caption="Bars show the average lean in each hour; the line shows the typical miss size."
        legend={
          <Legend>
            <LegendItem color={COLORS.short} label="Bias, too high" kind="block" />
            <LegendItem color={COLORS.long} label="Bias, too low" kind="block" />
            <LegendItem color={COLORS.ink} label="MAE" />
          </Legend>
        }
      >
        <Loaded load={byHour}>{(r) => <HourChart r={r} />}</Loaded>
      </Panel>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel
          title="Error by forecast lead time, all forecast vintages"
          caption="Every stored publish with a lead time of zero or more, not only the one you could trade on. This shows how the forecast decays with lead time; it is not a headline figure."
          legend={
            <Legend>
              <LegendItem color={COLORS.forecast} label="MAE" kind="block" />
              <LegendItem color={COLORS.muted} label="RMSE" kind="block" />
            </Legend>
          }
        >
          <Loaded load={byHorizon}>{(r) => <HorizonChart r={r} />}</Loaded>
        </Panel>
        <Panel
          title="How the hourly errors are spread"
          caption={distribution.status === "ready" ? histogramCaption(distribution.data) : undefined}
          legend={
            <Legend>
              <LegendItem color={COLORS.forecast} label="Hours per bin" kind="block" />
            </Legend>
          }
        >
          <Loaded load={distribution}>{(d) => <ErrorDistribution d={d} />}</Loaded>
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1fr]">
        <Panel
          title="Forecast against actual, every hour"
          caption="Points below the diagonal are hours where the forecast was too high."
          legend={
            <Legend>
              <LegendItem color={COLORS.forecast} label="One hour" kind="block" />
              <LegendItem color={COLORS.ink} label="Perfect forecast" />
            </Legend>
          }
        >
          <Loaded load={scatter}>{(r) => <ForecastScatter r={r} />}</Loaded>
        </Panel>
        <Panel title="Accuracy by wind level" caption="Hours split into thirds by how much wind actually blew.">
          <Loaded load={terciles}>{(r) => <TercileTable r={r} />}</Loaded>
        </Panel>
      </div>
    </article>
  );
}

function Headline({ m, cutoffLabel }: { m: Metrics; cutoffLabel: string }) {
  const high = (m.me_mw ?? 0) > 0;
  return (
    <>
      <h1 className="max-w-[26ch] font-cond text-[40px] font-semibold leading-[1.1] tracking-tight">
        Across January the {cutoffLabel} forecast ran {mw(Math.abs(m.me_mw ?? 0))} {high ? "high" : "low"} on average.
      </h1>
      <p className="mt-3 max-w-[70ch] text-muted">
        A lean that steady is correctable: anyone taking the forecast at face value starts most days{" "}
        {high ? "short" : "long"}. The typical hourly miss is {mw(m.mae_mw)} ({plainPct(m.nmae_pct)} of average wind), and
        the forecast still beats a “tomorrow looks like today” baseline with a skill score of {num2(m.skill_score)}.
      </p>
    </>
  );
}

function CutoffChart({ r }: { r: ByCutoffResponse }) {
  const data = r.rows.map((row) => ({
    label: hourLabel(row.cutoff_hour),
    publish: row.newest_publish ?? "",
    mae: row.metrics_common_hours.mae_mw,
    rmse: row.metrics_common_hours.rmse_mw,
  }));
  const { mae_change_mw: dMae, rmse_change_mw: dRmse, from_cutoff_hour, to_cutoff_hour } = r.comparison;
  const verb = (v: number | null) => (v == null ? "changes" : v < 0 ? "cuts" : "raises");
  return (
    <>
      <p className="mb-2 text-sm">
        Deciding at {hourLabel(to_cutoff_hour)} instead of {hourLabel(from_cutoff_hour)} {verb(dMae)} MAE by{" "}
        {mw(dMae == null ? null : Math.abs(dMae))} and {verb(dRmse)} RMSE by {mw(dRmse == null ? null : Math.abs(dRmse))}, on
        the same {int(r.n_observations)} hours. The fresher publish helps only a little; the bias above is the bigger lever.
      </p>
      <ResponsiveContainer width="100%" height={250}>
        <ComposedChart data={data} margin={{ top: 8, right: 36, bottom: 34, left: 8 }}>
          <CartesianGrid stroke={COLORS.rule} strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="label"
            {...AXIS}
            tick={({ x, y, payload, index }) => (
              <g transform={`translate(${x},${y})`}>
                <text dy={12} textAnchor="middle" fill={COLORS.ink} fontSize={12}>
                  {payload.value}
                </text>
                <text dy={26} textAnchor="middle" fill={COLORS.muted} fontSize={11}>
                  {data[index]?.publish}
                </text>
              </g>
            )}
            label={{ value: "Cut-off on D-1 (UTC), with the newest publish it allows", position: "insideBottom", offset: -30, style: AXIS_LABEL }}
          />
          <YAxis
            {...AXIS}
            width={64}
            domain={["auto", "auto"]}
            tickFormatter={(v: number) => int(v)}
            label={{ value: "Error (MW)", angle: -90, position: "insideLeft", offset: 0, style: AXIS_LABEL }}
          />
          <Tooltip formatter={(v, name) => [mw(Number(v)), String(name)]} />
          <Line dataKey="mae" name="MAE" stroke={COLORS.forecast} strokeWidth={2} isAnimationActive={false} />
          <Line dataKey="rmse" name="RMSE" stroke={COLORS.ink} strokeWidth={2} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </>
  );
}

function HourChart({ r }: { r: GroupedResponse }) {
  const data = r.groups.map((g) => ({ hour: hourLabel(Number(g.group)), bias: g.me_mw, mae: g.mae_mw }));
  const worst = [...r.groups].sort((a, b) => (b.mae_mw ?? 0) - (a.mae_mw ?? 0)).slice(0, 3);
  return (
    <>
      <p className="mb-2 text-sm">
        Worst hours: {worst.map((g) => `${hourLabel(Number(g.group))} (MAE ${mw(g.mae_mw)})`).join(", ")}.
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 20, left: 8 }}>
          <CartesianGrid stroke={COLORS.rule} strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="hour"
            {...AXIS}
            interval={1}
            label={{ value: "Hour of day, UK time (GMT)", position: "insideBottom", offset: -14, style: AXIS_LABEL }}
          />
          <YAxis
            {...AXIS}
            width={64}
            tickFormatter={(v: number) => int(v)}
            label={{ value: "Error (MW)", angle: -90, position: "insideLeft", offset: 0, style: AXIS_LABEL }}
          />
          <Tooltip formatter={(v, name) => [signedMw(Number(v)), String(name)]} />
          <ReferenceLine y={0} stroke={COLORS.ink} />
          <Bar dataKey="bias" name="Bias" isAnimationActive={false}>
            {data.map((d) => (
              <Cell key={d.hour} fill={errorColor(d.bias)} />
            ))}
          </Bar>
          <Line dataKey="mae" name="MAE" stroke={COLORS.ink} strokeWidth={2} dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </>
  );
}

function HorizonChart({ r }: { r: GroupedResponse }) {
  const data = r.groups.map((g) => ({ bucket: String(g.group), mae: g.mae_mw, rmse: g.rmse_mw, n: g.n }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 20, left: 8 }}>
        <CartesianGrid stroke={COLORS.rule} strokeDasharray="2 4" vertical={false} />
        <XAxis
          dataKey="bucket"
          {...AXIS}
          label={{ value: "Lead time: forecast hour minus publish time", position: "insideBottom", offset: -14, style: AXIS_LABEL }}
        />
        <YAxis
          {...AXIS}
          width={64}
          tickFormatter={(v: number) => int(v)}
          label={{ value: "Error (MW)", angle: -90, position: "insideLeft", offset: 0, style: AXIS_LABEL }}
        />
        <Tooltip
          formatter={(v, name) => [mw(Number(v)), String(name)]}
          labelFormatter={(label) => {
            const row = data.find((d) => d.bucket === label);
            return `${label} lead time, ${int(row?.n)} forecast-hours`;
          }}
        />
        <Bar dataKey="mae" name="MAE" fill={COLORS.forecast} isAnimationActive={false} />
        <Bar dataKey="rmse" name="RMSE" fill={COLORS.muted} isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function ForecastScatter({ r }: { r: ScatterResponse }) {
  // round the axis up to a tidy 2 GW step so the diagonal spans the plot
  const top = Math.ceil(Math.max(...r.points.flatMap((p) => [p.forecast_mw, p.actual_mw])) / 2000) * 2000;
  return (
    <ResponsiveContainer width="100%" height={320}>
      <ScatterChart margin={{ top: 8, right: 16, bottom: 20, left: 8 }}>
        <CartesianGrid stroke={COLORS.rule} strokeDasharray="2 4" />
        <XAxis
          type="number"
          dataKey="forecast_mw"
          domain={[0, top]}
          {...AXIS}
          tickFormatter={(v: number) => int(v)}
          label={{ value: "Decision-time forecast (MW)", position: "insideBottom", offset: -14, style: AXIS_LABEL }}
        />
        <YAxis
          type="number"
          dataKey="actual_mw"
          domain={[0, top]}
          {...AXIS}
          width={64}
          tickFormatter={(v: number) => int(v)}
          label={{ value: "Actual (MW)", angle: -90, position: "insideLeft", offset: 0, style: AXIS_LABEL }}
        />
        <Tooltip formatter={(v, name) => [mw(Number(v)), name === "forecast_mw" ? "Forecast" : "Actual"]} />
        <ReferenceLine segment={[{ x: 0, y: 0 }, { x: top, y: top }]} stroke={COLORS.ink} strokeWidth={1.5} />
        <Scatter data={r.points} fill={COLORS.forecast} fillOpacity={0.45} isAnimationActive={false} shape="circle" />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

function TercileTable({ r }: { r: GroupedResponse }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-rule text-left text-muted">
          <th className="py-2 pr-4 font-medium">Wind level</th>
          <th className="py-2 pr-4 text-right font-medium">Hours</th>
          <th className="py-2 pr-4 text-right font-medium">Average actual</th>
          <th className="py-2 pr-4 text-right font-medium">Bias</th>
          <th className="py-2 pr-4 text-right font-medium">MAE</th>
          <th className="py-2 text-right font-medium">nMAE</th>
        </tr>
      </thead>
      <tbody>
        {r.groups.map((g) => (
          <tr key={String(g.group)} className="border-b border-rule/60 last:border-0">
            <td className="py-2 pr-4 font-medium capitalize">{String(g.group)}</td>
            <td className="py-2 pr-4 text-right">{int(g.n)}</td>
            <td className="py-2 pr-4 text-right">{mw(g.mean_actual_mw)}</td>
            <td className="py-2 pr-4 text-right" style={{ color: errorColor(g.me_mw) }}>
              {signedInt(g.me_mw)} MW
            </td>
            <td className="py-2 pr-4 text-right">{mw(g.mae_mw)}</td>
            <td className="py-2 text-right">{plainPct(g.nmae_pct)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
