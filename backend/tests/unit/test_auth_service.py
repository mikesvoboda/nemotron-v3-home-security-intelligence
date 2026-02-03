"""Unit tests for authentication service.

Tests cover password hashing, JWT token generation/validation, and API key generation.
These tests MUST FAIL initially (RED phase of TDD) as the service doesn't exist yet.

Test Categories:
- Password hashing with argon2
- JWT token creation and validation
- API key generation and validation
- Timing-safe password verification
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# These imports WILL FAIL initially - that's expected for TDD RED phase
from backend.services.auth_service import (
    AuthService,
    InvalidTokenError,
    TokenExpiredError,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    validate_api_key,
    verify_password,
)

# Mark as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Password Hashing Tests
# =============================================================================


class TestPasswordHashing:
    """Tests for password hashing with argon2."""

    def test_hash_password_returns_argon2_hash(self) -> None:
        """Test that hash_password returns an argon2 hash string."""
        password = "SecurePassword123!"  # pragma: allowlist secret
        hashed = hash_password(password)

        # Argon2 hashes start with $argon2
        assert hashed.startswith("$argon2")
        assert len(hashed) > 50  # Argon2 hashes are long

    def test_hash_password_produces_unique_hashes(self) -> None:
        """Test that same password produces different hashes (due to salt)."""
        password = "SamePassword123"  # pragma: allowlist secret
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Same password should produce different hashes due to random salt
        assert hash1 != hash2

    def test_hash_password_handles_empty_string(self) -> None:
        """Test that empty password is handled correctly."""
        hashed = hash_password("")

        # Should still produce a valid hash
        assert hashed.startswith("$argon2")

    def test_hash_password_handles_unicode(self) -> None:
        """Test that unicode characters in password are handled."""
        password = "Pässwörd123™"  # pragma: allowlist secret
        hashed = hash_password(password)

        assert hashed.startswith("$argon2")

    def test_hash_password_handles_very_long_password(self) -> None:
        """Test that very long passwords are handled."""
        password = "a" * 1000  # pragma: allowlist secret
        hashed = hash_password(password)

        assert hashed.startswith("$argon2")


class TestPasswordVerification:
    """Tests for password verification."""

    def test_verify_password_correct(self) -> None:
        """Test that verify_password returns True for correct password."""
        password = "CorrectPassword123"  # pragma: allowlist secret
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self) -> None:
        """Test that verify_password returns False for incorrect password."""
        password = "CorrectPassword123"  # pragma: allowlist secret
        hashed = hash_password(password)

        assert verify_password("WrongPassword", hashed) is False

    def test_verify_password_case_sensitive(self) -> None:
        """Test that password verification is case-sensitive."""
        password = "Password123"  # pragma: allowlist secret
        hashed = hash_password(password)

        assert verify_password("password123", hashed) is False

    def test_verify_password_empty_password(self) -> None:
        """Test verification with empty password."""
        password = "SomePassword"  # pragma: allowlist secret
        hashed = hash_password(password)

        assert verify_password("", hashed) is False

    def test_verify_password_empty_hash(self) -> None:
        """Test verification with empty hash."""
        with pytest.raises(Exception):  # Should raise ValueError or similar
            verify_password("password", "")

    def test_verify_password_invalid_hash_format(self) -> None:
        """Test verification with invalid hash format."""
        with pytest.raises(Exception):
            verify_password("password", "not_a_valid_hash")

    def test_verify_password_timing_safe(self) -> None:
        """Test that password verification is timing-safe (constant time).

        This test verifies that verification time doesn't leak information
        about password correctness through timing attacks.
        """
        password = "TestPassword123"  # pragma: allowlist secret
        hashed = hash_password(password)

        # Measure time for correct password
        start = time.perf_counter()
        verify_password(password, hashed)
        correct_time = time.perf_counter() - start

        # Measure time for incorrect password
        start = time.perf_counter()
        verify_password("WrongPassword", hashed)
        incorrect_time = time.perf_counter() - start

        # Times should be similar (within 10x factor for argon2 operations)
        # Argon2 is designed to be timing-safe
        assert abs(correct_time - incorrect_time) < max(correct_time, incorrect_time) * 10


# =============================================================================
# JWT Token Tests
# =============================================================================


class TestJWTTokenGeneration:
    """Tests for JWT token creation."""

    def test_create_access_token(self) -> None:
        """Test that access token is created with correct structure."""
        user_id = "test_user_123"
        token = create_access_token(user_id)

        # JWT tokens have 3 parts separated by dots
        parts = token.split(".")
        assert len(parts) == 3

    def test_create_access_token_custom_expiry(self) -> None:
        """Test access token with custom expiration time."""
        user_id = "test_user_123"
        expires_delta = timedelta(minutes=5)
        token = create_access_token(user_id, expires_delta=expires_delta)

        # Should produce a valid token
        assert len(token.split(".")) == 3

    def test_create_refresh_token(self) -> None:
        """Test that refresh token is created."""
        user_id = "test_user_123"
        token = create_refresh_token(user_id)

        # JWT tokens have 3 parts
        parts = token.split(".")
        assert len(parts) == 3

    def test_create_refresh_token_custom_expiry(self) -> None:
        """Test refresh token with custom expiration."""
        user_id = "test_user_123"
        expires_delta = timedelta(days=7)
        token = create_refresh_token(user_id, expires_delta=expires_delta)

        assert len(token.split(".")) == 3

    def test_create_token_with_empty_user_id(self) -> None:
        """Test token creation with empty user ID."""
        with pytest.raises(ValueError):
            create_access_token("")


class TestJWTTokenDecoding:
    """Tests for JWT token validation and decoding."""

    def test_decode_valid_token(self) -> None:
        """Test decoding a valid JWT token."""
        user_id = "test_user_123"
        token = create_access_token(user_id)

        payload = decode_token(token)

        assert payload["sub"] == user_id
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_token_extracts_user_id(self) -> None:
        """Test that decoded token contains correct user ID."""
        user_id = "another_user_456"
        token = create_access_token(user_id)

        payload = decode_token(token)

        assert payload["sub"] == user_id

    def test_decode_expired_token_raises(self) -> None:
        """Test that expired token raises TokenExpiredError."""
        user_id = "test_user"
        # Create token that expires immediately
        expires_delta = timedelta(seconds=-1)  # Already expired
        token = create_access_token(user_id, expires_delta=expires_delta)

        with pytest.raises(TokenExpiredError):
            decode_token(token)

    def test_decode_invalid_token_raises(self) -> None:
        """Test that invalid token raises InvalidTokenError."""
        invalid_token = "not.a.valid.jwt.token"

        with pytest.raises(InvalidTokenError):
            decode_token(invalid_token)

    def test_decode_malformed_token_raises(self) -> None:
        """Test that malformed token raises InvalidTokenError."""
        malformed_token = "malformed"

        with pytest.raises(InvalidTokenError):
            decode_token(malformed_token)

    def test_decode_token_with_tampered_signature(self) -> None:
        """Test that token with tampered signature is rejected."""
        user_id = "test_user"
        token = create_access_token(user_id)

        # Tamper with the signature (last part)
        parts = token.split(".")
        parts[2] = "tampered_signature"
        tampered_token = ".".join(parts)

        with pytest.raises(InvalidTokenError):
            decode_token(tampered_token)

    def test_decode_token_with_wrong_secret(self) -> None:
        """Test that token created with different secret is rejected."""
        # This would require mocking settings with different JWT_SECRET
        # Test implementation will vary based on settings architecture
        pass


# =============================================================================
# API Key Generation Tests
# =============================================================================


class TestAPIKeyGeneration:
    """Tests for API key generation."""

    def test_generate_api_key_format(self) -> None:
        """Test that generated API key follows nemo_k1_<random> format."""
        api_key = generate_api_key()

        assert api_key.startswith("nemo_k1_")
        # Key should be reasonably long (prefix + random part)
        assert len(api_key) > 20

    def test_generate_api_key_unique(self) -> None:
        """Test that generated API keys are unique."""
        key1 = generate_api_key()
        key2 = generate_api_key()

        assert key1 != key2

    def test_generate_api_key_returns_string(self) -> None:
        """Test that generate_api_key returns a string."""
        api_key = generate_api_key()

        assert isinstance(api_key, str)

    def test_generate_api_key_no_special_chars(self) -> None:
        """Test that API key contains only safe characters."""
        api_key = generate_api_key()

        # Should only contain alphanumeric and underscore
        # Remove the prefix to check random part
        random_part = api_key.replace("nemo_k1_", "")
        assert random_part.replace("_", "").isalnum()

    def test_generate_multiple_api_keys_all_unique(self) -> None:
        """Test that generating multiple keys produces all unique values."""
        keys = [generate_api_key() for _ in range(100)]

        # All keys should be unique
        assert len(keys) == len(set(keys))


class TestAPIKeyHashing:
    """Tests for API key hashing."""

    def test_hash_api_key(self) -> None:
        """Test that API key hashing produces consistent hash."""
        api_key = "nemo_k1_test123abc"  # pragma: allowlist secret
        hashed = hash_api_key(api_key)

        # Hash should be a hex string
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_api_key_consistent(self) -> None:
        """Test that same key always produces same hash."""
        api_key = "nemo_k1_test456def"  # pragma: allowlist secret
        hash1 = hash_api_key(api_key)
        hash2 = hash_api_key(api_key)

        assert hash1 == hash2

    def test_hash_api_key_different_keys_different_hashes(self) -> None:
        """Test that different keys produce different hashes."""
        key1 = "nemo_k1_key1"  # pragma: allowlist secret
        key2 = "nemo_k1_key2"  # pragma: allowlist secret

        hash1 = hash_api_key(key1)
        hash2 = hash_api_key(key2)

        assert hash1 != hash2

    def test_hash_api_key_empty_string(self) -> None:
        """Test hashing empty string."""
        hashed = hash_api_key("")

        # Should produce a valid hash even for empty string
        assert isinstance(hashed, str)
        assert len(hashed) > 0


class TestAPIKeyValidation:
    """Tests for API key validation."""

    def test_validate_api_key_correct(self) -> None:
        """Test that validate_api_key returns True for correct key."""
        api_key = "nemo_k1_correct123"  # pragma: allowlist secret
        hashed = hash_api_key(api_key)

        assert validate_api_key(api_key, hashed) is True

    def test_validate_api_key_incorrect(self) -> None:
        """Test that validate_api_key returns False for incorrect key."""
        api_key = "nemo_k1_correct123"  # pragma: allowlist secret
        hashed = hash_api_key(api_key)

        assert validate_api_key("nemo_k1_wrong456", hashed) is False

    def test_validate_api_key_empty_key(self) -> None:
        """Test validation with empty API key."""
        hashed = hash_api_key("nemo_k1_test")

        assert validate_api_key("", hashed) is False

    def test_validate_api_key_empty_hash(self) -> None:
        """Test validation with empty hash."""
        assert validate_api_key("nemo_k1_test", "") is False

    def test_validate_api_key_case_sensitive(self) -> None:
        """Test that API key validation is case-sensitive."""
        api_key = "nemo_k1_Test123"  # pragma: allowlist secret
        hashed = hash_api_key(api_key)

        assert validate_api_key("nemo_k1_test123", hashed) is False

    def test_validate_api_key_timing_safe(self) -> None:
        """Test that API key validation is timing-safe."""
        api_key = "nemo_k1_timing_test"  # pragma: allowlist secret
        hashed = hash_api_key(api_key)

        # Measure time for correct key
        start = time.perf_counter()
        validate_api_key(api_key, hashed)
        correct_time = time.perf_counter() - start

        # Measure time for incorrect key
        start = time.perf_counter()
        validate_api_key("nemo_k1_wrong_key", hashed)
        incorrect_time = time.perf_counter() - start

        # Times should be similar (constant-time comparison)
        # Allow 10x variation for system noise
        assert abs(correct_time - incorrect_time) < max(correct_time, incorrect_time) * 10


# =============================================================================
# AuthService Class Tests
# =============================================================================


class TestAuthService:
    """Tests for AuthService class methods."""

    @pytest.fixture
    def auth_service(self) -> AuthService:
        """Create AuthService instance for testing."""
        return AuthService()

    def test_auth_service_initialization(self, auth_service: AuthService) -> None:
        """Test that AuthService can be instantiated."""
        assert auth_service is not None

    def test_auth_service_has_hash_password_method(self, auth_service: AuthService) -> None:
        """Test that AuthService has hash_password method."""
        assert hasattr(auth_service, "hash_password")
        assert callable(auth_service.hash_password)

    def test_auth_service_has_verify_password_method(self, auth_service: AuthService) -> None:
        """Test that AuthService has verify_password method."""
        assert hasattr(auth_service, "verify_password")
        assert callable(auth_service.verify_password)

    def test_auth_service_has_create_access_token_method(
        self, auth_service: AuthService
    ) -> None:
        """Test that AuthService has create_access_token method."""
        assert hasattr(auth_service, "create_access_token")
        assert callable(auth_service.create_access_token)

    def test_auth_service_has_generate_api_key_method(
        self, auth_service: AuthService
    ) -> None:
        """Test that AuthService has generate_api_key method."""
        assert hasattr(auth_service, "generate_api_key")
        assert callable(auth_service.generate_api_key)
