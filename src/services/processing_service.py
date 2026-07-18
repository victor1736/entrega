"""Procesamiento en tiempo real: recalcula métricas de las ventanas afectadas.

Cada vez que llegan eventos nuevos, se actualizan (near real-time) las
métricas de las ventanas horarias impactadas: conteo, magnitud promedio,
máxima, mínima y distribución por rangos.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.config.constants import empty_distribution, magnitude_bucket
from src.config.logging_config import get_logger
from src.database.repositories import EarthquakeRepository, MetricRepository
from src.models.metric import Metric

logger = get_logger(__name__)


class ProcessingService:
    """Calcula y persiste métricas por ventana horaria."""

    def __init__(
        self,
        earthquake_repo: EarthquakeRepository,
        metric_repo: MetricRepository,
    ) -> None:
        self._eq_repo = earthquake_repo
        self._metric_repo = metric_repo

    async def process_new_events(self, windows: set[str]) -> None:
        """Recalcula las métricas para cada ventana afectada."""
        for window in windows:
            await self.recompute_window(window)

    async def recompute_window(self, window: str) -> Metric | None:
        """Recalcula las métricas de una ventana concreta y las persiste."""
        agg = await self._eq_repo.aggregate_window(window)
        if agg is None:
            return None

        magnitudes = [m for m in agg.get("magnitudes", []) if m is not None]
        distribution = empty_distribution()
        for mag in agg.get("magnitudes", []):
            distribution[magnitude_bucket(mag)] += 1

        metric = Metric(
            window=window,
            earthquake_count=agg.get("earthquake_count", 0),
            avg_magnitude=round(agg["avg_magnitude"], 2)
            if agg.get("avg_magnitude") is not None
            else None,
            max_magnitude=agg.get("max_magnitude"),
            min_magnitude=agg.get("min_magnitude"),
            magnitude_distribution=distribution,
            updated_at=datetime.now(timezone.utc),
        )
        await self._metric_repo.upsert(metric.to_mongo())
        logger.debug(
            "Métricas actualizadas",
            extra={"window": window, "count": metric.earthquake_count},
        )
        return metric
