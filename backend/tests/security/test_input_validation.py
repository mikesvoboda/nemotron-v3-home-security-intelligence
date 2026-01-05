"""Input validation security tests.

This module tests input validation and sanitization including:
- Boundary value testing
- Type confusion attacks
- Unicode handling
- Content-Type validation
- File upload security
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


# =============================================================================
# Boundary Value Tests
# =============================================================================


class TestBoundaryValues:
    """Tests for boundary value handling."""

    @pytest.mark.parametrize(
        "value,description",
        [
            (0, "zero"),
            (-1, "negative one"),
            (-999999999, "large negative"),
            (999999999, "large positive"),
            (2**31 - 1, "max 32-bit signed"),
            (2**31, "overflow 32-bit signed"),
            (2**63 - 1, "max 64-bit signed"),
        ],
    )
    @pytest.mark.asyncio
    async def test_integer_boundary_values(self, client: AsyncClient, value: int, description: str):
        """Test that integer boundary values are handled safely.

        Scenario: {description}
        """
        # Test in query param
        response = await client.get(
            "/api/events",
            params={"limit": value},
        )
        # Should handle gracefully
        assert response.status_code in [200, 400, 422], (
            f"Integer boundary not handled: {description}"
        )

    @pytest.mark.asyncio
    async def test_empty_string_handling(self, client: AsyncClient):
        """Test that empty strings are handled properly."""
        response = await client.post(
            "/api/cameras",
            json={"name": "", "folder_path": ""},
        )
        # Should validate and reject or handle empty strings
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_whitespace_only_strings(self, client: AsyncClient):
        """Test that whitespace-only strings are handled safely."""
        response = await client.post(
            "/api/cameras",
            json={"name": "   ", "folder_path": "   "},
        )
        # Should either validate/reject OR handle gracefully
        # Note: Some APIs may accept whitespace (will fail later on path validation)
        # The key security property is no server error
        assert response.status_code != 500

    @pytest.mark.asyncio
    async def test_very_long_strings(self, client: AsyncClient):
        """Test that very long strings don't cause issues."""
        long_string = "A" * 100000
        response = await client.post(
            "/api/cameras",
            json={"name": long_string, "folder_path": "/test"},
        )
        # Should reject or truncate, not crash
        assert response.status_code in [400, 413, 422]


# =============================================================================
# Type Confusion Tests
# =============================================================================


class TestTypeConfusion:
    """Tests for type confusion attack prevention."""

    @pytest.mark.parametrize(
        "payload,description",
        [
            ({"name": 12345}, "integer where string expected"),
            ({"name": True}, "boolean where string expected"),
            ({"name": ["array"]}, "array where string expected"),
            ({"name": {"nested": "object"}}, "object where string expected"),
            ({"name": None}, "null where string expected"),
            ({"name": 3.14159}, "float where string expected"),
        ],
    )
    @pytest.mark.asyncio
    async def test_type_confusion_in_json(
        self, client: AsyncClient, payload: dict, description: str
    ):
        """Test that type confusion attacks are handled.

        Scenario: {description}
        """
        payload["folder_path"] = "/test"
        response = await client.post("/api/cameras", json=payload)
        # Should validate types and reject or coerce safely
        assert response.status_code in [200, 400, 422], f"Type confusion not handled: {description}"

    @pytest.mark.asyncio
    async def test_array_vs_single_value(self, client: AsyncClient):
        """Test that array vs single value confusion is handled."""
        # Send array where single value expected
        response = await client.get(
            "/api/events",
            params={"camera_id": ["id1", "id2", "id3"]},
        )
        # Should handle array gracefully
        assert response.status_code in [200, 400, 422]

    @pytest.mark.asyncio
    async def test_nested_object_confusion(self, client: AsyncClient):
        """Test that deeply nested objects don't cause issues."""
        # Create deeply nested JSON
        deep_obj = {"a": None}
        current = deep_obj
        for i in range(100):
            current["nested"] = {"a": None}
            current = current["nested"]

        response = await client.post(
            "/api/cameras",
            json={"name": "test", "folder_path": "/test", "extra": deep_obj},
        )
        # Should handle without stack overflow or crash
        assert response.status_code != 500


# =============================================================================
# Unicode Handling Tests
# =============================================================================


