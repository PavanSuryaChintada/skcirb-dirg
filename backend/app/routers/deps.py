"""Shared request plumbing: dataset access, date-range and cut-off validation."""
from dataclasses import asdict
from datetime import date

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.core.metrics import MetricSet
from app.data import Dataset, NoData, get_dataset
from app.schemas import MetricsOut


def dataset() -> Dataset:
    try:
        return get_dataset()
    except NoData as exc:
        raise HTTPException(503, str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, "database unreachable") from exc


def cutoff(cutoff_hour: int | None) -> int:
    return get_settings().decision_cutoff_hour_utc if cutoff_hour is None else cutoff_hour


def _loaded(ds: Dataset) -> str:
    return f"Loaded delivery days: {ds.days[0]} to {ds.days[-1]}."


def days_between(ds: Dataset, frm: date | None, to: date | None) -> list[date]:
    frm = frm or ds.days[0]
    to = to or ds.days[-1]
    if frm > to:
        raise HTTPException(422, f"'from' ({frm}) is after 'to' ({to}).")
    if frm < ds.days[0] or to > ds.days[-1]:
        raise HTTPException(404, f"No data for {frm} to {to}. {_loaded(ds)}")
    return [d for d in ds.days if frm <= d <= to]


def require_day(ds: Dataset, day: date) -> None:
    if day not in ds.days:
        raise HTTPException(404, f"No data for {day}. {_loaded(ds)}")


def metrics_out(m: MetricSet) -> MetricsOut:
    return MetricsOut(**asdict(m))
