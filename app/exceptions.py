"""app/exceptions.py — CQ-002: Consistent, typed exception hierarchy."""


class MEFPortalError(Exception):
    """Base exception for all MEF Portal errors."""
    http_code    = 500
    user_message = "An unexpected error occurred. Please try again."


class DatabaseError(MEFPortalError):
    """Raised when a database operation fails unrecoverably."""
    http_code    = 500
    user_message = "Database error. Please try again."


class ValidationError(MEFPortalError):
    """Raised when user-supplied input fails validation."""
    http_code    = 400
    user_message = "Invalid input. Please check your data and try again."


class AuthenticationError(MEFPortalError):
    """Raised on failed authentication."""
    http_code    = 401
    user_message = "Invalid credentials."


class AuthorizationError(MEFPortalError):
    """Raised when authenticated user lacks permission."""
    http_code    = 403
    user_message = "You do not have permission to perform this action."


class NotFoundError(MEFPortalError):
    """Raised when a requested resource does not exist."""
    http_code    = 404
    user_message = "The requested resource was not found."