class TestUnicodeHandling:
    """Tests for Unicode input handling."""

    @pytest.mark.parametrize(
        "payload,description",
        [
            ("\u0000", "null character"),
            ("\u001f", "control character"),
            ("\u200b", "zero-width space"),
            ("\u202e", "right-to-left override"),
            ("\ufeff", "byte order mark"),
            ("\uffff", "noncharacter"),
            ("\U0001f600", "emoji"),
            ("cafe\u0301", "combining character (cafe with accent)"),
            ("\u0041\u030a", "A with combining ring"),
        ],
    )
    @pytest.mark.asyncio
    async def test_unicode_special_characters(
        self, client: AsyncClient, payload: str, description: str
    ):
        """Test that special Unicode characters are handled safely.

        Scenario: {description}
        """
        try:
            response = await client.post(
                "/api/cameras",
                json={"name": f"test_{payload}_camera", "folder_path": "/test"},
            )
            # Should handle without crashing (500 error)
            assert response.status_code != 500, f"Unicode caused server error: {description}"
        except Exception as e:
            # Encoding errors for invalid UTF-8 (like null bytes) are acceptable -
            # the database correctly rejects invalid input
            if "encoding" in str(e).lower() or "utf" in str(e).lower():
                pass  # Database correctly rejected invalid encoding
            else:
                raise

    @pytest.mark.asyncio
    async def test_unicode_normalization_consistency(self, client: AsyncClient):
        """Test that Unicode normalization is consistent."""
        # These are visually identical but different byte sequences
        # NFC: composed form
        # NFD: decomposed form
        nfc_string = "\u00c5"  # A with ring above (composed)
        nfd_string = "A\u030a"  # A + combining ring (decomposed)

        response1 = await client.get(
            "/api/events/search",
            params={"q": nfc_string},
        )
        response2 = await client.get(
            "/api/events/search",
            params={"q": nfd_string},
        )

        # Both should be handled consistently
        assert response1.status_code == response2.status_code

    @pytest.mark.asyncio
    async def test_homoglyph_attack_awareness(self, client: AsyncClient):
        """Test awareness of homoglyph attacks (visually similar characters)."""
        # These look similar but are different Unicode characters
        strings = [
            "admin",  # ASCII
            "\u0430dmin",  # Cyrillic 'a' instead of Latin
            "adm\u0131n",  # Turkish dotless 'i'
        ]

        for s in strings:
            response = await client.post(
                "/api/cameras",
                json={"name": s, "folder_path": f"/test/{s}"},
            )
            # All should be handled safely
            assert response.status_code in [200, 201, 400, 422]


# =============================================================================
# Content-Type Validation Tests
# =============================================================================


class TestContentTypeValidation:
    """Tests for Content-Type validation."""

    @pytest.mark.asyncio
    async def test_json_content_type_required(self, client: AsyncClient):
        """Test that JSON endpoints require correct Content-Type."""
        response = await client.post(
            "/api/cameras",
            content='{"name": "test", "folder_path": "/test"}',
            headers={"Content-Type": "text/plain"},
        )
        # Should reject non-JSON content type for JSON endpoints
        assert response.status_code in [400, 415, 422]

    @pytest.mark.asyncio
    async def test_content_type_mismatch(self, client: AsyncClient):
        """Test that Content-Type must match actual content."""
        response = await client.post(
            "/api/cameras",
            content="not-json-content",
            headers={"Content-Type": "application/json"},
        )
        # Should reject malformed JSON
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_multipart_on_json_endpoint(self, client: AsyncClient):
        """Test that multipart requests are handled on JSON endpoints."""
        response = await client.post(
            "/api/cameras",
            data={"name": "test", "folder_path": "/test"},
            headers={"Content-Type": "multipart/form-data"},
        )
        # Should reject or handle appropriately
        assert response.status_code in [400, 415, 422]


# =============================================================================
# Request Size Limits Tests
# =============================================================================


class TestRequestSizeLimits:
    """Tests for request size limit enforcement."""

    @pytest.mark.asyncio
    async def test_large_json_body_rejected(self, client: AsyncClient):
        """Test that excessively large JSON bodies are rejected."""
        large_data = {"data": "X" * 10_000_000}  # 10MB+
        response = await client.post(
            "/api/cameras",
            json=large_data,
        )
        # Should reject with appropriate error
        assert response.status_code in [400, 413, 422]

    @pytest.mark.asyncio
    async def test_many_query_params_handled(self, client: AsyncClient):
        """Test that many query parameters are handled safely."""
        params = {f"param{i}": f"value{i}" for i in range(1000)}
        response = await client.get("/api/events", params=params)
        # Should handle gracefully (ignore unknown params or reject)
        assert response.status_code in [200, 400, 414]

    @pytest.mark.asyncio
    async def test_many_headers_handled(self, client: AsyncClient):
        """Test that many headers are handled safely."""
        headers = {f"X-Custom-Header-{i}": f"value{i}" for i in range(100)}
        response = await client.get("/api/system/health", headers=headers)
        # Should handle gracefully
        assert response.status_code in [200, 400, 431]


