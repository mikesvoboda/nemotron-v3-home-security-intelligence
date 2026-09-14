"""Session service for Redis-backed session management.

This module provides session management using Redis as the backing store.
Sessions are stored with configurable TTL for automatic expiration.
"""

from __future__ import annotations

import json
import secrets
from datetime import timedelta
from typing import Any

# Default session TTL (24 hours)
_DEFAULT_SESSION_TTL = timedelta(hours=24)

# Redis key prefix for sessions
_SESSION_KEY_PREFIX = "session:"


class SessionExpiredError(Exception):
    """Raised when a session has expired or doesn't exist."""

    pass


class SessionNotFoundError(Exception):
    """Raised when a session is not found."""

    pass


class SessionService:
    """Redis-backed session management service.

    Provides CRUD operations for user sessions with automatic TTL-based
    expiration.

    Attributes:
        redis: Redis client instance.
    """

    def __init__(self, redis: Any) -> None:
        """Initialize the SessionService.

        Args:
            redis: Redis client instance (async).
        """
        self._redis = redis

    def _session_key(self, session_id: str) -> str:
        """Build Redis key for a session.

        Args:
            session_id: Session identifier.

        Returns:
            Full Redis key for the session.
        """
        return f"{_SESSION_KEY_PREFIX}{session_id}"

    async def create_session(
        self,
        user_id: str | None,
        session_data: dict[str, Any],
        ttl: timedelta | None = None,
    ) -> str:
        """Create a new session in Redis.

        Args:
            user_id: User ID for the session.
            session_data: Data to store in the session.
            ttl: Optional time-to-live (defaults to 24 hours).

        Returns:
            Session ID.

        Raises:
            ValueError: If user_id is None.
        """
        if user_id is None:
            msg = "user_id cannot be None"
            raise ValueError(msg)

        # Generate unique session ID
        session_id = secrets.token_urlsafe(32)

        # Prepare session data with metadata
        full_data = {
            **session_data,
            "user_id": user_id,
            "session_id": session_id,
        }

        # Calculate TTL in seconds
        ttl_seconds = int((ttl or _DEFAULT_SESSION_TTL).total_seconds())

        # Store in Redis with TTL
        key = self._session_key(session_id)
        await self._redis.set(
            key,
            json.dumps(full_data),
            expire=ttl_seconds,
        )

        return session_id

    async def get_session(self, session_id: str) -> dict[str, Any]:
        """Retrieve a session from Redis.

        Args:
            session_id: Session identifier.

        Returns:
            Session data dictionary.

        Raises:
            ValueError: If session_id is empty.
            SessionExpiredError: If the session has expired.
            SessionNotFoundError: If the session doesn't exist.
        """
        if not session_id:
            msg = "session_id cannot be empty"
            raise ValueError(msg)

        key = self._session_key(session_id)
        data = await self._redis.get(key)

        if data is None:
            # Session doesn't exist or has expired
            # We raise SessionExpiredError for both cases since from the
            # client's perspective, an expired session is indistinguishable
            # from one that doesn't exist
            raise SessionExpiredError(f"Session {session_id} has expired or doesn't exist")

        # Parse JSON data
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        if isinstance(data, str):
            result: dict[str, Any] = json.loads(data)
            return result
        # Cast to expected type (Redis returns Any)
        return dict(data) if data else {}

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session from Redis.

        Args:
            session_id: Session identifier.

        Returns:
            True if the session was deleted, False if it didn't exist.
        """
        key = self._session_key(session_id)
        deleted: int = await self._redis.delete(key)
        return deleted > 0

    async def get_session_ttl(self, session_id: str) -> int:
        """Get the remaining TTL for a session.

        Args:
            session_id: Session identifier.

        Returns:
            Remaining TTL in seconds, or:
            - -1 if the key exists but has no TTL
            - -2 if the key doesn't exist
        """
        key = self._session_key(session_id)
        ttl: int = await self._redis.ttl(key)
        return ttl

    async def refresh_session(
        self,
        session_id: str,
        new_ttl: timedelta,
    ) -> bool:
        """Refresh/extend a session's TTL.

        Args:
            session_id: Session identifier.
            new_ttl: New time-to-live for the session.

        Returns:
            True if the session was refreshed, False if it doesn't exist.
        """
        key = self._session_key(session_id)
        ttl_seconds = int(new_ttl.total_seconds())
        result: bool = await self._redis.expire(key, ttl_seconds)
        return result
