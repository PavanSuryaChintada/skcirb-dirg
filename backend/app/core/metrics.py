"""Every formula from SPEC-1 §4.

Pure functions on the HOURLY frame (columns forecast_mw, actual_mw; optionally
start_time, horizon_hours, persistence_mw). No DB access, no FastAPI. A step-expanded
48-period frame is refused: it would double n without adding information.

No MAPE anywhere (SPEC-1 §4.1); nMAE is the headline percentage.
"""
import math
from dataclasses import dataclass
from datetime import date, datetime

import numpy as np
import pandas as pd

HOURS_PER_ROW = 1.0  # hourly frame: MW x 1 h = MWh
HORIZON_EDGES = [0, 6, 12, 18, 24, np.inf]
HORIZON_LABELS = ["0-6h", "6-12h", "12-18h", "18-24h", "24h+"]
TERCILE_LABELS = ["low", "medium", "high"]


@dataclass(frozen=True)
class MetricSet:
    n: int
    me_mw: float | None = None
    mae_mw: float | None = None
    rmse_mw: float | None = None
    nmae_pct: float | None = None
    p5_mw: float | None = None
    p50_mw: float | None = None
    p95_mw: float | None = None
    max_abs_error_mw: float | None = None
    max_abs_error_at: datetime | None = None
    energy_error_mwh: float | None = None
    mean_actual_mw: float | None = None
    skill_score: float | None = None
    n_skill: int = 0
    group: str | int | date | None = None


def _require_hourly(df: pd.DataFrame) -> None:
    if "step_expanded" in df.columns:
        raise ValueError("metrics run on the hourly frame only; step-expanded periods are presentation only")


def error_series(df: pd.DataFrame) -> pd.Series:
    """e = f - a. Positive = forecast over-predicted wind."""
    _require_hourly(df)
    return df["forecast_mw"] - df["actual_mw"]


def _rmse(e: pd.Series) -> float:
    return math.sqrt(float((e**2).mean()))


def skill_score(rmse_model: float | None, rmse_baseline: float | None) -> float | None:
    """1 - RMSE_model / RMSE_baseline. Positive = beats the baseline."""
    if rmse_model is None or not rmse_baseline:
        return None
    return 1.0 - rmse_model / rmse_baseline


def persistence_baseline(df: pd.DataFrame, hourly_actuals: pd.DataFrame) -> pd.Series:
    """persistence(D, H) = hourly mean actual at (D - 1 day, H). Missing stays missing."""
    lookup = pd.Series(
        hourly_actuals["actual_mw"].to_numpy(), index=pd.to_datetime(hourly_actuals["start_time"], utc=True)
    )
    previous_day = pd.to_datetime(df["start_time"], utc=True) - pd.Timedelta(days=1)
    return pd.Series(lookup.reindex(previous_day).to_numpy(), index=df.index, name="persistence_mw")


def compute_metrics(df: pd.DataFrame, group=None) -> MetricSet:
    """The full SPEC-1 §4 metric set. Rows missing either side are dropped first; n is what survived."""
    _require_hourly(df)
    valid = df.dropna(subset=["forecast_mw", "actual_mw"])
    n = len(valid)
    if n == 0:
        return MetricSet(n=0, group=group)

    e = (valid["forecast_mw"] - valid["actual_mw"]).astype(float)
    abs_e = e.abs()
    mean_actual = float(valid["actual_mw"].mean())
    p5, p50, p95 = (float(q) for q in e.quantile([0.05, 0.50, 0.95]))  # linear interpolation
    worst = abs_e.idxmax()
    worst_at = pd.Timestamp(valid.loc[worst, "start_time"]).to_pydatetime() if "start_time" in valid else None

    skill, n_skill = None, 0
    if "persistence_mw" in valid:
        both = valid.dropna(subset=["persistence_mw"])  # same rows for both RMSEs
        n_skill = len(both)
        if n_skill:
            skill = skill_score(
                _rmse(both["forecast_mw"] - both["actual_mw"]), _rmse(both["persistence_mw"] - both["actual_mw"])
            )

    return MetricSet(
        n=n,
        me_mw=float(e.mean()),
        mae_mw=float(abs_e.mean()),
        rmse_mw=_rmse(e),
        nmae_pct=100.0 * float(abs_e.mean()) / mean_actual if mean_actual else None,
        p5_mw=p5,
        p50_mw=p50,
        p95_mw=p95,
        max_abs_error_mw=float(abs_e.loc[worst]),
        max_abs_error_at=worst_at,
        energy_error_mwh=float(e.sum()) * HOURS_PER_ROW,
        mean_actual_mw=mean_actual,
        skill_score=skill,
        n_skill=n_skill,
        group=group,
    )


