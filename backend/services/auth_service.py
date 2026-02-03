"""Authentication service for password hashing, JWT tokens, and API keys.

This module provides secure authentication utilities including:
- Password hashing with Argon2id (memory-hard, timing-safe)
- JWT token generation and validation
- API key generation and validation

All operations are designed to be timing-safe to prevent side-channel attacks.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from jose import JWTError, jwt

# Module-level password hasher with secure defaults
# Uses Argon2id variant (hybrid of Argon2i and Argon2d)
_password_hasher = PasswordHasher(
    time_cost=3,  # Number of iterations
    memory_cost=65536,  # 64MB memory
    parallelism=4,  # Number of parallel threads
)

# JWT algorithm
_JWT_ALGORITHM = "HS256"

# Default token expiration times
_DEFAULT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
_DEFAULT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

# API key prefix format
_API_KEY_PREFIX = "nemo_k1_"


class TokenExpiredError(Exception):
    """Raised when a JWT token has expired."""

    pass


class InvalidTokenError(Exception):
    """Raised when a JWT token is invalid."""

    pass


def _get_jwt_secret() -> str:
    """Get JWT secret from settings.

    In test environments (ENVIRONMENT=test), uses a default test secret
    if JWT_SECRET is not configured. In production/staging, requires
    explicit configuration.

    Returns:
        JWT secret key.

    Raises:
        ValueError: If JWT_SECRET is not configured in non-test environments.
    """
    import os

    # Import here to avoid circular imports
    from backend.core.config import get_settings

    settings = get_settings()
    jwt_secret = settings.jwt_secret

    if jwt_secret is not None:
        return jwt_secret.get_secret_value()

    # In test environment, allow a default secret for unit tests
    # This is safe because test environments are isolated and short-lived
    environment = os.environ.get("ENVIRONMENT", "").lower()
    if environment in ("test", "testing", "development"):
        return "test-jwt-secret-do-not-use-in-production-" + "x" * 32

    msg = "JWT_SECRET is not configured"
    raise ValueError(msg)


def hash_password(password: str) -> str:
    """Hash a password using Argon2id.

    Uses the Argon2id variant which is resistant to both side-channel
    attacks and GPU-based attacks.

    Args:
        password: Plaintext password to hash.

    Returns:
        Argon2id hash string (includes algorithm parameters and salt).
    """
    return _password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash (timing-safe).

    Uses Argon2's built-in verification which is constant-time.

    Args:
        password: Plaintext password to verify.
        hashed: Argon2 hash to verify against.

    Returns:
        True if password matches, False otherwise.

    Raises:
        InvalidHashError: If the hash format is invalid.
        VerificationError: If the hash format is invalid.
    """
    if not hashed:
        msg = "Hash cannot be empty"
        raise ValueError(msg)
    try:
        _password_hasher.verify(hashed, password)
        return True
    except VerificationError:
        return False
    except InvalidHashError as e:
        # Re-raise as a more generic exception for invalid hash format
        raise InvalidHashError(str(e)) from e


