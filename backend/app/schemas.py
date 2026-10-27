"""Pydantic response models."""
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    db: Literal["connected", "unreachable"]
    rows: dict[str, int | None] = Field(
        description="Row count per table. null means the table has not been created yet."
    )
