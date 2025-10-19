"""
Unified Logging Configuration for ReDNA

Provides consistent JSON-structured logging across all services with
centralized log location and configurable levels.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# Unified log directory
LOG_DIR = Path(os.getenv("LOG_DIR", ".run/logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.

    Outputs logs in JSON format for easy parsing and analysis.
    """

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "service": self.service_name,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "req_id"):
            log_data["req_id"] = record.req_id
        if hasattr(record, "event"):
            log_data["event"] = record.event

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add any extra kwargs passed to logger
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data)


def configure_logging(
    service_name: str,
    level: str = "INFO",
    log_file: Optional[Path] = None,
    console: bool = True
) -> logging.Logger:
    """
    Configure unified logging for a service.

    Args:
        service_name: Name of the service (e.g., "core", "ucnrr", "devx")
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional custom log file path. If None, uses {LOG_DIR}/{service_name}.jsonl
        console: Whether to also log to console (default: True)

    Returns:
        Configured root logger
    """
    # Determine log file path
    if log_file is None:
        log_file = LOG_DIR / f"{service_name}.jsonl"

    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create JSON formatter
    json_formatter = JSONFormatter(service_name)

    # File handler (JSON)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)

    # Console handler (human-readable)
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    root_logger.info(
        f"Logging configured for {service_name}",
        extra={"event": "logging_init", "log_file": str(log_file)}
    )

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    event: str,
    level: str = "INFO",
    **kwargs: Any
) -> None:
    """
    Log a structured event with additional context.

    Args:
        logger: Logger instance
        event: Event name (e.g., "ingest_start", "resolve_complete")
        level: Log level
        **kwargs: Additional context fields (user_id, req_id, etc.)
    """
    log_level = getattr(logging, level.upper())
    extra = {"event": event, "extra_data": kwargs}

    logger.log(log_level, f"{event}", extra=extra)


# Default configuration for backward compatibility
def setup_default_logging(service_name: str = "core") -> None:
    """
    Setup default logging configuration.

    This is called automatically on import for backward compatibility.
    """
    log_level = os.getenv("LOG_LEVEL", "INFO")
    configure_logging(service_name, level=log_level)


# Example usage context manager
class LogContext:
    """
    Context manager for adding context to log records.

    Usage:
        with LogContext(user_id="TEST", req_id="abc123"):
            logger.info("Processing request")
            # Logs will include user_id and req_id
    """

    def __init__(self, **context: Any):
        self.context = context
        self.old_factory = None

    def __enter__(self):
        self.old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.old_factory:
            logging.setLogRecordFactory(self.old_factory)
