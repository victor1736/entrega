"""Modelo de reporte consolidado por hora (generado por Airflow)."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class HourlyReport(BaseModel):
    """Reporte consolidado de la actividad sísmica de una hora."""

    window: str = Field(..., description="Ventana horaria 'YYYY-MM-DDTHH' (UTC)")
    report_date: datetime = Field(..., description="Inicio de la hora reportada (UTC)")
    total_events: int = Field(default=0, ge=0)
    average_magnitude: float | None = Field(default=None)
    max_magnitude: float | None = Field(default=None)
    top_locations: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict:
        return self.model_dump()
