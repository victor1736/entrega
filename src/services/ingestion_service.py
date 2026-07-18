"""Servicio de ingesta: consume la API USGS, deduplica y persiste eventos.

Flujo:
1. Descarga el feed crudo (USGSClient).
2. Transforma cada feature al modelo interno (transformer).
3. Detecta nuevos eventos comparando contra los ``event_id`` ya existentes.
4. Persiste mediante *upsert* idempotente (doble garantía anti-duplicados:
   comparación previa + índice único en BD).
5. Dispara el procesamiento en tiempo real de las ventanas afectadas.
"""
from __future__ import annotations

from src.clients.usgs_client import USGSClient
from src.config.logging_config import get_logger
from src.database.repositories import EarthquakeRepository
from src.models.earthquake import Earthquake
from src.services.processing_service import ProcessingService
from src.services.transformer import feature_to_earthquake

logger = get_logger(__name__)


class IngestionService:
    """Orquesta la ingesta de eventos sísmicos."""

    def __init__(
        self,
        client: USGSClient,
        earthquake_repo: EarthquakeRepository,
        processing_service: ProcessingService,
    ) -> None:
        self._client = client
        self._repo = earthquake_repo
        self._processing = processing_service

    async def run_once(self) -> dict:
        """Ejecuta un ciclo completo de ingesta. Devuelve un resumen."""
        raw = await self._client.fetch_raw()
        features = raw.get("features", [])

        # Transformación (los features inválidos se descartan con log)
        parsed: list[Earthquake] = []
        for feature in features:
            eq = feature_to_earthquake(feature)
            if eq is not None:
                parsed.append(eq)

        if not parsed:
            logger.info("Sin eventos válidos en el feed")
            return {"received": len(features), "new": 0, "duplicates": 0}

        # Detección de nuevos vs duplicados
        incoming_ids = [eq.event_id for eq in parsed]
        existing = await self._repo.existing_ids(incoming_ids)
        new_events = [eq for eq in parsed if eq.event_id not in existing]
        duplicates = len(parsed) - len(new_events)

        if not new_events:
            logger.info(
                "No hay eventos nuevos",
                extra={"received": len(features), "duplicates": duplicates},
            )
            return {"received": len(features), "new": 0, "duplicates": duplicates}

        # Persistencia idempotente
        inserted = await self._repo.bulk_upsert(new_events)

        # Procesamiento en tiempo real de las ventanas afectadas
        affected_windows = {eq.window for eq in new_events}
        await self._processing.process_new_events(affected_windows)

        logger.info(
            "Ingesta completada",
            extra={
                "received": len(features),
                "new": inserted,
                "duplicates": duplicates,
                "windows": sorted(affected_windows),
            },
        )
        return {
            "received": len(features),
            "new": inserted,
            "duplicates": duplicates,
            "windows": sorted(affected_windows),
        }
