"""Unit tests for session service.

Tests cover Redis-backed session management including creation, retrieval,
expiration, and deletion. These tests MUST FAIL initially (RED phase of TDD).

Test Categories:
- Session creation with TTL
- Session retrieval (valid/expired/invalid)
- Session deletion
- TTL management
"""

from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

# These imports WILL FAIL initially - that's expected for TDD RED phase
from backend.services.session_service import (
    SessionExpiredError,
    SessionService,
)

# Mark as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Session Creation Tests
# =============================================================================


class TestSessionCreation:
    """Tests for session creation."""

    @pytest.mark.asyncio
    async def test_create_session(self, mock_redis_client: MagicMock) -> None:
        """Test that session is created in Redis."""
        service = SessionService(mock_redis_client)
        user_id = "test_user_123"
        session_data = {"user_id": user_id, "email": "test@example.com"}

        session_id = await service.create_session(user_id, session_data)

        # Should return a session ID
        assert session_id is not None
        assert isinstance(session_id, str)
        assert len(session_id) > 10  # Should be a reasonable length UUID or similar

    @pytest.mark.asyncio
    async def test_create_session_calls_redis_set(self, mock_redis_client: MagicMock) -> None:
        """Test that create_session stores data in Redis."""
        mock_redis_client.set = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)
        user_id = "test_user_123"
        session_data = {"user_id": user_id}

        session_id = await service.create_session(user_id, session_data)

        # Verify Redis set was called
        mock_redis_client.set.assert_called_once()
        # First arg should be session key, second should be data
        call_args = mock_redis_client.set.call_args
        assert session_id in str(call_args[0][0])  # Session ID in key

    @pytest.mark.asyncio
    async def test_create_session_with_custom_ttl(self, mock_redis_client: MagicMock) -> None:
        """Test session creation with custom TTL."""
        mock_redis_client.set = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)
        user_id = "test_user_123"
        session_data = {"user_id": user_id}
        ttl = timedelta(hours=2)

        session_id = await service.create_session(user_id, session_data, ttl=ttl)

        # Should create session successfully
        assert session_id is not None

    @pytest.mark.asyncio
    async def test_create_session_unique_ids(self, mock_redis_client: MagicMock) -> None:
        """Test that multiple sessions get unique IDs."""
        mock_redis_client.set = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)

        session_id1 = await service.create_session("user1", {"user_id": "user1"})
        session_id2 = await service.create_session("user2", {"user_id": "user2"})

        assert session_id1 != session_id2

    @pytest.mark.asyncio
    async def test_create_session_empty_data(self, mock_redis_client: MagicMock) -> None:
        """Test creating session with empty data."""
        mock_redis_client.set = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)

        session_id = await service.create_session("user123", {})

        assert session_id is not None


# =============================================================================
# Session Retrieval Tests
# =============================================================================


class TestSessionRetrieval:
    """Tests for session retrieval."""

    @pytest.mark.asyncio
    async def test_get_session_valid(self, mock_redis_client: MagicMock) -> None:
        """Test retrieving a valid session."""
        session_data = {"user_id": "test_user", "email": "test@example.com"}
        mock_redis_client.get = AsyncMock(return_value=session_data)
        service = SessionService(mock_redis_client)

        result = await service.get_session("session_123")

        assert result == session_data
        mock_redis_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session_expired(self, mock_redis_client: MagicMock) -> None:
        """Test that expired session raises SessionExpiredError."""
        # Redis returns None when key is expired/doesn't exist
        mock_redis_client.get = AsyncMock(return_value=None)
        service = SessionService(mock_redis_client)

        with pytest.raises(SessionExpiredError):
            await service.get_session("expired_session_123")

    @pytest.mark.asyncio
    async def test_get_session_invalid(self, mock_redis_client: MagicMock) -> None:
        """Test that invalid session raises SessionExpiredError.

        Note: Implementation intentionally raises SessionExpiredError for both
        expired and non-existent sessions to avoid leaking session existence info.
        """
        mock_redis_client.get = AsyncMock(return_value=None)
        service = SessionService(mock_redis_client)

        with pytest.raises(SessionExpiredError):
            await service.get_session("invalid_session_id")

    @pytest.mark.asyncio
    async def test_get_session_with_different_data(self, mock_redis_client: MagicMock) -> None:
        """Test retrieving sessions with different data."""
        session_data = {"user_id": "user123", "role": "admin", "permissions": ["read", "write"]}
        mock_redis_client.get = AsyncMock(return_value=session_data)
        service = SessionService(mock_redis_client)

        result = await service.get_session("session_456")

        assert result["user_id"] == "user123"
        assert result["role"] == "admin"
        assert "permissions" in result

    @pytest.mark.asyncio
    async def test_get_session_calls_redis_with_correct_key(
        self, mock_redis_client: MagicMock
    ) -> None:
        """Test that get_session calls Redis with correctly formatted key."""
        mock_redis_client.get = AsyncMock(return_value={"user_id": "test"})
        service = SessionService(mock_redis_client)
        session_id = "test_session_789"

        await service.get_session(session_id)

        # Verify Redis get was called with key containing session ID
        call_args = mock_redis_client.get.call_args
        assert session_id in str(call_args[0][0])


