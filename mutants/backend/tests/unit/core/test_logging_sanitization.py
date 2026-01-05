"""Unit tests for credential sanitization in logging module.

Tests cover:
- redact_url() - URL credential sanitization
- redact_sensitive_value() - Nested sensitive field redaction

Scenarios tested:
- Multiple password formats (encoded, special chars)
- Deeply nested structures
- Base64-encoded credentials
- Query string parameters with secrets
"""

import base64

from backend.core.logging import (
    SENSITIVE_FIELD_NAMES,
    redact_sensitive_value,
    redact_url,
    sanitize_error,
)

# =============================================================================
# redact_url() Tests - Credential Sanitization
# =============================================================================


class TestRedactUrlPasswordFormats:
    """Tests for redact_url with various password formats."""

    def test_simple_password(self) -> None:
        """Test redacting simple alphanumeric password."""
        url = "postgresql://user:password123@localhost:5432/db"
        result = redact_url(url)
        assert "password123" not in result
        assert "[REDACTED]" in result
        assert "user:" in result
        assert "localhost:5432/db" in result

    def test_password_with_special_characters(self) -> None:
        """Test redacting password with special characters."""
        url = "redis://admin:p@ss!w0rd#$%@redis:6379/0"
        result = redact_url(url)
        assert "[REDACTED]" in result
        assert "p@ss!w0rd#$%" not in result

    def test_url_encoded_password(self) -> None:
        """Test redacting URL-encoded password (percent-encoded special chars)."""
        # Password is "p@ss:word" encoded as "p%40ss%3Aword"
        url = "postgresql://user:p%40ss%3Aword@localhost:5432/db"
        result = redact_url(url)
        assert "p%40ss%3Aword" not in result
        assert "[REDACTED]" in result
        assert "user:" in result

    def test_password_with_unicode(self) -> None:
        """Test redacting password containing unicode characters."""
        url = "redis://user:pass%C3%A9%E4%B8%AD@localhost:6379/0"
        result = redact_url(url)
        assert "%C3%A9" not in result
        assert "%E4%B8%AD" not in result
        assert "[REDACTED]" in result

    def test_password_with_plus_sign(self) -> None:
        """Test redacting password with plus sign (common in URL encoding)."""
        url = "postgresql://user:pass+word@localhost:5432/db"
        result = redact_url(url)
        assert "pass+word" not in result
        assert "[REDACTED]" in result

    def test_password_with_slashes(self) -> None:
        """Test redacting password containing forward slashes (encoded)."""
        url = "redis://user:pass%2Fword@localhost:6379/0"
        result = redact_url(url)
        assert "pass%2Fword" not in result
        assert "[REDACTED]" in result

    def test_empty_password(self) -> None:
        """Test URL with empty password field."""
        url = "postgresql://user:@localhost:5432/db"
        result = redact_url(url)
        # Empty password should still be handled
        assert "user:" in result or result == url

    def test_very_long_password(self) -> None:
        """Test redacting very long password (256+ characters)."""
        long_pass = "a" * 300
        url = f"redis://admin:{long_pass}@localhost:6379/0"
        result = redact_url(url)
        assert long_pass not in result
        assert "[REDACTED]" in result

    def test_password_looks_like_url(self) -> None:
        """Test password that looks like a URL (contains :// pattern)."""
        # URL encoded "http://secret"
        url = "postgresql://user:http%3A%2F%2Fsecret@localhost:5432/db"
        result = redact_url(url)
        assert "http%3A%2F%2Fsecret" not in result
        assert "[REDACTED]" in result

    def test_base64_encoded_password(self) -> None:
        """Test redacting Base64-encoded password in URL."""
        # Base64 encode "mysecretpassword"
        b64_pass = base64.b64encode(b"mysecretpassword").decode()
        url = f"redis://default:{b64_pass}@localhost:6379/0"
        result = redact_url(url)
        assert b64_pass not in result
        assert "[REDACTED]" in result

    def test_base64_url_safe_encoded_password(self) -> None:
        """Test redacting URL-safe Base64-encoded password."""
        # URL-safe Base64 encode
        b64_pass = base64.urlsafe_b64encode(b"my+secret/password").decode()
        url = f"postgresql://user:{b64_pass}@localhost:5432/db"
        result = redact_url(url)
        assert b64_pass not in result
        assert "[REDACTED]" in result


