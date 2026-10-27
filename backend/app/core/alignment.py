"""Hourly forecasts vs half-hourly actuals (SPEC-1 §3.5).

Two frames, kept apart:
- the hourly frame, where every metric runs (to_hourly, hourly_pairs)
- the 48-period display frame (expand_to_periods), which is presentation only and
  is flagged with step_expanded=True so metrics.py refuses it

Pure functions, no DB access.
"""
from datetime import timedelta

import pandas as pd

from app.core.periods import PERIODS_PER_DAY, period_start, require_gmt_days, settlement_period

HALF_HOUR = timedelta(minutes=30)


def _utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True)


def to_hourly(actuals: pd.DataFrame) -> pd.DataFrame:
    """Hourly mean MW of the two half-hourly actuals in each hour.

    Takes start_time + generation_mw. Returns start_time (the hour), actual_mw and
    n_periods. An hour with only one of its two half-hours is missing (NaN): using
    the lone half would be imputation, not an hourly mean.
    """
    start = _utc(actuals["start_time"])
    grouped = actuals.groupby(start.dt.floor("h"))["generation_mw"].agg(["mean", "count"])
    return pd.DataFrame(
        {
            "start_time": grouped.index,
            "actual_mw": grouped["mean"].where(grouped["count"] == 2).to_numpy(),
            "n_periods": grouped["count"].to_numpy(),
        }
    )


def hourly_pairs(hourly_forecast: pd.DataFrame, hourly_actuals: pd.DataFrame) -> pd.DataFrame:
    """Forecast and actual side by side, one row per forecast hour. The frame metrics run on."""
    f = hourly_forecast.assign(start_time=_utc(hourly_forecast["start_time"]))
    a = hourly_actuals[["start_time", "actual_mw"]].assign(start_time=_utc(hourly_actuals["start_time"]))
    return f.merge(a, on="start_time", how="left")


def expand_to_periods(hourly_forecast: pd.DataFrame) -> pd.DataFrame:
    """48 rows per day: each hourly value held constant across both half-hours of its hour.

    Presentation only, never fed to metrics. Every day present in the input gets all
    48 periods; hours with no forecast (missing or absent) become two NaN periods,
    never 0.
    """
    hourly = hourly_forecast.assign(start_time=_utc(hourly_forecast["start_time"]))
    if (hourly["start_time"].dt.minute != 0).any():
        raise ValueError("expand_to_periods expects hourly rows")

    days = sorted(set(hourly["start_time"].dt.date))
    if days:
        require_gmt_days(days[0], days[-1])
    grid = pd.DatetimeIndex([period_start(d, sp) for d in days for sp in range(1, PERIODS_PER_DAY + 1)], name="start_time")

    both_halves = pd.concat([hourly, hourly.assign(start_time=hourly["start_time"] + HALF_HOUR)])
    out = both_halves.set_index("start_time").reindex(grid).reset_index()
    out["settlement_date"] = out["start_time"].dt.date
    out["settlement_period"] = [settlement_period(t) for t in out["start_time"]]
    out["step_expanded"] = True
    return out
