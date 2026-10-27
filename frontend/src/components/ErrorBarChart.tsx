import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { int } from "../format";
import { AXIS, AXIS_LABEL, COLORS, errorColor } from "./chartTheme";
import { CHART_MARGIN, PeriodTooltip, Y_AXIS_WIDTH, type DayRow } from "./ForecastActualChart";

// Same x axis, margins and y-axis width as the chart above, so the periods line up.
export default function ErrorBarChart({ rows }: { rows: DayRow[] }) {
  return (
    <ResponsiveContainer width="100%" height={190}>
      <BarChart data={rows} syncId="day" margin={{ ...CHART_MARGIN, bottom: 20 }}>
        <CartesianGrid stroke={COLORS.rule} strokeDasharray="2 4" vertical={false} />
        <XAxis
          dataKey="t"
          {...AXIS}
          interval={3}
          label={{ value: "Settlement period start, UK time (GMT)", position: "insideBottom", offset: -14, style: AXIS_LABEL }}
        />
        <YAxis
          {...AXIS}
          width={Y_AXIS_WIDTH}
          tickFormatter={(v: number) => int(v)}
          label={{ value: "Error (MW)", angle: -90, position: "insideLeft", offset: 0, style: AXIS_LABEL }}
        />
        <Tooltip content={<PeriodTooltip />} cursor={{ fill: COLORS.rule, fillOpacity: 0.4 }} />
        <ReferenceLine y={0} stroke={COLORS.ink} strokeWidth={1} />
        <Bar dataKey="error" isAnimationActive={false} name="Forecast minus actual">
          {rows.map((r) => (
            <Cell key={r.sp} fill={errorColor(r.error)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
