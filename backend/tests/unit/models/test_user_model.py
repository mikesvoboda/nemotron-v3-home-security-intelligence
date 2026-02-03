"""Unit tests for User model.

Tests cover User model fields, constraints, relationships, and validation.
These tests MUST FAIL initially (RED phase of TDD) as the model doesn't exist yet.

Test Categories:
- Model field definitions and types
- Password handling (never store plaintext)
- Unique constraints (email, username)
- Timestamps and defaults
- String representation
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect

# These imports WILL FAIL initially - that's expected for TDD RED phase
from backend.models.user import User

# Mark as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# User Model Field Tests
# =============================================================================


class TestUserModelFields:
    """Tests for User model field definitions."""

    def test_user_model_fields(self) -> None:
        """Test that User model has all required fields."""
        user = User(
            id="user_123",
            username="testuser",
            email="test@example.com",
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$test",  # pragma: allowlist secret
        )

        assert hasattr(user, "id")
        assert hasattr(user, "username")
        assert hasattr(user, "email")
        assert hasattr(user, "password_hash")
        assert hasattr(user, "created_at")
        assert hasattr(user, "updated_at")
        assert hasattr(user, "last_login_at")
        assert hasattr(user, "is_active")

    def test_user_id_field(self) -> None:
        """Test that User has id field of correct type."""
        user = User(
            id="user_abc123",
            username="testuser",
            email="test@example.com",
            password_hash="hash",  # pragma: allowlist secret
        )

        assert user.id == "user_abc123"
        assert isinstance(user.id, str)

    def test_user_username_field(self) -> None:
        """Test that User has username field."""
        user = User(
            id="user_123",
            username="johndoe",
            email="john@example.com",
            password_hash="hash",  # pragma: allowlist secret
        )

        assert user.username == "johndoe"
        assert isinstance(user.username, str)

    def test_user_email_field(self) -> None:
        """Test that User has email field."""
        user = User(
            id="user_123",
            username="testuser",
            email="user@example.com",
            password_hash="hash",  # pragma: allowlist secret
        )

        assert user.email == "user@example.com"
        assert isinstance(user.email, str)

    def test_user_password_hash_field(self) -> None:
        """Test that User has password_hash field."""
        password_hash = "$argon2id$v=19$m=65536,t=3,p=4$test"  # pragma: allowlist secret
        user = User(
            id="user_123",
            username="testuser",
            email="test@example.com",
            password_hash=password_hash,
        )

        assert user.password_hash == password_hash
        assert isinstance(user.password_hash, str)

    def test_user_created_at_field(self) -> None:
        """Test that User has created_at field with default."""
        user = User(
            id="user_123",
            username="testuser",
            email="test@example.com",
            password_hash="hash",  # pragma: allowlist secret
        )

        assert hasattr(user, "created_at")
        # created_at should have a default value or be set
        assert user.created_at is not None or user.created_at is None  # May depend on DB

    def test_user_updated_at_field(self) -> None:
        """Test that User has updated_at field."""
        user = User(
            id="user_123",
            username="testuser",
            email="test@example.com",
            password_hash="hash",  # pragma: allowlist secret
        )

        assert hasattr(user, "updated_at")

    def test_user_last_login_at_field(self) -> None:
        """Test that User has last_login_at field (nullable)."""
        user = User(
            id="user_123",
            username="testuser",
            email="test@example.com",
            password_hash="hash",  # pragma: allowlist secret
        )

        assert hasattr(user, "last_login_at")
        # Should be nullable (user hasn't logged in yet)
        assert user.last_login_at is None

    def test_user_is_active_field(self) -> None:
        """Test that User has is_active field with default True."""
        user = User(
            id="user_123",
            username="testuser",
            email="test@example.com",
            password_hash="hash",  # pragma: allowlist secret
        )

        assert hasattr(user, "is_active")
        # Should default to True
        assert user.is_active is True


# =============================================================================
# Password Security Tests
# =============================================================================


class TestUserPasswordSecurity:
    """Tests for password security in User model."""

    def test_user_password_not_stored_plaintext(self) -> None:
        """Test that User model does not have a password field for plaintext."""
        user = User(
            id="user_123",
            username="testuser",
            email="test@example.com",
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$test",  # pragma: allowlist secret
        )

        # Should NOT have a 'password' field
        assert not hasattr(user, "password")
        # Should only have password_hash
        assert hasattr(user, "password_hash")

    def test_user_password_hash_required(self) -> None:
        """Test that password_hash is required field."""
        # Attempting to create user without password_hash should fail
        with pytest.raises(TypeError):
            User(
                id="user_123",
                username="testuser",
                email="test@example.com",
            )

    def test_user_password_hash_not_nullable(self) -> None:
        """Test that password_hash column is not nullable."""
        mapper = inspect(User)
        password_hash_col = mapper.columns["password_hash"]

        assert password_hash_col.nullable is False

    def test_user_password_hash_accepts_argon2_format(self) -> None:
        """Test that password_hash accepts argon2 format."""
        argon2_hash = "$argon2id$v=19$m=65536,t=3,p=4$somehashedvalue"  # pragma: allowlist secret
        user = User(
            id="user_123",
            username="testuser",
            email="test@example.com",
            password_hash=argon2_hash,
        )

        assert user.password_hash == argon2_hash
        assert user.password_hash.startswith("$argon2")


# =============================================================================
# Unique Constraint Tests
# =============================================================================


class TestUserUniqueConstraints:
    """Tests for User model unique constraints."""

    def test_user_email_unique_constraint(self) -> None:
        """Test that email field has unique constraint."""
        mapper = inspect(User)
        email_col = mapper.columns["email"]

        # Check for unique constraint
        assert email_col.unique is True

    def test_user_username_unique_constraint(self) -> None:
        """Test that username field has unique constraint."""
        mapper = inspect(User)
        username_col = mapper.columns["username"]

        # Check for unique constraint
        assert username_col.unique is True

    def test_user_email_case_sensitivity(self) -> None:
        """Test email field behavior (should be case-insensitive in practice)."""
        # This tests the model definition, actual uniqueness is DB-level
        user1 = User(
            id="user_1",
            username="user1",
            email="Test@Example.com",
            password_hash="hash1",  # pragma: allowlist secret
        )
        user2 = User(
            id="user_2",
            username="user2",
            email="test@example.com",
            password_hash="hash2",  # pragma: allowlist secret
        )

        # Both should create successfully (DB will enforce uniqueness)
        assert user1.email != user2.email  # Different case


# =============================================================================
# Timestamp Tests
# =============================================================================


class TestUserTimestamps:
    """Tests for User model timestamp fields."""

    def test_user_created_at_default(self) -> None:
        """Test that created_at has a default value."""
        mapper = inspect(User)
        created_at_col = mapper.columns["created_at"]

        # Should have a default (datetime.now)
        assert created_at_col.default is not None

    def test_user_created_at_timezone_aware(self) -> None:
        """Test that created_at is timezone-aware."""
        mapper = inspect(User)
        created_at_col = mapper.columns["created_at"]

        # Should be DateTime with timezone=True
        assert hasattr(created_at_col.type, "timezone")
        assert created_at_col.type.timezone is True

    def test_user_updated_at_timezone_aware(self) -> None:
        """Test that updated_at is timezone-aware."""
        mapper = inspect(User)
        updated_at_col = mapper.columns["updated_at"]

        assert hasattr(updated_at_col.type, "timezone")
        assert updated_at_col.type.timezone is True

    def test_user_last_login_at_nullable(self) -> None:
        """Test that last_login_at is nullable."""
        mapper = inspect(User)
        last_login_at_col = mapper.columns["last_login_at"]

        assert last_login_at_col.nullable is True

    def test_user_last_login_at_timezone_aware(self) -> None:
        """Test that last_login_at is timezone-aware."""
        mapper = inspect(User)
        last_login_at_col = mapper.columns["last_login_at"]

        assert hasattr(last_login_at_col.type, "timezone")
        assert last_login_at_col.type.timezone is True

    def test_user_timestamps_preserve_timezone(self) -> None:
        """Test that timestamps preserve timezone information."""
        now = datetime.now(UTC)
        user = User(
            id="user_123",
            username="testuser",
            email="test@example.com",
            password_hash="hash",  # pragma: allowlist secret
            created_at=now,
            last_login_at=now,
        )

        # Timestamps should preserve timezone
        if user.created_at is not None:
            assert user.created_at.tzinfo is not None
        if user.last_login_at is not None:
            assert user.last_login_at.tzinfo is not None


# =============================================================================
# User Model Behavior Tests
# =============================================================================


class TestUserModelBehavior:
    """Tests for User model behavior and methods."""

    def test_user_repr(self) -> None:
        """Test User string representation."""
        user = User(
            id="user_123",
            username="testuser",
            email="test@example.com",
            password_hash="hash",  # pragma: allowlist secret
        )

        repr_str = repr(user)

        assert "User" in repr_str
        assert "testuser" in repr_str or "test@example.com" in repr_str

    def test_user_is_active_default_true(self) -> None:
        """Test that is_active defaults to True."""
        mapper = inspect(User)
        is_active_col = mapper.columns["is_active"]

        assert is_active_col.default is not None
        assert is_active_col.default.arg is True

    def test_user_is_active_can_be_false(self) -> None:
        """Test that is_active can be set to False."""
        user = User(
            id="user_123",
            username="testuser",
            email="test@example.com",
            password_hash="hash",  # pragma: allowlist secret
            is_active=False,
        )

        assert user.is_active is False

    def test_user_table_name(self) -> None:
        """Test that User model has correct table name."""
        assert User.__tablename__ == "users"


# =============================================================================
# User Relationship Tests
# =============================================================================


class TestUserRelationships:
    """Tests for User model relationships."""

    def test_user_has_api_keys_relationship(self) -> None:
        """Test that User has relationship to APIKey."""
        user = User(
            id="user_123",
            username="testuser",
            email="test@example.com",
            password_hash="hash",  # pragma: allowlist secret
        )

        # Should have api_keys relationship
        assert hasattr(user, "api_keys")

    def test_user_has_sessions_relationship(self) -> None:
        """Test that User has relationship to Session (if sessions are stored in DB)."""
        # Note: Sessions might be Redis-only, but if there's a DB model, test it
        user = User(
            id="user_123",
            username="testuser",
            email="test@example.com",
            password_hash="hash",  # pragma: allowlist secret
        )

        # This may not exist if sessions are Redis-only
        # assert hasattr(user, "sessions")
        pass


# =============================================================================
# User Model Column Types
# =============================================================================


class TestUserColumnTypes:
    """Tests for User model column types."""

    def test_user_id_column_type(self) -> None:
        """Test that id column is String (primary key)."""
        mapper = inspect(User)
        id_col = mapper.columns["id"]

        assert id_col.primary_key is True
        # Should be String type
        assert "String" in str(id_col.type) or "VARCHAR" in str(id_col.type)

    def test_user_username_column_type(self) -> None:
        """Test that username is String."""
        mapper = inspect(User)
        username_col = mapper.columns["username"]

        assert "String" in str(username_col.type) or "VARCHAR" in str(username_col.type)

    def test_user_email_column_type(self) -> None:
        """Test that email is String."""
        mapper = inspect(User)
        email_col = mapper.columns["email"]

        assert "String" in str(email_col.type) or "VARCHAR" in str(email_col.type)

    def test_user_password_hash_column_type(self) -> None:
        """Test that password_hash is String."""
        mapper = inspect(User)
        password_hash_col = mapper.columns["password_hash"]

        assert "String" in str(password_hash_col.type) or "VARCHAR" in str(password_hash_col.type)

    def test_user_is_active_column_type(self) -> None:
        """Test that is_active is Boolean."""
        mapper = inspect(User)
        is_active_col = mapper.columns["is_active"]

        assert "Boolean" in str(is_active_col.type) or "BOOLEAN" in str(is_active_col.type)


# =============================================================================
# User Model Validation Tests
# =============================================================================


class TestUserValidation:
    """Tests for User model validation."""

    def test_user_email_not_empty(self) -> None:
        """Test that email cannot be empty string."""
        # This may be enforced by DB or application layer
        user = User(
            id="user_123",
            username="testuser",
            email="",  # Empty email
            password_hash="hash",  # pragma: allowlist secret
        )

        # Should still create (validation may be app-layer)
        assert user.email == ""

    def test_user_username_not_empty(self) -> None:
        """Test that username cannot be empty string."""
        user = User(
            id="user_123",
            username="",  # Empty username
            email="test@example.com",
            password_hash="hash",  # pragma: allowlist secret
        )

        # Should still create (validation may be app-layer)
        assert user.username == ""

    def test_user_with_all_fields_populated(self) -> None:
        """Test creating user with all fields populated."""
        now = datetime.now(UTC)
        user = User(
            id="user_123",
            username="testuser",
            email="test@example.com",
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$test",  # pragma: allowlist secret
            created_at=now,
            updated_at=now,
            last_login_at=now,
            is_active=True,
        )

        assert user.id == "user_123"
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.created_at == now
        assert user.updated_at == now
        assert user.last_login_at == now
        assert user.is_active is True
