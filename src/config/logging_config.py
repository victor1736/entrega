"""Configuración de logging estructurado (JSON) para toda la plataforma.

Un logging estructurado facilita el monitoreo y la ingestión en herramientas
como ELK, Loki o CloudWatch. Se puede alternar a formato consola legible
mediante la variable de entorno ``LOG_FORMAT=console``.
"""
from __future__ import annotations

import logging
import sys

from pythonjsonlogger import json as jsonlogger

from .settings import get_settings

_CONFIGURED = False


def configure_logging() -> None:
    """Configura el logger raíz una única vez (idempotente)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)

    if settings.log_format.lower() == "json":
        formatter: logging.Formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
            timestamp=True,
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )

    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    # Reducir ruido de librerías de terceros
    for noisy in ("httpx", "httpcore", "pymongo", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger configurado con el nombre indicado."""
    configure_logging()
    return logging.getLogger(name)