class TestRedactUrlDifferentSchemes:
    """Tests for redact_url with different URL schemes."""

    def test_postgresql_asyncpg_url(self) -> None:
        """Test PostgreSQL asyncpg URL redaction."""
        url = "postgresql+asyncpg://security:secret123@localhost:5432/security"
        result = redact_url(url)
        assert "postgresql+asyncpg://" in result
        assert "secret123" not in result
        assert "[REDACTED]" in result

    def test_postgresql_psycopg2_url(self) -> None:
        """Test PostgreSQL psycopg2 URL redaction."""
        url = "postgresql+psycopg2://user:pass@localhost:5432/db"
        result = redact_url(url)
        assert "postgresql+psycopg2://" in result
        assert "pass" not in result.split("@")[0].split(":")[2]

    def test_redis_url(self) -> None:
        """Test Redis URL redaction."""
        url = "redis://default:mypassword@redis-host:6379/0"
        result = redact_url(url)
        assert "redis://" in result
        assert "mypassword" not in result

    def test_rediss_tls_url(self) -> None:
        """Test Redis TLS (rediss://) URL redaction."""
        url = "rediss://user:supersecret@secure-redis:6380/1"
        result = redact_url(url)
        assert "rediss://" in result
        assert "supersecret" not in result

    def test_mysql_url(self) -> None:
        """Test MySQL URL redaction."""
        url = "mysql://root:rootpass@mysql-host:3306/mydb"
        result = redact_url(url)
        assert "mysql://" in result
        assert "rootpass" not in result

    def test_mongodb_url(self) -> None:
        """Test MongoDB URL redaction."""
        url = "mongodb://admin:mongopass@mongo-host:27017/admin"
        result = redact_url(url)
        assert "mongodb://" in result
        assert "mongopass" not in result

    def test_amqp_url(self) -> None:
        """Test AMQP (RabbitMQ) URL redaction."""
        url = "amqp://guest:guestpass@rabbitmq:5672/"
        result = redact_url(url)
        assert "amqp://" in result
        assert "guestpass" not in result

    def test_http_basic_auth_url(self) -> None:
        """Test HTTP URL with basic auth redaction."""
        url = "http://apiuser:apikey123@api.example.com/v1/data"
        result = redact_url(url)
        assert "http://" in result
        assert "apikey123" not in result

    def test_https_basic_auth_url(self) -> None:
        """Test HTTPS URL with basic auth redaction."""
        url = "https://service:token@secure.example.com/api"
        result = redact_url(url)
        assert "https://" in result
        assert "token" not in result


class TestRedactUrlQueryParameters:
    """Tests for redact_url with query parameters."""

    def test_preserves_query_params(self) -> None:
        """Test that query parameters are preserved after redaction."""
        url = "postgresql://user:secret@localhost:5432/db?sslmode=require"
        result = redact_url(url)
        assert "sslmode=require" in result
        assert "secret" not in result

    def test_preserves_multiple_query_params(self) -> None:
        """Test that multiple query parameters are preserved."""
        url = "postgresql://user:pass@localhost:5432/db?sslmode=require&connect_timeout=10"
        result = redact_url(url)
        assert "sslmode=require" in result
        assert "connect_timeout=10" in result
        assert "pass" not in result.split("@")[0].split(":")[2]

    def test_password_in_query_param_not_redacted_by_redact_url(self) -> None:
        """Test that passwords in query params are NOT redacted by redact_url.

        Note: redact_url only handles URL credential portion, not query params.
        Applications should use redact_sensitive_value for query param handling.
        """
        # This is expected behavior - redact_url only handles the authority portion
        url = "http://localhost:8000?password=secret&api_key=abc123"
        result = redact_url(url)
        # No password in URL authority, so no redaction happens
        assert result == url

    def test_preserves_fragment(self) -> None:
        """Test that URL fragments are preserved."""
        url = "postgresql://user:pass@localhost:5432/db#section"
        result = redact_url(url)
        assert "#section" in result


