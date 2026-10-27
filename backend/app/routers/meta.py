"""Service metadata: /api/health now, /api/meta once data is loaded."""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.analysis import CANDIDATE_CUTOFFS, decision_frame
from app.config import get_settings
from app.core.metrics import group_metrics
from app.db import get_engine
from app.routers.deps import dataset
from app.schemas import HealthResponse, MetaResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["meta"])

TABLES = ("actuals", "forecasts")


@router.get("/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
def health():
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            existing = set(inspect(conn).get_table_names())
            # table names come from the constant above, never from the request
            rows = {
                t: conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar_one() if t in existing else None
                for t in TABLES
            }
    except SQLAlchemyError as exc:
        # class name only: driver messages can carry host and user details
        log.warning("health check: database unreachable (%s)", type(exc).__name__)
        body = HealthResponse(status="error", db="unreachable", rows={t: None for t in TABLES})
        return JSONResponse(status_code=503, content=body.model_dump())
    return HealthResponse(status="ok", db="connected", rows=rows)


@router.get("/meta", response_model=MetaResponse)
def meta():
    """Loaded date range, cut-off config, last ingest, row counts, and a default day worth looking at."""
    ds = dataset()
    default_cutoff = get_settings().decision_cutoff_hour_utc
    by_day = group_metrics(decision_frame(ds, default_cutoff, ds.days), "day")
    worst = max((m for m in by_day if m.mae_mw is not None), key=lambda m: m.mae_mw, default=None)
    return MetaResponse(
        date_from=ds.days[0],
        date_to=ds.days[-1],
        days_loaded=len(ds.days),
        default_date=worst.group if worst else ds.days[0],
        default_cutoff_hour=default_cutoff,
        candidate_cutoff_hours=list(CANDIDATE_CUTOFFS),
        last_ingest_at=ds.last_ingest_at,
        rows={"actuals": len(ds.actuals), "forecasts": len(ds.forecasts)},
    )
