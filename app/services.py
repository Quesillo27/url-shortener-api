import hashlib
import random
import string
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, Request

from .config import settings
from .database import db


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_url(value: str) -> str:
    if not value.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="La URL debe comenzar con http:// o https://")
    if value.count(".") == 0:
        raise HTTPException(status_code=422, detail="La URL debe incluir un dominio valido")
    return value


def generate_alias(url: str, length: int = settings.alias_length) -> str:
    seed = url + str(random.random())
    digest = hashlib.sha256(seed.encode()).hexdigest()
    charset = string.ascii_lowercase + string.digits
    return "".join(charset[int(digest[index:index + 2], 16) % len(charset)] for index in range(0, length * 2, 2))


def is_expired(expires_at: Optional[str]) -> bool:
    if not expires_at:
        return False
    try:
        parsed = datetime.fromisoformat(expires_at)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed <= datetime.now(timezone.utc)
    except Exception:
        return False


def build_url_response(row: dict) -> dict:
    return {
        "alias": row["alias"],
        "original": row["original"],
        "short_url": f"{settings.base_url}/{row['alias']}",
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "click_count": row["click_count"],
        "is_active": bool(row["is_active"]),
    }


def create_short_url(url: str, alias: Optional[str], expires_at: Optional[str]) -> dict:
    validate_url(url)
    selected_alias = alias

    if not selected_alias:
        for _ in range(10):
            candidate = generate_alias(url)
            with db() as conn:
                existing = conn.execute("SELECT id FROM urls WHERE alias=?", (candidate,)).fetchone()
            if not existing:
                selected_alias = candidate
                break
        else:
            raise HTTPException(status_code=500, detail="No se pudo generar un alias unico")
    else:
        with db() as conn:
            existing = conn.execute("SELECT id FROM urls WHERE alias=?", (selected_alias,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"El alias '{selected_alias}' ya esta en uso")

    created_at = utc_now_iso()
    with db() as conn:
        conn.execute(
            "INSERT INTO urls (alias, original, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (selected_alias, url, created_at, expires_at),
        )

    return {
        "alias": selected_alias,
        "original": url,
        "short_url": f"{settings.base_url}/{selected_alias}",
        "created_at": created_at,
        "expires_at": expires_at,
        "click_count": 0,
        "is_active": True,
    }


def get_url_or_404(alias: str) -> dict:
    with db() as conn:
        row = conn.execute("SELECT * FROM urls WHERE alias=?", (alias,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="URL no encontrada")
    return dict(row)


def list_urls(page: int, limit: int, active_only: bool, search: Optional[str], include_expired: bool) -> dict:
    safe_limit = min(100, max(1, limit))
    safe_page = max(1, page)
    offset = (safe_page - 1) * safe_limit

    clauses = []
    params = []
    if active_only:
        clauses.append("is_active=1")
    if search:
        clauses.append("(alias LIKE ? OR original LIKE ?)")
        pattern = f"%{search.strip()}%"
        params.extend([pattern, pattern])
    if not include_expired:
        clauses.append("(expires_at IS NULL OR expires_at > ?)")
        params.append(utc_now_iso())

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM urls {where}", tuple(params)).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM urls {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            tuple(params + [safe_limit, offset]),
        ).fetchall()

    return {
        "urls": [build_url_response(dict(row)) for row in rows],
        "meta": {
            "page": safe_page,
            "limit": safe_limit,
            "total": total,
            "pages": (total + safe_limit - 1) // safe_limit,
            "search": search or "",
            "include_expired": include_expired,
        },
    }


def record_redirect(alias: str, request: Request) -> str:
    with db() as conn:
        row = conn.execute("SELECT * FROM urls WHERE alias=? AND is_active=1", (alias,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="URL no encontrada o desactivada")
        url_row = dict(row)
        if is_expired(url_row.get("expires_at")):
            raise HTTPException(status_code=410, detail="Esta URL ha expirado")

        conn.execute(
            "INSERT INTO clicks (alias, clicked_at, ip, user_agent, referer) VALUES (?, ?, ?, ?, ?)",
            (
                alias,
                utc_now_iso(),
                request.client.host if request.client else None,
                request.headers.get("user-agent"),
                request.headers.get("referer"),
            ),
        )
        conn.execute("UPDATE urls SET click_count = click_count + 1 WHERE alias=?", (alias,))

    return url_row["original"]


def update_url(
    alias: str,
    url: Optional[str],
    expires_at: Optional[str],
    is_active: Optional[bool],
    provided_fields: Optional[set[str]] = None,
) -> dict:
    current = get_url_or_404(alias)
    provided_fields = provided_fields or set()
    updates = {
        "original": validate_url(url) if "url" in provided_fields else current["original"],
        "expires_at": expires_at if "expires_at" in provided_fields else current["expires_at"],
        "is_active": int(is_active if "is_active" in provided_fields else bool(current["is_active"])),
    }

    with db() as conn:
        conn.execute(
            "UPDATE urls SET original=?, expires_at=?, is_active=? WHERE alias=?",
            (updates["original"], updates["expires_at"], updates["is_active"], alias),
        )

    current.update(updates)
    return build_url_response(current)


def deactivate_url(alias: str) -> dict:
    get_url_or_404(alias)
    with db() as conn:
        conn.execute("UPDATE urls SET is_active=0 WHERE alias=?", (alias,))
    return {"deleted": True, "alias": alias}


def get_url_stats(alias: str) -> dict:
    url_row = get_url_or_404(alias)
    with db() as conn:
        daily = conn.execute(
            """
            SELECT substr(clicked_at, 1, 10) AS day, COUNT(*) AS count
            FROM clicks
            WHERE alias=? AND clicked_at >= datetime('now', '-30 days')
            GROUP BY day
            ORDER BY day DESC
            """,
            (alias,),
        ).fetchall()
        recent = conn.execute(
            """
            SELECT clicked_at, ip, user_agent, referer
            FROM clicks
            WHERE alias=?
            ORDER BY clicked_at DESC
            LIMIT ?
            """,
            (alias, settings.max_clicks_history),
        ).fetchall()

    return {
        "alias": alias,
        "original": url_row["original"],
        "total_clicks": url_row["click_count"],
        "created_at": url_row["created_at"],
        "expires_at": url_row["expires_at"],
        "last_click_at": recent[0]["clicked_at"] if recent else None,
        "clicks_by_day": [{"day": row["day"], "count": row["count"]} for row in daily],
        "recent_clicks": [dict(row) for row in recent],
    }


def global_stats() -> dict:
    with db() as conn:
        total_urls = conn.execute("SELECT COUNT(*) FROM urls").fetchone()[0]
        active_urls = conn.execute("SELECT COUNT(*) FROM urls WHERE is_active=1").fetchone()[0]
        expired_urls = conn.execute("SELECT COUNT(*) FROM urls WHERE expires_at IS NOT NULL AND expires_at <= ?", (utc_now_iso(),)).fetchone()[0]
        total_clicks = conn.execute("SELECT SUM(click_count) FROM urls").fetchone()[0] or 0
        top_urls = conn.execute(
            """
            SELECT alias, original, click_count
            FROM urls
            WHERE is_active=1
            ORDER BY click_count DESC, created_at DESC
            LIMIT 5
            """
        ).fetchall()

    return {
        "total_urls": total_urls,
        "active_urls": active_urls,
        "expired_urls": expired_urls,
        "total_clicks": total_clicks,
        "top_urls": [dict(row) for row in top_urls],
    }
