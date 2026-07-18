"""Esquemas Pydantic para requests y responses de la API.

Concentran la validación de parámetros (filtros, paginación, ordenamiento) y
el formato de las respuestas paginadas.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class SortDir(str, Enum):
    asc = "asc"
    desc = "desc"

    @property
    def mongo(self) -> int:
        from pymongo import ASCENDING, DESCENDING

        return ASCENDING if self is SortDir.asc else DESCENDING


class EarthquakeSortField(str, Enum):
    event_time = "event_time"
    magnitude = "magnitude"
    ingested_at = "ingested_at"


class PageMeta(BaseModel):
    """Metadatos de paginación."""

    total: int = Field(..., description="Total de elementos que cumplen el filtro")
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_pages: int = Field(..., ge=0)


class Paginated(BaseModel, Generic[T]):
    """Respuesta paginada genérica."""

    meta: PageMeta
    items: list[T]


class EarthquakeOut(BaseModel):
    event_id: str
    magnitude: float | None
    location: str | None
    latitude: float
    longitude: float
    depth: float | None
    event_time: datetime
    window: str
    ingested_at: datetime | None = None


class MetricOut(BaseModel):
    window: str
    earthquake_count: int
    avg_magnitude: float | None
    max_magnitude: float | None
    min_magnitude: float | None
    magnitude_distribution: dict[str, int] = Field(default_factory=dict)
    updated_at: datetime | None = None


class ReportOut(BaseModel):
    window: str
    report_date: datetime
    total_events: int
    average_magnitude: float | None
    max_magnitude: float | None
    top_locations: list[str] = Field(default_factory=list)
    generated_at: datetime | None = None


class MetricsSummaryOut(BaseModel):
    total_windows: int
    total_events: int
    avg_magnitude: float | None
    max_magnitude: float | None
