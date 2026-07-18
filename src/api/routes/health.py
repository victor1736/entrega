"""Endpoint de health check para orquestadores (Docker/K8s)."""
from __future__ import annotations

from fastapi import APIRouter

from src.database.mongodb import get_database

router = APIRouter(tags=["health"])


@router.get("/health", summary="Estado del servicio")
async def health() -> dict:
    """Verifica la conectividad con MongoDB."""
    try:
        await get_database().command("ping")
        db_ok = True
    except Exception:  # noqa: BLE001 - health nunca debe lanzar
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "mongodb": db_ok}
