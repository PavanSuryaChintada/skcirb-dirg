"""fetch -> normalise -> upsert.

Mirrors the source faithfully. The only rows dropped are ones that cannot be valid:
unparseable times, missing MW, negative MW on WIND actuals, and anything published
outside [lower, upper). Past-hour forecasts are kept (D3).
"""
import time as time_module
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import Engine, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import OperationalError

from app.core.periods import require_gmt_days, settlement_date, settlement_period
from app.ingest import elexon_client
from app.models import Actual, Base, Forecast

WIND = "WIND"
UTC = timezone.utc


def parse_ts(value) -> datetime | None:
    """Elexon timestamps are 'YYYY-MM-DDTHH:MM:SSZ' (A7). Anything else is rejected."""
    if not isinstance(value, str):
        return None
    try:
        ts = datetime.fromisoformat(value)
    except ValueError:
        return None
    return ts.astimezone(UTC) if ts.tzinfo else None


def _mw(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def normalise_actuals(raw: list[dict], lower: datetime, upper: datetime) -> tuple[list[dict], Counter]:
    """FUELHH -> actuals rows. WIND only; negative MW rejected for WIND (D7)."""
    stats: Counter = Counter()
    latest: dict[datetime, tuple[datetime, dict]] = {}
    for r in raw:
        if r.get("fuelType") != WIND:
            stats["other_fuel_skipped"] += 1
            continue
        start, pub, mw = parse_ts(r.get("startTime")), parse_ts(r.get("publishTime")), _mw(r.get("generation"))
        if start is None or pub is None:
            stats["rejected_bad_time"] += 1
            continue
        if not lower <= pub < upper:
            stats["outside_window"] += 1
            continue
        if mw is None:
            stats["rejected_missing_mw"] += 1
            continue
        if mw < 0:
            stats["rejected_negative_mw"] += 1
            continue
        sd, sp = settlement_date(start), settlement_period(start)
        if (r.get("settlementDate"), r.get("settlementPeriod")) != (sd.isoformat(), sp):
            stats["rejected_period_mismatch"] += 1
            continue
        row = {"start_time": start, "settlement_date": sd, "settlement_period": sp, "generation_mw": mw}
        seen = latest.get(start)
        if seen is not None:
            # same publishTime = chunk-edge overlap (A4); a later one = a revision
            stats["boundary_duplicates" if pub == seen[0] else "revisions"] += 1
            if pub <= seen[0]:
                continue  # keep the latest publish of a period
        latest[start] = (pub, row)
    rows = [row for _, row in latest.values()]
    stats["kept"] = len(rows)
    return rows, stats


def normalise_forecasts(raw: list[dict], lower: datetime, upper: datetime) -> tuple[list[dict], Counter]:
    """WINDFOR -> forecasts rows. Every vintage kept, past-hour rows included (D3)."""
    stats: Counter = Counter()
    rows: dict[tuple[datetime, datetime], dict] = {}
    for r in raw:
        start, pub, mw = parse_ts(r.get("startTime")), parse_ts(r.get("publishTime")), _mw(r.get("generation"))
        if start is None or pub is None:
            stats["rejected_bad_time"] += 1
            continue
        if not lower <= pub < upper:
            stats["outside_window"] += 1
            continue
        if mw is None:
            stats["rejected_missing_mw"] += 1
            continue
        if mw < 0:
            stats["negative_mw_stored"] += 1  # none seen in recon (A20); kept as published, but counted
        horizon = (start - pub).total_seconds() / 3600
        if horizon < 0:
            stats["past_hour_rows"] += 1
        key = (start, pub)
        if key in rows:
            stats["boundary_duplicates"] += 1
        rows[key] = {
            "start_time": start,
            "publish_time": pub,
            "settlement_date": settlement_date(start),
            "settlement_period": settlement_period(start),
            "generation_mw": mw,
            "horizon_hours": horizon,
        }
    stats["kept"] = len(rows)
    return list(rows.values()), stats


def upsert(conn, table, rows: list[dict], pk: list[str]) -> None:
    """INSERT ... ON CONFLICT (pk) DO UPDATE. Rows must be unique on pk.

    One compiled statement, executed with a list of parameter sets: SQLAlchemy and
    the driver batch the round trips, which matters against a remote pooler.
    """
    if not rows:
        return
    insert = pg_insert if conn.dialect.name == "postgresql" else sqlite_insert
    stmt = insert(table)
    stmt = stmt.on_conflict_do_update(
        index_elements=pk,
        set_={c.name: stmt.excluded[c.name] for c in table.columns if c.name not in pk},
    )
    conn.execute(stmt, rows)


def table_counts(conn) -> dict[str, int]:
    return {t.name: conn.execute(select(func.count()).select_from(t)).scalar_one() for t in (Actual.__table__, Forecast.__table__)}


def load(engine: Engine, actuals: list[dict], forecasts: list[dict]) -> tuple[dict, dict]:
    """Create tables if missing and upsert everything in one transaction. Returns (before, after) counts."""
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            # if this client dies mid-load, the server ends the orphaned transaction and
            # frees its row locks after 60s, instead of blocking the next run
            conn.execute(text("SET LOCAL idle_in_transaction_session_timeout = '60s'"))
        before = table_counts(conn)
        upsert(conn, Actual.__table__, actuals, ["start_time"])
        upsert(conn, Forecast.__table__, forecasts, ["start_time", "publish_time"])
        after = table_counts(conn)
    return before, after


def with_db_retry(fn: Callable, log: Callable[[str], None], attempts: int = 4, sleep: Callable = time_module.sleep):
    """Retry a database step after a dropped connection, with exponential backoff.

    Safe for load(): it is one transaction, so a failure rolls back completely, and
    every write is an upsert, so repeating it cannot duplicate anything.
    """
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except OperationalError as exc:
            if attempt == attempts:
                raise
            delay = 2 ** attempt
            log(f"    database error ({type(exc.orig).__name__}), rolled back; retry {attempt}/{attempts - 1} in {delay}s")
            sleep(delay)


def coverage(engine: Engine, start: date, end: date, lower: datetime, upper: datetime) -> dict:
    """What is actually stored, read back from the database."""
    with engine.connect() as conn:
        sps = conn.execute(
            select(Actual.settlement_date, Actual.settlement_period).where(
                Actual.settlement_date >= start, Actual.settlement_date <= end
            )
        ).all()
        hours = {
            ts.astimezone(UTC) if ts.tzinfo else ts.replace(tzinfo=UTC)
            for ts in conn.execute(
                select(Forecast.start_time).where(Forecast.start_time >= lower, Forecast.start_time < upper).distinct()
            ).scalars()
        }
        pubs = sorted(
            ts.astimezone(UTC) if ts.tzinfo else ts.replace(tzinfo=UTC)
            for ts in conn.execute(select(Forecast.publish_time).distinct()).scalars()
        )

    by_day: dict[date, set[int]] = {}
    for d, sp in sps:
        by_day.setdefault(d, set()).add(sp)
    actual_gaps = {}
    d = start
    while d <= end:
        missing = sorted(set(range(1, 49)) - by_day.get(d, set()))
        if missing:
            actual_gaps[d] = missing
        d += timedelta(days=1)

    all_hours = []
    h = lower
    while h < upper:
        all_hours.append(h)
        h += timedelta(hours=1)
    forecast_gaps = [h for h in all_hours if h not in hours]
    max_pub_gap = max((b - a for a, b in zip(pubs, pubs[1:])), default=None)

    return {
        "actual_days": (end - start).days + 1,
        "actual_days_complete": (end - start).days + 1 - len(actual_gaps),
        "actual_gaps": actual_gaps,
        "forecast_hours": len(all_hours),
        "forecast_hours_covered": len(all_hours) - len(forecast_gaps),
        "forecast_gaps": forecast_gaps,
        "publishes": len(pubs),
        "first_publish": pubs[0] if pubs else None,
        "last_publish": pubs[-1] if pubs else None,
        "max_publish_gap": max_pub_gap,
    }


@dataclass
class Summary:
    lower: datetime
    upper: datetime
    fetched: dict[str, int] = field(default_factory=dict)
    actual_stats: Counter = field(default_factory=Counter)
    forecast_stats: Counter = field(default_factory=Counter)
    written: dict[str, int] = field(default_factory=dict)
    before: dict[str, int] = field(default_factory=dict)
    after: dict[str, int] = field(default_factory=dict)
    coverage: dict = field(default_factory=dict)
    seconds: dict[str, float] = field(default_factory=dict)


def run(engine: Engine, start: date, end: date, chunk_days: int = 7, log: Callable[[str], None] = print) -> Summary:
    """Ingest everything published in [start 00:00Z, (end + 1 day) 00:00Z)."""
    require_gmt_days(start, end)
    lower = datetime.combine(start, time(0), tzinfo=UTC)
    upper = datetime.combine(end + timedelta(days=1), time(0), tzinfo=UTC)
    s = Summary(lower=lower, upper=upper)

    t = time_module.monotonic()
    raw_fuel = elexon_client.fetch("FUELHH", lower, upper, chunk_days, log=log)
    raw_wind = elexon_client.fetch("WINDFOR", lower, upper, chunk_days, log=log)
    s.fetched = {"FUELHH": len(raw_fuel), "WINDFOR": len(raw_wind)}
    s.seconds["fetch"], t = time_module.monotonic() - t, time_module.monotonic()

    actuals, s.actual_stats = normalise_actuals(raw_fuel, lower, upper)
    forecasts, s.forecast_stats = normalise_forecasts(raw_wind, lower, upper)
    s.seconds["normalise"], t = time_module.monotonic() - t, time_module.monotonic()

    s.before, s.after = with_db_retry(lambda: load(engine, actuals, forecasts), log)
    s.written = {"actuals": len(actuals), "forecasts": len(forecasts)}
    s.seconds["write"], t = time_module.monotonic() - t, time_module.monotonic()

    s.coverage = with_db_retry(lambda: coverage(engine, start, end, lower, upper), log)
    s.seconds["coverage"] = time_module.monotonic() - t
    return s
