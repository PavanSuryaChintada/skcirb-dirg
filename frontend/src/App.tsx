import { useEffect, useState } from "react";
import { API_BASE_URL, getHealth, type Health } from "./api/client";

type State = { kind: "loading" } | { kind: "ready"; health: Health } | { kind: "failed"; message: string };

export default function App() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    getHealth()
      .then((health) => setState({ kind: "ready", health }))
      .catch((err: Error) => setState({ kind: "failed", message: err.message }));
  }, []);

  return (
    <main className="mx-auto max-w-2xl px-6 py-16 text-slate-800">
      <h1 className="text-2xl font-semibold">Wind forecast accuracy</h1>
      <p className="mt-1 text-slate-500">GB national wind · day-ahead procurement · January 2026</p>

      <section className="mt-10 rounded border border-slate-200 p-5">
        <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">API status</h2>
        <StatusBody state={state} />
        <p className="mt-4 text-xs text-slate-400">{API_BASE_URL}/api/health</p>
      </section>

      <p className="mt-8 text-sm text-slate-500">Placeholder page. The dashboard screens are built in later phases.</p>
    </main>
  );
}

function StatusBody({ state }: { state: State }) {
  if (state.kind === "loading") return <p className="mt-3">Checking…</p>;
  if (state.kind === "failed") return <p className="mt-3 text-red-700">Could not reach the API: {state.message}</p>;

  const { health } = state;
  const ok = health.status === "ok";
  return (
    <dl className="mt-3 grid grid-cols-[8rem_1fr] gap-y-1 text-sm">
      <dt className="text-slate-500">status</dt>
      <dd className={ok ? "font-medium text-green-700" : "font-medium text-red-700"}>{health.status}</dd>
      <dt className="text-slate-500">database</dt>
      <dd>{health.db}</dd>
      {Object.entries(health.rows).map(([table, n]) => (
        <div key={table} className="contents">
          <dt className="text-slate-500">{table}</dt>
          <dd>{n === null ? "table not created yet" : `${n.toLocaleString()} rows`}</dd>
        </div>
      ))}
    </dl>
  );
}
