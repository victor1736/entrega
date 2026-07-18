"""Actualización en tiempo real vía WebSocket (Bono Nivel 3).

El API observa la colección ``earthquakes`` y, cuando detecta eventos nuevos,
los **empuja** (push) a todos los clientes conectados por WebSocket. Así el
dashboard se actualiza solo, al instante, sin recargar ni esperar al refresco.

Diseño desacoplado: el servicio de ingesta escribe en MongoDB y este vigilante
(dentro del API) detecta los cambios y notifica. En un despliegue de gran
escala, este vigilante se sustituiría por *MongoDB Change Streams* o un bus de
eventos (Kafka/RabbitMQ) sin cambiar el contrato del WebSocket.
"""
from __future__ import annotations

import asyncio

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

from src.config.logging_config import get_logger
from src.database.mongodb import get_database
from src.database.repositories import EarthquakeRepository

logger = get_logger(__name__)


class ConnectionManager:
    """Gestiona las conexiones WebSocket activas y el broadcast."""

    def __init__(self) -> None:
        self._active: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active.add(websocket)
        logger.info("Cliente WebSocket conectado", extra={"clients": len(self._active)})

    def disconnect(self, websocket: WebSocket) -> None:
        self._active.discard(websocket)
        logger.info("Cliente WebSocket desconectado", extra={"clients": len(self._active)})

    @property
    def count(self) -> int:
        return len(self._active)

    async def broadcast(self, message: dict) -> None:
        """Envía un mensaje JSON a todos los clientes; descarta los caídos."""
        dead: list[WebSocket] = []
        for ws in list(self._active):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 - cliente caído
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


async def event_watcher(manager: ConnectionManager, interval: int) -> None:
    """Tarea de fondo: vigila la BD y emite eventos nuevos por WebSocket."""
    repo = EarthquakeRepository(get_database())
    try:
        last_count = await repo.count({})
    except Exception:  # noqa: BLE001
        last_count = 0

    logger.info("Vigilante de tiempo real iniciado", extra={"interval_seconds": interval})

    while True:
        await asyncio.sleep(interval)
        try:
            count = await repo.count({})
            if count > last_count and manager.count > 0:
                latest = await repo.find(
                    filters={}, sort_field="event_time", sort_dir=-1, skip=0, limit=1
                )
                payload = {
                    "type": "update",
                    "total": count,
                    "new": count - last_count,
                    "latest": jsonable_encoder(latest[0]) if latest else None,
                }
                await manager.broadcast(payload)
                logger.info(
                    "Push en tiempo real emitido",
                    extra={"new": count - last_count, "clients": manager.count},
                )
            last_count = max(last_count, count)
        except Exception as exc:  # noqa: BLE001 - la tarea no debe morir
            logger.error("Error en el vigilante de tiempo real", extra={"error": str(exc)})
