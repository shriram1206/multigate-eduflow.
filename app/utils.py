"""
app/utils.py
CQ-001: Added type hints throughout.
CQ-004: normalize_department_name is the single canonical implementation.
"""
from __future__ import annotations

import re
import datetime
from typing import Tuple


def escape_like(value: str) -> str:
    """
    Escape LIKE special characters to prevent wildcard injection.
    Must be used with ESCAPE '\\' in the SQL clause.

    % matches any sequence  →  \\%
    _ matches any one char  →  \\_
    \\ escape char itself   →  \\\\
    """
    return (
        value
        .replace('\\', '\\\\')
        .replace('%', '\\%')
        .replace('_', '\\_')
    )

# ── Password validation ────────────────────────────────────────────────────────

def validate_password(password: str) -> Tuple[bool, str]:
    """
    Validate password against policy requirements.

    Returns:
        (True, "") on success.
        (False, human-readable reason) on failure.
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one digit"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    return True, ""


# ── Date validation ────────────────────────────────────────────────────────────

def validate_date_range(from_date_str: str, to_date_str: str) -> Tuple[bool, str]:
    """
    Validate that from_date ≤ to_date and both are valid YYYY-MM-DD strings.

    Returns:
        (True, "") on success.
        (False, reason) on failure.
    """
    try:
        from_dt = datetime.datetime.strptime(from_date_str, "%Y-%m-%d").date()
        to_dt   = datetime.datetime.strptime(to_date_str,   "%Y-%m-%d").date()
        if to_dt < from_dt:
            return False, "To date must be the same or after From date"
        return True, ""
    except Exception:
        return False, "Invalid date format (expected YYYY-MM-DD)"


# ── Enum validation ────────────────────────────────────────────────────────────

def validate_enum(value: str, allowed_values: list, field_name: str) -> Tuple[bool, str]:
    """Check that *value* is one of *allowed_values*."""
    if value not in allowed_values:
        return False, f"Invalid {field_name}: '{value}'"
    return True, ""


# ── Department normalisation ───────────────────────────────────────────────────

def normalize_department_name(department_value: object) -> str:
    """
    CQ-004: Single canonical implementation used everywhere.

    Strips leading Roman-numeral year prefixes (iv, v) and lowercases the result
    so that 'IV-CSE', 'V CSE', and 'cse' all compare equal.

    Args:
        department_value: Any value (str, None, …).

    Returns:
        Normalised department string (lowercase, no year prefix).
    """
    try:
        text = str(department_value or "").strip().lower()
        # Remove 'iv' or 'v' (year prefixes) followed by optional dash/space
        text = re.sub(r'^(iv[\s-]*|v[\s-]*)', '', text)
        return text.strip()
    except Exception:
        return ""
