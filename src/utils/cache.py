"""Caché en memoria con TTL (estrategia de caché — bonificación nivel 1).

Implementación ligera y sin dependencias externas, apta para respuestas de
solo lectura y de alta frecuencia (p.ej. resumen de métricas). Para un
despliegue multi-instancia se recomendaría Redis; aquí se documenta la
estrategia y se ofrece una implementación funcional para una sola instancia.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable


class TTLCache:
    """Caché clave-valor con expiración por tiempo de vida."""

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get_or_set(self, key: str, loader: Callable[[], Awaitable[Any]]) -> Any:
        """Devuelve el valor cacheado o lo calcula con ``loader`` si expiró."""
        now = time.monotonic()
        cached = self._store.get(key)
        if cached is not None and (now - cached[0]) < self._ttl:
            return cached[1]

        async with self._lock:
            # Doble verificación tras adquirir el lock
            cached = self._store.get(key)
            if cached is not None and (time.monotonic() - cached[0]) < self._ttl:
                return cached[1]
            value = await loader()
            self._store[key] = (time.monotonic(), value)
            return value

    def invalidate(self, key: str | None = None) -> None:
        """Invalida una clave concreta o toda la caché."""
        if key is None:
            self._store.clear()
        else:
            self._store.pop(key, None)
