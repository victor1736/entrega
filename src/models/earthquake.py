"""Modelo interno de un evento sísmico (dominio).

Es la representación canónica usada en toda la plataforma tras transformar
la respuesta cruda de la API USGS.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Earthquake(BaseModel):
    """Evento sísmico normalizado."""

    model_config = ConfigDict(populate_by_name=True)

    event_id: str = Field(..., description="Identificador único del evento (USGS id)")
    magnitude: float | None = Field(
        default=None, description="Magnitud del sismo (puede ser nula en la fuente)"
    )
    location: str | None = Field(default=None, description="Descripción textual del lugar")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    depth: float | None = Field(default=None, description="Profundidad en km")
    event_time: datetime = Field(..., description="Momento del evento (UTC)")
    window: str = Field(..., description="Ventana horaria 'YYYY-MM-DDTHH' (UTC)")
    ingested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Momento en que el evento fue ingerido en el sistema",
    )

    @field_validator("event_time", "ingested_at")
    @classmethod
    def _ensure_utc(cls, value: datetime) -> datetime:
        """Garantiza que las fechas tengan zona horaria UTC."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def to_mongo(self) -> dict:
        """Serializa el modelo al documento que se almacena en MongoDB."""
        return self.model_dump()
