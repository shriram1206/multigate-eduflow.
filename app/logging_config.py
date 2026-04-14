"""
app/logging_config.py
─────────────────────
Structured JSON logging for MEF Portal.

  • Development  → human-readable output to stderr
  • Production   → JSON output to stderr + rotating file (logs/mefportal.log)
  • Test         → file handler skipped (no disk I/O)

Usage:
    from app.logging_config import configure_logging
    configure_logging(app)
"""

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Formats every log record as a single-line JSON object."""

    # Keys that exist on every LogRecord — we skip these to avoid noise
    _SKIP = frozenset({
        "args", "asctime", "created", "exc_info", "exc_text", "filename",
        "funcName", "levelname", "levelno", "lineno", "message", "module",
        "msecs", "msg", "name", "pathname", "process", "processName",
        "relativeCreated", "stack_info", "thread", "threadName",
    })

    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
            "module":    record.module,
            "func":      record.funcName,
            "line":      record.lineno,
        }
        if record.exc_info:
            obj["exception"] = self.formatException(record.exc_info)

        # Include any extra= kwargs the caller passed
        for key, val in record.__dict__.items():
            if key not in self._SKIP and not key.startswith("_"):
                obj[key] = val

        return json.dumps(obj, default=str)


def configure_logging(app) -> None:
    """
    Attach structured logging to the Flask app.
    Call this once inside create_app(), after db.init_app().
    """
    is_debug   = bool(app.config.get("DEBUG"))
    is_testing = bool(app.config.get("TESTING"))
    log_level  = logging.DEBUG if is_debug else logging.INFO
    log_dir    = os.environ.get("LOG_DIR", "logs")

    app_logger = logging.getLogger("mefportal")
    app_logger.setLevel(log_level)
    app_logger.propagate = False
    app_logger.handlers.clear()

    # ── Formatter ──────────────────────────────────────────────────────────
    if is_debug:
        fmt: logging.Formatter = logging.Formatter(
            "%(asctime)s [%(levelname)-8s] %(name)s %(module)s:%(lineno)d — %(message)s",
            datefmt="%H:%M:%S",
        )
    else:
        fmt = JSONFormatter()

    # ── Stream handler (always on) ─────────────────────────────────────────
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(fmt)
    handler.setLevel(log_level)
    app_logger.addHandler(handler)

    # ── Rotating file handler (production only, skipped during tests) ───────
    if not is_testing:
        try:
            os.makedirs(log_dir, exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(
                os.path.join(log_dir, "mefportal.log"),
                maxBytes=10 * 1024 * 1024,   # 10 MB
                backupCount=5,
                encoding="utf-8",
            )
            fh.setFormatter(JSONFormatter())   # always JSON in files
            fh.setLevel(log_level)
            app_logger.addHandler(fh)
        except OSError:
            app_logger.warning(
                "Could not create log directory '%s'; file logging disabled.", log_dir
            )

    # Quieten noisy SQLAlchemy query logs in production
    if not is_debug:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    app_logger.info(
        "Logging configured",
        extra={"log_level": logging.getLevelName(log_level), "testing": is_testing},
    )
