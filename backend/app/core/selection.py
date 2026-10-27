"""Decision-time forecast selection (SPEC-1 §3.3).

For each hour of delivery day D: the latest WINDFOR publish with
publish_time <= cutoff(D) and horizon_hours >= 0. If none qualifies the hour is
missing (None / NaN). Never interpolated, never filled from a later publish.

The rule lives in one pure function, select_for_day. decision_time_forecasts only
fetches candidates and hands them to it, so the tested code is the shipped code on
both Postgres and SQLite.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Forecast

UTC = timezone.utc
COLUMNS = ["start_time", "publish_time", "generation_mw", "horizon_hours"]


def cutoff_for(delivery_date: date, cutoff_hour: int) -> datetime:
    """Latest moment a forecast could have been used for delivery_date: D-1 at cutoff_hour:00 UTC."""
    if not 0 <= cutoff_hour <= 23:
        raise ValueError(f"cutoff_hour must be 0-23, got {cutoff_hour}")
    return datetime.combine(delivery_date - timedelta(days=1), time(cutoff_hour), tzinfo=UTC)


def _day_bounds(delivery_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(delivery_date, time(0), tzinfo=UTC)
    return start, start + timedelta(days=1)


def select_for_day(forecasts: pd.DataFrame, delivery_date: date, cutoff_hour: int) -> pd.DataFrame:
    """24 rows, one per hour of delivery_date, in order.

    Takes any frame of start_time, publish_time, generation_mw, horizon_hours. Returns
    start_time, forecast_mw, publish_time, horizon_hours, forecast_available.
    """
    cutoff = cutoff_for(delivery_date, cutoff_hour)
    day_start, day_end = _day_bounds(delivery_date)
    f = forecasts[COLUMNS].assign(
        start_time=pd.to_datetime(forecasts["start_time"], utc=True),
        publish_time=pd.to_datetime(forecasts["publish_time"], utc=True),
    )
    candidates = f[
        (f["start_time"] >= day_start)
        & (f["start_time"] < day_end)
        & (f["publish_time"] <= cutoff)
        & (f["horizon_hours"] >= 0)
    ]
    latest = candidates.sort_values("publish_time").groupby("start_time").tail(1).set_index("start_time")

    hours = pd.date_range(day_start, periods=24, freq="h", name="start_time")
    out = latest.reindex(hours).reset_index().rename(columns={"generation_mw": "forecast_mw"})
    out["forecast_available"] = out["forecast_mw"].notna()
    return out[["start_time", "forecast_mw", "publish_time", "horizon_hours", "forecast_available"]]


def select_for_days(forecasts: pd.DataFrame, delivery_dates, cutoff_hour: int) -> pd.DataFrame:
    """select_for_day over several delivery days, concatenated in date order."""
    frames = [select_for_day(forecasts, d, cutoff_hour).assign(delivery_date=d) for d in sorted(delivery_dates)]
    return pd.concat(frames, ignore_index=True)


@dataclass(frozen=True)
class ForecastRow:
    start_time: datetime
    forecast_mw: float | None
    publish_time: datetime | None
    horizon_hours: float | None

    @property
    def forecast_available(self) -> bool:
        return self.forecast_mw is not None


def _float_or_none(value) -> float | None:
    return None if pd.isna(value) else float(value)


def decision_time_forecasts(delivery_date: date, cutoff_hour: int, session: Session) -> list[ForecastRow]:
    """Latest forecast per hourly start_time with publish_time <= cutoff and horizon_hours >= 0.

    Hours with no qualifying forecast come back with forecast_mw = None.
    """
    cutoff = cutoff_for(delivery_date, cutoff_hour)
    day_start, day_end = _day_bounds(delivery_date)
    result = session.execute(
        select(Forecast.start_time, Forecast.publish_time, Forecast.generation_mw, Forecast.horizon_hours).where(
            Forecast.start_time >= day_start,
            Forecast.start_time < day_end,
            Forecast.publish_time <= cutoff,
            Forecast.horizon_hours >= 0,
        )
    ).all()
    chosen = select_for_day(pd.DataFrame(result, columns=COLUMNS), delivery_date, cutoff_hour)
    return [
        ForecastRow(
            start_time=r.start_time.to_pydatetime(),
            forecast_mw=_float_or_none(r.forecast_mw),
            publish_time=None if pd.isna(r.publish_time) else r.publish_time.to_pydatetime(),
            horizon_hours=_float_or_none(r.horizon_hours),
        )
        for r in chosen.itertuples()
    ]
