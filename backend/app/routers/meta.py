"""Service metadata: /api/health now, /api/meta once data is loaded."""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_engine
from app.schemas import HealthResponse

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
