import type { ReactNode } from "react";
import type { Load } from "../useApi";

export function Panel(props: { title: string; caption?: ReactNode; legend?: ReactNode; children: ReactNode; className?: string }) {
  const { title, caption, legend, children, className = "" } = props;
  return (
    <section className={`border border-rule bg-panel px-5 pb-4 pt-5 ${className}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="font-cond text-lg font-semibold">{title}</h2>
        {legend}
      </div>
      {caption && <p className="mt-1 max-w-[72ch] text-sm text-muted">{caption}</p>}
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function Loaded<T>({ load, children }: { load: Load<T>; children: (data: T) => ReactNode }) {
  if (load.status === "loading") return <p className="py-10 text-sm text-muted">Loading…</p>;
  if (load.status === "failed") return <p className="py-10 text-sm text-short">Couldn't load this chart: {load.message}</p>;
  return <>{children(load.data)}</>;
}

export function LegendItem({ color, label, kind = "line" }: { color: string; label: string; kind?: "line" | "block" }) {
  return (
    <li className="flex items-center gap-2">
      <span
        className={kind === "line" ? "inline-block h-0.5 w-5" : "inline-block h-3 w-3"}
        style={{ background: color }}
      />
      {label}
    </li>
  );
}

export function Legend({ children }: { children: ReactNode }) {
  return <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">{children}</ul>;
}
