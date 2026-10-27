import io
import json
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from app.ingest.elexon_client import ElexonError, get_json
from app.ingest.loader import load, normalise_actuals, normalise_forecasts, with_db_retry

FIXTURES = Path(__file__).parent / "fixtures"
UTC = timezone.utc
LOWER = datetime(2026, 1, 15, tzinfo=UTC)
UPPER = datetime(2026, 1, 16, tzinfo=UTC)


def fixture(name):
    return json.loads((FIXTURES / name).read_bytes())


def test_actuals_keep_wind_only_and_drop_the_row_published_at_the_exclusive_bound():
    raw = fixture("fuelhh_stream_publish_2026-01-15.json")
    rows, stats = normalise_actuals(raw, LOWER, UPPER)
    # fixture holds 49 WIND rows: 14 Jan SP48 .. 15 Jan SP48; the last is published at exactly UPPER
    assert stats["other_fuel_skipped"] == 980 - 49
    assert stats["outside_window"] == 1
    assert len(rows) == 48
    assert max(r["start_time"] for r in rows) == datetime(2026, 1, 15, 23, 0, tzinfo=UTC)


def test_negative_mw_is_rejected_on_wind_rows_only():
    base = {"publishTime": "2026-01-15T10:30:00Z", "startTime": "2026-01-15T10:00:00Z",
            "settlementDate": "2026-01-15", "settlementPeriod": 21}
    raw = [
        {**base, "fuelType": "WIND", "generation": -5},
        {**base, "fuelType": "PS", "generation": -712},  # pumping: valid, just not wind
        {**base, "fuelType": "INTIRL", "generation": -400},  # export: valid, just not wind
    ]
    rows, stats = normalise_actuals(raw, LOWER, UPPER)
    assert rows == []
    assert stats["rejected_negative_mw"] == 1
    assert stats["other_fuel_skipped"] == 2


def test_forecasts_keep_every_row_including_past_hours_with_horizon_stored():
    raw = fixture("windfor_stream_publish_2026-01-15.json")
    rows, stats = normalise_forecasts(raw, LOWER, UPPER)
    assert len(rows) == 584
    past = [r for r in rows if r["horizon_hours"] < 0]
    assert past and stats["past_hour_rows"] == len(past)
    horizons = [r["horizon_hours"] for r in rows]
    assert min(horizons) == -25.5 and max(horizons) == 66.5  # A16
    assert {r["settlement_period"] % 2 for r in rows} == {1}  # hourly -> first SP of each hour


def test_upsert_is_idempotent():
    engine = create_engine("sqlite://")
    actuals, _ = normalise_actuals(fixture("fuelhh_stream_publish_2026-01-15.json"), LOWER, UPPER)
    forecasts, _ = normalise_forecasts(fixture("windfor_stream_publish_2026-01-15.json"), LOWER, UPPER)
    _, first = load(engine, actuals, forecasts)
    before, second = load(engine, actuals, forecasts)
    assert first == {"actuals": 48, "forecasts": 584}
    assert before == second == first


def test_dropped_database_connection_is_retried():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise OperationalError("INSERT ...", {}, ConnectionResetError("eof"))
        return "loaded"

    assert with_db_retry(flaky, log=lambda m: None, sleep=lambda s: None) == "loaded"
    assert len(calls) == 3


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_client_retries_5xx_then_succeeds():
    calls = []

    def opener(url, timeout):
        calls.append(url)
        if len(calls) < 3:
            raise urllib.error.HTTPError(url, 503, "busy", {}, None)
        return FakeResponse(b"[]")

    assert get_json("u", opener=opener, sleep=lambda s: None, log=lambda m: None) == []
    assert len(calls) == 3


def test_client_does_not_retry_4xx():
    calls = []

    def opener(url, timeout):
        calls.append(url)
        raise urllib.error.HTTPError(url, 400, "bad", {}, None)

    with pytest.raises(ElexonError):
        get_json("u", opener=opener, sleep=lambda s: None, log=lambda m: None)
    assert len(calls) == 1