# =============================================================================
# Session Deletion Tests
# =============================================================================


class TestSessionDeletion:
    """Tests for session deletion."""

    @pytest.mark.asyncio
    async def test_delete_session(self, mock_redis_client: MagicMock) -> None:
        """Test that session is deleted from Redis."""
        mock_redis_client.delete = AsyncMock(return_value=1)
        service = SessionService(mock_redis_client)

        result = await service.delete_session("session_123")

        assert result is True
        mock_redis_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_session_nonexistent(self, mock_redis_client: MagicMock) -> None:
        """Test deleting a session that doesn't exist."""
        mock_redis_client.delete = AsyncMock(return_value=0)
        service = SessionService(mock_redis_client)

        result = await service.delete_session("nonexistent_session")

        # Should return False if session didn't exist
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_session_calls_redis_with_correct_key(
        self, mock_redis_client: MagicMock
    ) -> None:
        """Test that delete_session calls Redis with correct key."""
        mock_redis_client.delete = AsyncMock(return_value=1)
        service = SessionService(mock_redis_client)
        session_id = "delete_test_456"

        await service.delete_session(session_id)

        call_args = mock_redis_client.delete.call_args
        assert session_id in str(call_args[0][0])

    @pytest.mark.asyncio
    async def test_delete_multiple_sessions(self, mock_redis_client: MagicMock) -> None:
        """Test deleting multiple sessions."""
        mock_redis_client.delete = AsyncMock(return_value=1)
        service = SessionService(mock_redis_client)

        result1 = await service.delete_session("session_1")
        result2 = await service.delete_session("session_2")

        assert result1 is True
        assert result2 is True
        assert mock_redis_client.delete.call_count == 2


# =============================================================================
# Session TTL Tests
# =============================================================================


