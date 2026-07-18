"""Definición y creación de índices de MongoDB.

Los índices se crean de forma idempotente al arrancar la aplicación.

Justificación del modelado (ver README para el detalle):
- ``earthquakes.event_id`` UNIQUE  -> garantiza deduplicación a nivel de BD.
- ``earthquakes.event_time``       -> consultas por rango temporal y ordenamiento.
- ``earthquakes.window``           -> agregaciones por hora (métricas/reportes).
- ``earthquakes.magnitude``        -> filtros por magnitud.
- ``metrics.window`` UNIQUE        -> una fila de métricas por ventana horaria.
- ``hourly_reports.window`` UNIQUE -> un reporte por hora (upsert idempotente).
"""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel

from src.config.constants import (
    COLLECTION_EARTHQUAKES,
    COLLECTION_HOURLY_REPORTS,
    COLLECTION_METRICS,
)
from src.config.logging_config import get_logger

logger = get_logger(__name__)


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    """Crea todos los índices necesarios (idempotente)."""
    await db[COLLECTION_EARTHQUAKES].create_indexes(
        [
            IndexModel([("event_id", ASCENDING)], unique=True, name="ux_event_id"),
            IndexModel([("event_time", DESCENDING)], name="ix_event_time"),
            IndexModel([("window", ASCENDING)], name="ix_window"),
            IndexModel([("magnitude", DESCENDING)], name="ix_magnitude"),
        ]
    )
    await db[COLLECTION_METRICS].create_indexes(
        [IndexModel([("window", ASCENDING)], unique=True, name="ux_metrics_window")]
    )
    await db[COLLECTION_HOURLY_REPORTS].create_indexes(
        [
            IndexModel([("window", ASCENDING)], unique=True, name="ux_report_window"),
            IndexModel([("report_date", DESCENDING)], name="ix_report_date"),
        ]
    )
    logger.info("Índices de MongoDB verificados/creados")
