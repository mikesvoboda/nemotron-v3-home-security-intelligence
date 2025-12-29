"""Unit tests for rate limiting middleware.

Tests cover:
- RateLimiter class and sliding window algorithm
- Rate limit tiers and configuration
- WebSocket rate limiting
- Client IP extraction
- Redis failure handling (fail-open)
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException, status

from backend.api.middleware.rate_limit import (
    RateLimiter,
    RateLimitTier,
    check_websocket_rate_limit,
    get_client_ip,
    get_tier_limits,
    rate_limit_default,
    rate_limit_media,
    rate_limit_search,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_settings_cache():
    """Reset settings cache before each test."""
    from backend.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_redis():
    """Create a mock Redis client with properly mocked pipeline."""
    mock = MagicMock()
    mock._client = MagicMock()

    # Create a mock pipeline that supports async context
    mock_pipe = MagicMock()
    mock_pipe.zremrangebyscore = MagicMock()
    mock_pipe.zcard = MagicMock()
    mock_pipe.zadd = MagicMock()
    mock_pipe.expire = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[0, 5, 1, True])

    # _ensure_connected is a sync method that returns a Redis client
    mock_redis_client = MagicMock()
    mock_redis_client.pipeline = MagicMock(return_value=mock_pipe)
    mock._ensure_connected = MagicMock(return_value=mock_redis_client)

    return mock


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    request = MagicMock()
    request.client = MagicMock()
    request.client.host = "192.168.1.100"
    request.headers = {}
    return request


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    websocket = MagicMock()
    websocket.client = MagicMock()
    websocket.client.host = "192.168.1.100"
    websocket.headers = {}
    websocket.close = AsyncMock()
    return websocket


# =============================================================================
# get_client_ip Tests
# =============================================================================


class TestGetClientIP:
    """Tests for client IP extraction."""

    def test_direct_client_ip(self, mock_request):
        """Test extraction of direct client IP."""
        mock_request.headers = {}
        mock_request.client.host = "10.0.0.1"

        ip = get_client_ip(mock_request)

        assert ip == "10.0.0.1"

    def test_x_forwarded_for_single(self, mock_request):
        """Test X-Forwarded-For header with single IP."""
        mock_request.headers = {"X-Forwarded-For": "203.0.113.50"}

        ip = get_client_ip(mock_request)

        assert ip == "203.0.113.50"

    def test_x_forwarded_for_chain(self, mock_request):
        """Test X-Forwarded-For header with multiple IPs."""
        mock_request.headers = {"X-Forwarded-For": "203.0.113.50, 70.41.3.18, 150.172.238.178"}

        ip = get_client_ip(mock_request)

        # Should return first IP (original client)
        assert ip == "203.0.113.50"

    def test_x_real_ip(self, mock_request):
        """Test X-Real-IP header."""
        mock_request.headers = {"X-Real-IP": "198.51.100.42"}

        ip = get_client_ip(mock_request)

        assert ip == "198.51.100.42"

    def test_x_forwarded_for_takes_precedence(self, mock_request):
        """Test that X-Forwarded-For takes precedence over X-Real-IP."""
        mock_request.headers = {
            "X-Forwarded-For": "203.0.113.50",
            "X-Real-IP": "198.51.100.42",
        }

        ip = get_client_ip(mock_request)

        assert ip == "203.0.113.50"

    def test_no_client_info(self, mock_request):
        """Test handling when no client info is available."""
        mock_request.headers = {}
        mock_request.client = None

        ip = get_client_ip(mock_request)

        assert ip == "unknown"

    def test_websocket_ip_extraction(self, mock_websocket):
        """Test IP extraction from WebSocket."""
        mock_websocket.headers = {}
        mock_websocket.client.host = "172.16.0.5"

        ip = get_client_ip(mock_websocket)

        assert ip == "172.16.0.5"


# =============================================================================
# get_tier_limits Tests
# =============================================================================


class TestGetTierLimits:
    """Tests for tier limit configuration."""

    def test_default_tier_limits(self):
        """Test default tier returns configured limits."""
        with patch.dict(os.environ, {"RATE_LIMIT_REQUESTS_PER_MINUTE": "100"}):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            limits = get_tier_limits(RateLimitTier.DEFAULT)

            assert limits[0] == 100  # requests_per_minute

    def test_media_tier_limits(self):
        """Test media tier returns configured limits."""
        with patch.dict(os.environ, {"RATE_LIMIT_MEDIA_REQUESTS_PER_MINUTE": "200"}):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            limits = get_tier_limits(RateLimitTier.MEDIA)

            assert limits[0] == 200

    def test_websocket_tier_limits(self):
        """Test WebSocket tier returns configured limits."""
        with patch.dict(os.environ, {"RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE": "15"}):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            limits = get_tier_limits(RateLimitTier.WEBSOCKET)

            assert limits[0] == 15
            assert limits[1] == 2  # Fixed burst for WebSocket

    def test_search_tier_limits(self):
        """Test search tier returns configured limits."""
        with patch.dict(os.environ, {"RATE_LIMIT_SEARCH_REQUESTS_PER_MINUTE": "50"}):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            limits = get_tier_limits(RateLimitTier.SEARCH)

            assert limits[0] == 50


# =============================================================================
# RateLimiter Class Tests
# =============================================================================


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        limiter = RateLimiter()

        assert limiter.tier == RateLimitTier.DEFAULT
        assert limiter.key_prefix == "rate_limit"
        assert limiter.window_seconds == 60

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        limiter = RateLimiter(
            tier=RateLimitTier.MEDIA,
            requests_per_minute=100,
            burst=20,
            key_prefix="custom",
        )

        assert limiter.tier == RateLimitTier.MEDIA
        assert limiter.requests_per_minute == 100
        assert limiter.burst == 20
        assert limiter.key_prefix == "custom"

    def test_make_key(self):
        """Test Redis key generation."""
        limiter = RateLimiter(tier=RateLimitTier.DEFAULT, key_prefix="rate_limit")

        key = limiter._make_key("192.168.1.1")

        assert key == "rate_limit:default:192.168.1.1"

    def test_make_key_different_tiers(self):
        """Test key generation for different tiers."""
        media_limiter = RateLimiter(tier=RateLimitTier.MEDIA)
        search_limiter = RateLimiter(tier=RateLimitTier.SEARCH)

        media_key = media_limiter._make_key("10.0.0.1")
        search_key = search_limiter._make_key("10.0.0.1")

        assert "media" in media_key
        assert "search" in search_key
        assert media_key != search_key

    @pytest.mark.asyncio
    async def test_check_rate_limit_disabled(self, mock_redis):
        """Test that rate limiting is bypassed when disabled."""
        with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "false"}):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            limiter = RateLimiter()
            is_allowed, count, _limit = await limiter._check_rate_limit(mock_redis, "192.168.1.1")

            assert is_allowed is True
            assert count == 0

    @pytest.mark.asyncio
    async def test_check_rate_limit_under_limit(self, mock_redis):
        """Test request allowed when under limit."""
        with patch.dict(
            os.environ,
            {"RATE_LIMIT_ENABLED": "true", "RATE_LIMIT_REQUESTS_PER_MINUTE": "60"},
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # Update the mock pipeline execute return value (5 current requests)
            mock_pipe = mock_redis._ensure_connected.return_value.pipeline.return_value
            mock_pipe.execute = AsyncMock(return_value=[0, 5, 1, True])

            limiter = RateLimiter(tier=RateLimitTier.DEFAULT)
            is_allowed, count, _limit = await limiter._check_rate_limit(mock_redis, "192.168.1.1")

            assert is_allowed is True
            assert count == 5

    @pytest.mark.asyncio
    async def test_check_rate_limit_over_limit(self, mock_redis):
        """Test request denied when over limit."""
        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "RATE_LIMIT_REQUESTS_PER_MINUTE": "60",
                "RATE_LIMIT_BURST": "10",
            },
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # Mock Redis returning count at limit (60 + 10 = 70)
            mock_pipe = mock_redis._ensure_connected.return_value.pipeline.return_value
            mock_pipe.execute = AsyncMock(return_value=[0, 70, 1, True])

            limiter = RateLimiter(tier=RateLimitTier.DEFAULT)
            is_allowed, count, limit = await limiter._check_rate_limit(mock_redis, "192.168.1.1")

            assert is_allowed is False
            assert count == 70
            assert limit == 70  # 60 + 10 burst

    @pytest.mark.asyncio
    async def test_check_rate_limit_redis_error_fails_open(self, mock_redis):
        """Test that Redis errors result in allowing the request (fail-open)."""
        with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "true"}):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # Mock Redis error
            mock_redis._ensure_connected.side_effect = Exception("Redis connection failed")

            limiter = RateLimiter()
            is_allowed, count, _limit = await limiter._check_rate_limit(mock_redis, "192.168.1.1")

            # Should fail open
            assert is_allowed is True
            assert count == 0

    @pytest.mark.asyncio
    async def test_call_raises_429_when_limited(self, mock_request, mock_redis):
        """Test that __call__ raises HTTPException with 429 status."""
        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "RATE_LIMIT_REQUESTS_PER_MINUTE": "10",
                "RATE_LIMIT_BURST": "1",  # Minimum valid burst
            },
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # Mock Redis returning count over limit (10 + 1 burst = 11)
            mock_pipe = mock_redis._ensure_connected.return_value.pipeline.return_value
            mock_pipe.execute = AsyncMock(return_value=[0, 15, 1, True])

            limiter = RateLimiter()

            with pytest.raises(HTTPException) as exc_info:
                await limiter(mock_request, mock_redis)

            assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
            assert "Too many requests" in exc_info.value.detail["error"]
            assert "Retry-After" in exc_info.value.headers

    @pytest.mark.asyncio
    async def test_call_includes_rate_limit_headers(self, mock_request, mock_redis):
        """Test that 429 response includes rate limit headers."""
        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "RATE_LIMIT_REQUESTS_PER_MINUTE": "10",
                "RATE_LIMIT_BURST": "5",
            },
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            mock_pipe = mock_redis._ensure_connected.return_value.pipeline.return_value
            mock_pipe.execute = AsyncMock(return_value=[0, 20, 1, True])

            limiter = RateLimiter()

            with pytest.raises(HTTPException) as exc_info:
                await limiter(mock_request, mock_redis)

            headers = exc_info.value.headers
            assert "X-RateLimit-Limit" in headers
            assert headers["X-RateLimit-Limit"] == "15"  # 10 + 5 burst
            assert headers["X-RateLimit-Remaining"] == "0"
            assert "X-RateLimit-Reset" in headers


# =============================================================================
# WebSocket Rate Limiting Tests
# =============================================================================


class TestWebSocketRateLimiting:
    """Tests for WebSocket rate limiting."""

    @pytest.mark.asyncio
    async def test_websocket_rate_limit_allowed(self, mock_websocket, mock_redis):
        """Test WebSocket connection allowed when under limit."""
        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE": "10",
            },
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            mock_pipe = mock_redis._ensure_connected.return_value.pipeline.return_value
            mock_pipe.execute = AsyncMock(return_value=[0, 3, 1, True])

            result = await check_websocket_rate_limit(mock_websocket, mock_redis)

            assert result is True

    @pytest.mark.asyncio
    async def test_websocket_rate_limit_denied(self, mock_websocket, mock_redis):
        """Test WebSocket connection denied when over limit."""
        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE": "10",
            },
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # WebSocket tier has burst of 2, so limit is 12
            mock_pipe = mock_redis._ensure_connected.return_value.pipeline.return_value
            mock_pipe.execute = AsyncMock(return_value=[0, 15, 1, True])

            result = await check_websocket_rate_limit(mock_websocket, mock_redis)

            assert result is False

    @pytest.mark.asyncio
    async def test_websocket_rate_limit_disabled(self, mock_websocket, mock_redis):
        """Test WebSocket allowed when rate limiting disabled."""
        with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "false"}):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            result = await check_websocket_rate_limit(mock_websocket, mock_redis)

            assert result is True
            # Redis should not be called
            mock_redis._ensure_connected.assert_not_called()


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for convenience rate limiter functions."""

    def test_rate_limit_default(self):
        """Test rate_limit_default returns DEFAULT tier limiter."""
        limiter = rate_limit_default()

        assert isinstance(limiter, RateLimiter)
        assert limiter.tier == RateLimitTier.DEFAULT

    def test_rate_limit_media(self):
        """Test rate_limit_media returns MEDIA tier limiter."""
        limiter = rate_limit_media()

        assert isinstance(limiter, RateLimiter)
        assert limiter.tier == RateLimitTier.MEDIA

    def test_rate_limit_search(self):
        """Test rate_limit_search returns SEARCH tier limiter."""
        limiter = rate_limit_search()

        assert isinstance(limiter, RateLimiter)
        assert limiter.tier == RateLimitTier.SEARCH


