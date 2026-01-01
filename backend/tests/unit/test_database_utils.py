"""Tests for database utility functions.

Tests cover:
- ILIKE pattern escaping to prevent injection attacks
"""

from __future__ import annotations

from backend.core.database import escape_ilike_pattern


class TestEscapeIlikePattern:
    """Tests for ILIKE pattern escaping function."""

    def test_empty_string(self):
        """Empty string returns empty string."""
        assert escape_ilike_pattern("") == ""

    def test_normal_text(self):
        """Normal text without special characters is unchanged."""
        assert escape_ilike_pattern("hello") == "hello"
        assert escape_ilike_pattern("hello world") == "hello world"
        assert escape_ilike_pattern("person123") == "person123"

    def test_escape_percent(self):
        """Percent sign is escaped to prevent wildcard matching."""
        assert escape_ilike_pattern("%") == "\\%"
        assert escape_ilike_pattern("100%") == "100\\%"
        assert escape_ilike_pattern("100% complete") == "100\\% complete"
        assert escape_ilike_pattern("%prefix") == "\\%prefix"
        assert escape_ilike_pattern("suffix%") == "suffix\\%"

    def test_escape_underscore(self):
        """Underscore is escaped to prevent single character wildcard."""
        assert escape_ilike_pattern("_") == "\\_"
        assert escape_ilike_pattern("file_name") == "file\\_name"
        assert escape_ilike_pattern("test_case_one") == "test\\_case\\_one"
        assert escape_ilike_pattern("_prefix") == "\\_prefix"
        assert escape_ilike_pattern("suffix_") == "suffix\\_"

    def test_escape_backslash(self):
        """Backslash is escaped to prevent escape sequence injection."""
        assert escape_ilike_pattern("\\") == "\\\\"
        assert escape_ilike_pattern("path\\to\\file") == "path\\\\to\\\\file"
        assert escape_ilike_pattern("\\prefix") == "\\\\prefix"
        assert escape_ilike_pattern("suffix\\") == "suffix\\\\"

    def test_mixed_special_characters(self):
        """Multiple special characters are all properly escaped."""
        # Test with all three special characters
        assert escape_ilike_pattern("%_\\") == "\\%\\_\\\\"
        assert escape_ilike_pattern("100%_value\\path") == "100\\%\\_value\\\\path"

    def test_escape_order_matters(self):
        """Backslash must be escaped first to avoid double-escaping."""
        # If we escaped % first as \%, then escaped \, we'd get \\%
        # But we want \% to remain as \% (the backslash is the escape char)
        # Actually, we need to escape backslash first, so:
        # Input: \% -> becomes \\% (escaped backslash, then literal %)
        # Then escape %: \\% -> \\\% (escaped backslash, escaped percent)
        assert escape_ilike_pattern("\\%") == "\\\\\\%"

    def test_unicode_characters(self):
        """Unicode characters are preserved."""
        assert escape_ilike_pattern("cafe") == "cafe"
        assert escape_ilike_pattern("100% complete") == "100\\% complete"

    def test_real_world_injection_attempts(self):
        """Common injection patterns are properly neutralized."""
        # Attempt to match any string
        assert escape_ilike_pattern("%") == "\\%"

        # Attempt to match strings with certain patterns
        assert escape_ilike_pattern("a%b") == "a\\%b"

        # Attempt to use underscore as single-char wildcard
        assert escape_ilike_pattern("test_") == "test\\_"

        # Attempt to escape the escape character
        assert escape_ilike_pattern("\\%") == "\\\\\\%"

        # Complex injection attempt
        assert escape_ilike_pattern("%admin%") == "\\%admin\\%"

    def test_preserves_spaces_and_punctuation(self):
        """Non-ILIKE special characters are preserved."""
        assert escape_ilike_pattern("hello world!") == "hello world!"
        assert escape_ilike_pattern("test@example.com") == "test@example.com"
        assert escape_ilike_pattern("price: $100") == "price: $100"
        assert escape_ilike_pattern("a + b = c") == "a + b = c"


class TestEscapeIlikePatternEdgeCases:
    """Edge case tests for ILIKE escaping."""

    def test_only_special_characters(self):
        """String containing only special characters."""
        assert escape_ilike_pattern("%%%") == "\\%\\%\\%"
        assert escape_ilike_pattern("___") == "\\_\\_\\_"
        assert escape_ilike_pattern("\\\\\\") == "\\\\\\\\\\\\"

    def test_alternating_special_characters(self):
        """Alternating special and normal characters."""
        assert escape_ilike_pattern("a%b_c\\d") == "a\\%b\\_c\\\\d"

    def test_whitespace_handling(self):
        """Various whitespace is preserved."""
        assert escape_ilike_pattern("  ") == "  "
        assert escape_ilike_pattern("\t") == "\t"
        assert escape_ilike_pattern("\n") == "\n"
        assert escape_ilike_pattern("a\tb%c\nd") == "a\tb\\%c\nd"

    def test_very_long_string(self):
        """Long strings are handled correctly."""
        long_string = "a" * 10000
        assert escape_ilike_pattern(long_string) == long_string

        # With special characters throughout
        long_with_special = "a%_\\" * 1000
        expected = "a\\%\\_\\\\" * 1000
        assert escape_ilike_pattern(long_with_special) == expected


