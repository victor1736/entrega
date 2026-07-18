"""Gestión eficiente de la conexión a MongoDB (driver asíncrono Motor).

Se usa un cliente singleton con *connection pooling* nativo de Motor/PyMongo.
El pool se reutiliza en toda la aplicación (API e ingesta), evitando abrir
una conexión por operación — requisito de "gestión eficiente de conexiones".
"""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.config.logging_config import get_logger
from src.config.settings import get_settings

logger = get_logger(__name__)


class MongoDB:
    """Contenedor singleton del cliente Motor."""

    client: AsyncIOMotorClient | None = None
    database: AsyncIOMotorDatabase | None = None


async def connect() -> AsyncIOMotorDatabase:
    """Abre (una sola vez) la conexión y devuelve el objeto database."""
    if MongoDB.client is None:
        settings = get_settings()
        logger.info(
            "Conectando a MongoDB",
            extra={"host": settings.mongo_host, "db": settings.mongo_db},
        )
        MongoDB.client = AsyncIOMotorClient(
            settings.mongodb_uri,
            maxPoolSize=50,
            minPoolSize=5,
            serverSelectionTimeoutMS=5000,
            uuidRepresentation="standard",
        )
        MongoDB.database = MongoDB.client[settings.mongo_db]
        # Verifica conectividad de forma temprana
        await MongoDB.client.admin.command("ping")
        logger.info("Conexión a MongoDB establecida")
    return MongoDB.database  # type: ignore[return-value]


def get_database() -> AsyncIOMotorDatabase:
    """Devuelve la database ya conectada.

    Lanza ``RuntimeError`` si ``connect()`` no se ha invocado aún.
    """
    if MongoDB.database is None:
        raise RuntimeError("La base de datos no está inicializada. Llama a connect() primero.")
    return MongoDB.database


async def close_database() -> None:
    """Cierra la conexión limpiamente (usado en el shutdown de la app)."""
    if MongoDB.client is not None:
        MongoDB.client.close()
        MongoDB.client = None
        MongoDB.database = None
        logger.info("Conexión a MongoDB cerrada")
