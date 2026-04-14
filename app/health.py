"""
app/health.py

OP-003: Comprehensive health check endpoints.

Provides multiple health check endpoints for load balancers and orchestrators:
  - /healthz/live: Kubernetes liveness probe (always returns 200 if process running)
  - /healthz/ready: Kubernetes readiness probe (returns 503 if dependencies down)
  - /healthz: Legacy endpoint (same as readiness)

CQ-005: Comprehensive docstrings explaining each endpoint.
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Tuple

from flask import Blueprint, jsonify, current_app
from sqlalchemy import text

from app.extensions import db

logger = logging.getLogger('mefportal')

bp = Blueprint('health', __name__)


class HealthChecker:
    """Centralized health checking for all dependencies."""

    @staticmethod
    def check_database() -> Dict[str, Any]:
        """
        Check database connectivity and latency.

        Returns:
            Dictionary with 'status' ('healthy', 'degraded', 'unhealthy') and 'latency_ms'
        """
        try:
            start = time.time()
            db.session.execute(text("SELECT 1"))
            latency = (time.time() - start) * 1000  # Convert to milliseconds

            if latency > 1000:
                status = "degraded"
            else:
                status = "healthy"

            return {
                "status": status,
                "latency_ms": round(latency, 2),
            }
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)[:100],  # Truncate error message
            }

    @staticmethod
    def check_filesystem() -> Dict[str, Any]:
        """
        Check filesystem writability (for logs, uploads).

        Returns:
            Dictionary with 'status' ('healthy' or 'unhealthy')
        """
        try:
            import tempfile
            import os

            # Try to create a temporary file (indicates /tmp or logs dir is writable)
            with tempfile.NamedTemporaryFile(delete=True):
                pass

            return {"status": "healthy"}
        except Exception as e:
            logger.warning(f"Filesystem health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)[:100],
            }

    @staticmethod
    def check_config() -> Dict[str, Any]:
        """
        Check that critical configuration is present.

        Returns:
            Dictionary with 'status' and any missing configs
        """
        required_keys = [
            "SECRET_KEY",
            "SQLALCHEMY_DATABASE_URI",
        ]

        missing = []
        for key in required_keys:
            if not current_app.config.get(key):
                missing.append(key)

        if missing:
            return {
                "status": "unhealthy",
                "missing_configs": missing,
            }

        return {"status": "healthy"}

    @classmethod
    def liveness(cls) -> Dict[str, Any]:
        """
        Liveness check: Is the process running and responsive?

        Used by Kubernetes/Docker: If this fails, container is restarted.
        Should return 200 whenever the application process is running.

        Returns:
            {"status": "alive", "timestamp": ISO8601_timestamp}
        """
        from datetime import datetime

        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat(),
            "version": current_app.config.get("APP_VERSION", "unknown"),
        }

    @classmethod
    def readiness(cls) -> Tuple[Dict[str, Any], int]:
        """
        Readiness check: Is the application ready to serve traffic?

        Used by Kubernetes/Docker: If this fails (status_code != 200), traffic is not routed.
        Checks all critical dependencies.

        Returns:
            (status_dict, http_status_code)
            - 200 if ready
            - 503 if not ready (dependencies unhealthy)
        """
        checks = {
            "database": cls.check_database(),
            "filesystem": cls.check_filesystem(),
            "config": cls.check_config(),
        }

        # Determine overall readiness
        all_healthy = all(
            check.get("status") in ("healthy",) for check in checks.values()
        )

        status_code = 200 if all_healthy else 503

        return (
            {
                "ready": all_healthy,
                "checks": checks,
                "timestamp": datetime.utcnow().isoformat(),
            },
            status_code,
        )


# ────────────────────────────────────────────────────────────────────────────────
# Flask Routes
# ────────────────────────────────────────────────────────────────────────────────


@bp.route("/healthz/live", methods=["GET"])
def liveness():
    """
    Kubernetes liveness probe endpoint.

    Returns:
        200 if process is running
        (Never returns > 500 if implemented correctly)

    Used by: Kubernetes, Docker, load balancers
    Action on failure: Container restart
    """
    return jsonify(HealthChecker.liveness()), 200


@bp.route("/healthz/ready", methods=["GET"])
def readiness():
    """
    Kubernetes readiness probe endpoint.

    Returns:
        200 if ready to serve traffic (all dependencies healthy)
        503 if dependencies unavailable (database down, config missing, etc.)

    Used by: Kubernetes, Docker, load balancers
    Action on failure: Remove from load balancer, don't route traffic
    """
    status_dict, status_code = HealthChecker.readiness()
    return jsonify(status_dict), status_code


@bp.route("/healthz", methods=["GET"])
def health():
    """
    Legacy health check endpoint (backwards compatibility).

    Equivalent to /healthz/ready.

    Returns:
        200 if ready
        503 if not ready
    """
    status_dict, status_code = HealthChecker.readiness()
    return jsonify(status_dict), status_code


@bp.route("/health/status", methods=["GET"])
def detailed_status():
    """
    Detailed health status (for debugging).

    Returns: Full status of all checks with details
    (Recommended: Protect with authentication for production)
    """
    liveness_info = HealthChecker.liveness()
    readiness_info, _ = HealthChecker.readiness()

    return jsonify({
        "application": {
            "version": liveness_info.get("version"),
            "timestamp": liveness_info.get("timestamp"),
        },
        "liveness": liveness_info,
        "readiness": readiness_info,
    }), 200
