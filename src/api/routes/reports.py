"""Endpoints GET /reports (lectura) y POST /reports/generate (bajo demanda)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_reporting_service
from src.api.schemas import PageMeta, Paginated, ReportOut
from src.services.reporting_service import ReportingService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=Paginated[ReportOut], summary="Listar reportes horarios")
async def list_reports(
    service: Annotated[ReportingService, Depends(get_reporting_service)],
    window_from: Annotated[str | None, Query(description="Ventana mínima 'YYYY-MM-DDTHH'")] = None,
    window_to: Annotated[str | None, Query(description="Ventana máxima 'YYYY-MM-DDTHH'")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
) -> Paginated[ReportOut]:
    items, total = await service.list_reports(
        window_from=window_from,
        window_to=window_to,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    total_pages = (total + page_size - 1) // page_size
    return Paginated[ReportOut](
        meta=PageMeta(total=total, page=page, page_size=page_size, total_pages=total_pages),
        items=[ReportOut(**doc) for doc in items],
    )


@router.post(
    "/generate/{window}",
    response_model=ReportOut,
    summary="Generar/regenerar el reporte de una ventana bajo demanda",
)
async def generate_report(
    window: str,
    service: Annotated[ReportingService, Depends(get_reporting_service)],
) -> ReportOut:
    report = await service.generate_for_window(window)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Sin eventos para la ventana {window}")
    return ReportOut(**report.to_mongo())
