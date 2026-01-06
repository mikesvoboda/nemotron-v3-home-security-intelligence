"""Unit tests for APIKey model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- Key hash field requirements
- Active/inactive state handling
- Property-based tests for field values
"""

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.api_key import APIKey

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid key hashes (64 character hex strings like SHA-256)
key_hashes = st.text(
    alphabet="0123456789abcdef",
    min_size=64,
    max_size=64,
)

# Strategy for API key names
key_names = st.text(
    min_size=1,
    max_size=100,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs"), whitelist_characters="-_"
    ),
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_api_key():
    """Create a sample API key for testing."""
    return APIKey(
        id=1,
        key_hash="a" * 64,  # 64-character hash
        name="Production API Key",
        is_active=True,
    )


@pytest.fixture
def inactive_api_key():
    """Create an inactive API key for testing."""
    return APIKey(
        id=2,
        key_hash="b" * 64,
        name="Deprecated Key",
        is_active=False,
    )


@pytest.fixture
def minimal_api_key():
    """Create an API key with minimal required fields."""
    return APIKey(
        key_hash="c" * 64,
        name="Test Key",
    )


# =============================================================================
# APIKey Model Initialization Tests
# =============================================================================


class TestAPIKeyModelInitialization:
    """Tests for APIKey model initialization."""

    def test_api_key_creation_minimal(self):
        """Test creating an API key with minimal required fields."""
        api_key = APIKey(
            key_hash="d" * 64,
            name="Test Key",
        )

        assert api_key.key_hash == "d" * 64
        assert api_key.name == "Test Key"

    def test_api_key_with_all_fields(self, sample_api_key):
        """Test API key with all fields populated."""
        assert sample_api_key.id == 1
        assert sample_api_key.key_hash == "a" * 64
        assert sample_api_key.name == "Production API Key"
        assert sample_api_key.is_active is True

    def test_api_key_default_is_active_column_definition(self):
        """Test that is_active column defaults to True.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(APIKey)
        is_active_col = mapper.columns["is_active"]
        assert is_active_col.default is not None
        assert is_active_col.default.arg is True

    def test_api_key_with_custom_id(self):
        """Test API key with custom ID."""
        api_key = APIKey(
            id=100,
            key_hash="e" * 64,
            name="Custom ID Key",
        )
        assert api_key.id == 100


# =============================================================================
# APIKey Field Tests
# =============================================================================


class TestAPIKeyHashField:
    """Tests for APIKey key_hash field."""

    def test_key_hash_64_chars(self, sample_api_key):
        """Test key hash is 64 characters."""
        assert len(sample_api_key.key_hash) == 64

    def test_key_hash_lowercase_hex(self):
        """Test key hash with lowercase hex characters."""
        api_key = APIKey(
            key_hash="0123456789abcdef" * 4,
            name="Test",
        )
        assert api_key.key_hash == "0123456789abcdef" * 4

    def test_key_hash_uppercase_hex(self):
        """Test key hash with uppercase hex characters."""
        api_key = APIKey(
            key_hash="0123456789ABCDEF" * 4,
            name="Test",
        )
        assert api_key.key_hash == "0123456789ABCDEF" * 4

    def test_key_hash_mixed_case_hex(self):
        """Test key hash with mixed case hex characters."""
        api_key = APIKey(
            key_hash="aAbBcCdD" * 8,
            name="Test",
        )
        assert api_key.key_hash == "aAbBcCdD" * 8

    def test_key_hash_all_zeros(self):
        """Test key hash with all zeros."""
        api_key = APIKey(
            key_hash="0" * 64,
            name="Test",
        )
        assert api_key.key_hash == "0" * 64

    def test_key_hash_all_fs(self):
        """Test key hash with all 'f' characters."""
        api_key = APIKey(
            key_hash="f" * 64,
            name="Test",
        )
        assert api_key.key_hash == "f" * 64


class TestAPIKeyNameField:
    """Tests for APIKey name field."""

    def test_key_name_simple(self, sample_api_key):
        """Test key with simple name."""
        assert sample_api_key.name == "Production API Key"

    def test_key_name_short(self):
        """Test key with short name."""
        api_key = APIKey(
            key_hash="0" * 64,
            name="X",
        )
        assert api_key.name == "X"

    def test_key_name_max_length(self):
        """Test key with maximum length name (100 chars)."""
        long_name = "A" * 100
        api_key = APIKey(
            key_hash="0" * 64,
            name=long_name,
        )
        assert api_key.name == long_name
        assert len(api_key.name) == 100

    def test_key_name_with_spaces(self):
        """Test key name with spaces."""
        api_key = APIKey(
            key_hash="0" * 64,
            name="My Test API Key",
        )
        assert api_key.name == "My Test API Key"

    def test_key_name_with_special_chars(self):
        """Test key name with special characters."""
        api_key = APIKey(
            key_hash="0" * 64,
            name="Test-Key_v2.0",
        )
        assert api_key.name == "Test-Key_v2.0"


class TestAPIKeyActiveField:
    """Tests for APIKey is_active field."""

    def test_key_active_explicit(self, sample_api_key):
        """Test key with explicit is_active=True."""
        assert sample_api_key.is_active is True

    def test_key_can_be_inactive(self, inactive_api_key):
        """Test key can be set to inactive."""
        assert inactive_api_key.is_active is False

    def test_key_active_explicit_true(self):
        """Test explicitly setting active to True."""
        api_key = APIKey(
            key_hash="0" * 64,
            name="Test",
            is_active=True,
        )
        assert api_key.is_active is True

    def test_key_active_explicit_false(self):
        """Test explicitly setting active to False."""
        api_key = APIKey(
            key_hash="0" * 64,
            name="Test",
            is_active=False,
        )
        assert api_key.is_active is False


class TestAPIKeyCreatedAt:
    """Tests for APIKey created_at field."""

    def test_key_has_created_at(self, sample_api_key):
        """Test key has created_at field."""
        assert hasattr(sample_api_key, "created_at")

    def test_key_created_at_with_explicit_time(self):
        """Test key with explicit created_at time."""
        now = datetime.now(UTC)
        api_key = APIKey(
            key_hash="0" * 64,
            name="Test",
            created_at=now,
        )
        assert api_key.created_at == now


# =============================================================================
# APIKey Repr Tests
# =============================================================================


class TestAPIKeyRepr:
    """Tests for APIKey string representation."""

    def test_api_key_repr_contains_class_name(self, sample_api_key):
        """Test repr contains class name."""
        repr_str = repr(sample_api_key)
        assert "APIKey" in repr_str

    def test_api_key_repr_contains_id(self, sample_api_key):
        """Test repr contains API key id."""
        repr_str = repr(sample_api_key)
        assert "id=1" in repr_str

    def test_api_key_repr_contains_name(self, sample_api_key):
        """Test repr contains API key name."""
        repr_str = repr(sample_api_key)
        assert "Production API Key" in repr_str

    def test_api_key_repr_contains_is_active(self, sample_api_key):
        """Test repr contains is_active status."""
        repr_str = repr(sample_api_key)
        assert "is_active=True" in repr_str

    def test_api_key_repr_inactive(self, inactive_api_key):
        """Test repr shows inactive status."""
        repr_str = repr(inactive_api_key)
        assert "is_active=False" in repr_str

    def test_api_key_repr_format(self, sample_api_key):
        """Test repr has expected format."""
        repr_str = repr(sample_api_key)
        assert repr_str.startswith("<APIKey(")
        assert repr_str.endswith(")>")

    def test_api_key_repr_does_not_contain_hash(self, sample_api_key):
        """Test repr does NOT contain the key hash (security)."""
        repr_str = repr(sample_api_key)
        # The full hash should not be in repr for security
        assert sample_api_key.key_hash not in repr_str


# =============================================================================
# APIKey Table Tests
# =============================================================================


class TestAPIKeyTable:
    """Tests for APIKey table configuration."""

    def test_api_key_tablename(self):
        """Test APIKey has correct table name."""
        assert APIKey.__tablename__ == "api_keys"

    def test_api_key_has_id_primary_key(self):
        """Test APIKey has id as primary key."""
        # Check through column inspection
        assert hasattr(APIKey, "id")


# =============================================================================
# Property-based Tests
# =============================================================================


class TestAPIKeyProperties:
    """Property-based tests for APIKey model."""

    @given(key_hash=key_hashes)
    @settings(max_examples=50)
    def test_key_hash_roundtrip(self, key_hash: str):
        """Property: Key hash values roundtrip correctly."""
        api_key = APIKey(
            key_hash=key_hash,
            name="Test",
        )
        assert api_key.key_hash == key_hash

    @given(name=key_names)
    @settings(max_examples=50)
    def test_name_roundtrip(self, name: str):
        """Property: Name values roundtrip correctly."""
        api_key = APIKey(
            key_hash="0" * 64,
            name=name,
        )
        assert api_key.name == name

    @given(is_active=st.booleans())
    @settings(max_examples=10)
    def test_is_active_roundtrip(self, is_active: bool):
        """Property: is_active values roundtrip correctly."""
        api_key = APIKey(
            key_hash="0" * 64,
            name="Test",
            is_active=is_active,
        )
        assert api_key.is_active == is_active

    @given(id_value=st.integers(min_value=1, max_value=1000000))
    @settings(max_examples=50)
    def test_id_roundtrip(self, id_value: int):
        """Property: ID values roundtrip correctly."""
        api_key = APIKey(
            id=id_value,
            key_hash="0" * 64,
            name="Test",
        )
        assert api_key.id == id_value

    @given(key_hash=key_hashes, name=key_names, is_active=st.booleans())
    @settings(max_examples=50)
    def test_all_fields_roundtrip(self, key_hash: str, name: str, is_active: bool):
        """Property: All fields roundtrip correctly together."""
        api_key = APIKey(
            key_hash=key_hash,
            name=name,
            is_active=is_active,
        )
        assert api_key.key_hash == key_hash
        assert api_key.name == name
        assert api_key.is_active == is_active


class TestAPIKeyHashProperties:
    """Property-based tests for key hash field."""

    @given(key_hash=key_hashes)
    @settings(max_examples=100)
    def test_hash_length_always_64(self, key_hash: str):
        """Property: Key hash is always 64 characters."""
        api_key = APIKey(
            key_hash=key_hash,
            name="Test",
        )
        assert len(api_key.key_hash) == 64

    @given(key_hash=key_hashes)
    @settings(max_examples=100)
    def test_hash_is_hex_string(self, key_hash: str):
        """Property: Key hash is a valid hex string."""
        api_key = APIKey(
            key_hash=key_hash,
            name="Test",
        )
        # Should be able to convert to int as hex
        int(api_key.key_hash, 16)  # Should not raise


class TestAPIKeySecurityProperties:
    """Property-based tests for APIKey security considerations."""

    @given(key_hash=key_hashes)
    @settings(max_examples=50)
    def test_repr_never_leaks_full_hash(self, key_hash: str):
        """Property: repr never contains the full key hash."""
        api_key = APIKey(
            key_hash=key_hash,
            name="Test",
        )
        repr_str = repr(api_key)
        # The full 64-character hash should never appear in repr
        assert key_hash not in repr_str
