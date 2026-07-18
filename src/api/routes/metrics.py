"""Endpoints GET /metrics con filtros, paginación y resumen (con caché)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.api.dependencies import get_metrics_service
from src.api.schemas import (
    MetricOut,
    MetricsSummaryOut,
    PageMeta,
    Paginated,
)
from src.services.metrics_service import MetricsService

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", response_model=Paginated[MetricOut], summary="Listar métricas por hora")
async def list_metrics(
    service: Annotated[MetricsService, Depends(get_metrics_service)],
    window_from: Annotated[str | None, Query(description="Ventana mínima 'YYYY-MM-DDTHH'")] = None,
    window_to: Annotated[str | None, Query(description="Ventana máxima 'YYYY-MM-DDTHH'")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 24,
) -> Paginated[MetricOut]:
    items, total = await service.list_metrics(
        window_from=window_from,
        window_to=window_to,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    total_pages = (total + page_size - 1) // page_size
    return Paginated[MetricOut](
        meta=PageMeta(total=total, page=page, page_size=page_size, total_pages=total_pages),
        items=[MetricOut(**doc) for doc in items],
    )


@router.get("/summary", response_model=MetricsSummaryOut, summary="Resumen global (cacheado)")
async def metrics_summary(
    request: Request,
    service: Annotated[MetricsService, Depends(get_metrics_service)],
) -> MetricsSummaryOut:
    """Resumen agregado global. Se sirve desde caché TTL para reducir carga."""
    cache = request.app.state.cache
    data = await cache.get_or_set("metrics_summary", service.summary)
    return MetricsSummaryOut(**data)


@router.get("/{window}", response_model=MetricOut, summary="Métrica de una ventana")
async def get_metric(
    window: str,
    service: Annotated[MetricsService, Depends(get_metrics_service)],
) -> MetricOut:
    doc = await service.get_window(window)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Sin métricas para la ventana {window}")
    return MetricOut(**doc)
