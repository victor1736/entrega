"""DAG de Airflow: genera un reporte consolidado por hora.

Se ejecuta cada hora (@hourly). Para cada intervalo:
1. Lee los eventos sísmicos almacenados en la ventana horaria correspondiente.
2. Genera un reporte consolidado (total, promedio, máximo, top ubicaciones).
3. Persiste el resultado en la colección ``hourly_reports`` (upsert idempotente).

Usa PyMongo (síncrono) por ser el patrón natural en tareas de Airflow, y
reutiliza los helpers de dominio del paquete ``src`` (montado en el contenedor).
"""
from __future__ import annotations

import logging
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

import pendulum
from airflow.decorators import dag, task
from pymongo import MongoClient

# Helpers de dominio compartidos (src se monta en /opt/airflow/src)
from src.config.constants import (
    COLLECTION_EARTHQUAKES,
    COLLECTION_HOURLY_REPORTS,
    HOUR_WINDOW_FORMAT,
)
from src.utils.locations import extract_region

log = logging.getLogger(__name__)

TOP_LOCATIONS_LIMIT = 3


def _mongo_uri() -> str:
    uri = os.getenv("MONGO_URI")
    if uri:
        return uri
    user = os.getenv("MONGO_INITDB_ROOT_USERNAME", "seismic")
    pwd = os.getenv("MONGO_INITDB_ROOT_PASSWORD", "seismic_secret_change_me")
    host = os.getenv("MONGO_HOST", "mongodb")
    port = os.getenv("MONGO_PORT", "27017")
    return f"mongodb://{user}:{pwd}@{host}:{port}/?authSource=admin"


@dag(
    dag_id="hourly_seismic_report",
    schedule="@hourly",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["seismic", "reporting"],
    doc_md=__doc__,
)
def hourly_seismic_report():
    @task
    def generate_report(data_interval_start=None) -> dict:
        # Ventana horaria a reportar (hora del intervalo de datos)
        window_dt: datetime = (data_interval_start or pendulum.now("UTC")).in_timezone("UTC")
        window = window_dt.strftime(HOUR_WINDOW_FORMAT)
        log.info("Generando reporte para la ventana %s", window)

        client = MongoClient(_mongo_uri(), serverSelectionTimeoutMS=5000)
        try:
            db = client[os.getenv("MONGO_DB", "seismic")]
            pipeline = [
                {"$match": {"window": window}},
                {
                    "$group": {
                        "_id": "$window",
                        "earthquake_count": {"$sum": 1},
                        "avg_magnitude": {"$avg": "$magnitude"},
                        "max_magnitude": {"$max": "$magnitude"},
                        "locations": {"$push": "$location"},
                    }
                },
            ]
            docs = list(db[COLLECTION_EARTHQUAKES].aggregate(pipeline))

            if not docs:
                log.info("Sin eventos para la ventana %s; no se genera reporte", window)
                return {"window": window, "total_events": 0}

            agg = docs[0]
            regions = [
                r for r in (extract_region(loc) for loc in agg.get("locations", [])) if r
            ]
            top = [name for name, _ in Counter(regions).most_common(TOP_LOCATIONS_LIMIT)]
            avg = agg.get("avg_magnitude")

            report = {
                "window": window,
                "report_date": datetime.strptime(window, HOUR_WINDOW_FORMAT).replace(
                    tzinfo=timezone.utc
                ),
                "total_events": agg.get("earthquake_count", 0),
                "average_magnitude": round(avg, 2) if avg is not None else None,
                "max_magnitude": agg.get("max_magnitude"),
                "top_locations": top,
                "generated_at": datetime.now(timezone.utc),
            }

            db[COLLECTION_HOURLY_REPORTS].update_one(
                {"window": window}, {"$set": report}, upsert=True
            )
            log.info(
                "Reporte persistido: %s eventos, top=%s",
                report["total_events"],
                top,
            )
            return {"window": window, "total_events": report["total_events"]}
        finally:
            client.close()

    generate_report()


hourly_seismic_report()
