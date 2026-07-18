"""Inyección de dependencias de la API (FastAPI ``Depends``).

Construye repositorios y servicios a partir de la conexión compartida a
MongoDB. Aplica el principio de inversión de dependencias: las rutas reciben
servicios ya ensamblados.
"""
from __future__ import annotations

from src.database.mongodb import get_database
from src.database.repositories import (
    EarthquakeRepository,
    MetricRepository,
    ReportRepository,
)
from src.services.metrics_service import MetricsService
from src.services.processing_service import ProcessingService
from src.services.reporting_service import ReportingService


def get_earthquake_repo() -> EarthquakeRepository:
    return EarthquakeRepository(get_database())


def get_metric_repo() -> MetricRepository:
    return MetricRepository(get_database())


def get_report_repo() -> ReportRepository:
    return ReportRepository(get_database())


def get_metrics_service() -> MetricsService:
    return MetricsService(get_metric_repo())


def get_processing_service() -> ProcessingService:
    return ProcessingService(get_earthquake_repo(), get_metric_repo())


def get_reporting_service() -> ReportingService:
    return ReportingService(get_earthquake_repo(), get_report_repo())