class TestSessionTTL:
    """Tests for session TTL (time-to-live) management."""

    @pytest.mark.asyncio
    async def test_session_ttl_set_correctly(self, mock_redis_client: MagicMock) -> None:
        """Test that session TTL is set correctly in Redis."""
        mock_redis_client.set = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)
        ttl = timedelta(hours=1)

        await service.create_session("user123", {"user_id": "user123"}, ttl=ttl)

        # Verify set was called with expire parameter
        call_args = mock_redis_client.set.call_args
        # Should have expire argument (in seconds)
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_session_default_ttl(self, mock_redis_client: MagicMock) -> None:
        """Test that session uses default TTL when none specified."""
        mock_redis_client.set = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)

        # Create session without specifying TTL
        await service.create_session("user123", {"user_id": "user123"})

        # Should still set some TTL (default)
        mock_redis_client.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session_ttl(self, mock_redis_client: MagicMock) -> None:
        """Test retrieving remaining TTL for a session."""
        mock_redis_client.ttl = AsyncMock(return_value=3600)  # 1 hour remaining
        service = SessionService(mock_redis_client)

        ttl = await service.get_session_ttl("session_123")

        assert ttl == 3600
        mock_redis_client.ttl.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session_ttl_expired(self, mock_redis_client: MagicMock) -> None:
        """Test getting TTL for expired session."""
        mock_redis_client.ttl = AsyncMock(return_value=-2)  # Key doesn't exist
        service = SessionService(mock_redis_client)

        ttl = await service.get_session_ttl("expired_session")

        assert ttl == -2

    @pytest.mark.asyncio
    async def test_refresh_session_ttl(self, mock_redis_client: MagicMock) -> None:
        """Test refreshing/extending session TTL."""
        mock_redis_client.expire = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)
        new_ttl = timedelta(hours=2)

        result = await service.refresh_session("session_123", new_ttl)

        assert result is True
        mock_redis_client.expire.assert_called_once()


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestSessionEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_create_session_redis_failure(self, mock_redis_client: MagicMock) -> None:
        """Test handling of Redis failure during session creation."""
        mock_redis_client.set = AsyncMock(side_effect=Exception("Redis connection failed"))
        service = SessionService(mock_redis_client)

        with pytest.raises(Exception):
            await service.create_session("user123", {"user_id": "user123"})

    @pytest.mark.asyncio
    async def test_get_session_redis_failure(self, mock_redis_client: MagicMock) -> None:
        """Test handling of Redis failure during session retrieval."""
        mock_redis_client.get = AsyncMock(side_effect=Exception("Redis connection failed"))
        service = SessionService(mock_redis_client)

        with pytest.raises(Exception):
            await service.get_session("session_123")

    @pytest.mark.asyncio
    async def test_delete_session_redis_failure(self, mock_redis_client: MagicMock) -> None:
        """Test handling of Redis failure during session deletion."""
        mock_redis_client.delete = AsyncMock(side_effect=Exception("Redis connection failed"))
        service = SessionService(mock_redis_client)

        with pytest.raises(Exception):
            await service.delete_session("session_123")

    @pytest.mark.asyncio
    async def test_create_session_with_none_user_id(self, mock_redis_client: MagicMock) -> None:
        """Test creating session with None user_id."""
        service = SessionService(mock_redis_client)

        with pytest.raises(ValueError):
            await service.create_session(None, {"data": "test"})

    @pytest.mark.asyncio
    async def test_get_session_with_empty_session_id(self, mock_redis_client: MagicMock) -> None:
        """Test getting session with empty session ID."""
        service = SessionService(mock_redis_client)

        with pytest.raises(ValueError):
            await service.get_session("")

    @pytest.mark.asyncio
    async def test_session_data_serialization(self, mock_redis_client: MagicMock) -> None:
        """Test that session data is properly serialized/deserialized."""
        complex_data = {
            "user_id": "user123",
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "timestamp": "2026-02-02T10:00:00Z",
        }
        mock_redis_client.set = AsyncMock(return_value=True)
        mock_redis_client.get = AsyncMock(return_value=complex_data)
        service = SessionService(mock_redis_client)

        session_id = await service.create_session("user123", complex_data)
        retrieved_data = await service.get_session(session_id)

        assert retrieved_data == complex_data


# =============================================================================
# Session Service Integration Tests
# =============================================================================


class TestSessionServiceIntegration:
    """Integration tests for SessionService workflow."""

    @pytest.mark.asyncio
    async def test_full_session_lifecycle(self, mock_redis_client: MagicMock) -> None:
        """Test complete session lifecycle: create, get, delete."""
        session_data = {"user_id": "user123", "email": "test@example.com"}
        mock_redis_client.set = AsyncMock(return_value=True)
        mock_redis_client.get = AsyncMock(return_value=session_data)
        mock_redis_client.delete = AsyncMock(return_value=1)
        service = SessionService(mock_redis_client)

        # Create session
        session_id = await service.create_session("user123", session_data)
        assert session_id is not None

        # Retrieve session
        retrieved = await service.get_session(session_id)
        assert retrieved == session_data

        # Delete session
        deleted = await service.delete_session(session_id)
        assert deleted is True

    @pytest.mark.asyncio
    async def test_concurrent_sessions_for_same_user(self, mock_redis_client: MagicMock) -> None:
        """Test that same user can have multiple concurrent sessions."""
        mock_redis_client.set = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)
        user_id = "user123"

        session_id1 = await service.create_session(user_id, {"device": "desktop"})
        session_id2 = await service.create_session(user_id, {"device": "mobile"})

        # Should create different session IDs
        assert session_id1 != session_id2


