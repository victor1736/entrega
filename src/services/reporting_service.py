"""Servicio de reportes consolidados por hora.

Usado tanto por la API (generación bajo demanda / lectura) como por el DAG de
Airflow (a través de la variante síncrona en ``airflow/dags``). La lógica de
consolidación vive aquí para mantener una única fuente de verdad de negocio.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from src.config.constants import HOUR_WINDOW_FORMAT
from src.config.logging_config import get_logger
from src.database.repositories import EarthquakeRepository, ReportRepository
from src.models.report import HourlyReport
from src.utils.locations import extract_region

logger = get_logger(__name__)

TOP_LOCATIONS_LIMIT = 3


def window_to_report_date(window: str) -> datetime:
    """Convierte 'YYYY-MM-DDTHH' al datetime UTC de inicio de esa hora."""
    return datetime.strptime(window, HOUR_WINDOW_FORMAT).replace(tzinfo=timezone.utc)


def build_report_from_aggregation(window: str, agg: dict) -> HourlyReport:
    """Construye un ``HourlyReport`` a partir del resultado de agregación."""
    locations = [loc for loc in agg.get("locations", []) if loc]
    regions = [r for r in (extract_region(loc) for loc in locations) if r]
    top = [name for name, _ in Counter(regions).most_common(TOP_LOCATIONS_LIMIT)]

    avg = agg.get("avg_magnitude")
    return HourlyReport(
        window=window,
        report_date=window_to_report_date(window),
        total_events=agg.get("earthquake_count", 0),
        average_magnitude=round(avg, 2) if avg is not None else None,
        max_magnitude=agg.get("max_magnitude"),
        top_locations=top,
    )


class ReportingService:
    """Genera y consulta reportes horarios."""

    def __init__(
        self,
        earthquake_repo: EarthquakeRepository,
        report_repo: ReportRepository,
    ) -> None:
        self._eq_repo = earthquake_repo
        self._report_repo = report_repo

    async def generate_for_window(self, window: str) -> HourlyReport | None:
        """Genera (y persiste) el reporte consolidado de una ventana horaria."""
        agg = await self._eq_repo.aggregate_window(window)
        if agg is None:
            logger.info("Sin eventos para reportar", extra={"window": window})
            return None
        report = build_report_from_aggregation(window, agg)
        await self._report_repo.upsert(report.to_mongo())
        logger.info(
            "Reporte generado",
            extra={"window": window, "total_events": report.total_events},
        )
        return report

    async def list_reports(
        self, *, window_from: str | None, window_to: str | None, skip: int, limit: int
    ) -> tuple[list[dict], int]:
        filters: dict = {}
        window_filter: dict[str, str] = {}
        if window_from:
            window_filter["$gte"] = window_from
        if window_to:
            window_filter["$lte"] = window_to
        if window_filter:
            filters["window"] = window_filter

        total = await self._report_repo.count(filters)
        items = await self._report_repo.find(filters=filters, skip=skip, limit=limit)
        return items, total
