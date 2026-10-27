"""Builds the frames the routers need from the cached dataset.

Composition only: selection, alignment and every formula live in app/core. This module
just decides which rows go in.
"""
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone

import pandas as pd

from app.core.alignment import hourly_pairs
from app.core.metrics import persistence_baseline
from app.core.selection import COLUMNS, select_for_day
from app.data import Dataset

UTC = timezone.utc
CANDIDATE_CUTOFFS = (2, 4, 7, 9, 11)  # each makes a different WINDFOR publish the newest (SPEC-1 §3.6)
EMPTY = pd.DataFrame(columns=COLUMNS)


def decision_frame(ds: Dataset, cutoff_hour: int, days: list[date]) -> pd.DataFrame:
    """Hourly frame of decision-time forecast, hourly actual and persistence, for the given days."""
    key = ("decision", cutoff_hour)
    if key not in ds.cache:
        selected = pd.concat(
            [select_for_day(ds.forecasts_by_day.get(d, EMPTY), d, cutoff_hour).assign(delivery_date=d) for d in ds.days],
            ignore_index=True,
        )
        frame = hourly_pairs(selected, ds.hourly_actuals)
        frame["persistence_mw"] = persistence_baseline(frame, ds.hourly_actuals)
        ds.cache[key] = frame
    frame = ds.cache[key]
    return frame[frame["delivery_date"].isin(days)].reset_index(drop=True)


def vintage_frame(ds: Dataset, days: list[date]) -> pd.DataFrame:
    """Every stored forecast for the given days paired with its hourly actual: all vintages, no cut-off."""
    start = datetime.combine(min(days), time(0), tzinfo=UTC)
    end = datetime.combine(max(days) + timedelta(days=1), time(0), tzinfo=UTC)
    f = ds.forecasts
    rows = f[
        (f["start_time"] >= start)
        & (f["start_time"] < end)
        & (f["horizon_hours"] >= 0)  # explicit: past-hour rows never enter analytics
    ].rename(columns={"generation_mw": "forecast_mw"})
    rows = rows[rows["start_time"].dt.date.isin(days)]
    return hourly_pairs(rows, ds.hourly_actuals)


def newest_publish_label(frame: pd.DataFrame) -> str | None:
    """Most common selected publish, relative to the delivery day, e.g. 'D-1 07:30'."""
    labels = Counter()
    for d, p in zip(frame["delivery_date"], frame["publish_time"]):
        if pd.isna(p):
            continue
        offset = (p.date() - d).days
        labels[f"D{offset:+d} {p:%H:%M}".replace("D+0", "D")] += 1
    return labels.most_common(1)[0][0] if labels else None
