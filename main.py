"""Compatibility shim for the refactored FastAPI app."""

from app.main import app
from app.database import db, reset_conn
