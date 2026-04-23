import logging

from .config import settings


def configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return logging.getLogger(settings.app_name)


logger = configure_logging()