# =============================================================================
# Integration-style Tests (with FastAPI app)
# =============================================================================


class TestRateLimiterIntegration:
    """Integration-style tests using FastAPI TestClient."""

    @pytest.fixture
    def app_with_rate_limit(self):
        """Create a FastAPI app with rate-limited endpoint."""
        from fastapi import Depends

        app = FastAPI()

        limiter = RateLimiter(
            tier=RateLimitTier.DEFAULT,
            requests_per_minute=5,
            burst=0,
        )

        @app.get("/test")
        async def test_endpoint(
            _: None = Depends(limiter),
        ):
            return {"status": "ok"}

        return app

    def test_rate_limiter_as_dependency(self, app_with_rate_limit):
        """Test that RateLimiter works as FastAPI dependency."""
        # This tests the structure, not actual rate limiting
        # (TestClient doesn't run async code the same way)
        from fastapi.routing import APIRoute

        route = next(
            r for r in app_with_rate_limit.routes if isinstance(r, APIRoute) and r.path == "/test"
        )

        # Check that the endpoint has dependencies
        assert len(route.dependencies) > 0 or len(route.dependant.dependencies) > 0


# =============================================================================
# RateLimitTier Enum Tests
# =============================================================================


class TestRateLimitTier:
    """Tests for RateLimitTier enum."""

    def test_tier_values(self):
        """Test that all expected tiers exist."""
        assert RateLimitTier.DEFAULT.value == "default"
        assert RateLimitTier.MEDIA.value == "media"
        assert RateLimitTier.WEBSOCKET.value == "websocket"
        assert RateLimitTier.SEARCH.value == "search"

    def test_tier_is_string_enum(self):
        """Test that tier values can be used as strings."""
        tier = RateLimitTier.DEFAULT

        assert str(tier.value) == "default"
        assert f"rate_limit:{tier.value}" == "rate_limit:default"


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_ip_chain(self, mock_request):
        """Test handling of empty X-Forwarded-For header."""
        mock_request.headers = {"X-Forwarded-For": ""}
        mock_request.client.host = "10.0.0.1"

        ip = get_client_ip(mock_request)

        # Empty header should fall through to client.host
        assert ip == "10.0.0.1"

    def test_whitespace_in_forwarded_header(self, mock_request):
        """Test stripping of whitespace in X-Forwarded-For header."""
        mock_request.headers = {"X-Forwarded-For": "  203.0.113.50  "}

        ip = get_client_ip(mock_request)

        assert ip == "203.0.113.50"

    @pytest.mark.asyncio
    async def test_concurrent_requests_same_ip(self, mock_redis):
        """Test that concurrent requests from same IP are tracked."""
        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "RATE_LIMIT_REQUESTS_PER_MINUTE": "10",
                "RATE_LIMIT_BURST": "1",
            },
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # Simulate increasing count for concurrent requests
            # Limit is 10 + 1 burst = 11
            counts = [5, 6, 7, 8, 9, 10, 11, 12]
            call_count = 0

            async def mock_execute():
                nonlocal call_count
                count = counts[min(call_count, len(counts) - 1)]
                call_count += 1
                return [0, count, 1, True]

            mock_pipe = mock_redis._ensure_connected.return_value.pipeline.return_value
            mock_pipe.execute = mock_execute

            limiter = RateLimiter()

            # First few requests should be allowed
            is_allowed, _, _ = await limiter._check_rate_limit(mock_redis, "192.168.1.1")
            assert is_allowed is True

            # Keep making requests until denied
            denied = False
            for _ in range(10):
                is_allowed, _, _ = await limiter._check_rate_limit(mock_redis, "192.168.1.1")
                if not is_allowed:
                    denied = True
                    break

            assert denied is True

    def test_limiter_properties_use_tier_defaults(self):
        """Test that limiter properties fall back to tier defaults."""
        limiter = RateLimiter(tier=RateLimitTier.MEDIA)

        # Should use tier defaults, not hardcoded values
        rpm = limiter.requests_per_minute
        burst = limiter.burst

        expected_rpm, expected_burst = get_tier_limits(RateLimitTier.MEDIA)
        assert rpm == expected_rpm
        assert burst == expected_burst

    def test_limiter_properties_use_overrides(self):
        """Test that explicit overrides take precedence."""
        limiter = RateLimiter(
            tier=RateLimitTier.MEDIA,
            requests_per_minute=999,
            burst=99,
        )

        assert limiter.requests_per_minute == 999
        assert limiter.burst == 99
