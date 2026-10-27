"""Load FUELHH wind actuals and WINDFOR forecasts into the database.

    python -m scripts.ingest --from 2025-12-30 --to 2026-02-01

--from and --to are UTC publish dates, both inclusive. The window is
[from 00:00Z, (to + 1 day) 00:00Z), so --to 2026-02-01 ends at 2026-02-02T00:00Z,
exclusive. Safe to rerun: every write is an upsert on the table's primary key.
"""
import argparse
import time
from datetime import date

from app.db import get_engine
from app.ingest.loader import Summary, run

FMT = "%Y-%m-%dT%H:%MZ"


def print_summary(s: Summary, elapsed: float) -> None:
    c = s.coverage
    print()
    print(f"window      [{s.lower.strftime(FMT)}, {s.upper.strftime(FMT)})  publishTime, upper bound exclusive")
    print(f"fetched     FUELHH {s.fetched['FUELHH']:,} rows (all fuels)   WINDFOR {s.fetched['WINDFOR']:,} rows")
    print(f"actuals     {dict(sorted(s.actual_stats.items()))}")
    print(f"forecasts   {dict(sorted(s.forecast_stats.items()))}")
    print(f"written     actuals {s.written['actuals']:,} upserted   forecasts {s.written['forecasts']:,} upserted")
    for t in ("actuals", "forecasts"):
        print(f"table       {t:<9} before {s.before[t]:>6,}  after {s.after[t]:>6,}  new {s.after[t] - s.before[t]:,}")
    print(f"coverage    actuals: {c['actual_days_complete']}/{c['actual_days']} settlement days have SP1-SP48")
    for d, missing in c["actual_gaps"].items():
        print(f"  gap       actuals {d}: missing SP {missing}")
    print(f"coverage    forecasts: {c['forecast_hours_covered']}/{c['forecast_hours']} hours in the window have at least one forecast")
    for h in c["forecast_gaps"]:
        print(f"  gap       forecasts: no row for {h.strftime(FMT)}")
    first = c["first_publish"].strftime(FMT) if c["first_publish"] else "-"
    last = c["last_publish"].strftime(FMT) if c["last_publish"] else "-"
    print(f"publishes   {c['publishes']} distinct, {first} .. {last}, longest gap between publishes {c['max_publish_gap']}")
    stages = "  ".join(f"{k} {v:.1f}s" for k, v in s.seconds.items())
    print(f"done in {elapsed:.1f}s  ({stages})")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="start", type=date.fromisoformat, required=True, help="first publish date, UTC")
    parser.add_argument("--to", dest="end", type=date.fromisoformat, required=True, help="last publish date, UTC, inclusive")
    parser.add_argument("--chunk-days", type=int, default=7, help="days per request (default 7)")
    args = parser.parse_args(argv)
    if args.end < args.start:
        parser.error("--to is before --from")

    t0 = time.monotonic()
    summary = run(get_engine(), args.start, args.end, chunk_days=args.chunk_days)
    print_summary(summary, time.monotonic() - t0)


if __name__ == "__main__":
    main()
