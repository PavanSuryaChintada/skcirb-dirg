"""Settlement period <-> timestamp conversion.

Only GMT days are supported: there UTC == UK local time and every day has exactly
48 periods. BST days (local = UTC+1) and the two clock-change days (46 and 50
periods) raise instead of returning a wrong answer. January sits entirely on GMT.
"""
from datetime import date, datetime, time, timedelta, timezone

PERIOD = timedelta(minutes=30)
PERIODS_PER_DAY = 48


def _last_sunday(year: int, month: int) -> date:
    last_day = date(year, month + 1, 1) - timedelta(days=1)
    return last_day - timedelta(days=(last_day.weekday() - 6) % 7)


def is_gmt_day(d: date) -> bool:
    """True when the whole UK day is on GMT. Clocks change on the last Sunday of March and October."""
    return d < _last_sunday(d.year, 3) or d > _last_sunday(d.year, 10)


def require_gmt_days(start: date, end: date) -> None:
    """Fail loudly if any day in [start, end] is not a 48-period GMT day."""
    d = start
    while d <= end:
        if not is_gmt_day(d):
            raise ValueError(f"{d} is not a 48-period GMT day (BST or clock change); not supported")
        d += timedelta(days=1)


def _utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        raise ValueError(f"timestamp must be timezone-aware: {ts!r}")
    return ts.astimezone(timezone.utc)


def settlement_date(ts: datetime) -> date:
    d = _utc(ts).date()
    require_gmt_days(d, d)
    return d


def settlement_period(ts: datetime) -> int:
    """1-48 for the half hour starting at ts."""
    utc = _utc(ts)
    if utc.minute not in (0, 30) or utc.second or utc.microsecond:
        raise ValueError(f"not a settlement period boundary: {ts.isoformat()}")
    d = settlement_date(utc)
    return int((utc - datetime.combine(d, time(0), tzinfo=timezone.utc)) / PERIOD) + 1


def period_start(d: date, sp: int) -> datetime:
    require_gmt_days(d, d)
    if not 1 <= sp <= PERIODS_PER_DAY:
        raise ValueError(f"settlement period out of range: {sp}")
    return datetime.combine(d, time(0), tzinfo=timezone.utc) + (sp - 1) * PERIOD
