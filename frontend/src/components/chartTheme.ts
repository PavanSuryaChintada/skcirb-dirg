// Shared chart styling so every chart reads as one system.

export const COLORS = {
  ink: "#142033",
  muted: "#5b6878",
  rule: "#d5dbe2",
  forecast: "#2f5d9e",
  band: "#2f5d9e",
  short: "#b97a12",
  long: "#1b7f79",
};

export const AXIS = {
  stroke: COLORS.rule,
  tick: { fill: COLORS.muted, fontSize: 12 },
  tickLine: false,
};

export const AXIS_LABEL = { fill: COLORS.muted, fontSize: 12 };

// short = forecast too high (e > 0), long = forecast too low (e < 0)
export const errorColor = (e: number | null) => (e == null ? COLORS.rule : e > 0 ? COLORS.short : COLORS.long);