def create_access_token(
    user_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token.

    Args:
        user_id: User ID to encode in the token.
        expires_delta: Optional custom expiration time.

    Returns:
        Encoded JWT token string.

    Raises:
        ValueError: If user_id is empty.
    """
    if not user_id:
        msg = "user_id cannot be empty"
        raise ValueError(msg)

    expire = datetime.now(UTC) + (expires_delta or _DEFAULT_ACCESS_TOKEN_EXPIRES)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    # HS256 is acceptable for single-user local deployment (no distributed secrets)
    token: str = jwt.encode(
        payload, _get_jwt_secret(), algorithm=_JWT_ALGORITHM
    )  # nosemgrep: jwt-weak-algorithm
    return token


def create_refresh_token(
    user_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT refresh token.

    Refresh tokens have longer expiration and are used to obtain new access tokens.

    Args:
        user_id: User ID to encode in the token.
        expires_delta: Optional custom expiration time.

    Returns:
        Encoded JWT token string.

    Raises:
        ValueError: If user_id is empty.
    """
    if not user_id:
        msg = "user_id cannot be empty"
        raise ValueError(msg)

    expire = datetime.now(UTC) + (expires_delta or _DEFAULT_REFRESH_TOKEN_EXPIRES)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "refresh",
    }
    # HS256 is acceptable for single-user local deployment (no distributed secrets)
    token: str = jwt.encode(
        payload, _get_jwt_secret(), algorithm=_JWT_ALGORITHM
    )  # nosemgrep: jwt-weak-algorithm
    return token


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: JWT token string to decode.

    Returns:
        Decoded token payload.

    Raises:
        TokenExpiredError: If the token has expired.
        InvalidTokenError: If the token is invalid.
    """
    try:
        # HS256 is acceptable for single-user local deployment (no distributed secrets)
        payload: dict[str, Any] = jwt.decode(
            token, _get_jwt_secret(), algorithms=[_JWT_ALGORITHM]
        )  # nosemgrep: jwt-weak-algorithm
        return payload
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("Token has expired") from e
    except JWTError as e:
        raise InvalidTokenError(f"Invalid token: {e}") from e


def generate_api_key() -> str:
    """Generate a new API key.

    Generates a cryptographically secure random API key with the format:
    nemo_k1_<32_random_chars>

    The random part contains only alphanumeric characters and underscores
    for easy copying/pasting in various contexts.

    Returns:
        New API key string.
    """
    # Generate random bytes and encode as hex (alphanumeric only)
    random_part = secrets.token_hex(16)  # 32 hex chars
    return f"{_API_KEY_PREFIX}{random_part}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key using SHA256.

    API keys are hashed with SHA256 (not Argon2) because:
    1. API keys are high-entropy secrets (not user-chosen passwords)
    2. Faster lookup is needed for every API request
    3. SHA256 is sufficient for random 256-bit secrets

    Args:
        api_key: API key to hash.

    Returns:
        SHA256 hex digest of the API key.
    """
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def validate_api_key(api_key: str, stored_hash: str) -> bool:
    """Validate an API key against its stored hash (timing-safe).

    Uses constant-time comparison to prevent timing attacks.

    Args:
        api_key: API key to validate.
        stored_hash: SHA256 hash to validate against.

    Returns:
        True if API key matches, False otherwise.
    """
    if not api_key or not stored_hash:
        return False
    computed_hash = hash_api_key(api_key)
    # Use hmac.compare_digest for constant-time comparison
    return hmac.compare_digest(computed_hash, stored_hash)


class AuthService:
    """Authentication service class providing all auth operations.

    This class wraps the module-level functions for use with dependency injection.
    """

    def __init__(self) -> None:
        """Initialize the AuthService."""
        pass

    def hash_password(self, password: str) -> str:
        """Hash a password using Argon2id.

        Args:
            password: Plaintext password to hash.

        Returns:
            Argon2id hash string.
        """
        return hash_password(password)

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password against its hash.

        Args:
            password: Plaintext password to verify.
            hashed: Argon2 hash to verify against.

        Returns:
            True if password matches, False otherwise.
        """
        return verify_password(password, hashed)

    def create_access_token(
        self,
        user_id: str,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a JWT access token.

        Args:
            user_id: User ID to encode in the token.
            expires_delta: Optional custom expiration time.

        Returns:
            Encoded JWT token string.
        """
        return create_access_token(user_id, expires_delta)

    def create_refresh_token(
        self,
        user_id: str,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a JWT refresh token.

        Args:
            user_id: User ID to encode in the token.
            expires_delta: Optional custom expiration time.

        Returns:
            Encoded JWT token string.
        """
        return create_refresh_token(user_id, expires_delta)

    def decode_token(self, token: str) -> dict[str, Any]:
        """Decode and validate a JWT token.

        Args:
            token: JWT token string to decode.

        Returns:
            Decoded token payload.
        """
        return decode_token(token)

    def generate_api_key(self) -> str:
        """Generate a new API key.

        Returns:
            New API key string.
        """
        return generate_api_key()

    def hash_api_key(self, api_key: str) -> str:
        """Hash an API key using SHA256.

        Args:
            api_key: API key to hash.

        Returns:
            SHA256 hex digest of the API key.
        """
        return hash_api_key(api_key)

    def validate_api_key(self, api_key: str, stored_hash: str) -> bool:
        """Validate an API key against its stored hash.

        Args:
            api_key: API key to validate.
            stored_hash: SHA256 hash to validate against.

        Returns:
            True if API key matches, False otherwise.
        """
        return validate_api_key(api_key, stored_hash)
