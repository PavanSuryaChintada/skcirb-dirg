"""Hand-check MAE and RMSE for one delivery day against metrics.py.

    python -m scripts.hand_verify 2026-01-12 [cutoff_hour]

The manual side shares no logic with the app: raw SQL DISTINCT ON for selection,
explicit pairing of half-hours, and plain arithmetic.
"""
import math
import sys
from datetime import date, datetime, time, timedelta, timezone

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.alignment import hourly_pairs, to_hourly
from app.core.metrics import compute_metrics
from app.core.selection import decision_time_forecasts
from app.db import get_engine

UTC = timezone.utc


def main() -> None:
    day = date.fromisoformat(sys.argv[1])
    cutoff_hour = int(sys.argv[2]) if len(sys.argv) > 2 else 9
    day_start = datetime.combine(day, time(0), tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    cutoff = datetime.combine(day - timedelta(days=1), time(cutoff_hour), tzinfo=UTC)

    engine = get_engine()
    with engine.connect() as conn:
        forecasts = conn.execute(
            text(
                """SELECT DISTINCT ON (start_time) start_time, publish_time, generation_mw
                   FROM forecasts
                   WHERE start_time >= :a AND start_time < :b AND publish_time <= :cutoff AND horizon_hours >= 0
                   ORDER BY start_time, publish_time DESC"""
            ),
            {"a": day_start, "b": day_end, "cutoff": cutoff},
        ).all()
        actuals = conn.execute(
            text("SELECT start_time, generation_mw FROM actuals WHERE start_time >= :a AND start_time < :b ORDER BY start_time"),
            {"a": day_start, "b": day_end},
        ).all()

    # --- by hand ---
    half = {r.start_time: r.generation_mw for r in actuals}
    errors = []
    print(f"{day} cut-off {cutoff:%Y-%m-%d %H:%M}Z   hour | forecast | actual (mean of 2 half-hours) | error")
    for r in forecasts:
        a1, a2 = half.get(r.start_time), half.get(r.start_time + timedelta(minutes=30))
        if a1 is None or a2 is None:
            continue
        actual = (a1 + a2) / 2
        e = r.generation_mw - actual
        errors.append(e)
        print(f"  {r.start_time:%H:%M}  {r.generation_mw:8.1f}  ({a1:.0f} + {a2:.0f}) / 2 = {actual:8.1f}  {e:+9.1f}   [published {r.publish_time:%m-%d %H:%M}]")
    n = len(errors)
    mae_hand = sum(abs(e) for e in errors) / n
    rmse_hand = math.sqrt(sum(e * e for e in errors) / n)

    # --- through the app ---
    with Session(engine) as session:
        selected = decision_time_forecasts(day, cutoff_hour, session)
    hourly_fc = pd.DataFrame([{"start_time": r.start_time, "forecast_mw": r.forecast_mw} for r in selected])
    m = compute_metrics(hourly_pairs(hourly_fc, to_hourly(pd.DataFrame(actuals, columns=["start_time", "generation_mw"]))))

    print()
    print(f"            n      MAE (MW)          RMSE (MW)")
    print(f"by hand    {n:3d}  {mae_hand:16.6f}  {rmse_hand:16.6f}")
    print(f"metrics.py {m.n:3d}  {m.mae_mw:16.6f}  {m.rmse_mw:16.6f}")
    match = n == m.n and round(mae_hand, 6) == round(m.mae_mw, 6) and round(rmse_hand, 6) == round(m.rmse_mw, 6)
    print("MATCH to 6 dp" if match else "MISMATCH")
    sys.exit(0 if match else 1)


if __name__ == "__main__":
    main()
