from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import monotonic

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse

from .config import settings
from .database import db, init_db
from .logger import logger
from .schemas import CreateURLRequest, UpdateURLRequest
from .services import create_short_url, deactivate_url, get_url_or_404, get_url_stats, global_stats, list_urls, record_redirect, update_url


START_TIME = datetime.now(timezone.utc)
REQUEST_COUNT = 0
ERROR_COUNT = 0
LATENCY_TOTAL_MS = 0.0
RATE_BUCKETS = defaultdict(deque)


@asynccontextmanager
async def lifespan(application: FastAPI):
    init_db()
    logger.info("service_started version=%s db_path=%s", settings.version, settings.db_path)
    yield


app = FastAPI(
    title=settings.app_name,
    description="Acortador de URLs con estadisticas de clics, alias personalizados y expiracion.",
    version=settings.version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.middleware("http")
async def metrics_and_security(request: Request, call_next):
    global REQUEST_COUNT, ERROR_COUNT, LATENCY_TOTAL_MS

    client_ip = request.client.host if request.client else "unknown"
    bucket = RATE_BUCKETS[client_ip]
    current_time = monotonic()
    window_start = current_time - settings.rate_limit_window_seconds
    while bucket and bucket[0] < window_start:
        bucket.popleft()
    if len(bucket) >= settings.rate_limit_max_requests:
        raise HTTPException(status_code=429, detail="Demasiadas solicitudes, intenta de nuevo en un minuto")
    bucket.append(current_time)

    started_at = monotonic()
    REQUEST_COUNT += 1
    response = await call_next(request)
    elapsed_ms = (monotonic() - started_at) * 1000
    LATENCY_TOTAL_MS += elapsed_ms
    if response.status_code >= 400:
        ERROR_COUNT += 1

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
def health():
    with db() as conn:
        total_urls = conn.execute("SELECT COUNT(*) FROM urls").fetchone()[0]
    avg_latency_ms = round(LATENCY_TOTAL_MS / REQUEST_COUNT, 2) if REQUEST_COUNT else 0.0
    return {
        "status": "ok",
        "version": settings.version,
        "uptime_seconds": int((datetime.now(timezone.utc) - START_TIME).total_seconds()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "db": "connected",
        "metrics": {
            "total_urls": total_urls,
            "requests_total": REQUEST_COUNT,
            "errors_total": ERROR_COUNT,
            "average_latency_ms": avg_latency_ms,
        },
    }


@app.post("/shorten", status_code=201)
def create_short_url_route(request_data: CreateURLRequest):
    return create_short_url(request_data.url, request_data.alias, request_data.expires_at)


@app.get("/api/urls")
def list_urls_route(page: int = 1, limit: int = 20, active_only: bool = False, search: str | None = None, include_expired: bool = True):
    return list_urls(page, limit, active_only, search, include_expired)


@app.get("/api/urls/{alias}")
def get_url_route(alias: str):
    return update_url(alias, None, None, None)


@app.patch("/api/urls/{alias}")
def update_url_route(alias: str, payload: UpdateURLRequest):
    if payload.url is None and payload.expires_at is None and payload.is_active is None:
        raise HTTPException(status_code=422, detail="Debes enviar al menos un campo para actualizar")
    return update_url(alias, payload.url, payload.expires_at, payload.is_active)


@app.get("/api/urls/{alias}/stats")
def get_stats_route(alias: str):
    return get_url_stats(alias)


@app.delete("/api/urls/{alias}")
def deactivate_url_route(alias: str):
    return deactivate_url(alias)


@app.get("/api/stats/global")
def global_stats_route():
    return global_stats()


@app.get("/{alias}")
def redirect(alias: str, request: Request):
    destination = record_redirect(alias, request)
    return RedirectResponse(url=destination, status_code=302)
