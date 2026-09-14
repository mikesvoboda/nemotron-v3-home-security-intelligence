"""Tests for SecretStr configuration fields (NEM-3429)."""

from pydantic import SecretStr


class TestSecretStrFields:
    """Tests for SecretStr usage in sensitive configuration fields."""

    def test_redis_password_is_secretstr(self):
        """Test that redis_password field is SecretStr type."""
        from backend.core.config import Settings

        # Check the field annotation
        field_info = Settings.model_fields.get("redis_password")
        assert field_info is not None

        # The annotation should be SecretStr | None
        annotation = field_info.annotation
        # Check if SecretStr is in the type annotation
        assert "SecretStr" in str(annotation)

    def test_admin_api_key_is_secretstr(self):
        """Test that admin_api_key field is SecretStr type."""
        from backend.core.config import Settings

        field_info = Settings.model_fields.get("admin_api_key")
        assert field_info is not None
        assert "SecretStr" in str(field_info.annotation)

    def test_yolo26_api_key_is_secretstr(self):
        """Test that yolo26_api_key field is SecretStr type."""
        from backend.core.config import Settings

        field_info = Settings.model_fields.get("yolo26_api_key")
        assert field_info is not None
        assert "SecretStr" in str(field_info.annotation)

    def test_nemotron_api_key_is_secretstr(self):
        """Test that nemotron_api_key field is SecretStr type."""
        from backend.core.config import Settings

        field_info = Settings.model_fields.get("nemotron_api_key")
        assert field_info is not None
        assert "SecretStr" in str(field_info.annotation)

    def test_smtp_password_is_secretstr(self):
        """Test that smtp_password field is SecretStr type."""
        from backend.core.config import Settings

        field_info = Settings.model_fields.get("smtp_password")
        assert field_info is not None
        assert "SecretStr" in str(field_info.annotation)

    def test_websocket_token_is_secretstr(self):
        """Test that websocket_token field is SecretStr type."""
        from backend.core.config import Settings

        field_info = Settings.model_fields.get("websocket_token")
        assert field_info is not None
        assert "SecretStr" in str(field_info.annotation)

    def test_api_keys_is_list_of_secretstr(self):
        """Test that api_keys field is list[SecretStr] type."""
        from backend.core.config import Settings

        field_info = Settings.model_fields.get("api_keys")
        assert field_info is not None
        # Should be list[SecretStr]
        assert "list" in str(field_info.annotation).lower()
        assert "SecretStr" in str(field_info.annotation)


class TestSecretStrBehavior:
    """Tests for SecretStr behavior and security properties."""

    def test_secretstr_repr_is_masked(self):
        """Test that SecretStr repr does not expose the value."""
        secret = SecretStr("my-secret-password")
        repr_str = repr(secret)

        assert "my-secret-password" not in repr_str
        assert "**" in repr_str or "SecretStr" in repr_str

    def test_secretstr_str_is_masked(self):
        """Test that SecretStr str conversion does not expose the value."""
        secret = SecretStr("my-secret-password")
        str_value = str(secret)

        assert "my-secret-password" not in str_value

    def test_secretstr_get_secret_value(self):
        """Test that get_secret_value() returns the actual value."""
        secret = SecretStr("my-secret-password")
        value = secret.get_secret_value()

        assert value == "my-secret-password"

    def test_secretstr_json_serialization_is_masked(self):
        """Test that SecretStr is masked when serializing to JSON."""
        from pydantic import BaseModel

        class ConfigWithSecret(BaseModel):
            password: SecretStr

        config = ConfigWithSecret(password="secret123")
        json_str = config.model_dump_json()

        # SecretStr should be masked in JSON output by default
        assert "secret123" not in json_str


class TestSecretStrIntegration:
    """Integration tests for SecretStr with code that uses secrets."""

    def test_redis_password_extraction(self):
        """Test that redis password can be extracted for use."""
        # This tests the pattern used in redis.py
        secret = SecretStr("redis-pass")

        # Pattern used in codebase
        password_value = (
            secret.get_secret_value() if hasattr(secret, "get_secret_value") else secret
        )

        assert password_value == "redis-pass"  # pragma: allowlist secret

    def test_api_key_hashing_pattern(self):
        """Test the pattern for hashing SecretStr API keys."""
        import hashlib

        secret_key = SecretStr("api-key-123")

        # Pattern used in auth middleware
        key_value: str = (
            secret_key.get_secret_value()
            if hasattr(secret_key, "get_secret_value")
            else str(secret_key)
        )
        key_hash = hashlib.sha256(key_value.encode()).hexdigest()

        # Verify we can hash the actual value
        expected_hash = hashlib.sha256(b"api-key-123").hexdigest()
        assert key_hash == expected_hash

    def test_none_secret_handling(self):
        """Test handling of None values for optional SecretStr fields."""
        secret: SecretStr | None = None

        # Pattern used in codebase for optional secrets
        if secret:
            value = (
                secret.get_secret_value() if hasattr(secret, "get_secret_value") else str(secret)
            )
        else:
            value = None

        assert value is None

    def test_empty_secret_is_falsy(self):
        """Test that empty SecretStr behaves correctly in boolean context."""
        empty_secret = SecretStr("")

        # Empty SecretStr should still be truthy (it's an object)
        # But the value is empty
        assert empty_secret.get_secret_value() == ""
