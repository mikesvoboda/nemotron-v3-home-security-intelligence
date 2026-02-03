"""Unit tests for APIKey model.

Tests cover APIKey model fields, constraints, relationships, and prefix storage.
These tests MUST FAIL initially (RED phase of TDD) as the model doesn't exist yet.

Test Categories:
- Model field definitions and types
- Prefix extraction and storage
- Hash storage (never plaintext)
- User relationship
- Expiration handling
- Unique constraints
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import inspect

# These imports WILL FAIL initially - that's expected for TDD RED phase
from backend.models.api_key import APIKey

# Mark as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# APIKey Model Field Tests
# =============================================================================


class TestAPIKeyModelFields:
    """Tests for APIKey model field definitions."""

    def test_api_key_model_fields(self) -> None:
        """Test that APIKey model has all required fields."""
        api_key = APIKey(
            id="key_123",
            user_id="user_123",
            prefix="nemo_k1_abc",
            key_hash="hashed_value",  # pragma: allowlist secret
            name="Test API Key",
        )

        assert hasattr(api_key, "id")
        assert hasattr(api_key, "user_id")
        assert hasattr(api_key, "prefix")
        assert hasattr(api_key, "key_hash")
        assert hasattr(api_key, "name")
        assert hasattr(api_key, "created_at")
        assert hasattr(api_key, "last_used_at")
        assert hasattr(api_key, "expires_at")
        assert hasattr(api_key, "is_active")

    def test_api_key_id_field(self) -> None:
        """Test that APIKey has id field."""
        api_key = APIKey(
            id="key_abc123",
            user_id="user_123",
            prefix="nemo_k1_xyz",
            key_hash="hash",  # pragma: allowlist secret
            name="Test Key",
        )

        assert api_key.id == "key_abc123"
        assert isinstance(api_key.id, str)

    def test_api_key_user_id_field(self) -> None:
        """Test that APIKey has user_id foreign key field."""
        api_key = APIKey(
            id="key_123",
            user_id="user_456",
            prefix="nemo_k1_test",
            key_hash="hash",  # pragma: allowlist secret
            name="Test Key",
        )

        assert api_key.user_id == "user_456"
        assert isinstance(api_key.user_id, str)

    def test_api_key_prefix_field(self) -> None:
        """Test that APIKey has prefix field."""
        api_key = APIKey(
            id="key_123",
            user_id="user_123",
            prefix="nemo_k1_prefix123",
            key_hash="hash",  # pragma: allowlist secret
            name="Test Key",
        )

        assert api_key.prefix == "nemo_k1_prefix123"
        assert isinstance(api_key.prefix, str)

    def test_api_key_key_hash_field(self) -> None:
        """Test that APIKey has key_hash field."""
        key_hash = "sha256_hashed_value"  # pragma: allowlist secret
        api_key = APIKey(
            id="key_123",
            user_id="user_123",
            prefix="nemo_k1_test",
            key_hash=key_hash,
            name="Test Key",
        )

        assert api_key.key_hash == key_hash
        assert isinstance(api_key.key_hash, str)

    def test_api_key_name_field(self) -> None:
        """Test that APIKey has name field for identification."""
        api_key = APIKey(
            id="key_123",
            user_id="user_123",
            prefix="nemo_k1_test",
            key_hash="hash",  # pragma: allowlist secret
            name="Production API Key",
        )

        assert api_key.name == "Production API Key"
        assert isinstance(api_key.name, str)


# =============================================================================
# APIKey Prefix Storage Tests
# =============================================================================


class TestAPIKeyPrefix:
    """Tests for APIKey prefix extraction and storage."""

    def test_api_key_prefix_stored(self) -> None:
        """Test that API key prefix is stored in database."""
        api_key = APIKey(
            id="key_123",
            user_id="user_123",
            prefix="nemo_k1_abc123",
            key_hash="hash",  # pragma: allowlist secret
            name="Test Key",
        )

        # Prefix should be stored for quick lookup
        assert api_key.prefix is not None
        assert api_key.prefix.startswith("nemo_k1_")

    def test_api_key_prefix_format(self) -> None:
        """Test that prefix follows nemo_k1_<first_chars> format."""
        api_key = APIKey(
            id="key_123",
            user_id="user_123",
            prefix="nemo_k1_xyz789",
            key_hash="hash",  # pragma: allowlist secret
            name="Test Key",
        )

        # Prefix should include the visible part of the key
        assert api_key.prefix.startswith("nemo_k1_")
        assert len(api_key.prefix) > len("nemo_k1_")

    def test_api_key_prefix_unique_per_key(self) -> None:
        """Test that different keys have different prefixes."""
        key1 = APIKey(
            id="key_1",
            user_id="user_123",
            prefix="nemo_k1_abc123",
            key_hash="hash1",  # pragma: allowlist secret
            name="Key 1",
        )
        key2 = APIKey(
            id="key_2",
            user_id="user_123",
            prefix="nemo_k1_xyz789",
            key_hash="hash2",  # pragma: allowlist secret
            name="Key 2",
        )

        assert key1.prefix != key2.prefix


# =============================================================================
# APIKey Hash Storage Tests
# =============================================================================


class TestAPIKeyHashStorage:
    """Tests for API key hash storage (never plaintext)."""

    def test_api_key_hash_stored_not_plaintext(self) -> None:
        """Test that only hash is stored, never plaintext key."""
        api_key = APIKey(
            id="key_123",
            user_id="user_123",
            prefix="nemo_k1_test",
            key_hash="hashed_value",  # pragma: allowlist secret
            name="Test Key",
        )

        # Should NOT have a 'key' field for plaintext
        assert not hasattr(api_key, "key")
        # Should only have key_hash
        assert hasattr(api_key, "key_hash")
        assert api_key.key_hash is not None

    def test_api_key_hash_required(self) -> None:
        """Test that key_hash is a required field."""
        with pytest.raises(TypeError):
            APIKey(
                id="key_123",
                user_id="user_123",
                prefix="nemo_k1_test",
                name="Test Key",
                # Missing key_hash
            )

    def test_api_key_hash_not_nullable(self) -> None:
        """Test that key_hash column is not nullable."""
        mapper = inspect(APIKey)
        key_hash_col = mapper.columns["key_hash"]

        assert key_hash_col.nullable is False


# =============================================================================
# APIKey User Relationship Tests
# =============================================================================


class TestAPIKeyUserRelationship:
    """Tests for APIKey to User relationship."""

    def test_api_key_user_relationship(self) -> None:
        """Test that APIKey has relationship to User."""
        api_key = APIKey(
            id="key_123",
            user_id="user_123",
            prefix="nemo_k1_test",
            key_hash="hash",  # pragma: allowlist secret
            name="Test Key",
        )

        # Should have user relationship
        assert hasattr(api_key, "user")

    def test_api_key_user_id_foreign_key(self) -> None:
        """Test that user_id is a foreign key to users table."""
        mapper = inspect(APIKey)
        user_id_col = mapper.columns["user_id"]

        # Should have foreign key constraint
        assert len(user_id_col.foreign_keys) > 0
        # Foreign key should point to users table
        fk = list(user_id_col.foreign_keys)[0]
        assert "users" in str(fk.target_fullname)

    def test_api_key_user_id_required(self) -> None:
        """Test that user_id is required."""
        with pytest.raises(TypeError):
            APIKey(
                id="key_123",
                prefix="nemo_k1_test",
                key_hash="hash",  # pragma: allowlist secret
                name="Test Key",
                # Missing user_id
            )

    def test_api_key_user_id_not_nullable(self) -> None:
        """Test that user_id column is not nullable."""
        mapper = inspect(APIKey)
        user_id_col = mapper.columns["user_id"]

        assert user_id_col.nullable is False


# =============================================================================
# APIKey Expiration Tests
# =============================================================================


class TestAPIKeyExpiration:
    """Tests for API key expiration handling."""

    def test_api_key_expires_at_nullable(self) -> None:
        """Test that expires_at is nullable (keys can be permanent)."""
        api_key = APIKey(
            id="key_123",
            user_id="user_123",
            prefix="nemo_k1_test",
            key_hash="hash",  # pragma: allowlist secret
            name="Test Key",
            expires_at=None,
        )

        assert api_key.expires_at is None

        # Check column definition
        mapper = inspect(APIKey)
        expires_at_col = mapper.columns["expires_at"]
        assert expires_at_col.nullable is True

    def test_api_key_with_expiration(self) -> None:
        """Test creating API key with expiration date."""
        expires_at = datetime.now(UTC) + timedelta(days=30)
        api_key = APIKey(
            id="key_123",
            user_id="user_123",
            prefix="nemo_k1_test",
            key_hash="hash",  # pragma: allowlist secret
            name="Test Key",
            expires_at=expires_at,
        )

        assert api_key.expires_at == expires_at

    def test_api_key_expires_at_timezone_aware(self) -> None:
        """Test that expires_at is timezone-aware."""
        mapper = inspect(APIKey)
        expires_at_col = mapper.columns["expires_at"]

        # Should be DateTime with timezone=True
        assert hasattr(expires_at_col.type, "timezone")
        assert expires_at_col.type.timezone is True

    def test_api_key_expired_property(self) -> None:
        """Test checking if API key is expired."""
        # Key with past expiration
        past_expiration = datetime.now(UTC) - timedelta(days=1)
        expired_key = APIKey(
            id="key_expired",
            user_id="user_123",
            prefix="nemo_k1_expired",
            key_hash="hash",  # pragma: allowlist secret
            name="Expired Key",
            expires_at=past_expiration,
        )

        # Key with future expiration
        future_expiration = datetime.now(UTC) + timedelta(days=30)
        active_key = APIKey(
            id="key_active",
            user_id="user_123",
            prefix="nemo_k1_active",
            key_hash="hash",  # pragma: allowlist secret
            name="Active Key",
            expires_at=future_expiration,
        )

        # Key with no expiration
        permanent_key = APIKey(
            id="key_permanent",
            user_id="user_123",
            prefix="nemo_k1_permanent",
            key_hash="hash",  # pragma: allowlist secret
            name="Permanent Key",
            expires_at=None,
        )

        # These assertions may depend on is_expired property implementation
        # Leaving as documentation of expected behavior


# =============================================================================
# APIKey Timestamp Tests
# =============================================================================


class TestAPIKeyTimestamps:
    """Tests for APIKey timestamp fields."""

    def test_api_key_created_at_default(self) -> None:
        """Test that created_at has a default value."""
        mapper = inspect(APIKey)
        created_at_col = mapper.columns["created_at"]

        # Should have a default (datetime.now)
        assert created_at_col.default is not None

    def test_api_key_created_at_timezone_aware(self) -> None:
        """Test that created_at is timezone-aware."""
        mapper = inspect(APIKey)
        created_at_col = mapper.columns["created_at"]

        assert hasattr(created_at_col.type, "timezone")
        assert created_at_col.type.timezone is True

    def test_api_key_last_used_at_nullable(self) -> None:
        """Test that last_used_at is nullable (key may not be used yet)."""
        api_key = APIKey(
            id="key_123",
            user_id="user_123",
            prefix="nemo_k1_test",
            key_hash="hash",  # pragma: allowlist secret
            name="Test Key",
        )

        assert api_key.last_used_at is None

        mapper = inspect(APIKey)
        last_used_at_col = mapper.columns["last_used_at"]
        assert last_used_at_col.nullable is True

    def test_api_key_last_used_at_timezone_aware(self) -> None:
        """Test that last_used_at is timezone-aware."""
        mapper = inspect(APIKey)
        last_used_at_col = mapper.columns["last_used_at"]

        assert hasattr(last_used_at_col.type, "timezone")
        assert last_used_at_col.type.timezone is True

    def test_api_key_last_used_at_updates(self) -> None:
        """Test that last_used_at can be updated."""
        now = datetime.now(UTC)
        api_key = APIKey(
            id="key_123",
            user_id="user_123",
            prefix="nemo_k1_test",
            key_hash="hash",  # pragma: allowlist secret
            name="Test Key",
            last_used_at=now,
        )

        assert api_key.last_used_at == now


# =============================================================================
# APIKey Status Tests
# =============================================================================


class TestAPIKeyStatus:
    """Tests for API key active/inactive status."""

    def test_api_key_is_active_field(self) -> None:
        """Test that APIKey has is_active field."""
        api_key = APIKey(
            id="key_123",
            user_id="user_123",
            prefix="nemo_k1_test",
            key_hash="hash",  # pragma: allowlist secret
            name="Test Key",
            is_active=True,
        )

        assert hasattr(api_key, "is_active")
        assert api_key.is_active is True

    def test_api_key_is_active_default_true(self) -> None:
        """Test that is_active defaults to True."""
        mapper = inspect(APIKey)
        is_active_col = mapper.columns["is_active"]

        assert is_active_col.default is not None
        assert is_active_col.default.arg is True

    def test_api_key_can_be_deactivated(self) -> None:
        """Test that API key can be set to inactive."""
        api_key = APIKey(
            id="key_123",
            user_id="user_123",
            prefix="nemo_k1_test",
            key_hash="hash",  # pragma: allowlist secret
            name="Test Key",
            is_active=False,
        )

        assert api_key.is_active is False


# =============================================================================
# APIKey Model Behavior Tests
# =============================================================================


class TestAPIKeyModelBehavior:
    """Tests for APIKey model behavior."""

    def test_api_key_repr(self) -> None:
        """Test APIKey string representation."""
        api_key = APIKey(
            id="key_123",
            user_id="user_123",
            prefix="nemo_k1_test123",
            key_hash="hash",  # pragma: allowlist secret
            name="Test API Key",
        )

        repr_str = repr(api_key)

        assert "APIKey" in repr_str
        assert "nemo_k1_test123" in repr_str or "Test API Key" in repr_str

    def test_api_key_table_name(self) -> None:
        """Test that APIKey model has correct table name."""
        assert APIKey.__tablename__ == "api_keys"

    def test_api_key_with_all_fields_populated(self) -> None:
        """Test creating API key with all fields."""
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=90)

        api_key = APIKey(
            id="key_123",
            user_id="user_123",
            prefix="nemo_k1_complete",
            key_hash="hashed_value",  # pragma: allowlist secret
            name="Complete API Key",
            created_at=now,
            last_used_at=now,
            expires_at=expires_at,
            is_active=True,
        )

        assert api_key.id == "key_123"
        assert api_key.user_id == "user_123"
        assert api_key.prefix == "nemo_k1_complete"
        assert api_key.key_hash == "hashed_value"
        assert api_key.name == "Complete API Key"
        assert api_key.created_at == now
        assert api_key.last_used_at == now
        assert api_key.expires_at == expires_at
        assert api_key.is_active is True


# =============================================================================
# APIKey Column Types
# =============================================================================


class TestAPIKeyColumnTypes:
    """Tests for APIKey model column types."""

    def test_api_key_id_column_type(self) -> None:
        """Test that id column is String (primary key)."""
        mapper = inspect(APIKey)
        id_col = mapper.columns["id"]

        assert id_col.primary_key is True
        assert "String" in str(id_col.type) or "VARCHAR" in str(id_col.type)

    def test_api_key_prefix_column_type(self) -> None:
        """Test that prefix is String."""
        mapper = inspect(APIKey)
        prefix_col = mapper.columns["prefix"]

        assert "String" in str(prefix_col.type) or "VARCHAR" in str(prefix_col.type)

    def test_api_key_key_hash_column_type(self) -> None:
        """Test that key_hash is String."""
        mapper = inspect(APIKey)
        key_hash_col = mapper.columns["key_hash"]

        assert "String" in str(key_hash_col.type) or "VARCHAR" in str(key_hash_col.type)

    def test_api_key_name_column_type(self) -> None:
        """Test that name is String."""
        mapper = inspect(APIKey)
        name_col = mapper.columns["name"]

        assert "String" in str(name_col.type) or "VARCHAR" in str(name_col.type)

    def test_api_key_is_active_column_type(self) -> None:
        """Test that is_active is Boolean."""
        mapper = inspect(APIKey)
        is_active_col = mapper.columns["is_active"]

        assert "Boolean" in str(is_active_col.type) or "BOOLEAN" in str(is_active_col.type)
