import { useEffect, useState } from "react";
import { api, type Meta } from "./api/client";
import { hourLabel } from "./format";
import Accuracy from "./pages/Accuracy";
import DailyDetail from "./pages/DailyDetail";
import Dashboard from "./pages/Dashboard";
import { useApi } from "./useApi";

const PAGES = [
  { id: "day", label: "Day view" },
  { id: "accuracy", label: "Accuracy" },
  { id: "detail", label: "Periods" },
] as const;
type PageId = (typeof PAGES)[number]["id"];

function pageFromHash(): PageId {
  const id = window.location.hash.replace("#/", "");
  return (PAGES.find((p) => p.id === id)?.id ?? "day") as PageId;
}

export default function App() {
  const meta = useApi(api.meta, []);
  const [page, setPage] = useState<PageId>(pageFromHash);
  const [date, setDate] = useState<string | null>(null);
  const [cutoff, setCutoff] = useState<number | null>(null);

  useEffect(() => {
    const onHash = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (meta.status === "ready") {
      setDate((d) => d ?? meta.data.default_date);
      setCutoff((c) => c ?? meta.data.default_cutoff_hour);
    }
  }, [meta]);

  return (
    <div className="min-h-screen">
      <header className="border-b border-rule bg-panel">
        <div className="mx-auto flex max-w-[1180px] flex-wrap items-end gap-x-10 gap-y-4 px-6 py-4">
          <div>
            <p className="font-cond text-xl font-semibold leading-none">Wind forecast accuracy</p>
            <p className="mt-1 text-sm text-muted">GB national wind, day-ahead, January 2026</p>
          </div>
          <nav className="flex gap-6 text-sm" aria-label="Screens">
            {PAGES.map((p) => (
              <a
                key={p.id}
                href={`#/${p.id}`}
                aria-current={page === p.id ? "page" : undefined}
                className={
                  page === p.id
                    ? "border-b-2 border-forecast pb-1 font-medium text-ink"
                    : "border-b-2 border-transparent pb-1 text-muted hover:text-ink"
                }
              >
                {p.label}
              </a>
            ))}
          </nav>
          {meta.status === "ready" && date !== null && cutoff !== null && (
            <Controls meta={meta.data} date={date} cutoff={cutoff} onDate={setDate} onCutoff={setCutoff} />
          )}
        </div>
      </header>

      <main className="mx-auto max-w-[1180px] px-6 py-8">
        {meta.status === "loading" && <p className="text-muted">Loading the January dataset…</p>}
        {meta.status === "failed" && (
          <p className="text-short">
            Can't reach the API ({meta.message}). Check that the backend is running and that data has been ingested.
          </p>
        )}
        {meta.status === "ready" && date !== null && cutoff !== null && page === "day" && (
          <Dashboard date={date} cutoff={cutoff} />
        )}
        {meta.status === "ready" && cutoff !== null && page === "accuracy" && <Accuracy cutoff={cutoff} />}
        {meta.status === "ready" && date !== null && cutoff !== null && page === "detail" && (
          <DailyDetail date={date} cutoff={cutoff} />
        )}
      </main>
    </div>
  );
}

function Controls(props: {
  meta: Meta;
  date: string;
  cutoff: number;
  onDate: (d: string) => void;
  onCutoff: (c: number) => void;
}) {
  const { meta, date, cutoff, onDate, onCutoff } = props;
  return (
    <div className="ml-auto flex flex-wrap items-end gap-5 text-sm">
      <label className="flex flex-col gap-1">
        <span className="text-muted">Delivery day</span>
        <input
          type="date"
          value={date}
          min={meta.date_from}
          max={meta.date_to}
          onChange={(e) => e.target.value && onDate(e.target.value)}
          className="rounded-[3px] border border-rule bg-panel px-2 py-1"
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-muted">Decision cut-off (D-1, UTC)</span>
        <select
          value={cutoff}
          onChange={(e) => onCutoff(Number(e.target.value))}
          className="rounded-[3px] border border-rule bg-panel px-2 py-1"
        >
          {Array.from({ length: 24 }, (_, h) => (
            <option key={h} value={h}>
              {hourLabel(h)}
              {h === meta.default_cutoff_hour ? " (default)" : ""}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
