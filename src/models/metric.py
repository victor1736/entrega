"""Modelo de métricas agregadas por ventana horaria."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Metric(BaseModel):
    """Métricas calculadas en tiempo real para una ventana horaria."""

    window: str = Field(..., description="Ventana horaria 'YYYY-MM-DDTHH' (UTC)")
    earthquake_count: int = Field(default=0, ge=0)
    avg_magnitude: float | None = Field(default=None)
    max_magnitude: float | None = Field(default=None)
    min_magnitude: float | None = Field(default=None)
    magnitude_distribution: dict[str, int] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict:
        return self.model_dump()
