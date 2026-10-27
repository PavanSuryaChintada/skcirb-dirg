"""One delivery day: the 48-period display view (step-expanded) plus hourly-frame totals."""
from datetime import date

import pandas as pd
from fastapi import APIRouter, Query

from app.analysis import decision_frame
from app.core.alignment import expand_to_periods
from app.core.metrics import MetricSet, compute_metrics, display_period_errors, energy_totals, error_band
from app.core.selection import cutoff_for
from app.data import Dataset
from app.routers.deps import cutoff, dataset, require_day
from app.schemas import DayPeriod, DayResponse, DayTotals, ErrorBand

router = APIRouter(prefix="/api", tags=["day"])


def _none(value):
    return None if pd.isna(value) else value


def build_day(ds: Dataset, day: date, cutoff_hour: int) -> DayResponse:
    require_day(ds, day)
    hourly = decision_frame(ds, cutoff_hour, [day])

    # the band comes from every other January day, so the day is not judged by its own errors
    others = [d for d in ds.days if d != day]
    history = compute_metrics(decision_frame(ds, cutoff_hour, others)) if others else MetricSet(n=0)

    periods = expand_to_periods(hourly[["start_time", "forecast_mw", "publish_time", "horizon_hours"]])
    half_hours = ds.actuals.loc[ds.actuals["settlement_date"] == day, ["start_time", "generation_mw"]]
    periods = periods.merge(half_hours.rename(columns={"generation_mw": "actual_mw"}), on="start_time", how="left")
    periods["error_mw"], periods["abs_error_mw"] = display_period_errors(periods)
    periods["band_low_mw"], periods["band_high_mw"] = error_band(periods["forecast_mw"], history.p5_mw, history.p95_mw)

    return DayResponse(
        date=day,
        cutoff_hour=cutoff_hour,
        cutoff_time=cutoff_for(day, cutoff_hour),
        publish_times=sorted({p.to_pydatetime() for p in hourly["publish_time"].dropna()}),
        totals=DayTotals(**energy_totals(hourly)),
        band=ErrorBand(
            p5_mw=history.p5_mw,
            p95_mw=history.p95_mw,
            n_observations=history.n,
            basis="P5-P95 of hourly error on every other loaded day, same cut-off",
        ),
        periods=[
            DayPeriod(
                settlement_period=int(r.settlement_period),
                start_time=r.start_time.to_pydatetime(),
                forecast_mw=_none(r.forecast_mw),
                actual_mw=_none(r.actual_mw),
                error_mw=_none(r.error_mw),
                abs_error_mw=_none(r.abs_error_mw),
                band_low_mw=_none(r.band_low_mw),
                band_high_mw=_none(r.band_high_mw),
                publish_time=None if pd.isna(r.publish_time) else r.publish_time.to_pydatetime(),
                horizon_hours=_none(r.horizon_hours),
                forecast_available=not pd.isna(r.forecast_mw),
            )
            for r in periods.itertuples()
        ],
    )


@router.get("/day/{day}", response_model=DayResponse)
def day_view(day: date, cutoff_hour: int | None = Query(None, ge=0, le=23)):
    """48 settlement periods. The forecast is step-expanded from hourly and flagged as such."""
    return build_day(dataset(), day, cutoff(cutoff_hour))
