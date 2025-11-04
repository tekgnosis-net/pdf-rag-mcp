import logging
from typing import Optional

from .config import Settings


def configure_logging(settings: Optional[Settings] = None) -> None:
    """Configure the global logging output for the service."""
    level = logging.INFO
    if settings:
        level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
