"""Transformación de features GeoJSON de USGS al modelo interno ``Earthquake``.

Aislar esta lógica (SRP) permite testearla y cambiar el formato de la fuente
sin tocar la ingesta ni la persistencia.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.config.constants import HOUR_WINDOW_FORMAT
from src.config.logging_config import get_logger
from src.models.earthquake import Earthquake

logger = get_logger(__name__)


def _epoch_ms_to_utc(epoch_ms: int) -> datetime:
    """Convierte epoch en milisegundos (formato USGS) a datetime UTC."""
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)


def window_for(event_time: datetime) -> str:
    """Deriva la ventana horaria 'YYYY-MM-DDTHH' a partir de una fecha UTC."""
    return event_time.astimezone(timezone.utc).strftime(HOUR_WINDOW_FORMAT)


def feature_to_earthquake(feature: dict) -> Earthquake | None:
    """Convierte un ``feature`` GeoJSON a ``Earthquake``.

    Devuelve ``None`` (y registra un warning) si el feature es inválido, para
    no interrumpir el procesamiento del resto del lote.
    """
    try:
        event_id = feature["id"]
        props = feature.get("properties", {}) or {}
        geometry = feature.get("geometry", {}) or {}
        coords = geometry.get("coordinates") or [None, None, None]

        longitude, latitude, depth = (
            coords[0],
            coords[1],
            coords[2] if len(coords) > 2 else None,
        )

        if latitude is None or longitude is None:
            logger.warning("Feature sin coordenadas válidas", extra={"event_id": event_id})
            return None

        time_ms = props.get("time")
        if time_ms is None:
            logger.warning("Feature sin timestamp", extra={"event_id": event_id})
            return None

        event_time = _epoch_ms_to_utc(int(time_ms))

        return Earthquake(
            event_id=event_id,
            magnitude=props.get("mag"),
            location=props.get("place"),
            latitude=float(latitude),
            longitude=float(longitude),
            depth=float(depth) if depth is not None else None,
            event_time=event_time,
            window=window_for(event_time),
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "No se pudo transformar el feature",
            extra={"error": str(exc), "feature_id": feature.get("id")},
        )
        return None
