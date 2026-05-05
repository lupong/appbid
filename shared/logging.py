"""Rich-formatted structured logging setup for Credit App+."""
from __future__ import annotations

import logging

from rich.console import Console
from rich.logging import RichHandler

from shared.config import get_settings

_configured = False


def setup_logging(level: str | None = None) -> None:
    """Idempotent rich-handler logging setup. Call once at process start."""
    global _configured
    if _configured:
        return
    settings = get_settings()
    log_level = (level or settings.log_level).upper()
    handler = RichHandler(
        console=Console(stderr=True),
        rich_tracebacks=True,
        markup=False,
        show_path=False,
    )
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[handler],
        force=True,
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
