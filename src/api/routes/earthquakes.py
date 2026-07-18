"""Endpoint GET /earthquakes con filtros, paginación y ordenamiento."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_earthquake_repo
from src.api.schemas import (
    EarthquakeOut,
    EarthquakeSortField,
    PageMeta,
    Paginated,
    SortDir,
)
from src.database.repositories import EarthquakeRepository

router = APIRouter(prefix="/earthquakes", tags=["earthquakes"])


@router.get("", response_model=Paginated[EarthquakeOut], summary="Listar eventos sísmicos")
async def list_earthquakes(
    repo: Annotated[EarthquakeRepository, Depends(get_earthquake_repo)],
    min_magnitude: Annotated[float | None, Query(ge=-1, le=12)] = None,
    max_magnitude: Annotated[float | None, Query(ge=-1, le=12)] = None,
    start_time: Annotated[datetime | None, Query(description="Desde (UTC ISO-8601)")] = None,
    end_time: Annotated[datetime | None, Query(description="Hasta (UTC ISO-8601)")] = None,
    location: Annotated[str | None, Query(description="Búsqueda parcial en la ubicación")] = None,
    window: Annotated[str | None, Query(description="Ventana horaria 'YYYY-MM-DDTHH'")] = None,
    sort_by: EarthquakeSortField = EarthquakeSortField.event_time,
    sort_dir: SortDir = SortDir.desc,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
) -> Paginated[EarthquakeOut]:
    """Devuelve eventos sísmicos filtrados, ordenados y paginados."""
    filters: dict[str, Any] = {}

    mag_filter: dict[str, float] = {}
    if min_magnitude is not None:
        mag_filter["$gte"] = min_magnitude
    if max_magnitude is not None:
        mag_filter["$lte"] = max_magnitude
    if mag_filter:
        filters["magnitude"] = mag_filter

    time_filter: dict[str, datetime] = {}
    if start_time is not None:
        time_filter["$gte"] = start_time
    if end_time is not None:
        time_filter["$lte"] = end_time
    if time_filter:
        filters["event_time"] = time_filter

    if location:
        filters["location"] = {"$regex": location, "$options": "i"}
    if window:
        filters["window"] = window

    total = await repo.count(filters)
    items = await repo.find(
        filters=filters,
        sort_field=sort_by.value,
        sort_dir=sort_dir.mongo,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    total_pages = (total + page_size - 1) // page_size

    return Paginated[EarthquakeOut](
        meta=PageMeta(
            total=total, page=page, page_size=page_size, total_pages=total_pages
        ),
        items=[EarthquakeOut(**doc) for doc in items],
    )
