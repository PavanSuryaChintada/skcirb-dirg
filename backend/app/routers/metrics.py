"""Accuracy metrics. All figures come from the hourly frame (n = 744 for January)."""
from datetime import date

from fastapi import APIRouter, Query

from app.analysis import CANDIDATE_CUTOFFS, decision_frame, newest_publish_label, vintage_frame
from app.core.metrics import compare, compute_metrics, error_histogram, group_metrics
from app.routers.deps import cutoff, dataset, days_between, metrics_out
from app.schemas import (
    ByCutoffResponse,
    CutoffComparison,
    CutoffRow,
    DistributionResponse,
    GroupedMetricsResponse,
    MetricsResponse,
    ScatterPoint,
    ScatterResponse,
)

router = APIRouter(prefix="/api", tags=["metrics"])

FROM = Query(None, alias="from", description="First delivery day (default: first loaded)")
TO = Query(None, alias="to", description="Last delivery day, inclusive (default: last loaded)")
CUTOFF = Query(None, ge=0, le=23, description="Hour (UTC) on D-1; default from DECISION_CUTOFF_HOUR_UTC")


@router.get("/metrics", response_model=MetricsResponse)
def metrics(frm: date | None = FROM, to: date | None = TO, cutoff_hour: int | None = CUTOFF):
    """Full metric set for the window, decision-time selection."""
    ds, c = dataset(), cutoff(cutoff_hour)
    days = days_between(ds, frm, to)
    m = compute_metrics(decision_frame(ds, c, days))
    return MetricsResponse(
        selection="decision_time", cutoff_hour=c, from_date=days[0], to_date=days[-1], n_observations=m.n, metrics=metrics_out(m)
    )


def _grouped(by: str, frm, to, cutoff_hour) -> GroupedMetricsResponse:
    ds, c = dataset(), cutoff(cutoff_hour)
    days = days_between(ds, frm, to)
    groups = group_metrics(decision_frame(ds, c, days), by)
    return GroupedMetricsResponse(
        selection="decision_time",
        cutoff_hour=c,
        from_date=days[0],
        to_date=days[-1],
        n_observations=sum(g.n for g in groups),
        grouped_by=by,
        groups=[metrics_out(g) for g in groups],
    )


@router.get("/metrics/by-hour", response_model=GroupedMetricsResponse)
def by_hour(frm: date | None = FROM, to: date | None = TO, cutoff_hour: int | None = CUTOFF):
    """Grouped by hour of day 00-23 (hour H = settlement periods 2H+1 and 2H+2)."""
    return _grouped("hour", frm, to, cutoff_hour)


@router.get("/metrics/by-day", response_model=GroupedMetricsResponse)
def by_day(frm: date | None = FROM, to: date | None = TO, cutoff_hour: int | None = CUTOFF):
    return _grouped("day", frm, to, cutoff_hour)


@router.get("/metrics/by-tercile", response_model=GroupedMetricsResponse)
def by_tercile(frm: date | None = FROM, to: date | None = TO, cutoff_hour: int | None = CUTOFF):
    """Grouped by actual wind level: low / medium / high tercile of hourly actual MW."""
    return _grouped("tercile", frm, to, cutoff_hour)


@router.get("/metrics/by-horizon", response_model=GroupedMetricsResponse)
def by_horizon(frm: date | None = FROM, to: date | None = TO):
    """All forecast vintages (no cut-off), bucketed by lead time. Not a headline metric."""
    ds = dataset()
    days = days_between(ds, frm, to)
    groups = group_metrics(vintage_frame(ds, days), "horizon")
    return GroupedMetricsResponse(
        selection="all_vintages",
        cutoff_hour=None,
        from_date=days[0],
        to_date=days[-1],
        n_observations=sum(g.n for g in groups),
        grouped_by="horizon",
        note="all forecast vintages: every stored publish with horizon >= 0, no cut-off applied",
        groups=[metrics_out(g) for g in groups],
    )


@router.get("/metrics/by-cutoff", response_model=ByCutoffResponse)
def by_cutoff(frm: date | None = FROM, to: date | None = TO):
    """Full metric set at each candidate cut-off; each makes a different publish the newest available."""
    ds = dataset()
    days = days_between(ds, frm, to)
    frames = {c: decision_frame(ds, c, days) for c in CANDIDATE_CUTOFFS}

    # early cut-offs miss some hours (A19); compare like with like on the hours every cut-off has
    valid = [set(f.dropna(subset=["forecast_mw", "actual_mw"])["start_time"]) for f in frames.values()]
    common = set.intersection(*valid)

    rows, common_sets = [], {}
    for c, f in frames.items():
        common_sets[c] = compute_metrics(f[f["start_time"].isin(common)])
        rows.append(
            CutoffRow(
                cutoff_hour=c,
                newest_publish=newest_publish_label(f),
                metrics=metrics_out(compute_metrics(f)),
                metrics_common_hours=metrics_out(common_sets[c]),
            )
        )
    return ByCutoffResponse(
        cutoff_hours=list(CANDIDATE_CUTOFFS),
        from_date=days[0],
        to_date=days[-1],
        n_observations=len(common),
        rows=rows,
        comparison=CutoffComparison(from_cutoff_hour=9, to_cutoff_hour=11, **compare(common_sets[9], common_sets[11])),
    )


@router.get("/distribution", response_model=DistributionResponse)
def distribution(
    frm: date | None = FROM,
    to: date | None = TO,
    cutoff_hour: int | None = CUTOFF,
    bin_mw: float = Query(500.0, gt=0, le=5000),
):
    """Histogram of hourly error plus P5/P50/P95."""
    ds, c = dataset(), cutoff(cutoff_hour)
    days = days_between(ds, frm, to)
    frame = decision_frame(ds, c, days)
    m = compute_metrics(frame)
    return DistributionResponse(
        cutoff_hour=c,
        from_date=days[0],
        to_date=days[-1],
        n_observations=m.n,
        bin_mw=bin_mw,
        bins=error_histogram(frame, bin_mw),
        p5_mw=m.p5_mw,
        p50_mw=m.p50_mw,
        p95_mw=m.p95_mw,
    )


@router.get("/scatter", response_model=ScatterResponse)
def scatter(frm: date | None = FROM, to: date | None = TO, cutoff_hour: int | None = CUTOFF):
    """Hourly forecast/actual pairs for the forecast-vs-actual scatter."""
    ds, c = dataset(), cutoff(cutoff_hour)
    days = days_between(ds, frm, to)
    valid = decision_frame(ds, c, days).dropna(subset=["forecast_mw", "actual_mw"])
    return ScatterResponse(
        cutoff_hour=c,
        from_date=days[0],
        to_date=days[-1],
        n_observations=len(valid),
        points=[
            ScatterPoint(start_time=r.start_time.to_pydatetime(), forecast_mw=r.forecast_mw, actual_mw=r.actual_mw)
            for r in valid.itertuples()
        ],
    )
