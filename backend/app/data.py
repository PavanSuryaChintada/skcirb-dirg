"""The study month, loaded from the database and held in memory.

The dataset is a closed month (~20k forecast rows), so every request reading Postgres
again would only add latency. It is reloaded after CACHE_TTL, so a fresh ingest shows
up without a restart.
"""
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import func, inspect, select

from app.config import get_settings
from app.core.alignment import to_hourly
from app.db import get_engine
from app.models import Actual, Forecast, IngestRun

UTC = timezone.utc
CACHE_TTL = timedelta(minutes=10)


class NoData(RuntimeError):
    pass


@dataclass
class Dataset:
    forecasts: pd.DataFrame
    forecasts_by_day: dict[date, pd.DataFrame]
    actuals: pd.DataFrame
    hourly_actuals: pd.DataFrame
    days: list[date]  # delivery days in the study window with all 48 actual periods
    last_ingest_at: datetime | None
    loaded_at: datetime
    cache: dict = field(default_factory=dict)


_lock = threading.Lock()
_current: Dataset | None = None


def _load() -> Dataset:
    settings = get_settings()
    engine = get_engine()
    with engine.connect() as conn:
        forecasts = pd.DataFrame(
            conn.execute(
                select(Forecast.start_time, Forecast.publish_time, Forecast.generation_mw, Forecast.horizon_hours)
            ).all(),
            columns=["start_time", "publish_time", "generation_mw", "horizon_hours"],
        )
        actuals = pd.DataFrame(
            conn.execute(
                select(Actual.start_time, Actual.settlement_date, Actual.settlement_period, Actual.generation_mw)
            ).all(),
            columns=["start_time", "settlement_date", "settlement_period", "generation_mw"],
        )
        last_ingest = (
            conn.execute(select(func.max(IngestRun.finished_at))).scalar_one()
            if inspect(conn).has_table(IngestRun.__tablename__)
            else None
        )
    if actuals.empty or forecasts.empty:
        raise NoData("no data loaded yet - run: python -m scripts.ingest --from 2025-12-30 --to 2026-02-01")

    for col in ("start_time", "publish_time"):
        forecasts[col] = pd.to_datetime(forecasts[col], utc=True)
    actuals["start_time"] = pd.to_datetime(actuals["start_time"], utc=True)

    per_day = actuals.groupby("settlement_date")["settlement_period"].nunique()
    days = [d for d, n in per_day.items() if n == 48 and settings.study_from <= d <= settings.study_to]
    if last_ingest is not None and last_ingest.tzinfo is None:
        last_ingest = last_ingest.replace(tzinfo=UTC)

    return Dataset(
        forecasts=forecasts,
        forecasts_by_day={d: g for d, g in forecasts.groupby(forecasts["start_time"].dt.date)},
        actuals=actuals,
        hourly_actuals=to_hourly(actuals),
        days=sorted(days),
        last_ingest_at=last_ingest,
        loaded_at=datetime.now(UTC),
    )


def get_dataset() -> Dataset:
    global _current
    with _lock:
        if _current is None or datetime.now(UTC) - _current.loaded_at > CACHE_TTL:
            _current = _load()
        return _current


def reset_cache() -> None:
    global _current
    with _lock:
        _current = None