def energy_totals(df: pd.DataFrame) -> dict:
    """Day or window totals on the hourly frame, over hours where both sides exist."""
    _require_hourly(df)
    valid = df.dropna(subset=["forecast_mw", "actual_mw"])
    forecast_mwh = float(valid["forecast_mw"].sum()) * HOURS_PER_ROW
    actual_mwh = float(valid["actual_mw"].sum()) * HOURS_PER_ROW
    error_mwh = forecast_mwh - actual_mwh
    return {
        "n_hours": len(valid),
        "forecast_gwh": forecast_mwh / 1000,
        "actual_gwh": actual_mwh / 1000,
        "error_gwh": error_mwh / 1000,
        "error_pct": 100 * error_mwh / actual_mwh if actual_mwh else None,
    }


def compare(before: MetricSet, after: MetricSet) -> dict:
    """Change in MAE and RMSE going from one metric set to another (negative = better)."""

    def diff(a, b):
        return None if a is None or b is None else b - a

    return {"mae_change_mw": diff(before.mae_mw, after.mae_mw), "rmse_change_mw": diff(before.rmse_mw, after.rmse_mw)}


def display_period_errors(periods: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Per-row e and |e| for the 48-period display table and error bars.

    The one function allowed to touch a step-expanded frame: it never aggregates, so
    it cannot inflate n. Every summary figure comes from the hourly frame instead.
    """
    e = periods["forecast_mw"] - periods["actual_mw"]
    return e, e.abs()


def error_band(forecast_mw: pd.Series, p5_mw: float | None, p95_mw: float | None) -> tuple[pd.Series, pd.Series]:
    """Where the actual is expected to land, from historical error quantiles.

    e = f - a, so a = f - e: the 90% range for the actual is [f - P95, f - P5].
    """
    if p5_mw is None or p95_mw is None:
        missing = pd.Series(np.nan, index=forecast_mw.index)
        return missing, missing
    return forecast_mw - p95_mw, forecast_mw - p5_mw


def error_histogram(df: pd.DataFrame, bin_mw: float = 500.0) -> list[dict]:
    """Counts of e = f - a in fixed-width bins aligned to multiples of bin_mw. Valid pairs only."""
    _require_hourly(df)
    if bin_mw <= 0:
        raise ValueError("bin_mw must be positive")
    e = error_series(df).dropna()
    if e.empty:
        return []
    lo = math.floor(e.min() / bin_mw) * bin_mw
    hi = math.ceil(e.max() / bin_mw) * bin_mw
    if hi == lo:
        hi = lo + bin_mw
    edges = np.arange(lo, hi + bin_mw / 2, bin_mw)
    counts, _ = np.histogram(e, bins=edges)
    return [{"lo_mw": float(a), "hi_mw": float(b), "count": int(c)} for a, b, c in zip(edges[:-1], edges[1:], counts)]


def group_metrics(df: pd.DataFrame, by: str) -> list[MetricSet]:
    """Metric set per group. by = 'hour' (00-23), 'day', 'horizon' (bucketed) or 'tercile' (of actual MW)."""
    _require_hourly(df)
    if by == "hour":
        keys = pd.to_datetime(df["start_time"], utc=True).dt.hour
    elif by == "day":
        keys = pd.to_datetime(df["start_time"], utc=True).dt.date
    elif by == "horizon":
        df = df[df["horizon_hours"] >= 0]  # explicit: past-hour rows never enter analytics
        keys = pd.cut(df["horizon_hours"], bins=HORIZON_EDGES, right=False, labels=HORIZON_LABELS)
    elif by == "tercile":
        df = df.dropna(subset=["forecast_mw", "actual_mw"])
        keys = pd.qcut(df["actual_mw"], 3, labels=TERCILE_LABELS)
    else:
        raise ValueError(f"unknown grouping: {by!r}")
    return [
        compute_metrics(g, group=label.item() if isinstance(label, np.generic) else label)
        for label, g in df.groupby(keys, observed=True, sort=True)
    ]
