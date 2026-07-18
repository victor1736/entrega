"""Servicio de consulta de métricas (lectura para la API)."""
from __future__ import annotations

from typing import Any

from src.config.logging_config import get_logger
from src.database.repositories import MetricRepository

logger = get_logger(__name__)


class MetricsService:
    """Expone las métricas persistidas y un resumen global."""

    def __init__(self, metric_repo: MetricRepository) -> None:
        self._repo = metric_repo

    async def list_metrics(
        self, *, window_from: str | None, window_to: str | None, skip: int, limit: int
    ) -> tuple[list[dict], int]:
        filters: dict[str, Any] = {}
        window_filter: dict[str, str] = {}
        if window_from:
            window_filter["$gte"] = window_from
        if window_to:
            window_filter["$lte"] = window_to
        if window_filter:
            filters["window"] = window_filter

        total = await self._repo.count(filters)
        items = await self._repo.find(filters=filters, skip=skip, limit=limit)
        return items, total

    async def get_window(self, window: str) -> dict | None:
        return await self._repo.get(window)

    async def summary(self) -> dict:
        """Resumen global agregando todas las ventanas de métricas."""
        docs = await self._repo.find(filters={}, skip=0, limit=10_000)
        total_events = sum(d.get("earthquake_count", 0) for d in docs)
        max_mag = max(
            (d["max_magnitude"] for d in docs if d.get("max_magnitude") is not None),
            default=None,
        )
        # Promedio ponderado por cantidad de eventos
        weighted_sum = sum(
            (d.get("avg_magnitude") or 0) * d.get("earthquake_count", 0) for d in docs
        )
        avg_mag = round(weighted_sum / total_events, 2) if total_events else None

        return {
            "total_windows": len(docs),
            "total_events": total_events,
            "avg_magnitude": avg_mag,
            "max_magnitude": max_mag,
        }
