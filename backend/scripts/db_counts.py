"""Row counts and content checksums for the two tables. Used to prove ingest idempotency.

    python -m scripts.db_counts
"""
from sqlalchemy import text

from app.db import get_engine

QUERIES = {
    "actuals total": "SELECT COUNT(*) FROM actuals",
    "actuals WIND January": "SELECT COUNT(*) FROM actuals WHERE settlement_date BETWEEN '2026-01-01' AND '2026-01-31'",
    "actuals sum MW": "SELECT ROUND(CAST(SUM(generation_mw) AS NUMERIC), 1) FROM actuals",
    "forecasts total": "SELECT COUNT(*) FROM forecasts",
    "forecasts past-hour (horizon < 0)": "SELECT COUNT(*) FROM forecasts WHERE horizon_hours < 0",
    "forecasts distinct publishes": "SELECT COUNT(DISTINCT publish_time) FROM forecasts",
    "forecasts sum MW": "SELECT ROUND(CAST(SUM(generation_mw) AS NUMERIC), 1) FROM forecasts",
    "forecasts sum horizon_hours": "SELECT ROUND(CAST(SUM(horizon_hours) AS NUMERIC), 3) FROM forecasts",
}


def main() -> None:
    with get_engine().connect() as conn:
        for label, sql in QUERIES.items():
            print(f"{label:<36} {conn.execute(text(sql)).scalar_one()}")


if __name__ == "__main__":
    main()
