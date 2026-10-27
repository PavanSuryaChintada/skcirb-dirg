import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Period } from "../api/client";
import { clock, int, signedMw, stamp } from "../format";
import { AXIS, AXIS_LABEL, COLORS } from "./chartTheme";

export type DayRow = {
  t: string;
  sp: number;
  forecast: number | null;
  actual: number | null;
  error: number | null;
  band: [number, number] | null;
  publish: string | null;
};

export const toRows = (periods: Period[]): DayRow[] =>
  periods.map((p) => ({
    t: clock(p.start_time),
    sp: p.settlement_period,
    forecast: p.forecast_mw,
    actual: p.actual_mw,
    error: p.error_mw,
    band: p.band_low_mw != null && p.band_high_mw != null ? [p.band_low_mw, p.band_high_mw] : null,
    publish: p.publish_time,
  }));

export const Y_AXIS_WIDTH = 64;
export const CHART_MARGIN = { top: 8, right: 16, bottom: 0, left: 8 };

export function PeriodTooltip({ active, payload }: { active?: boolean; payload?: { payload: DayRow }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-[3px] border border-rule bg-panel px-3 py-2 text-xs shadow-sm">
      <p className="font-medium">
        SP{r.sp}, {r.t}
      </p>
      <dl className="mt-1 grid grid-cols-[auto_auto] gap-x-4 gap-y-0.5">
        <dt className="text-muted">Forecast</dt>
        <dd>{r.forecast == null ? "none before cut-off" : `${int(r.forecast)} MW`}</dd>
        <dt className="text-muted">Actual</dt>
        <dd>{r.actual == null ? "–" : `${int(r.actual)} MW`}</dd>
        <dt className="text-muted">Error</dt>
        <dd>{signedMw(r.error)}</dd>
        <dt className="text-muted">Published</dt>
        <dd>{stamp(r.publish)}</dd>
      </dl>
    </div>
  );
}

export default function ForecastActualChart({ rows }: { rows: DayRow[] }) {
  return (
    <ResponsiveContainer width="100%" height={340}>
      <ComposedChart data={rows} syncId="day" margin={CHART_MARGIN}>
        <CartesianGrid stroke={COLORS.rule} strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="t" {...AXIS} interval={3} />
        <YAxis
          {...AXIS}
          width={Y_AXIS_WIDTH}
          tickFormatter={(v: number) => int(v)}
          label={{ value: "Wind generation (MW)", angle: -90, position: "insideLeft", offset: 0, style: AXIS_LABEL }}
        />
        <Tooltip content={<PeriodTooltip />} />
        <Area
          dataKey="band"
          type="stepAfter"
          stroke="none"
          fill={COLORS.band}
          fillOpacity={0.13}
          isAnimationActive={false}
          name="Where the actual landed on 90% of other days"
        />
        <Line
          dataKey="forecast"
          type="stepAfter"
          stroke={COLORS.forecast}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
          name="Decision-time forecast"
        />
        <Line
          dataKey="actual"
          type="linear"
          stroke={COLORS.ink}
          strokeWidth={1.75}
          dot={false}
          isAnimationActive={false}
          name="Actual"
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
