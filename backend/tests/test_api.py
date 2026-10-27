"""API smoke tests on a tiny synthetic month in SQLite. No network."""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app import data
from app.core.periods import period_start
from app.ingest.loader import load

UTC = timezone.utc
DAYS = [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]


def _forecast_rows(day: date, publish: datetime, mw: float, last_hour: int = 23):
    rows = []
    for h in range(last_hour + 1):
        start = datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(hours=h)
        rows.append(
            {
                "start_time": start,
                "publish_time": publish,
                "settlement_date": day,
                "settlement_period": 2 * h + 1,
                "generation_mw": mw,
                "horizon_hours": (start - publish).total_seconds() / 3600,
            }
        )
    return rows


@pytest.fixture
def client(monkeypatch, tmp_path):
    url = f"sqlite:///{(tmp_path / 'api.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("STUDY_FROM", "2026-01-01")
    monkeypatch.setenv("STUDY_TO", "2026-01-03")

    actuals = [
        {"start_time": period_start(d, sp), "settlement_date": d, "settlement_period": sp, "generation_mw": 1000.0}
        for d in [date(2025, 12, 31), *DAYS]
        for sp in range(1, 49)
    ]
    forecasts = []
    for d in DAYS:
        prev = datetime.combine(d - timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        forecasts += _forecast_rows(d, prev - timedelta(hours=1, minutes=30), 1300.0, last_hour=21)  # D-2 22:30
        forecasts += _forecast_rows(d, prev + timedelta(hours=7, minutes=30), 1200.0)  # D-1 07:30
        forecasts += _forecast_rows(d, prev + timedelta(hours=9, minutes=30), 1100.0)  # D-1 09:30
    load(create_engine(url), actuals, forecasts)

    data.reset_cache()
    from app.main import create_app

    yield TestClient(create_app())
    data.reset_cache()


def test_meta_reports_range_and_rows(client):
    body = client.get("/api/meta").json()
    assert (body["date_from"], body["date_to"], body["days_loaded"]) == ("2026-01-01", "2026-01-03", 3)
    assert body["candidate_cutoff_hours"] == [2, 4, 7, 9, 11]
    assert body["last_ingest_at"] is not None


def test_day_is_48_step_expanded_periods_from_the_decision_time_publish(client):
    body = client.get("/api/day/2026-01-02", params={"cutoff_hour": 9}).json()
    assert body["forecast_step_expanded"] is True
    assert "held constant across both settlement periods" in body["forecast_note"]
    assert len(body["periods"]) == 48
    assert {p["forecast_mw"] for p in body["periods"]} == {1200.0}  # 07:30 publish, not 09:30
    assert body["publish_times"] == ["2026-01-01T07:30:00Z"]
    assert body["totals"]["n_hours"] == 24
    assert body["totals"]["error_gwh"] == pytest.approx(24 * 200 / 1000)


def test_dates_outside_the_loaded_range_get_a_useful_404(client):
    r = client.get("/api/day/2026-02-15")
    assert r.status_code == 404
    assert "Loaded delivery days: 2026-01-01 to 2026-01-03" in r.json()["detail"]
    assert client.get("/api/metrics", params={"from": "2025-12-01"}).status_code == 404
    assert client.get("/api/metrics", params={"from": "2026-01-03", "to": "2026-01-01"}).status_code == 422


def test_metrics_carry_cutoff_and_n_and_run_on_the_hourly_frame(client):
    body = client.get("/api/metrics", params={"cutoff_hour": 11}).json()
    assert body["cutoff_hour"] == 11 and body["frame"] == "hourly"
    assert body["n_observations"] == 72  # 3 days x 24 hours, not 144
    assert body["metrics"]["mae_mw"] == pytest.approx(100.0)  # 09:30 publish: 1100 vs 1000


def test_by_cutoff_compares_on_common_hours(client):
    body = client.get("/api/metrics/by-cutoff").json()
    rows = {r["cutoff_hour"]: r for r in body["rows"]}
    assert rows[2]["metrics"]["n"] == 66  # 22:00 and 23:00 missing at 02:00 (D-2 publish stops at 21:00)
    assert rows[9]["metrics"]["n"] == 72
    assert body["n_observations"] == 66
    assert rows[9]["newest_publish"] == "D-1 07:30" and rows[11]["newest_publish"] == "D-1 09:30"
    assert body["comparison"]["mae_change_mw"] == pytest.approx(-100.0)


def test_csv_has_48_rows_and_blank_cells_for_missing_forecasts(client):
    r = client.get("/api/export/day/2026-01-02.csv", params={"cutoff_hour": 2})
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("settlement_period,clock_time_utc")
    assert len(lines) == 49
    sp45 = lines[45].split(",")
    assert sp45[0] == "45" and sp45[4] == "" and sp45[6] == ""  # forecast and error blank, not 0
