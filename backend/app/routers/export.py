"""CSV for Screen 3. Missing values are blank cells, never 0."""
import csv
import io
from datetime import date

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.routers.day import build_day
from app.routers.deps import cutoff, dataset

router = APIRouter(prefix="/api", tags=["export"])

HEADER = [
    "settlement_period",
    "clock_time_utc",
    "publish_time_utc",
    "horizon_h",
    "forecast_mw",
    "actual_mw",
    "error_mw",
    "abs_error_mw",
    "forecast_step_expanded",
]


def _cell(value, fmt="{:.1f}"):
    return "" if value is None else fmt.format(value)


@router.get("/export/day/{day}.csv", response_class=Response)
def export_day(day: date, cutoff_hour: int | None = Query(None, ge=0, le=23)):
    c = cutoff(cutoff_hour)
    view = build_day(dataset(), day, c)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(HEADER)
    for p in view.periods:
        writer.writerow(
            [
                p.settlement_period,
                p.start_time.strftime("%Y-%m-%d %H:%M"),
                p.publish_time.strftime("%Y-%m-%d %H:%M") if p.publish_time else "",
                _cell(p.horizon_hours),
                _cell(p.forecast_mw),
                _cell(p.actual_mw),
                _cell(p.error_mw),
                _cell(p.abs_error_mw),
                "yes",  # forecast is hourly, held constant across both settlement periods
            ]
        )
    filename = f"wind_{day}_cutoff{c:02d}.csv"
    return Response(
        buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