class TestRedactUrlEdgeCases:
    """Tests for redact_url edge cases."""

    def test_empty_string(self) -> None:
        """Test empty string returns empty."""
        assert redact_url("") == ""

    def test_url_without_credentials(self) -> None:
        """Test URL without any credentials."""
        url = "http://localhost:8000/api/v1"
        result = redact_url(url)
        assert result == url

    def test_url_with_username_only(self) -> None:
        """Test URL with username but no password."""
        url = "redis://user@localhost:6379/0"
        result = redact_url(url)
        assert result == url

    def test_ipv4_host_preserved(self) -> None:
        """Test that IPv4 address is preserved in host."""
        url = "redis://admin:pass@192.168.1.100:6379/0"
        result = redact_url(url)
        assert "192.168.1.100" in result
        assert "pass" not in result

    def test_ipv6_host_preserved(self) -> None:
        """Test that IPv6 address is preserved in host."""
        url = "redis://admin:pass@[::1]:6379/0"
        result = redact_url(url)
        # IPv6 parsing can be tricky - check redaction worked
        assert "pass" not in result.split("@")[0]

    def test_port_preserved(self) -> None:
        """Test that port number is preserved."""
        url = "postgresql://user:pass@localhost:5432/db"
        result = redact_url(url)
        assert ":5432" in result

    def test_database_path_preserved(self) -> None:
        """Test that database path is preserved."""
        url = "postgresql://admin:secret@db.example.com:5432/myapp_production"
        result = redact_url(url)
        assert "/myapp_production" in result
        assert "secret" not in result

    def test_invalid_url_returns_error_placeholder(self) -> None:
        """Test that malformed URLs return error placeholder."""
        # Intentionally malformed URL that might cause parse errors
        url = "://malformed"
        result = redact_url(url)
        # Should either return as-is or error placeholder
        assert result in (url, "[URL REDACTED - PARSE ERROR]")

    def test_password_only_no_username(self) -> None:
        """Test URL with password but no explicit username."""
        url = "redis://:password@localhost:6379/0"
        result = redact_url(url)
        assert "password" not in result
        assert "[REDACTED]" in result

    def test_whitespace_in_url(self) -> None:
        """Test handling of whitespace (should be URL encoded)."""
        # This is technically invalid but should handle gracefully
        url = "postgresql://user:pass word@localhost:5432/db"
        result = redact_url(url)
        # Should handle without crashing
        assert "pass word" not in result or "[REDACTED]" in result


# =============================================================================
# redact_sensitive_value() Tests - Nested Sensitive Fields
# =============================================================================


class TestRedactSensitiveValueNested:
    """Tests for redact_sensitive_value with nested structures."""

    def test_simple_sensitive_field(self) -> None:
        """Test simple sensitive field redaction."""
        result = redact_sensitive_value("password", "mysecret")
        assert result == "[REDACTED]"

    def test_database_url_preserves_structure(self) -> None:
        """Test database_url preserves URL structure while redacting password."""
        url = "postgresql+asyncpg://user:secretpass@localhost:5432/db"
        result = redact_sensitive_value("database_url", url)
        assert "postgresql+asyncpg://" in result
        assert "user:" in result
        assert "localhost:5432/db" in result
        assert "secretpass" not in result
        assert "[REDACTED]" in result

    def test_redis_url_preserves_structure(self) -> None:
        """Test redis_url preserves URL structure while redacting password."""
        url = "redis://default:redispassword@redis:6379/0"
        result = redact_sensitive_value("redis_url", url)
        assert "redis://" in result
        assert "redispassword" not in result
        assert "[REDACTED]" in result

    def test_api_key_fully_redacted(self) -> None:
        """Test API key is fully redacted (not URL-style)."""
        result = redact_sensitive_value("api_key", "sk-1234567890abcdef")
        assert result == "[REDACTED]"
        assert "sk-1234567890abcdef" not in str(result)

    def test_list_of_api_keys_redacted(self) -> None:
        """Test list of API keys are all redacted."""
        keys = ["key1-abc", "key2-def", "key3-ghi"]
        result = redact_sensitive_value("api_keys", keys)
        assert result == ["[REDACTED]", "[REDACTED]", "[REDACTED]"]
        assert len(result) == 3

    def test_empty_list_remains_empty(self) -> None:
        """Test empty list of sensitive values."""
        result = redact_sensitive_value("api_keys", [])
        assert result == []

    def test_non_sensitive_field_unchanged(self) -> None:
        """Test non-sensitive fields are not modified."""
        result = redact_sensitive_value("app_name", "MyApp")
        assert result == "MyApp"

    def test_non_sensitive_boolean_unchanged(self) -> None:
        """Test non-sensitive boolean values are not modified."""
        result = redact_sensitive_value("debug", True)
        assert result is True

    def test_non_sensitive_integer_unchanged(self) -> None:
        """Test non-sensitive integer values are not modified."""
        result = redact_sensitive_value("port", 8000)
        assert result == 8000


