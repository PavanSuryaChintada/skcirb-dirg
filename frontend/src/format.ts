// Display formatting only. No figures are derived here; the API supplies them.

const mw0 = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });
const one = new Intl.NumberFormat("en-GB", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const two = new Intl.NumberFormat("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// typographic minus, and an explicit plus, so signs read clearly in tables and headlines
const signed = (s: string, v: number) => (v > 0 ? `+${s}` : s.replace("-", "−"));

export const mw = (v: number | null | undefined) => (v == null ? "–" : `${mw0.format(v).replace("-", "−")} MW`);
export const signedInt = (v: number | null | undefined) => (v == null ? "–" : signed(mw0.format(v), v));
export const signedMw = (v: number | null | undefined) => (v == null ? "–" : `${signed(mw0.format(v), v)} MW`);
export const gwh = (v: number | null | undefined) => (v == null ? "–" : `${one.format(v)} GWh`);
export const signedGwh = (v: number | null | undefined) => (v == null ? "–" : `${signed(one.format(v), v)} GWh`);
export const pct = (v: number | null | undefined) => (v == null ? "–" : `${signed(one.format(v), v)}%`);
export const plainPct = (v: number | null | undefined) => (v == null ? "–" : `${one.format(v)}%`);
export const num2 = (v: number | null | undefined) => (v == null ? "–" : two.format(v));
export const num1 = (v: number | null | undefined) => (v == null ? "–" : one.format(v));
export const int = (v: number | null | undefined) => (v == null ? "–" : mw0.format(v));

// Elexon timestamps are UTC; in January UTC is UK local time, so slicing is enough.
export const clock = (iso: string | null) => (iso ? iso.slice(11, 16) : "–");
export const stamp = (iso: string | null) => (iso ? `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC` : "–");
export const hourLabel = (h: number) => `${String(h).padStart(2, "0")}:00`;

export function longDate(isoDate: string) {
  const d = new Date(`${isoDate}T00:00:00Z`);
  return d.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });
}

export function shortDate(isoDate: string) {
  const d = new Date(`${isoDate}T00:00:00Z`);
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
}
