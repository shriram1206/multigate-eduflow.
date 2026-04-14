"""
tests/test_utils.py
────────────────────
Pure unit tests for app/utils.py.

These tests have ZERO database interaction — they are pure Python logic tests.
Every test here should always pass, even with no internet or DB connection.
"""

import pytest
from app.utils import (
    validate_password,
    validate_date_range,
    validate_enum,
    normalize_department_name,
    escape_like,
)


# ════════════════════════════════════════════════════════════════════════
# Password Validation
# ════════════════════════════════════════════════════════════════════════

class TestValidatePassword:

    def test_strong_password_passes(self):
        ok, msg = validate_password("Strong@1234")
        assert ok is True
        assert msg == ""

    def test_too_short_fails(self):
        ok, msg = validate_password("Ab@1")
        assert ok is False
        assert "8 characters" in msg

    def test_no_uppercase_fails(self):
        ok, msg = validate_password("weak@1234")
        assert ok is False
        assert "uppercase" in msg

    def test_no_lowercase_fails(self):
        ok, msg = validate_password("WEAK@1234")
        assert ok is False
        assert "lowercase" in msg

    def test_no_digit_fails(self):
        ok, msg = validate_password("Weakpass@")
        assert ok is False
        assert "digit" in msg

    def test_no_special_char_fails(self):
        ok, msg = validate_password("Weakpass1")
        assert ok is False
        assert "special" in msg

    def test_empty_password_fails(self):
        ok, msg = validate_password("")
        assert ok is False


# ════════════════════════════════════════════════════════════════════════
# Date Range Validation
# ════════════════════════════════════════════════════════════════════════

class TestValidateDateRange:

    def test_same_day_is_valid(self):
        ok, msg = validate_date_range("2025-06-01", "2025-06-01")
        assert ok is True

    def test_valid_range_passes(self):
        ok, msg = validate_date_range("2025-06-01", "2025-06-05")
        assert ok is True

    def test_reversed_range_fails(self):
        ok, msg = validate_date_range("2025-06-10", "2025-06-05")
        assert ok is False
        assert "after" in msg.lower()

    def test_invalid_format_fails(self):
        ok, msg = validate_date_range("01/06/2025", "10/06/2025")
        assert ok is False
        assert "YYYY-MM-DD" in msg

    def test_empty_strings_fail(self):
        ok, msg = validate_date_range("", "")
        assert ok is False

    def test_partial_invalid_fails(self):
        ok, msg = validate_date_range("2025-06-01", "not-a-date")
        assert ok is False


# ════════════════════════════════════════════════════════════════════════
# Enum Validation
# ════════════════════════════════════════════════════════════════════════

class TestValidateEnum:

    def test_valid_enum_passes(self):
        ok, msg = validate_enum("Leave", ["Leave", "Apology", "On Duty"], "type")
        assert ok is True

    def test_invalid_enum_fails(self):
        ok, msg = validate_enum("Holiday", ["Leave", "Apology"], "type")
        assert ok is False
        assert "Holiday" in msg

    def test_empty_value_fails(self):
        ok, msg = validate_enum("", ["Leave"], "type")
        assert ok is False

    def test_case_sensitive(self):
        """Enum validation is deliberately case-sensitive."""
        ok, msg = validate_enum("leave", ["Leave", "Apology"], "type")
        assert ok is False


# ════════════════════════════════════════════════════════════════════════
# Department Normalisation
# ════════════════════════════════════════════════════════════════════════

class TestNormalizeDepartmentName:

    def test_strips_iv_prefix(self):
        assert normalize_department_name("IV-CSE") == "cse"

    def test_strips_v_prefix(self):
        assert normalize_department_name("V-CSE") == "cse"

    def test_strips_v_with_space(self):
        assert normalize_department_name("V CSE") == "cse"

    def test_already_normalized(self):
        assert normalize_department_name("cse") == "cse"

    def test_uppercased_input(self):
        assert normalize_department_name("CSE") == "cse"

    def test_none_returns_empty_string(self):
        assert normalize_department_name(None) == ""

    def test_whitespace_is_stripped(self):
        assert normalize_department_name("  CSE  ") == "cse"

    def test_iv_prefix_with_space(self):
        assert normalize_department_name("IV ECE") == "ece"

    def test_mixed_case_prefix(self):
        result = normalize_department_name("Iv-EEE")
        # Normalisation should lowercase everything
        assert "eee" in result


# ════════════════════════════════════════════════════════════════════════
# LIKE Escape
# ════════════════════════════════════════════════════════════════════════

class TestEscapeLike:

    def test_percent_is_escaped(self):
        assert "\\%" in escape_like("100%")

    def test_underscore_is_escaped(self):
        assert "\\_" in escape_like("user_name")

    def test_backslash_is_escaped(self):
        result = escape_like("back\\slash")
        assert "\\\\" in result

    def test_clean_string_unchanged(self):
        assert escape_like("hello") == "hello"

    def test_empty_string(self):
        assert escape_like("") == ""
