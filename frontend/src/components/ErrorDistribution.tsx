import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DistributionResponse } from "../api/client";
import { int, signedInt } from "../format";
import { AXIS, AXIS_LABEL, COLORS } from "./chartTheme";

// A step outline over the bin edges, so the P5/P50/P95 lines sit at their exact values.
export default function ErrorDistribution({ d }: { d: DistributionResponse }) {
  const points = d.bins.map((b) => ({ x: b.lo_mw, count: b.count, hi: b.hi_mw }));
  const last = d.bins[d.bins.length - 1];
  if (last) points.push({ x: last.hi_mw, count: last.count, hi: last.hi_mw });

  const marks: [number | null, string][] = [
    [d.p5_mw, "P5"],
    [d.p50_mw, "P50"],
    [d.p95_mw, "P95"],
  ];
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={points} margin={{ top: 22, right: 16, bottom: 20, left: 8 }}>
        <CartesianGrid stroke={COLORS.rule} strokeDasharray="2 4" vertical={false} />
        <XAxis
          dataKey="x"
          type="number"
          domain={["dataMin", "dataMax"]}
          {...AXIS}
          tickFormatter={(v: number) => signedInt(v)}
          label={{ value: "Hourly error, forecast minus actual (MW)", position: "insideBottom", offset: -14, style: AXIS_LABEL }}
        />
        <YAxis
          {...AXIS}
          width={56}
          allowDecimals={false}
          label={{ value: "Hours", angle: -90, position: "insideLeft", offset: 4, style: AXIS_LABEL }}
        />
        <Tooltip
          formatter={(v) => [`${v} hours`, "Count"]}
          labelFormatter={(x) => `${signedInt(Number(x))} to ${signedInt(Number(x) + d.bin_mw)} MW`}
        />
        <Area dataKey="count" type="stepAfter" stroke={COLORS.forecast} fill={COLORS.forecast} fillOpacity={0.18} isAnimationActive={false} />
        {marks.map(([v, label]) =>
          v == null ? null : (
            <ReferenceLine
              key={label}
              x={v}
              stroke={label === "P50" ? COLORS.ink : COLORS.short}
              strokeDasharray={label === "P50" ? undefined : "4 3"}
              label={{ value: `${label} ${signedInt(v)}`, position: "top", fill: COLORS.ink, fontSize: 11 }}
            />
          ),
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
}

export const histogramCaption = (d: DistributionResponse) =>
  `${int(d.n_observations)} hours in ${int(d.bin_mw)} MW bins. Dashed lines mark P5 and P95, the solid line the median.`;
