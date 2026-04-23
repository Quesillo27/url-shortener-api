import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str = os.environ.get("DB_PATH", "urls.db")
    base_url: str = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
    alias_length: int = int(os.environ.get("ALIAS_LENGTH", "6"))
    max_clicks_history: int = int(os.environ.get("MAX_CLICKS_HISTORY", "100"))
    version: str = "1.1.0"
    app_name: str = "url-shortener-api"
    log_level: str = os.environ.get("LOG_LEVEL", "INFO").upper()
    rate_limit_window_seconds: int = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))
    rate_limit_max_requests: int = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", "120"))


settings = Settings()
