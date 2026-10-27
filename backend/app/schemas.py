"""Pydantic response models. Every metrics response carries cutoff_hour and n_observations."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Selection = Literal["decision_time", "all_vintages"]


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    db: Literal["connected", "unreachable"]
    rows: dict[str, int | None] = Field(
        description="Row count per table. null means the table has not been created yet."
    )


class MetaResponse(BaseModel):
    date_from: date
    date_to: date
    days_loaded: int
    default_date: date = Field(description="Delivery day with the largest MAE at the default cut-off")
    default_cutoff_hour: int
    candidate_cutoff_hours: list[int]
    last_ingest_at: datetime | None
    rows: dict[str, int]


class MetricsOut(BaseModel):
    group: date | int | str | None = None
    n: int
    me_mw: float | None
    mae_mw: float | None
    rmse_mw: float | None
    nmae_pct: float | None
    p5_mw: float | None
    p50_mw: float | None
    p95_mw: float | None
    max_abs_error_mw: float | None
    max_abs_error_at: datetime | None
    energy_error_mwh: float | None
    mean_actual_mw: float | None
    skill_score: float | None = Field(description="1 - RMSE / RMSE(persistence), on hours where both exist")
    n_skill: int


class MetricsResponse(BaseModel):
    selection: Selection
    frame: Literal["hourly"] = "hourly"
    cutoff_hour: int | None
    from_date: date
    to_date: date
    n_observations: int
    metrics: MetricsOut


class GroupedMetricsResponse(BaseModel):
    selection: Selection
    frame: Literal["hourly"] = "hourly"
    cutoff_hour: int | None
    from_date: date
    to_date: date
    n_observations: int
    grouped_by: str
    note: str | None = None
    groups: list[MetricsOut]


class CutoffRow(BaseModel):
    cutoff_hour: int
    newest_publish: str | None = Field(description="Publish selected most often, relative to delivery day D")
    metrics: MetricsOut = Field(description="Every hour with a decision-time forecast at this cut-off")
    metrics_common_hours: MetricsOut = Field(description="Only hours that have a forecast at every candidate cut-off")


class CutoffComparison(BaseModel):
    from_cutoff_hour: int
    to_cutoff_hour: int
    basis: Literal["common_hours"] = "common_hours"
    mae_change_mw: float | None
    rmse_change_mw: float | None


class ByCutoffResponse(BaseModel):
    selection: Selection = "decision_time"
    frame: Literal["hourly"] = "hourly"
    cutoff_hours: list[int]
    from_date: date
    to_date: date
    n_observations: int = Field(description="Hours common to every candidate cut-off")
    rows: list[CutoffRow]
    comparison: CutoffComparison


class HistogramBin(BaseModel):
    lo_mw: float
    hi_mw: float
    count: int


class DistributionResponse(BaseModel):
    selection: Selection = "decision_time"
    frame: Literal["hourly"] = "hourly"
    cutoff_hour: int
    from_date: date
    to_date: date
    n_observations: int
    bin_mw: float
    bins: list[HistogramBin]
    p5_mw: float | None
    p50_mw: float | None
    p95_mw: float | None


class ScatterPoint(BaseModel):
    start_time: datetime
    forecast_mw: float
    actual_mw: float


class ScatterResponse(BaseModel):
    selection: Selection = "decision_time"
    frame: Literal["hourly"] = "hourly"
    cutoff_hour: int
    from_date: date
    to_date: date
    n_observations: int
    points: list[ScatterPoint]


class DayPeriod(BaseModel):
    settlement_period: int
    start_time: datetime
    forecast_mw: float | None
    actual_mw: float | None
    error_mw: float | None
    abs_error_mw: float | None
    band_low_mw: float | None
    band_high_mw: float | None
    publish_time: datetime | None
    horizon_hours: float | None
    forecast_available: bool


class DayTotals(BaseModel):
    n_hours: int
    forecast_gwh: float
    actual_gwh: float
    error_gwh: float
    error_pct: float | None


class ErrorBand(BaseModel):
    p5_mw: float | None
    p95_mw: float | None
    n_observations: int
    basis: str


class DayResponse(BaseModel):
    date: date
    cutoff_hour: int
    cutoff_time: datetime
    forecast_step_expanded: bool = True
    forecast_note: str = "forecast is published hourly, held constant across both settlement periods"
    publish_times: list[datetime]
    totals: DayTotals = Field(description="Hourly frame: hours where both forecast and actual exist")
    band: ErrorBand
    periods: list[DayPeriod]
