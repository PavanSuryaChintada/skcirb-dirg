from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from app.core.alignment import expand_to_periods, hourly_pairs, to_hourly

UTC = timezone.utc
DAY = datetime(2026, 1, 16, tzinfo=UTC)


def half_hourly(values):
    return pd.DataFrame({"start_time": [DAY + timedelta(minutes=30 * i) for i in range(48)], "generation_mw": values})


def hourly_forecast(values):
    return pd.DataFrame({"start_time": [DAY + timedelta(hours=h) for h in range(len(values))], "forecast_mw": values})


def test_to_hourly_averages_the_two_half_hours_of_each_hour():
    h = to_hourly(half_hourly([float(i) for i in range(48)]))
    assert len(h) == 24
    assert h.actual_mw.tolist() == [2 * i + 0.5 for i in range(24)]  # mean(2i, 2i+1)
    assert (h.start_time.dt.minute == 0).all()


def test_hour_with_one_half_hour_missing_is_missing_not_the_remaining_half():
    h = to_hourly(half_hourly([float(i) for i in range(48)]).drop(index=47))
    assert len(h) == 24
    assert pd.isna(h.iloc[23].actual_mw)


def test_expand_gives_48_rows_with_each_hourly_value_on_both_of_its_periods():
    p = expand_to_periods(hourly_forecast([1000.0 + h for h in range(24)]))
    assert len(p) == 48
    assert p.settlement_period.tolist() == list(range(1, 49))
    assert p.forecast_mw.tolist() == [1000.0 + i // 2 for i in range(48)]
    assert p.step_expanded.all()


def test_missing_hourly_forecast_expands_to_two_missing_periods_never_zero():
    p = expand_to_periods(hourly_forecast([500.0] * 22 + [np.nan, np.nan]))
    assert p.iloc[44:].forecast_mw.isna().all()
    assert not (p.forecast_mw == 0).any()


def test_hours_absent_from_the_input_still_give_48_periods_with_gaps():
    p = expand_to_periods(hourly_forecast([500.0] * 22))
    assert len(p) == 48
    assert p.iloc[44:].forecast_mw.isna().all()


def test_hourly_pairs_joins_forecast_and_actual_on_the_hour():
    actual = to_hourly(half_hourly([100.0] * 48))
    pairs = hourly_pairs(hourly_forecast([110.0] * 24), actual)
    assert len(pairs) == 24
    assert pairs.forecast_mw.tolist() == [110.0] * 24
    assert pairs.actual_mw.tolist() == [100.0] * 24
    assert "step_expanded" not in pairs.columns
