"""Entrypoint del servicio de ingesta (worker independiente).

Ejecuta un ciclo de ingesta cada ``INGESTION_INTERVAL_SECONDS`` (por defecto
180 s = 3 minutos, según el requerimiento). Corre como contenedor separado
de la API para respetar la separación de responsabilidades.
"""
from __future__ import annotations

import asyncio
import signal

from src.clients.usgs_client import USGSClient
from src.config.logging_config import get_logger
from src.config.settings import get_settings
from src.database.indexes import create_indexes
from src.database.mongodb import close_database, connect
from src.database.repositories import EarthquakeRepository, MetricRepository
from src.services.ingestion_service import IngestionService
from src.services.processing_service import ProcessingService

logger = get_logger(__name__)

_shutdown = asyncio.Event()


def _handle_signal(*_: object) -> None:
    logger.info("Señal de apagado recibida")
    _shutdown.set()


async def main() -> None:
    settings = get_settings()

    db = await connect()
    await create_indexes(db)

    # Ensamblado de dependencias (inyección manual)
    client = USGSClient(settings)
    eq_repo = EarthquakeRepository(db)
    metric_repo = MetricRepository(db)
    processing = ProcessingService(eq_repo, metric_repo)
    ingestion = IngestionService(client, eq_repo, processing)

    interval = settings.ingestion_interval_seconds
    logger.info("Servicio de ingesta iniciado", extra={"interval_seconds": interval})

    try:
        while not _shutdown.is_set():
            try:
                summary = await ingestion.run_once()
                logger.info("Ciclo de ingesta OK", extra=summary)
            except Exception as exc:  # noqa: BLE001 - el worker no debe morir
                logger.error("Error en ciclo de ingesta", extra={"error": str(exc)})

            # Espera interrumpible por señal
            try:
                await asyncio.wait_for(_shutdown.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
    finally:
        await close_database()
        logger.info("Servicio de ingesta detenido")


if __name__ == "__main__":
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_signal)
        except (ValueError, OSError):
            pass
    asyncio.run(main())