class TestRedactSensitiveValueFieldNamePatterns:
    """Tests for field name pattern matching in redact_sensitive_value."""

    def test_exact_match_password(self) -> None:
        """Test exact match 'password' field."""
        result = redact_sensitive_value("password", "secret")
        assert result == "[REDACTED]"

    def test_partial_match_password_prefix(self) -> None:
        """Test partial match with 'password' as prefix."""
        result = redact_sensitive_value("password_hash", "hashed_value")
        assert result == "[REDACTED]"

    def test_partial_match_password_suffix(self) -> None:
        """Test partial match with 'password' as suffix."""
        result = redact_sensitive_value("admin_password", "supersecret")
        assert result == "[REDACTED]"

    def test_partial_match_password_infix(self) -> None:
        """Test partial match with 'password' in middle."""
        result = redact_sensitive_value("user_password_hash", "hashed")
        assert result == "[REDACTED]"

    def test_case_insensitive_matching(self) -> None:
        """Test case-insensitive field name matching."""
        assert redact_sensitive_value("PASSWORD", "secret") == "[REDACTED]"
        assert redact_sensitive_value("Password", "secret") == "[REDACTED]"
        assert (
            redact_sensitive_value("DATABASE_URL", "postgresql://u:p@h/d") != "postgresql://u:p@h/d"
        )

    def test_secret_field_pattern(self) -> None:
        """Test 'secret' pattern matching."""
        result = redact_sensitive_value("client_secret", "abcd1234")
        assert result == "[REDACTED]"

    def test_token_field_pattern(self) -> None:
        """Test 'token' pattern matching."""
        result = redact_sensitive_value("access_token", "eyJhbGciOiJI...")
        assert result == "[REDACTED]"

    def test_key_field_pattern(self) -> None:
        """Test 'key' pattern matching."""
        result = redact_sensitive_value("encryption_key", "0x1234abcd")
        assert result == "[REDACTED]"

    def test_credential_field_pattern(self) -> None:
        """Test 'credential' pattern matching."""
        result = redact_sensitive_value("service_credential", "cred_value")
        assert result == "[REDACTED]"

    def test_all_known_sensitive_fields(self) -> None:
        """Test all fields in SENSITIVE_FIELD_NAMES are properly matched."""
        # Use appropriate test values for different field types
        test_values = {
            "database_url": "postgresql://user:pass@localhost/db",
            "redis_url": "redis://user:pass@localhost:6379/0",
        }

        for field_name in SENSITIVE_FIELD_NAMES:
            test_value = test_values.get(field_name, "test_value")
            result = redact_sensitive_value(field_name, test_value)
            # All should be redacted (either fully or with URL structure)
            assert "[REDACTED]" in str(result), f"Field {field_name} was not redacted"


