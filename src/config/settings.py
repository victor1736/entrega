"""Configuración central de la aplicación.

Toda la configuración se obtiene de variables de entorno (12-factor app).
Ninguna credencial está hardcodeada: los valores por defecto son solo para
desarrollo local y deben sobreescribirse mediante `.env` / entorno.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración tipada y validada mediante Pydantic."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Aplicación ----
    app_name: str = "seismic-platform"
    environment: str = "development"
    log_level: str = "INFO"
    log_format: str = Field(default="json", description="json | console")

    # ---- MongoDB ----
    mongo_initdb_root_username: str = "seismic"
    mongo_initdb_root_password: str = "seismic_secret_change_me"
    mongo_host: str = "mongodb"
    mongo_port: int = 27017
    mongo_db: str = "seismic"
    mongo_uri: str = ""

    # ---- Cliente USGS ----
    usgs_feed_url: str = (
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
    )
    usgs_timeout_seconds: int = 30

    # ---- Ingesta ----
    ingestion_interval_seconds: int = 180

    # ---- Caché ----
    cache_ttl_seconds: int = 30

    # ---- Tiempo real (WebSocket) ----
    # Cada cuántos segundos el API observa la BD para detectar eventos nuevos
    # y empujarlos a los clientes conectados por WebSocket.
    realtime_poll_seconds: int = 5

    # ---- API ----
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @computed_field  # type: ignore[misc]
    @property
    def mongodb_uri(self) -> str:
        """Devuelve la URI de conexión, construyéndola si no se define explícita."""
        if self.mongo_uri:
            return self.mongo_uri
        return (
            f"mongodb://{self.mongo_initdb_root_username}:"
            f"{self.mongo_initdb_root_password}@"
            f"{self.mongo_host}:{self.mongo_port}/"
            f"?authSource=admin"
        )


@lru_cache
def get_settings() -> Settings:
    """Singleton de configuración (cacheado para reutilizar en toda la app)."""
    return Settings()
