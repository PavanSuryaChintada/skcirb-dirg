// Every API call lives here. The backend does the maths; the UI only renders.

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type Health = {
  status: "ok" | "error";
  db: "connected" | "unreachable";
  // null = table not created yet
  rows: Record<string, number | null>;
};

export async function getHealth(): Promise<Health> {
  const res = await fetch(`${API_BASE_URL}/api/health`);
  // a 503 still carries a Health body describing what is wrong
  if (!res.ok && res.status !== 503) {
    throw new Error(`health check failed: HTTP ${res.status}`);
  }
  return res.json();
}
