"""Utilidades para derivar una región legible desde el campo ``place`` de USGS.

Ejemplos de ``place``:
  "20 km NW of California"      -> "California"
  "100km SSW of Kokopo, Papua"  -> "Papua"
  "South of the Fiji Islands"   -> "Fiji Islands"
Se usa para construir el ranking ``top_locations`` de los reportes.
"""
from __future__ import annotations

import re

_OF_SPLIT = re.compile(r"\bof\b", flags=re.IGNORECASE)


def extract_region(place: str | None) -> str | None:
    """Devuelve la región principal de un texto de ubicación USGS."""
    if not place:
        return None
    text = place.strip()

    # Toma lo que sigue al último " of " si existe
    if _OF_SPLIT.search(text):
        text = _OF_SPLIT.split(text)[-1].strip()

    # Si hay coma, la región suele ser el último segmento (país/estado)
    if "," in text:
        text = text.split(",")[-1].strip()

    return text or None
