"""Punto de entrada de la API FastAPI.

Gestiona el ciclo de vida (conexión a MongoDB + creación de índices + caché),
registra los routers y sirve el dashboard estático.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src import __version__
from src.api.routes import earthquakes, health, metrics, reports
from src.config.logging_config import get_logger
from src.config.settings import get_settings
from src.database.indexes import create_indexes
from src.database.mongodb import close_database, connect
from src.utils.cache import TTLCache

logger = get_logger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa recursos al arrancar y los libera al apagar."""
    settings = get_settings()
    db = await connect()
    await create_indexes(db)
    app.state.cache = TTLCache(ttl_seconds=settings.cache_ttl_seconds)
    logger.info("API lista", extra={"version": __version__})
    yield
    await close_database()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Plataforma de Eventos Sísmicos en Tiempo Real",
        description=(
            "Ingesta, procesamiento en tiempo real y reportería de eventos "
            "sísmicos (USGS) con MongoDB, FastAPI y Airflow."
        ),
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers de la API
    app.include_router(health.router)
    app.include_router(earthquakes.router)
    app.include_router(metrics.router)
    app.include_router(reports.router)

    # Dashboard (interfaz web) — se sirve en la raíz "/"
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        @app.get("/", include_in_schema=False)
        async def dashboard() -> FileResponse:
            return FileResponse(str(STATIC_DIR / "index.html"))

    return app


app = create_app()
