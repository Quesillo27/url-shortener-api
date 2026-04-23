import sqlite3
import threading
from contextlib import contextmanager
from typing import Optional

from .config import settings


_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(settings.db_path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        if settings.db_path != ":memory:":
            _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


def reset_conn() -> None:
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


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
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
            CREATE INDEX IF NOT EXISTS idx_urls_active    ON urls(is_active);

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
            """
        )