class TestRedactSensitiveValueSpecificFields:
    """Tests for specific sensitive field names."""

    def test_admin_api_key(self) -> None:
        """Test admin_api_key redaction."""
        result = redact_sensitive_value("admin_api_key", "admin-secret-key-123")
        assert result == "[REDACTED]"

    def test_rtdetr_api_key(self) -> None:
        """Test rtdetr_api_key redaction."""
        result = redact_sensitive_value("rtdetr_api_key", "rtdetr-key-abc")
        assert result == "[REDACTED]"

    def test_nemotron_api_key(self) -> None:
        """Test nemotron_api_key redaction."""
        result = redact_sensitive_value("nemotron_api_key", "nemotron-xyz-789")
        assert result == "[REDACTED]"

    def test_smtp_password(self) -> None:
        """Test smtp_password redaction."""
        result = redact_sensitive_value("smtp_password", "mailsecret123")
        assert result == "[REDACTED]"


class TestRedactSensitiveValueBase64Credentials:
    """Tests for Base64-encoded credentials in sensitive values."""

    def test_base64_encoded_api_key(self) -> None:
        """Test Base64-encoded API key is redacted."""
        b64_key = base64.b64encode(b"my-api-key-12345").decode()
        result = redact_sensitive_value("api_key", b64_key)
        assert result == "[REDACTED]"

    def test_base64_encoded_password(self) -> None:
        """Test Base64-encoded password is redacted."""
        b64_pass = base64.b64encode(b"supersecretpassword").decode()
        result = redact_sensitive_value("password", b64_pass)
        assert result == "[REDACTED]"

    def test_base64_in_url_redacted(self) -> None:
        """Test Base64 password in URL is redacted."""
        b64_pass = base64.b64encode(b"dbpassword").decode()
        url = f"postgresql://user:{b64_pass}@localhost:5432/db"
        result = redact_sensitive_value("database_url", url)
        assert b64_pass not in result
        assert "[REDACTED]" in result


# =============================================================================
# sanitize_error() Tests - Error Message Sanitization
# =============================================================================