class TestWp44SessionServiceGaps:
    """WP4.4 kill batch (session_service.md C4/C5/C6/C10/C11 — 22 TEST-GAP mutants).

    The suite asserted redis calls via assert_called_once()/substring only, so
    key-identity, serialized-payload and expire-value mutants all survived.
    The auth middleware validates sessions by reading user_id from the stored
    blob (api/middleware/auth.py), making key names + TTL load-bearing.
    """

    @pytest.mark.asyncio
    async def test_create_session_stores_serialized_payload_with_identity_metadata(
        self, mock_redis_client: MagicMock
    ) -> None:
        """Stored JSON payload = caller data + exact user_id/session_id keys (kills C4, 8)."""
        mock_redis_client.set = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)
        session_data = {"email": "test@example.com", "role": "admin"}

        session_id = await service.create_session("user_42", session_data)

        call = mock_redis_client.set.call_args
        raw_payload = call.args[1]
        assert isinstance(raw_payload, str), "session payload must be a JSON string"
        stored = json.loads(raw_payload)
        assert stored == {
            "email": "test@example.com",
            "role": "admin",
            "user_id": "user_42",
            "session_id": session_id,
        }

    @pytest.mark.asyncio
    async def test_create_session_sets_default_24h_expire_on_redis_set(
        self, mock_redis_client: MagicMock
    ) -> None:
        """Default session written with expire=86400 (kills C5: None/deleted expire)."""
        mock_redis_client.set = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)

        await service.create_session("user123", {"device": "desktop"})

        mock_redis_client.set.assert_called_once()
        call = mock_redis_client.set.call_args
        assert call.kwargs["expire"] == 86400

    @pytest.mark.asyncio
    async def test_create_session_custom_ttl_passed_as_expire_seconds(
        self, mock_redis_client: MagicMock
    ) -> None:
        """Custom timedelta TTL reaches Redis as exact integer seconds."""
        mock_redis_client.set = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)

        await service.create_session("user123", {"device": "mobile"}, ttl=timedelta(hours=2))

        call = mock_redis_client.set.call_args
        assert call.kwargs["expire"] == 7200

    @pytest.mark.asyncio
    async def test_create_session_redis_set_receives_prefixed_key_as_first_positional_arg(
        self, mock_redis_client: MagicMock
    ) -> None:
        """redis.set shape is (session:<id>, payload) exactly (kills C6 positional shift).

        The old substring check session_id in str(args[0]) is satisfied by the
        payload blob too, so an arg-deletion mutant passed there.
        """
        mock_redis_client.set = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)

        session_id = await service.create_session("user123", {"device": "desktop"})

        call = mock_redis_client.set.call_args
        assert len(call.args) == 2
        assert call.args[0] == f"session:{session_id}"

    @pytest.mark.asyncio
    async def test_get_session_ttl_queries_prefixed_key(self, mock_redis_client: MagicMock) -> None:
        """ttl() must get the exact session:<id> key (kills C10, 3: None/session:None)."""
        mock_redis_client.ttl = AsyncMock(return_value=3600)
        service = SessionService(mock_redis_client)

        ttl = await service.get_session_ttl("session_123")

        assert ttl == 3600
        mock_redis_client.ttl.assert_called_once_with("session:session_123")

    @pytest.mark.asyncio
    async def test_refresh_session_calls_expire_with_key_and_seconds(
        self, mock_redis_client: MagicMock
    ) -> None:
        """expire(session:<id>, int(seconds)) exactly (kills C11, 7 arg mutations)."""
        mock_redis_client.expire = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)

        result = await service.refresh_session("session_123", timedelta(hours=2))

        assert result is True
        mock_redis_client.expire.assert_called_once_with("session:session_123", 7200)
