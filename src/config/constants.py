"""Constantes de dominio compartidas por toda la plataforma."""
from __future__ import annotations

# Nombres de colecciones en MongoDB (única fuente de verdad)
COLLECTION_EARTHQUAKES = "earthquakes"
COLLECTION_METRICS = "metrics"
COLLECTION_HOURLY_REPORTS = "hourly_reports"

# Formato de la ventana horaria usada para agrupar métricas y reportes.
# Ej: "2026-06-17T10" representa la hora 10:00-10:59 UTC.
HOUR_WINDOW_FORMAT = "%Y-%m-%dT%H"

# ---------------------------------------------------------------------------
# Distribución por rangos de magnitud (clasificación estándar tipo Richter).
# Cada rango se define como (nombre, límite_inferior_incl, límite_superior_excl).
# El último rango usa infinito como límite superior.
# ---------------------------------------------------------------------------
MAGNITUDE_RANGES: list[tuple[str, float, float]] = [
    ("micro", float("-inf"), 2.0),      # < 2.0   Imperceptibles
    ("minor", 2.0, 4.0),                # 2.0-3.9 Menores
    ("light", 4.0, 5.0),                # 4.0-4.9 Ligeros
    ("moderate", 5.0, 6.0),             # 5.0-5.9 Moderados
    ("strong", 6.0, 7.0),               # 6.0-6.9 Fuertes
    ("major", 7.0, 8.0),                # 7.0-7.9 Mayores
    ("great", 8.0, float("inf")),       # >= 8.0  Grandes
]


def magnitude_bucket(magnitude: float | None) -> str:
    """Clasifica una magnitud en su rango correspondiente.

    Devuelve ``"unknown"`` si la magnitud es ``None`` (la API USGS puede
    devolver eventos sin magnitud calculada).
    """
    if magnitude is None:
        return "unknown"
    for name, low, high in MAGNITUDE_RANGES:
        if low <= magnitude < high:
            return name
    return "unknown"


def empty_distribution() -> dict[str, int]:
    """Devuelve un diccionario de distribución inicializado en cero."""
    dist = {name: 0 for name, _, _ in MAGNITUDE_RANGES}
    dist["unknown"] = 0
    return dist
