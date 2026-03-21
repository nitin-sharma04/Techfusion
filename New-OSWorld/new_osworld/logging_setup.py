"""Centralised logging configuration -- initialised once, used everywhere."""

from __future__ import annotations

import datetime
import logging
import os
import sys
from typing import Optional

from new_osworld.config import LoggingConfig


_INITIALISED = False

_ANSI_FORMAT = (
    "\033[1;33m[%(asctime)s \033[31m%(levelname)s "
    "\033[32m%(module)s/%(lineno)d-%(processName)s\033[1;33m] \033[0m%(message)s"
)
_PLAIN_FORMAT = (
    "[%(asctime)s %(levelname)s %(module)s/%(lineno)d-%(processName)s] %(message)s"
)


def setup_logging(cfg: Optional[LoggingConfig] = None) -> None:
    """Configure the root logger with file + stdout handlers.

    Safe to call multiple times -- only the first invocation takes effect.

    Args:
        cfg: Logging section of the application config.  Falls back to
             sensible defaults when *None*.
    """
    global _INITIALISED
    if _INITIALISED:
        return
    _INITIALISED = True

    if cfg is None:
        cfg = LoggingConfig()

    log_dir = cfg.log_dir
    os.makedirs(log_dir, exist_ok=True)

    level = getattr(logging, cfg.level.upper(), logging.INFO)
    timestamp = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fmt = _ANSI_FORMAT if cfg.colored_output else _PLAIN_FORMAT
    formatter = logging.Formatter(fmt=fmt)
    plain_formatter = logging.Formatter(fmt=_PLAIN_FORMAT)

    info_handler = logging.FileHandler(
        os.path.join(log_dir, f"info-{timestamp}.log"), encoding="utf-8"
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(plain_formatter)

    debug_handler = logging.FileHandler(
        os.path.join(log_dir, f"debug-{timestamp}.log"), encoding="utf-8"
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(plain_formatter)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.setFormatter(formatter)
    stdout_handler.addFilter(logging.Filter("osworld"))

    root.addHandler(info_handler)
    root.addHandler(debug_handler)
    root.addHandler(stdout_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``osworld`` namespace.

    Args:
        name: Dot-separated logger name (e.g. ``"env"`` becomes ``"osworld.env"``).
    """
    return logging.getLogger(f"osworld.{name}")
