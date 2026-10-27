// Every API call lives here. The backend does the maths; the UI only renders.

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type Health = {
  status: "ok" | "error";
  db: "connected" | "unreachable";
  rows: Record<string, number | null>;
};

export type Meta = {
  date_from: string;
  date_to: string;
  days_loaded: number;
  default_date: string;
  default_cutoff_hour: number;
  candidate_cutoff_hours: number[];
  last_ingest_at: string | null;
  rows: Record<string, number>;
};

export type Metrics = {
  group: string | number | null;
  n: number;
  me_mw: number | null;
  mae_mw: number | null;
  rmse_mw: number | null;
  nmae_pct: number | null;
  p5_mw: number | null;
  p50_mw: number | null;
  p95_mw: number | null;
  max_abs_error_mw: number | null;
  max_abs_error_at: string | null;
  energy_error_mwh: number | null;
  mean_actual_mw: number | null;
  skill_score: number | null;
  n_skill: number;
};

type Window = { cutoff_hour: number | null; from_date: string; to_date: string; n_observations: number };

export type MetricsResponse = Window & { selection: string; metrics: Metrics };
export type GroupedResponse = Window & { selection: string; grouped_by: string; note: string | null; groups: Metrics[] };

export type CutoffRow = { cutoff_hour: number; newest_publish: string | null; metrics: Metrics; metrics_common_hours: Metrics };
export type ByCutoffResponse = {
  cutoff_hours: number[];
  from_date: string;
  to_date: string;
  n_observations: number;
  rows: CutoffRow[];
  comparison: { from_cutoff_hour: number; to_cutoff_hour: number; mae_change_mw: number | null; rmse_change_mw: number | null };
};

export type DistributionResponse = Window & {
  bin_mw: number;
  bins: { lo_mw: number; hi_mw: number; count: number }[];
  p5_mw: number | null;
  p50_mw: number | null;
  p95_mw: number | null;
};

export type ScatterResponse = Window & { points: { start_time: string; forecast_mw: number; actual_mw: number }[] };

export type Period = {
  settlement_period: number;
  start_time: string;
  forecast_mw: number | null;
  actual_mw: number | null;
  error_mw: number | null;
  abs_error_mw: number | null;
  band_low_mw: number | null;
  band_high_mw: number | null;
  publish_time: string | null;
  horizon_hours: number | null;
  forecast_available: boolean;
};

export type DayResponse = {
  date: string;
  cutoff_hour: number;
  cutoff_time: string;
  forecast_step_expanded: boolean;
  forecast_note: string;
  publish_times: string[];
  totals: { n_hours: number; forecast_gwh: number; actual_gwh: number; error_gwh: number; error_pct: number | null };
  band: { p5_mw: number | null; p95_mw: number | null; n_observations: number; basis: string };
  periods: Period[];
};

async function get<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const query = Object.entries(params)
    .filter(([, v]) => v !== undefined)
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join("&");
  const res = await fetch(`${API_BASE_URL}${path}${query ? `?${query}` : ""}`);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* body was not JSON */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  meta: () => get<Meta>("/api/meta"),
  day: (date: string, cutoff_hour: number) => get<DayResponse>(`/api/day/${date}`, { cutoff_hour }),
  metrics: (cutoff_hour: number) => get<MetricsResponse>("/api/metrics", { cutoff_hour }),
  byHour: (cutoff_hour: number) => get<GroupedResponse>("/api/metrics/by-hour", { cutoff_hour }),
  byTercile: (cutoff_hour: number) => get<GroupedResponse>("/api/metrics/by-tercile", { cutoff_hour }),
  byHorizon: () => get<GroupedResponse>("/api/metrics/by-horizon"),
  byCutoff: () => get<ByCutoffResponse>("/api/metrics/by-cutoff"),
  distribution: (cutoff_hour: number) => get<DistributionResponse>("/api/distribution", { cutoff_hour }),
  scatter: (cutoff_hour: number) => get<ScatterResponse>("/api/scatter", { cutoff_hour }),
  csvUrl: (date: string, cutoff_hour: number) => `${API_BASE_URL}/api/export/day/${date}.csv?cutoff_hour=${cutoff_hour}`,
};
