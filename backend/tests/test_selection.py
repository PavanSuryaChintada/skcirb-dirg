import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.selection import cutoff_for, decision_time_forecasts, select_for_day
from app.ingest.loader import load, normalise_forecasts

UTC = timezone.utc
FIXTURES = Path(__file__).parent / "fixtures"
D = date(2026, 1, 16)


def ts(day, hh, mm=0):
    return datetime(2026, 1, day, hh, mm, tzinfo=UTC)


def frame(rows):
    """rows of (start_time, publish_time, mw) -> the forecasts frame selection works on"""
    return pd.DataFrame(
        [
            {"start_time": s, "publish_time": p, "generation_mw": mw, "horizon_hours": (s - p).total_seconds() / 3600}
            for s, p, mw in rows
        ],
        columns=["start_time", "publish_time", "generation_mw", "horizon_hours"],
    )


THREE_PUBLISHES = [(ts(16, 10), ts(15, 6), 100.0), (ts(16, 10), ts(15, 8), 200.0), (ts(16, 10), ts(15, 10), 300.0)]


def test_cutoff_is_d_minus_1_at_the_cutoff_hour():
    assert cutoff_for(D, 9) == ts(15, 9)
    with pytest.raises(ValueError):
        cutoff_for(D, 24)


def test_latest_publish_at_or_before_cutoff_is_selected():
    row = select_for_day(frame(THREE_PUBLISHES), D, 9).iloc[10]
    assert row.forecast_mw == 200.0
    assert row.publish_time == ts(15, 8)


def test_publish_after_cutoff_is_never_selected_even_when_it_is_the_only_one():
    row = select_for_day(frame([(ts(16, 10), ts(15, 10), 300.0)]), D, 9).iloc[10]
    assert pd.isna(row.forecast_mw)
    assert not row.forecast_available


def test_hour_without_a_pre_cutoff_forecast_is_missing_not_zero_not_the_next_publish():
    row = select_for_day(frame([(ts(16, 10), ts(15, 10), 300.0)]), D, 9).iloc[10]
    assert pd.isna(row.forecast_mw) and row.forecast_mw != 0
    assert pd.isna(row.publish_time)  # no fallback to the 10:00 publish


def test_changing_cutoff_hour_changes_the_selected_row():
    f = frame(THREE_PUBLISHES)
    assert select_for_day(f, D, 7).iloc[10].publish_time == ts(15, 6)
    assert select_for_day(f, D, 9).iloc[10].publish_time == ts(15, 8)
    assert select_for_day(f, D, 11).iloc[10].publish_time == ts(15, 10)


def test_row_with_negative_horizon_is_never_selected():
    # the explicit horizon_hours >= 0 filter must hold even for a row that would pass the cut-off
    f = frame([(ts(16, 10), ts(15, 8), 200.0)])
    f.loc[0, "horizon_hours"] = -1.0
    assert pd.isna(select_for_day(f, D, 9).iloc[10].forecast_mw)


def test_always_24_hourly_rows_in_order():
    r = select_for_day(frame([]), D, 9)
    assert len(r) == 24
    assert list(r.start_time) == [ts(16, h) for h in range(24)]
    assert r.forecast_mw.isna().all()


# --- real cases from the Phase 0 recon, using the WINDFOR fixture (publishes from 2026-01-15) ---


@pytest.fixture(scope="module")
def windfor_rows():
    raw = json.loads((FIXTURES / "windfor_stream_publish_2026-01-15.json").read_bytes())
    rows, _ = normalise_forecasts(raw, ts(15, 0), ts(16, 0))
    return rows


@pytest.mark.parametrize(
    "cutoff_hour, expected_publish",
    [
        (11, ts(15, 9, 30)),
        (12, ts(15, 9, 30)),  # the telling case: an on-time 11:30 publish would have passed 12:00
        (13, ts(15, 12, 25)),
    ],
)
def test_15_jan_late_publish_is_excluded_until_it_actually_appeared(windfor_rows, cutoff_hour, expected_publish):
    """The 11:30 WINDFOR slot on 2026-01-15 was published at 12:25 (ASSUMPTIONS A11, A15)."""
    r = select_for_day(pd.DataFrame(windfor_rows), D, cutoff_hour)
    assert r.forecast_available.all()
    assert (r.publish_time == expected_publish).all()


def test_0100_cutoff_leaves_2200_and_2300_as_missing_never_zero(windfor_rows):
    # D = 17 Jan. At 01:00 on 16 Jan the newest publish is 15 Jan 22:30, which stops at 17 Jan 21:00 (A16, A19)
    r = select_for_day(pd.DataFrame(windfor_rows), date(2026, 1, 17), 1)
    assert r.iloc[:22].forecast_available.all()
    assert (r.iloc[:22].publish_time == ts(15, 22, 30)).all()
    assert r.iloc[22:].forecast_mw.isna().all()
    assert not (r.forecast_mw == 0).any()


def test_db_selection_returns_none_for_missing_hours(windfor_rows, tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'sel.db').as_posix()}")
    load(engine, [], windfor_rows)
    with Session(engine) as session:
        rows = decision_time_forecasts(date(2026, 1, 17), 1, session)
    assert len(rows) == 24
    assert all(r.forecast_available for r in rows[:22])
    assert [r.forecast_mw for r in rows[22:]] == [None, None]
    assert rows[22].publish_time is None and rows[22].horizon_hours is None


def test_db_selection_matches_the_pure_function(windfor_rows, tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'sel.db').as_posix()}")
    load(engine, [], windfor_rows)
    with Session(engine) as session:
        rows = decision_time_forecasts(D, 12, session)
    pure = select_for_day(pd.DataFrame(windfor_rows), D, 12)
    assert [r.forecast_mw for r in rows] == pure.forecast_mw.tolist()
    assert all(r.publish_time == ts(15, 9, 30) for r in rows)