class TestSanitizeError:
    """Tests for sanitize_error function."""

    def test_sanitize_password_in_error(self) -> None:
        """Test sanitizing password patterns in error messages."""
        error = Exception("Connection failed: password=secret123")
        result = sanitize_error(error)
        assert "secret123" not in result
        assert "[REDACTED]" in result

    def test_sanitize_secret_in_error(self) -> None:
        """Test sanitizing secret patterns in error messages."""
        error = Exception("Auth error: secret=mysecretvalue")
        result = sanitize_error(error)
        assert "mysecretvalue" not in result
        assert "[REDACTED]" in result

    def test_sanitize_token_in_error(self) -> None:
        """Test sanitizing token patterns in error messages."""
        error = Exception("Invalid token: token=abc123def456")
        result = sanitize_error(error)
        assert "abc123def456" not in result
        assert "[REDACTED]" in result

    def test_sanitize_api_key_in_error(self) -> None:
        """Test sanitizing API key patterns in error messages."""
        error = Exception("API call failed: api_key=sk-1234567890")
        result = sanitize_error(error)
        assert "sk-1234567890" not in result
        assert "[REDACTED]" in result

    def test_sanitize_bearer_token_in_error(self) -> None:
        """Test sanitizing Bearer token patterns in error messages."""
        error = Exception("Auth failed: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        result = sanitize_error(error)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "[REDACTED]" in result

    def test_sanitize_file_paths(self) -> None:
        """Test sanitizing file paths in error messages."""
        error = Exception("File not found: /home/user/secrets/config.yaml")
        result = sanitize_error(error)
        assert "/home/user/secrets" not in result
        assert "config.yaml" in result  # Filename preserved

    def test_sanitize_preserves_error_context(self) -> None:
        """Test that sanitization preserves error context."""
        error = Exception("Database connection failed")
        result = sanitize_error(error)
        assert "Database connection failed" in result

    def test_sanitize_truncates_long_messages(self) -> None:
        """Test that long error messages are truncated."""
        long_msg = "Error: " + "x" * 600
        error = Exception(long_msg)
        result = sanitize_error(error, max_length=500)
        assert len(result) <= 500 + len("...[truncated]")
        assert result.endswith("...[truncated]")

    def test_sanitize_multiple_credentials(self) -> None:
        """Test sanitizing multiple credential patterns in one message."""
        error = Exception("Failed: password=secret1 token=abc123 api_key=key456")
        result = sanitize_error(error)
        assert "secret1" not in result
        assert "abc123" not in result
        assert "key456" not in result
        assert result.count("[REDACTED]") >= 3


# =============================================================================
# Integration Tests
# =============================================================================


class TestCredentialSanitizationIntegration:
    """Integration tests for credential sanitization scenarios."""

    def test_real_world_postgres_connection_error_with_explicit_credential(self) -> None:
        """Test sanitizing PostgreSQL connection error with explicit credential pattern.

        Note: sanitize_error only handles explicit credential patterns like 'password=...',
        not credentials embedded in URL authority sections. For URL redaction, use redact_url().
        """
        # Use explicit credential patterns that sanitize_error handles
        error_msg = "Connection refused to db.production.internal password=Sup3rS3cr3t!"
        error = Exception(error_msg)
        result = sanitize_error(error)
        assert "Sup3rS3cr3t!" not in result
        assert "[REDACTED]" in result

    def test_real_world_redis_connection_error_with_explicit_credential(self) -> None:
        """Test sanitizing Redis connection error with explicit credential pattern.

        Note: sanitize_error only handles explicit credential patterns like 'password=...',
        not credentials embedded in URL authority sections. For URL redaction, use redact_url().
        """
        # Use explicit credential patterns that sanitize_error handles
        error_msg = "Redis connection failed: auth=R3d1sP@ss!"
        error = Exception(error_msg)
        result = sanitize_error(error)
        # Note: sanitize_error uses pattern 'auth' which is caught by 'auth' in pattern
        assert "R3d1sP@ss!" not in result

    def test_url_credential_redaction_requires_redact_url(self) -> None:
        """Test that URL credentials require redact_url, not sanitize_error.

        This test documents that sanitize_error does NOT redact credentials
        embedded in URL authority sections - use redact_url for that.
        """
        url = "postgresql://admin:secret@localhost/db"
        # sanitize_error does NOT handle URL-embedded credentials
        error = Exception(f"Connection to {url} failed")
        result = sanitize_error(error)
        # The secret IS still in the result (expected behavior)
        # This documents that you should use redact_url for URL credentials
        assert "localhost" in result  # URL structure preserved

        # To properly redact, use redact_url:
        redacted_url = redact_url(url)
        assert "secret" not in redacted_url

    def test_settings_dict_redaction(self) -> None:
        """Test redacting a dictionary of settings (simulated Settings object)."""
        settings_dict = {
            "database_url": "postgresql://user:dbpass@localhost/db",
            "redis_url": "redis://:redispass@localhost:6379/0",
            "api_key": "sk-secret-key-123",
            "admin_api_key": "admin-key-456",
            "debug": True,
            "log_level": "INFO",
        }

        redacted = {}
        for key, value in settings_dict.items():
            redacted[key] = redact_sensitive_value(key, value)

        # Check sensitive values are redacted
        assert "dbpass" not in str(redacted["database_url"])
        assert "redispass" not in str(redacted["redis_url"])
        assert redacted["api_key"] == "[REDACTED]"
        assert redacted["admin_api_key"] == "[REDACTED]"

        # Check non-sensitive values are preserved
        assert redacted["debug"] is True
        assert redacted["log_level"] == "INFO"

    def test_nested_config_redaction(self) -> None:
        """Test redacting nested configuration structure."""
        config = {
            "database": {
                "url": "postgresql://user:pass@localhost/db",
                "pool_size": 5,
            },
            "redis": {
                "url": "redis://:secret@localhost:6379/0",
                "max_connections": 10,
            },
            "auth": {
                "api_key": "my-secret-api-key",
                "jwt_secret": "jwt-signing-secret",
            },
        }

        # Redact nested values
        assert "pass" not in redact_url(config["database"]["url"])
        assert "secret" not in redact_url(config["redis"]["url"])
        assert redact_sensitive_value("api_key", config["auth"]["api_key"]) == "[REDACTED]"
        assert redact_sensitive_value("jwt_secret", config["auth"]["jwt_secret"]) == "[REDACTED]"
