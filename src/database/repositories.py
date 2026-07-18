"""Repositorios: única capa que conoce los detalles de acceso a MongoDB.

Aplicando el patrón *Repository* (SOLID / separación de responsabilidades),
los servicios de negocio dependen de estas abstracciones y no de Motor
directamente, lo que facilita el testing y el mantenimiento.
"""
from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING, UpdateOne

from src.config.constants import (
    COLLECTION_EARTHQUAKES,
    COLLECTION_HOURLY_REPORTS,
    COLLECTION_METRICS,
)
from src.config.logging_config import get_logger
from src.models.earthquake import Earthquake

logger = get_logger(__name__)


class EarthquakeRepository:
    """Acceso a la colección ``earthquakes``."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db[COLLECTION_EARTHQUAKES]

    async def existing_ids(self, event_ids: list[str]) -> set[str]:
        """Devuelve el subconjunto de ``event_ids`` que ya existe en BD."""
        if not event_ids:
            return set()
        cursor = self._col.find(
            {"event_id": {"$in": event_ids}}, projection={"event_id": 1, "_id": 0}
        )
        return {doc["event_id"] async for doc in cursor}

    async def bulk_upsert(self, earthquakes: list[Earthquake]) -> int:
        """Inserta/actualiza eventos de forma idempotente por ``event_id``.

        Devuelve la cantidad de documentos realmente insertados (nuevos).
        """
        if not earthquakes:
            return 0
        ops = [
            UpdateOne(
                {"event_id": eq.event_id},
                {
                    "$set": eq.to_mongo(),
                    "$setOnInsert": {"first_seen": eq.ingested_at},
                },
                upsert=True,
            )
            for eq in earthquakes
        ]
        result = await self._col.bulk_write(ops, ordered=False)
        return result.upserted_count

    async def find(
        self,
        *,
        filters: dict[str, Any],
        sort_field: str,
        sort_dir: int,
        skip: int,
        limit: int,
    ) -> list[dict]:
        cursor = (
            self._col.find(filters, projection={"_id": 0})
            .sort(sort_field, sort_dir)
            .skip(skip)
            .limit(limit)
        )
        return [doc async for doc in cursor]

    async def count(self, filters: dict[str, Any]) -> int:
        return await self._col.count_documents(filters)

    async def distinct_windows(self) -> list[str]:
        return await self._col.distinct("window")

    async def aggregate_window(self, window: str) -> dict | None:
        """Agrega métricas de una ventana horaria concreta."""
        pipeline = [
            {"$match": {"window": window}},
            {
                "$group": {
                    "_id": "$window",
                    "earthquake_count": {"$sum": 1},
                    "avg_magnitude": {"$avg": "$magnitude"},
                    "max_magnitude": {"$max": "$magnitude"},
                    "min_magnitude": {"$min": "$magnitude"},
                    "magnitudes": {"$push": "$magnitude"},
                    "locations": {"$push": "$location"},
                }
            },
        ]
        docs = await self._col.aggregate(pipeline).to_list(length=1)
        return docs[0] if docs else None


class MetricRepository:
    """Acceso a la colección ``metrics``."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db[COLLECTION_METRICS]

    async def upsert(self, metric_doc: dict) -> None:
        await self._col.update_one(
            {"window": metric_doc["window"]}, {"$set": metric_doc}, upsert=True
        )

    async def get(self, window: str) -> dict | None:
        return await self._col.find_one({"window": window}, projection={"_id": 0})

    async def find(
        self, *, filters: dict[str, Any], skip: int, limit: int
    ) -> list[dict]:
        cursor = (
            self._col.find(filters, projection={"_id": 0})
            .sort("window", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        return [doc async for doc in cursor]

    async def count(self, filters: dict[str, Any]) -> int:
        return await self._col.count_documents(filters)


class ReportRepository:
    """Acceso a la colección ``hourly_reports``."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db[COLLECTION_HOURLY_REPORTS]

    async def upsert(self, report_doc: dict) -> None:
        await self._col.update_one(
            {"window": report_doc["window"]}, {"$set": report_doc}, upsert=True
        )

    async def find(
        self, *, filters: dict[str, Any], skip: int, limit: int
    ) -> list[dict]:
        cursor = (
            self._col.find(filters, projection={"_id": 0})
            .sort("report_date", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        return [doc async for doc in cursor]

    async def count(self, filters: dict[str, Any]) -> int:
        return await self._col.count_documents(filters)
