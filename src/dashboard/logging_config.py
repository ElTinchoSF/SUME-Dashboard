"""
Centralized logging configuration for SUME Dashboard.

Provides a consistent logging setup with file + console output,
structured format, and log level controlled via environment variable.
"""

import logging
import os
import sys
from pathlib import Path


def setup_logging() -> logging.Logger:
    """
    Configure application-wide logging.

    Returns the root logger for the SUME dashboard package.
    Log level is controlled by SUME_LOG_LEVEL env var (default: INFO).
    Logs go to both stderr and a file at logs/sume-dashboard.log.
    """
    log_level = os.environ.get("SUME_LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    # Create logs directory relative to project root
    project_root = Path(__file__).resolve().parent.parent.parent
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "sume-dashboard.log"

    # Root logger for the project
    root_logger = logging.getLogger("sume")
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers on re-run
    if root_logger.handlers:
        return root_logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (rotating by size would be ideal, but keeping simple for now)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    root_logger.info("Logging initialized — level=%s, file=%s", log_level, log_file)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the 'sume' namespace."""
    return logging.getLogger(f"sume.{name}")