class TestEscapeIlikePatternNoneAndNonString:
    """Tests for None and non-string input handling."""

    def test_none_returns_empty_string(self):
        """None input returns empty string."""
        assert escape_ilike_pattern(None) == ""

    def test_integer_converted_to_string(self):
        """Integer input is converted to string."""
        assert escape_ilike_pattern(123) == "123"
        assert escape_ilike_pattern(0) == "0"
        assert escape_ilike_pattern(-42) == "-42"

    def test_float_converted_to_string(self):
        """Float input is converted to string."""
        assert escape_ilike_pattern(3.14) == "3.14"
        assert escape_ilike_pattern(0.0) == "0.0"
        assert escape_ilike_pattern(-2.5) == "-2.5"

    def test_boolean_converted_to_string(self):
        """Boolean input is converted to string."""
        assert escape_ilike_pattern(True) == "True"
        assert escape_ilike_pattern(False) == "False"

    def test_list_converted_to_string(self):
        """List input is converted to string representation."""
        result = escape_ilike_pattern([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_dict_converted_to_string(self):
        """Dict input is converted to string representation."""
        result = escape_ilike_pattern({"a": 1})
        assert result == "{'a': 1}"

    def test_non_string_with_special_chars(self):
        """Non-string that contains special chars when stringified."""
        # Float with percentage-like appearance won't have %, but test conversion
        result = escape_ilike_pattern(100)
        assert result == "100"

    def test_object_with_custom_str(self):
        """Object with custom __str__ is handled correctly."""

        class CustomObj:
            def __str__(self):
                return "custom_value%"

        result = escape_ilike_pattern(CustomObj())
        assert result == r"custom\_value\%"

    def test_object_with_special_chars_in_str(self):
        """Object whose __str__ returns special ILIKE characters."""

        class SpecialObj:
            def __str__(self):
                return r"path\file_name%"

        result = escape_ilike_pattern(SpecialObj())
        assert result == r"path\\file\_name\%"


class TestDatabasePoolConfiguration:
    """Tests for database connection pool configuration settings."""

    def test_default_pool_settings(self):
        """Test that default pool settings are configurable and have sensible defaults."""

        # Clear the settings cache to test with fresh settings
        from backend.core.config import get_settings

        get_settings.cache_clear()

        # Test with default values
        settings = get_settings()

        # Verify pool settings exist and have reasonable defaults
        assert hasattr(settings, "database_pool_size")
        assert hasattr(settings, "database_pool_overflow")
        assert hasattr(settings, "database_pool_timeout")
        assert hasattr(settings, "database_pool_recycle")

        # Verify defaults are reasonable for production workloads
        # Pool size should be >= 5 (minimum) and reasonable for concurrent access
        assert settings.database_pool_size >= 5
        assert settings.database_pool_size <= 100

        # Overflow should allow burst capacity
        assert settings.database_pool_overflow >= 0
        assert settings.database_pool_overflow <= 100

        # Timeout should be reasonable (5-120 seconds)
        assert settings.database_pool_timeout >= 5
        assert settings.database_pool_timeout <= 120

        # Recycle should prevent stale connections (300-7200 seconds)
        assert settings.database_pool_recycle >= 300
        assert settings.database_pool_recycle <= 7200

        # Clean up
        get_settings.cache_clear()

    def test_pool_size_exceeds_previous_default(self):
        """Test that default pool size is larger than previous hardcoded value.

        Previous default was 10 with overflow 20 (30 max), which caused
        'Too many connections' errors under load. New default should
        provide more headroom.
        """
        from backend.core.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()

        # Total max connections (pool_size + overflow) should exceed old 30
        max_connections = settings.database_pool_size + settings.database_pool_overflow
        assert max_connections > 30, (
            f"Max connections ({max_connections}) should exceed previous "
            f"default of 30 to prevent 'Too many connections' errors"
        )

        get_settings.cache_clear()

    def test_pool_settings_are_used_in_engine_kwargs(self):
        """Verify that pool settings are actually used in engine configuration.

        This is a design verification test to ensure the settings
        are not just defined but actually applied.
        """
        # This test verifies the code structure - the actual engine
        # creation is tested in integration tests

        from backend.core import database

        # Read the init_db source to verify settings are used
        init_source_file = database.__file__
        assert init_source_file is not None

        with open(init_source_file) as f:
            source_code = f.read()

        # Verify the engine_kwargs uses settings attributes, not hardcoded values
        assert "settings.database_pool_size" in source_code
        assert "settings.database_pool_overflow" in source_code
        assert "settings.database_pool_timeout" in source_code
        assert "settings.database_pool_recycle" in source_code
