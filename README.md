# Plataforma de Procesamiento de Eventos Sísmicos en Tiempo Real

Plataforma que consume eventos sísmicos de la API pública de **USGS**, los
procesa en *near real-time*, los almacena en **MongoDB** y genera reportes
horarios con **Airflow**, exponiendo todo mediante una **API REST (FastAPI)**
y un **dashboard web**. Se ejecuta por completo con **Docker Compose**.

---

## Tabla de contenido

- [Arquitectura](#arquitectura)
- [Stack tecnológico](#stack-tecnológico)
- [Requisitos previos](#requisitos-previos)
- [Puesta en marcha](#puesta-en-marcha)
- [Servicios y puertos](#servicios-y-puertos)
- [API REST](#api-rest)
- [Modelo de datos y decisiones](#modelo-de-datos-y-decisiones)
- [Procesamiento en tiempo real](#procesamiento-en-tiempo-real)
- [Airflow](#airflow)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Variables de entorno](#variables-de-entorno)
- [Bonificaciones cubiertas](#bonificaciones-cubiertas)

---

## Arquitectura

El diagrama completo (Mermaid) está en [`docs/architecture.md`](docs/architecture.md).

```
USGS feed ──> Ingesta (cada 3 min) ──> MongoDB ──> API REST ──> Dashboard
                     │                    ▲            │
                     └─> Procesamiento ───┘            │
                         (métricas RT)                 │
             Airflow (@hourly) ──> hourly_reports ─────┘
```

Componentes desacoplados:

- **Servicio de ingesta** (`src/ingestion_main.py`): worker que sondea la API,
  deduplica y persiste.
- **Procesamiento en tiempo real** (`ProcessingService`): recalcula métricas de
  las ventanas afectadas apenas llegan eventos nuevos.
- **API REST** (`src/api`): consultas con filtros, paginación y ordenamiento.
- **Airflow** (`airflow/dags`): consolida reportes por hora.
- **MongoDB**: persistencia con índices optimizados.

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| API | FastAPI + Uvicorn |
| Validación | Pydantic v2 / pydantic-settings |
| Base de datos | MongoDB 7 (driver async Motor) |
| Orquestación | Apache Airflow 2.10 |
| Cliente HTTP | httpx + tenacity (reintentos) |
| Logging | Estructurado en JSON (python-json-logger) |
| Contenedores | Docker + Docker Compose |

## Requisitos previos

- Docker y Docker Compose v2 (`docker compose version`).
- Puertos libres: `8000` (API), `8080` (Airflow), `27017` (MongoDB).

## Puesta en marcha

```bash
# 1. Clonar el repositorio
git clone <url-del-repo> && cd <repo>

# 2. Crear el archivo de entorno a partir del ejemplo
cp .env.example .env
#    (opcional) editar credenciales/URI en .env

# 3. Levantar toda la plataforma
docker compose up --build
```

Al arrancar:

- La **API** queda en <http://localhost:8000> y el **dashboard** en la raíz `/`.
- La documentación interactiva (Swagger) en <http://localhost:8000/docs>.
- **Airflow** en <http://localhost:8080> (usuario `admin` / contraseña `admin`).
- El servicio de **ingesta** empieza a consultar USGS cada 3 minutos.

> Los primeros datos aparecen tras el primer ciclo de ingesta. Si el feed de la
> última hora tiene pocos sismos, es normal ver pocas filas al inicio.

Para detener y limpiar:

```bash
docker compose down          # detiene
docker compose down -v        # detiene y elimina volúmenes (datos)
```

## Servicios y puertos

| Servicio | Contenedor | Puerto | Descripción |
|----------|-----------|--------|-------------|
| MongoDB | `seismic-mongodb` | 27017 | Base de datos |
| API REST | `seismic-api` | 8000 | API + dashboard |
| Ingesta | `seismic-ingestion` | — | Worker cada 3 min |
| Airflow | `seismic-airflow` | 8080 | Scheduler + webserver |
| Postgres | `seismic-airflow-db` | — | Metadatos de Airflow |

## API REST

Base URL: `http://localhost:8000`. Se incluye la colección
[`postman_collection.json`](postman_collection.json).

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Estado del servicio y de MongoDB |
| GET | `/earthquakes` | Lista de eventos (filtros, paginación, orden) |
| GET | `/metrics` | Métricas por ventana horaria |
| GET | `/metrics/summary` | Resumen global (cacheado con TTL) |
| GET | `/metrics/{window}` | Métrica de una ventana concreta |
| GET | `/reports` | Reportes horarios consolidados |
| POST | `/reports/generate/{window}` | Genera/regenera un reporte bajo demanda |

### Parámetros de `/earthquakes`

| Parámetro | Tipo | Ejemplo | Descripción |
|-----------|------|---------|-------------|
| `min_magnitude` / `max_magnitude` | float | `2.5` | Filtro por magnitud |
| `start_time` / `end_time` | ISO-8601 | `2026-06-17T00:00:00Z` | Rango temporal |
| `location` | string | `California` | Búsqueda parcial (case-insensitive) |
| `window` | string | `2026-06-17T10` | Ventana horaria exacta |
| `sort_by` | enum | `event_time` | `event_time`, `magnitude`, `ingested_at` |
| `sort_dir` | enum | `desc` | `asc`, `desc` |
| `page` / `page_size` | int | `1` / `20` | Paginación (máx. 200) |

Ejemplo:

```bash
curl "http://localhost:8000/earthquakes?min_magnitude=4&sort_by=magnitude&sort_dir=desc&page=1&page_size=10"
```

## Modelo de datos y decisiones

Colecciones (detalle e índices en [`docs/architecture.md`](docs/architecture.md)):

- **`earthquakes`** — eventos normalizados. Índice **único** en `event_id`
  (deduplicación garantizada por la BD), más índices en `event_time`, `window`
  y `magnitude` para acelerar filtros y agregaciones.
- **`metrics`** — métricas por ventana horaria. Índice **único** en `window`.
- **`hourly_reports`** — reportes por hora. Índice **único** en `window`.

**Por qué MongoDB:** cada evento es un documento autocontenido, de esquema
flexible; el patrón de escritura es *upsert idempotente* y las lecturas son
agregaciones por ventana temporal, resueltas eficientemente con el
*aggregation pipeline* e índices compuestos. No hay relaciones que justifiquen
un modelo relacional.

## Procesamiento en tiempo real

Cada evento nuevo dispara el recálculo de las métricas de su ventana horaria:

- Cantidad de sismos por hora.
- Magnitud promedio, máxima y mínima.
- **Distribución por rangos de magnitud** (clasificación tipo Richter):
  `micro` (<2), `minor` (2–4), `light` (4–5), `moderate` (5–6), `strong` (6–7),
  `major` (7–8), `great` (≥8).

## Airflow

DAG `hourly_seismic_report` (`airflow/dags/hourly_report_dag.py`), programado
`@hourly`:

1. Lee los eventos de la ventana horaria correspondiente.
2. Genera un reporte consolidado (total, promedio, máximo, top 3 ubicaciones).
3. Persiste el resultado en `hourly_reports` (upsert idempotente).

Para ejecutarlo manualmente: entra a <http://localhost:8080>, activa/dispara el
DAG `hourly_seismic_report`. También puedes generar un reporte al instante con
`POST /reports/generate/{window}`.

## Estructura del proyecto

```
.
├── docker-compose.yml          # Orquestación de todos los servicios
├── requirements.txt
├── .env.example                # Plantilla de configuración (sin secretos)
├── deploy/Dockerfile           # Imagen de API e ingesta
├── docs/architecture.md        # Diagrama y decisiones
├── postman_collection.json     # Colección Postman
├── airflow/dags/               # DAG horario de reportes
└── src/
    ├── config/                 # settings, logging, constantes
    ├── models/                 # modelos Pydantic (dominio)
    ├── database/               # conexión, índices, repositorios
    ├── clients/                # cliente USGS
    ├── services/               # ingesta, procesamiento, métricas, reportes
    ├── api/                    # FastAPI: rutas, esquemas, dependencias
    ├── static/                 # dashboard web
    ├── utils/                  # caché TTL, utilidades
    └── ingestion_main.py       # entrypoint del worker de ingesta
```

## Explicación de cada archivo

### Raíz del proyecto

| Archivo | Qué hace |
|---------|----------|
| `docker-compose.yml` | Orquesta todos los contenedores (MongoDB, API, ingesta, Airflow y su Postgres), sus redes, volúmenes y variables. Es el único comando de arranque. |
| `requirements.txt` | Dependencias de Python de la API y del worker de ingesta. |
| `.env.example` | Plantilla de configuración. Se copia a `.env`; **no contiene secretos reales**. |
| `.gitignore` | Excluye entornos virtuales, cachés, logs y datos de MongoDB del repositorio. |
| `postman_collection.json` | Colección Postman con todos los endpoints listos para probar. |
| `README.md` | Este documento. |

### `deploy/`

| Archivo | Qué hace |
|---------|----------|
| `deploy/Dockerfile` | Imagen base (Python 3.12 slim) compartida por la API y la ingesta. Instala dependencias, copia `src/` y ejecuta como usuario no root. |

### `docs/`

| Archivo | Qué hace |
|---------|----------|
| `docs/architecture.md` | Diagrama de arquitectura (Mermaid), flujo de datos y justificación del modelado de datos e índices. |

### `airflow/`

| Archivo | Qué hace |
|---------|----------|
| `airflow/dags/hourly_report_dag.py` | DAG que corre **cada hora**: lee los eventos de la ventana horaria, genera el reporte consolidado (total, promedio, máximo, top 3 ubicaciones) y lo guarda en `hourly_reports`. |

### `src/config/` — Configuración

| Archivo | Qué hace |
|---------|----------|
| `settings.py` | Configuración tipada con `pydantic-settings`. Lee variables de entorno y construye la URI de MongoDB. Singleton cacheado. |
| `logging_config.py` | Configura **logging estructurado en JSON** (o consola). Se aplica una sola vez en toda la app. |
| `constants.py` | Nombres de colecciones, formato de ventana horaria y **rangos de magnitud** (clasificación Richter) con las funciones `magnitude_bucket()` y `empty_distribution()`. |

### `src/models/` — Modelos de dominio (Pydantic)

| Archivo | Qué hace |
|---------|----------|
| `earthquake.py` | Modelo `Earthquake`: evento sísmico normalizado. Valida rangos de lat/lon y normaliza fechas a UTC. |
| `metric.py` | Modelo `Metric`: métricas agregadas por ventana horaria (conteo, promedio, máx, mín, distribución). |
| `report.py` | Modelo `HourlyReport`: reporte consolidado por hora. |

### `src/database/` — Persistencia

| Archivo | Qué hace |
|---------|----------|
| `mongodb.py` | Cliente **Motor** (async) singleton con *connection pooling*. Funciones `connect()`, `get_database()` y `close_database()`. |
| `indexes.py` | Crea los índices de forma idempotente al arrancar (únicos y compuestos). Documenta la justificación de cada uno. |
| `repositories.py` | Patrón **Repository**: única capa que conoce MongoDB. `EarthquakeRepository`, `MetricRepository` y `ReportRepository` encapsulan las consultas y agregaciones. |

### `src/clients/` — Integraciones externas

| Archivo | Qué hace |
|---------|----------|
| `usgs_client.py` | Cliente HTTP asíncrono (`httpx`) del feed USGS, con **reintentos y backoff exponencial** (`tenacity`). Solo descarga el GeoJSON crudo. |

### `src/services/` — Lógica de negocio

| Archivo | Qué hace |
|---------|----------|
| `transformer.py` | Convierte cada *feature* GeoJSON de USGS al modelo interno `Earthquake` y deriva la ventana horaria. Descarta *features* inválidos con log. |
| `ingestion_service.py` | Orquesta la ingesta: descarga → transforma → **detecta duplicados** → *upsert* → dispara el procesamiento en tiempo real. |
| `processing_service.py` | **Procesamiento en tiempo real**: recalcula las métricas de las ventanas afectadas apenas llegan eventos nuevos. |
| `metrics_service.py` | Consulta de métricas para la API (listado con filtros y resumen global). |
| `reporting_service.py` | Genera y consulta reportes horarios. Lógica de consolidación y ranking de ubicaciones. |

### `src/api/` — API REST (FastAPI)

| Archivo | Qué hace |
|---------|----------|
| `main.py` | Crea la app FastAPI, gestiona el ciclo de vida (conexión + índices + caché), registra los routers y **sirve el dashboard**. |
| `dependencies.py` | Inyección de dependencias: ensambla repositorios y servicios a partir de la conexión a la BD. |
| `schemas.py` | Esquemas Pydantic de request/response: enums de ordenamiento, paginación genérica y modelos de salida. |
| `routes/earthquakes.py` | `GET /earthquakes` con filtros (magnitud, tiempo, ubicación, ventana), paginación y ordenamiento. |
| `routes/metrics.py` | `GET /metrics`, `/metrics/summary` (cacheado) y `/metrics/{window}`. |
| `routes/reports.py` | `GET /reports` y `POST /reports/generate/{window}` (generación bajo demanda). |
| `routes/health.py` | `GET /health`: verifica la conectividad con MongoDB. |

### `src/static/` — Dashboard web

| Archivo | Qué hace |
|---------|----------|
| `index.html` | Estructura del dashboard: KPIs, gráficos y tablas. |
| `styles.css` | Estilos (tema oscuro, fondo animado, tarjetas *glass*, responsive). |
| `app.js` | Consume la API, pinta los KPIs, gráficos (Chart.js) y tablas, y **auto-refresca cada 30 s**. |

### `src/utils/` — Utilidades

| Archivo | Qué hace |
|---------|----------|
| `cache.py` | `TTLCache`: caché en memoria con expiración por tiempo (estrategia de caché). |
| `locations.py` | `extract_region()`: deriva la región legible del campo `place` de USGS para el ranking `top_locations`. |

### Entrypoint

| Archivo | Qué hace |
|---------|----------|
| `src/ingestion_main.py` | Proceso del **worker de ingesta**: loop asíncrono que ejecuta un ciclo cada 3 minutos, con apagado limpio ante señales. |

## Variables de entorno

Todas se definen en `.env` (ver `.env.example`). **No hay credenciales en el
código.** Las principales:

| Variable | Por defecto | Descripción |
|----------|-------------|-------------|
| `MONGO_INITDB_ROOT_USERNAME` / `_PASSWORD` | `seismic` / `***` | Credenciales MongoDB |
| `MONGO_DB` | `seismic` | Base de datos |
| `USGS_FEED_URL` | *(feed all_hour)* | Fuente de datos |
| `INGESTION_INTERVAL_SECONDS` | `180` | Frecuencia de sondeo (3 min) |
| `CACHE_TTL_SECONDS` | `30` | TTL de la caché del resumen |
| `LOG_FORMAT` | `json` | `json` o `console` |

## Bonificaciones cubiertas

- **Nivel 1**: Pydantic v2 (modelos y validación de parámetros), logging
  estructurado en JSON, modularización y principios SOLID, gestión eficiente de
  conexiones (pool Motor singleton) y estrategia de caché (TTL en memoria).
- **Base para Nivel 3/4**: arquitectura orientada a eventos y separación clara
  entre ingesta, procesamiento y reportería, lista para incorporar colas
  (Kafka/RabbitMQ) o WebSockets sin reescribir el núcleo.
