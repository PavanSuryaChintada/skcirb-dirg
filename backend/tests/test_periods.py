from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.periods import is_gmt_day, period_start, require_gmt_days, settlement_date, settlement_period

UTC = timezone.utc


def test_midnight_is_sp1_and_2330_is_sp48():
    assert settlement_period(datetime(2026, 1, 15, 0, 0, tzinfo=UTC)) == 1
    assert settlement_period(datetime(2026, 1, 15, 23, 30, tzinfo=UTC)) == 48


def test_round_trip_holds_for_all_48_periods_on_every_january_day():
    for day in range(1, 32):
        d = date(2026, 1, day)
        for sp in range(1, 49):
            ts = period_start(d, sp)
            assert (settlement_date(ts), settlement_period(ts)) == (d, sp)


def test_whole_fetch_window_is_on_gmt():
    # 2025-12-30 .. 2026-02-04 covers every startTime the ingest can see
    require_gmt_days(date(2025, 12, 30), date(2026, 2, 4))


@pytest.mark.parametrize(
    "d",
    [
        date(2026, 3, 29),  # spring forward, 46 periods
        date(2026, 7, 1),  # BST, local != UTC
        date(2026, 10, 25),  # fall back, 50 periods
    ],
)
def test_non_gmt_days_fail_loudly(d):
    assert not is_gmt_day(d)
    with pytest.raises(ValueError):
        settlement_period(datetime(d.year, d.month, d.day, 12, tzinfo=UTC))


def test_days_either_side_of_the_clock_changes_are_gmt():
    assert is_gmt_day(date(2026, 3, 28))
    assert is_gmt_day(date(2026, 10, 26))


def test_naive_and_off_boundary_timestamps_are_refused():
    with pytest.raises(ValueError):
        settlement_period(datetime(2026, 1, 15, 10, 0))
    with pytest.raises(ValueError):
        settlement_period(datetime(2026, 1, 15, 10, 15, tzinfo=UTC))
    with pytest.raises(ValueError):
        period_start(date(2026, 1, 15), 49)
    assert settlement_period(datetime(2026, 1, 15, 10, 0, tzinfo=UTC) + timedelta(minutes=30)) == 22
