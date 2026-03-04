"""Minimal logging setup for backend + graph starters."""

from __future__ import annotations

import logging
import os


_CONFIGURED = False


def configure_logging(level: str | None = None) -> None:
    """Configure process-level logging once."""

    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = (level or os.getenv("PR_FLOW_LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)
