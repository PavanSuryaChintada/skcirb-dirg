"""ORM tables. Mirrors SPEC-2 §3.2."""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Double, Index, Integer, SmallInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Actual(Base):
    """FUELHH half-hourly outturn. fuelType WIND only."""

    __tablename__ = "actuals"

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    settlement_date: Mapped[date] = mapped_column(Date, nullable=False)
    settlement_period: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    generation_mw: Mapped[float] = mapped_column(Double, nullable=False)


class Forecast(Base):
    """WINDFOR hourly forecasts, every vintage as published.

    Includes past-hour rows (horizon_hours < 0). They are stored, never used:
    analytics filter them out with an explicit horizon_hours >= 0.
    """

    __tablename__ = "forecasts"

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    publish_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    settlement_date: Mapped[date] = mapped_column(Date, nullable=False)
    settlement_period: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    generation_mw: Mapped[float] = mapped_column(Double, nullable=False)
    horizon_hours: Mapped[float] = mapped_column(Double, nullable=False)


class IngestRun(Base):
    """One row per successful ingest, so /api/meta can say when data was last loaded."""

    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actuals_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    forecasts_rows: Mapped[int] = mapped_column(Integer, nullable=False)


Index("idx_fc_start_publish", Forecast.start_time, Forecast.publish_time.desc())
Index("idx_fc_date", Forecast.settlement_date)
Index("idx_ac_date", Actual.settlement_date)