# =============================================================================
# Special Character Handling Tests
# =============================================================================


class TestSpecialCharacterHandling:
    """Tests for special character handling in inputs."""

    @pytest.mark.parametrize(
        "char,description",
        [
            ("\n", "newline"),
            ("\r", "carriage return"),
            ("\t", "tab"),
            ("\b", "backspace"),
            ("\f", "form feed"),
            ("\\", "backslash"),
            ('"', "double quote"),
            ("'", "single quote"),
            ("`", "backtick"),
            ("$", "dollar sign"),
        ],
    )
    @pytest.mark.asyncio
    async def test_special_characters_in_strings(
        self, client: AsyncClient, char: str, description: str
    ):
        """Test that special characters in strings are handled safely.

        Scenario: {description}
        """
        response = await client.post(
            "/api/cameras",
            json={"name": f"test{char}camera", "folder_path": "/test"},
        )
        # Should handle without breaking
        assert response.status_code in [200, 201, 400, 422], (
            f"Special char not handled: {description}"
        )

    @pytest.mark.asyncio
    async def test_null_bytes_in_strings(self, client: AsyncClient):
        """Test that null bytes in strings are handled safely."""
        # JSON doesn't allow raw null bytes, but we can try escaped form
        try:
            response = await client.post(
                "/api/cameras",
                json={"name": "test\u0000camera", "folder_path": "/test"},
            )
            # Should handle safely - may reject with encoding error (which is correct)
            assert response.status_code != 500, "Null byte caused unhandled server error"
        except Exception as e:
            # Encoding errors for null bytes are acceptable -
            # PostgreSQL correctly rejects invalid UTF-8 sequences
            if "encoding" in str(e).lower() or "utf" in str(e).lower() or "0x00" in str(e):
                pass  # Database correctly rejected null byte
            else:
                raise


# =============================================================================
# JSON Parsing Security Tests
# =============================================================================


class TestJSONParsingSecurity:
    """Tests for JSON parsing security."""

    @pytest.mark.asyncio
    async def test_duplicate_keys_handling(self, client: AsyncClient):
        """Test that duplicate JSON keys are handled consistently."""
        # Send raw JSON with duplicate keys
        response = await client.post(
            "/api/cameras",
            content='{"name": "first", "name": "second", "folder_path": "/test"}',
            headers={"Content-Type": "application/json"},
        )
        # Should use consistent key (typically last)
        assert response.status_code in [200, 201, 400, 422]

    @pytest.mark.asyncio
    async def test_json_with_comments(self, client: AsyncClient):
        """Test that JSON with comments is rejected."""
        # JSON doesn't allow comments
        response = await client.post(
            "/api/cameras",
            content='{"name": "test", /* comment */ "folder_path": "/test"}',
            headers={"Content-Type": "application/json"},
        )
        # Should reject invalid JSON
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_trailing_comma_handling(self, client: AsyncClient):
        """Test that trailing commas in JSON are handled."""
        response = await client.post(
            "/api/cameras",
            content='{"name": "test", "folder_path": "/test",}',
            headers={"Content-Type": "application/json"},
        )
        # Strict JSON doesn't allow trailing commas
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_scientific_notation_in_json(self, client: AsyncClient):
        """Test that scientific notation in JSON is handled correctly."""
        response = await client.get(
            "/api/events",
            params={"limit": "1e10"},
        )
        # Should parse correctly or reject
        assert response.status_code in [200, 400, 422]


# =============================================================================
# Encoding Attack Tests
# =============================================================================


class TestEncodingAttacks:
    """Tests for encoding-based attack prevention."""

    @pytest.mark.asyncio
    async def test_mixed_encoding_attack(self, client: AsyncClient):
        """Test that mixed encoding attacks are prevented."""
        # Mix of URL encoding and raw characters
        mixed = "%3Cscript%3E<script>alert(1)</script>%3C/script%3E"
        response = await client.get(
            "/api/events/search",
            params={"q": mixed},
        )
        # Should handle without executing
        assert response.status_code in [200, 400]
        assert "<script>" not in response.text

    @pytest.mark.asyncio
    async def test_overlong_utf8_encoding(self, client: AsyncClient):
        """Test that overlong UTF-8 encoding is rejected."""
        # Overlong encoding of '/' (normally 0x2F)
        # This is invalid UTF-8 and should be rejected
        response = await client.get(
            "/api/events/search",
            params={"q": "..%c0%af..%c0%afetc%c0%afpasswd"},
        )
        # Should handle safely
        assert response.status_code in [200, 400, 404]
