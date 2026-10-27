import dataclasses
import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from app.core.alignment import expand_to_periods
from app.core.metrics import MetricSet, compute_metrics, error_series, group_metrics, persistence_baseline, skill_score

UTC = timezone.utc
T0 = datetime(2026, 1, 15, tzinfo=UTC)

F = [100.0, 200.0, 300.0, 400.0, 500.0]
A = [110.0, 190.0, 330.0, 380.0, 520.0]  # e = -10, 10, -30, 20, -20


def five():
    return pd.DataFrame({"start_time": [T0 + timedelta(hours=h) for h in range(5)], "forecast_mw": F, "actual_mw": A})


def january(seed=0):
    rng = np.random.default_rng(seed)
    start = [datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=h) for h in range(31 * 24)]
    actual = rng.uniform(1000, 15000, len(start))
    return pd.DataFrame(
        {
            "start_time": start,
            "forecast_mw": actual + rng.normal(0, 800, len(start)),
            "actual_mw": actual,
            "horizon_hours": np.tile(np.arange(16.5, 40.5), 31),
        }
    )


def test_error_is_forecast_minus_actual():
    assert error_series(five()).tolist() == [-10.0, 10.0, -30.0, 20.0, -20.0]


def test_hand_computed_metrics_on_a_5_row_frame_match_to_6_dp():
    m = compute_metrics(five())
    assert m.n == 5
    assert m.me_mw == pytest.approx(-6.0, abs=1e-6)  # -30 / 5
    assert m.mae_mw == pytest.approx(18.0, abs=1e-6)  # 90 / 5
    assert m.rmse_mw == pytest.approx(math.sqrt(380.0), abs=1e-6)  # sqrt(1900 / 5)
    assert m.nmae_pct == pytest.approx(100 * 18.0 / 306.0, abs=1e-6)  # mean(a) = 306
    assert m.p5_mw == pytest.approx(-28.0, abs=1e-6)  # linear: -30 + 0.2 * 10
    assert m.p50_mw == pytest.approx(-10.0, abs=1e-6)
    assert m.p95_mw == pytest.approx(18.0, abs=1e-6)  # linear: 10 + 0.8 * 10
    assert m.max_abs_error_mw == pytest.approx(30.0, abs=1e-6)
    assert m.max_abs_error_at == T0 + timedelta(hours=2)
    assert m.energy_error_mwh == pytest.approx(-30.0, abs=1e-6)  # sum(e) x 1 h


def test_perfect_forecast_gives_zero_error_and_skill_1_against_a_worse_baseline():
    df = five().assign(forecast_mw=A, persistence_mw=[a + 50 for a in A])
    m = compute_metrics(df)
    assert m.me_mw == m.mae_mw == m.rmse_mw == 0
    assert m.skill_score == 1.0
    assert m.n_skill == 5


def test_nulls_are_excluded_before_computing_and_n_is_reported():
    df = five()
    df.loc[1, "forecast_mw"] = np.nan
    df.loc[3, "actual_mw"] = np.nan
    m = compute_metrics(df)
    assert m.n == 3
    assert m.mae_mw == pytest.approx(20.0, abs=1e-6)  # rows 0, 2, 4: |-10|, |-30|, |-20|


def test_no_valid_rows_gives_none_not_zero():
    m = compute_metrics(five().assign(forecast_mw=np.nan))
    assert m.n == 0
    assert m.mae_mw is None and m.rmse_mw is None and m.me_mw is None


def test_skill_score():
    assert skill_score(5.0, 10.0) == 0.5
    assert skill_score(10.0, 0.0) is None
    assert skill_score(10.0, None) is None


def test_persistence_is_the_hourly_actual_24_hours_earlier():
    hourly_actuals = pd.DataFrame(
        {"start_time": [T0 - timedelta(days=1) + timedelta(hours=h) for h in range(48)], "actual_mw": [float(h) for h in range(48)]}
    )
    df = pd.DataFrame({"start_time": [T0 + timedelta(hours=h) for h in range(24)] + [T0 - timedelta(days=1)]})
    p = persistence_baseline(df, hourly_actuals)
    assert p.iloc[:24].tolist() == [float(h) for h in range(24)]  # 15 Jan hour h <- 14 Jan hour h
    assert pd.isna(p.iloc[24])  # 14 Jan needs 13 Jan, which is absent: missing, not 0


def test_metrics_refuse_step_expanded_data():
    p = expand_to_periods(five().drop(columns="actual_mw")).assign(actual_mw=100.0)
    with pytest.raises(ValueError):
        compute_metrics(p)
    with pytest.raises(ValueError):
        group_metrics(p, "hour")


def test_full_month_on_the_hourly_frame_is_n_744():
    assert compute_metrics(january()).n == 744


def test_group_by_hour_day_horizon_and_tercile():
    df = january()
    by_hour = group_metrics(df, "hour")
    assert [m.group for m in by_hour] == list(range(24)) and {m.n for m in by_hour} == {31}
    by_day = group_metrics(df, "day")
    assert len(by_day) == 31 and {m.n for m in by_day} == {24}
    terciles = group_metrics(df, "tercile")
    assert [m.group for m in terciles] == ["low", "medium", "high"]
    assert sum(m.n for m in terciles) == 744


def test_horizon_buckets_exclude_negative_horizons_explicitly():
    df = pd.DataFrame(
        {
            "start_time": [T0] * 6,
            "forecast_mw": [1.0] * 6,
            "actual_mw": [0.0] * 6,
            "horizon_hours": [-3.5, 2.5, 7.5, 13.5, 20.5, 40.5],
        }
    )
    buckets = group_metrics(df, "horizon")
    assert [(m.group, m.n) for m in buckets] == [("0-6h", 1), ("6-12h", 1), ("12-18h", 1), ("18-24h", 1), ("24h+", 1)]


def test_no_mape_in_the_metric_set():
    assert not any("mape" in f.name for f in dataclasses.fields(MetricSet))
