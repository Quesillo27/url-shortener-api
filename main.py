"""
url-shortener-api — FastAPI + SQLite
Acortador de URLs con estadísticas de clics, alias personalizados y expiración.
"""

import os
import sqlite3
import hashlib
import string
import random
import threading
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Optional

# Fix for deprecated on_event - use lifespan
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, HttpUrl, field_validator

# ─── Config ──────────────────────────────────────────────────────────────────

DB_PATH = os.environ.get("DB_PATH", "urls.db")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
ALIAS_LENGTH = int(os.environ.get("ALIAS_LENGTH", "6"))
MAX_CLICKS_HISTORY = int(os.environ.get("MAX_CLICKS_HISTORY", "100"))

# ─── Database ────────────────────────────────────────────────────────────────

_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()


def get_conn() -> sqlite3.Connection:
    """Shared SQLite connection (thread-safe via lock)."""
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        if DB_PATH != ":memory:":
            _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


def reset_conn():
    """Reset connection (used in tests)."""
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None


@contextmanager
def db():
    with _lock:
        conn = get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def init_db():
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS urls (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                alias       TEXT    NOT NULL UNIQUE,
                original    TEXT    NOT NULL,
                created_at  TEXT    NOT NULL,
                expires_at  TEXT,
                click_count INTEGER NOT NULL DEFAULT 0,
                is_active   INTEGER NOT NULL DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_urls_alias     ON urls(alias);
            CREATE INDEX IF NOT EXISTS idx_urls_created   ON urls(created_at);
            CREATE INDEX IF NOT EXISTS idx_urls_expires   ON urls(expires_at);

            CREATE TABLE IF NOT EXISTS clicks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                alias       TEXT    NOT NULL,
                clicked_at  TEXT    NOT NULL,
                ip          TEXT,
                user_agent  TEXT,
                referer     TEXT,
                FOREIGN KEY (alias) REFERENCES urls(alias)
            );

            CREATE INDEX IF NOT EXISTS idx_clicks_alias ON clicks(alias);
            CREATE INDEX IF NOT EXISTS idx_clicks_at    ON clicks(clicked_at);
        """)


# ─── App ─────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(application: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="url-shortener-api",
    description="Acortador de URLs con estadísticas de clics, alias personalizados y expiración.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ─── Models ──────────────────────────────────────────────────────────────────

class CreateURLRequest(BaseModel):
    url: str
    alias: Optional[str] = None
    expires_at: Optional[str] = None  # ISO 8601 datetime string

    @field_validator("alias")
    @classmethod
    def alias_valid(cls, v):
        if v is None:
            return v
        allowed = string.ascii_letters + string.digits + "-_"
        if not all(c in allowed for c in v):
            raise ValueError("El alias solo puede contener letras, números, guiones y guiones bajos")
        if len(v) < 3 or len(v) > 50:
            raise ValueError("El alias debe tener entre 3 y 50 caracteres")
        return v

    @field_validator("expires_at")
    @classmethod
    def expires_valid(cls, v):
        if v is None:
            return v
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt <= now:
                raise ValueError("La fecha de expiración debe ser futura")
            return dt.isoformat()
        except ValueError as e:
            raise ValueError(f"Formato de fecha inválido: {e}")


class URLResponse(BaseModel):
    alias: str
    original: str
    short_url: str
    created_at: str
    expires_at: Optional[str]
    click_count: int
    is_active: bool


# ─── Helpers ─────────────────────────────────────────────────────────────────

def generate_alias(url: str, length: int = ALIAS_LENGTH) -> str:
    """Generate a short alias from URL hash + random salt."""
    seed = url + str(random.random())
    h = hashlib.sha256(seed.encode()).hexdigest()
    charset = string.ascii_lowercase + string.digits
    return "".join(charset[int(h[i:i+2], 16) % len(charset)] for i in range(0, length * 2, 2))


def row_to_dict(row) -> dict:
    return dict(row) if row else None


def is_expired(expires_at: Optional[str]) -> bool:
    if not expires_at:
        return False
    try:
        dt = datetime.fromisoformat(expires_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt <= datetime.now(timezone.utc)
    except Exception:
        return False


def build_url_response(row: dict) -> dict:
    return {
        "alias": row["alias"],
        "original": row["original"],
        "short_url": f"{BASE_URL}/{row['alias']}",
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "click_count": row["click_count"],
        "is_active": bool(row["is_active"]),
    }


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM urls").fetchone()[0]
    return {"status": "ok", "total_urls": total}


@app.post("/shorten", status_code=201)
def create_short_url(req: CreateURLRequest):
    """Crea una URL corta. El alias es opcional (se genera automáticamente)."""
    # Validate URL has a scheme
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="La URL debe comenzar con http:// o https://")

    # Generate or use provided alias
    alias = req.alias
    if not alias:
        for _ in range(10):
            candidate = generate_alias(req.url)
            with db() as conn:
                existing = conn.execute("SELECT id FROM urls WHERE alias=?", (candidate,)).fetchone()
            if not existing:
                alias = candidate
                break
        else:
            raise HTTPException(status_code=500, detail="No se pudo generar un alias único")
    else:
        with db() as conn:
            existing = conn.execute("SELECT id FROM urls WHERE alias=?", (alias,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"El alias '{alias}' ya está en uso")

    now = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        conn.execute(
            "INSERT INTO urls (alias, original, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (alias, req.url, now, req.expires_at)
        )

    return {
        "alias": alias,
        "original": req.url,
        "short_url": f"{BASE_URL}/{alias}",
        "created_at": now,
        "expires_at": req.expires_at,
        "click_count": 0,
        "is_active": True,
    }


@app.get("/{alias}")
def redirect(alias: str, request: Request):
    """Redirige a la URL original y registra el clic."""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM urls WHERE alias=? AND is_active=1",
            (alias,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="URL no encontrada o desactivada")

        row = dict(row)
        if is_expired(row.get("expires_at")):
            raise HTTPException(status_code=410, detail="Esta URL ha expirado")

        # Record click
        now = datetime.now(timezone.utc).isoformat()
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")
        ref = request.headers.get("referer")

        conn.execute(
            "INSERT INTO clicks (alias, clicked_at, ip, user_agent, referer) VALUES (?, ?, ?, ?, ?)",
            (alias, now, ip, ua, ref)
        )
        conn.execute(
            "UPDATE urls SET click_count = click_count + 1 WHERE alias=?",
            (alias,)
        )

    return RedirectResponse(url=row["original"], status_code=302)


@app.get("/api/urls", response_model=None)
def list_urls(page: int = 1, limit: int = 20, active_only: bool = False):
    """Lista todas las URLs con paginación."""
    limit = min(100, max(1, limit))
    page = max(1, page)
    offset = (page - 1) * limit

    where = "WHERE is_active=1" if active_only else ""
    with db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM urls {where}").fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM urls {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()

    return {
        "urls": [build_url_response(dict(r)) for r in rows],
        "meta": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }


@app.get("/api/urls/{alias}")
def get_url(alias: str):
    """Obtiene información de una URL por su alias."""
    with db() as conn:
        row = conn.execute("SELECT * FROM urls WHERE alias=?", (alias,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="URL no encontrada")
    return build_url_response(dict(row))


@app.get("/api/urls/{alias}/stats")
def get_stats(alias: str):
    """Estadísticas de clics de una URL: total, por día, últimos clics."""
    with db() as conn:
        url_row = conn.execute("SELECT * FROM urls WHERE alias=?", (alias,)).fetchone()
        if not url_row:
            raise HTTPException(status_code=404, detail="URL no encontrada")

        # Clicks by day (last 30 days)
        daily = conn.execute("""
            SELECT substr(clicked_at, 1, 10) as day, COUNT(*) as count
            FROM clicks
            WHERE alias=?
              AND clicked_at >= datetime('now', '-30 days')
            GROUP BY day
            ORDER BY day DESC
        """, (alias,)).fetchall()

        # Recent clicks
        recent = conn.execute("""
            SELECT clicked_at, ip, user_agent, referer
            FROM clicks
            WHERE alias=?
            ORDER BY clicked_at DESC
            LIMIT ?
        """, (alias, MAX_CLICKS_HISTORY)).fetchall()

    url = dict(url_row)
    return {
        "alias": alias,
        "original": url["original"],
        "total_clicks": url["click_count"],
        "created_at": url["created_at"],
        "expires_at": url["expires_at"],
        "clicks_by_day": [{"day": r["day"], "count": r["count"]} for r in daily],
        "recent_clicks": [
            {
                "clicked_at": r["clicked_at"],
                "ip": r["ip"],
                "user_agent": r["user_agent"],
                "referer": r["referer"]
            }
            for r in recent
        ]
    }


@app.delete("/api/urls/{alias}")
def deactivate_url(alias: str):
    """Desactiva (borra lógicamente) una URL."""
    with db() as conn:
        row = conn.execute("SELECT id FROM urls WHERE alias=?", (alias,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="URL no encontrada")
        conn.execute("UPDATE urls SET is_active=0 WHERE alias=?", (alias,))
    return {"deleted": True, "alias": alias}


@app.get("/api/stats/global")
def global_stats():
    """Estadísticas globales del servicio."""
    with db() as conn:
        total_urls = conn.execute("SELECT COUNT(*) FROM urls").fetchone()[0]
        active_urls = conn.execute("SELECT COUNT(*) FROM urls WHERE is_active=1").fetchone()[0]
        total_clicks = conn.execute("SELECT SUM(click_count) FROM urls").fetchone()[0] or 0
        top_urls = conn.execute("""
            SELECT alias, original, click_count
            FROM urls WHERE is_active=1
            ORDER BY click_count DESC
            LIMIT 5
        """).fetchall()

    return {
        "total_urls": total_urls,
        "active_urls": active_urls,
        "total_clicks": total_clicks,
        "top_urls": [dict(r) for r in top_urls]
    }
