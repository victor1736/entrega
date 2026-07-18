"""Cliente HTTP para el feed público de terremotos de USGS.

Responsabilidad única: obtener el GeoJSON crudo de la API. La transformación
al modelo interno se realiza en la capa de servicios (separación de capas).
"""
from __future__ import annotations

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.logging_config import get_logger
from src.config.settings import Settings

logger = get_logger(__name__)


class USGSClient:
    """Cliente asíncrono para el USGS Earthquake feed."""

    def __init__(self, settings: Settings) -> None:
        self._url = settings.usgs_feed_url
        self._timeout = settings.usgs_timeout_seconds

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    )
    async def fetch_raw(self) -> dict:
        """Descarga el feed y devuelve el GeoJSON como dict.

        Reintenta hasta 3 veces con backoff exponencial ante fallos de red
        o respuestas 5xx.
        """
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            logger.debug("Solicitando feed USGS", extra={"url": self._url})
            response = await client.get(self._url)
            response.raise_for_status()
            data = response.json()
            feature_count = len(data.get("features", []))
            logger.info("Feed USGS recibido", extra={"features": feature_count})
            return data
