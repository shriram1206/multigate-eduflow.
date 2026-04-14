"""
app/error_handlers.py

OP-004: Comprehensive error page handling.

Provides:
  - Custom error pages for HTTP errors (400, 401, 403, 404, 500, 503)
  - User-friendly error messages
  - No stack trace leakage to users
  - Proper HTTP status codes

CQ-005: Comprehensive docstrings for all error handlers.
"""

import logging
from flask import render_template, request

logger = logging.getLogger('mefportal')


def register_error_handlers(app):
    """
    Register error handlers for all HTTP status codes.

    Called from app/__init__.py during app creation.

    Args:
        app: Flask application instance
    """

    @app.errorhandler(400)
    def bad_request(error):
        """
        400: Bad Request

        Triggered by: Invalid input, malformed request data
        """
        logger.warning(f"400 Bad Request: {request.path} - {error}")
        return (
            render_template(
                "errors/400.html",
                error_message="Invalid request. Please check your input.",
            ),
            400,
        )

    @app.errorhandler(401)
    def unauthorized(error):
        """
        401: Unauthorized

        Triggered by: User not authenticated when authentication required
        """
        logger.warning(f"401 Unauthorized: {request.path}")
        return render_template("errors/401.html"), 401

    @app.errorhandler(403)
    def forbidden(error):
        """
        403: Forbidden

        Triggered by: User authenticated but lacks permission for resource
        """
        logger.warning(f"403 Forbidden: {request.path} - {error}")
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        """
        404: Not Found

        Triggered by: Requested path does not exist
        """
        logger.debug(f"404 Not Found: {request.path}")
        return render_template("errors/404.html"), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        """
        405: Method Not Allowed

        Triggered by: GET request to POST-only route, etc.
        """
        logger.warning(f"405 Method Not Allowed: {request.method} {request.path}")
        return (
            render_template(
                "errors/405.html",
                method=request.method,
            ),
            405,
        )

    @app.errorhandler(500)
    def internal_error(error):
        """
        500: Internal Server Error

        Triggered by: Unhandled exceptions during request processing

        SECURITY: Does NOT expose stack trace to users
        - Logs full exception with traceback for debugging
        - Shows friendly message to user
        - Includes error ID for support reference
        """
        error_id = request.headers.get("X-Request-ID", "unknown")
        logger.exception(
            f"500 Internal Server Error (ID: {error_id}): {request.path}",
            extra={"error": str(error)},
        )

        return (
            render_template(
                "errors/500.html",
                error_id=error_id,
            ),
            500,
        )

    @app.errorhandler(502)
    def bad_gateway(error):
        """
        502: Bad Gateway

        Triggered by: Upstream service unavailable
        """
        logger.error(f"502 Bad Gateway: {request.path}")
        return render_template("errors/502.html"), 502

    @app.errorhandler(503)
    def service_unavailable(error):
        """
        503: Service Unavailable

        Triggered by: Application temporarily down, database unavailable, etc.
        """
        logger.error(f"503 Service Unavailable: {request.path}")
        return render_template("errors/503.html"), 503

    @app.errorhandler(504)
    def gateway_timeout(error):
        """
        504: Gateway Timeout

        Triggered by: Request took too long to process

        """
        logger.error(f"504 Gateway Timeout: {request.path}")
        return render_template("errors/504.html"), 504
