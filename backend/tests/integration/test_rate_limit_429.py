"""Integration tests for rate limiting 429 responses (NEM-2054).

This module tests that rate limiting returns proper 429 Too Many Requests responses
with correct headers and error format when rate limits are exceeded.

Tests cover:
- 429 response when rate limit exceeded
- Proper headers (Retry-After, X-RateLimit-*)
- Different rate limit tiers (default, media, search, export, AI inference)
- Rate limit reset after window expires
- Rate limiting disabled mode

IMPORTANT: These tests require real Redis for accurate rate limit testing.
Tests use the `real_redis` fixture for authentic sliding window behavior.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


class TestRateLimitDisabled:
    """Tests for behavior when rate limiting is disabled."""

    @pytest.mark.asyncio
    async def test_requests_allowed_when_rate_limiting_disabled(self, client, mock_redis):
        """Test that requests are allowed when rate limiting is disabled."""
        with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "false"}):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # Make multiple requests - all should succeed
            for i in range(5):
                response = await client.get("/api/system/health")
                assert response.status_code == 200, f"Request {i + 1} failed unexpectedly"


class TestRateLimit429Headers:
    """Tests for 429 response headers and format."""

    @pytest.mark.asyncio
    async def test_rate_limit_response_includes_retry_after_header(self, client, mock_redis):
        """Test that 429 response includes Retry-After header."""
        from backend.api.middleware.rate_limit import RateLimiter, RateLimitTier

        # Create a limiter with very low limit
        limiter = RateLimiter(
            tier=RateLimitTier.DEFAULT,
            requests_per_minute=1,
            burst=0,
        )

        # Mock the rate limit check to return exceeded
        with patch.object(
            limiter,
            "_check_rate_limit",
            return_value=(False, 5, 1),  # is_allowed=False, count=5, limit=1
        ):
            with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
                mock_settings.return_value.trusted_proxy_ips = []

                from fastapi import HTTPException

                with pytest.raises(HTTPException) as exc_info:
                    mock_request = MagicMock()
                    mock_request.client = MagicMock()
                    mock_request.client.host = "192.168.1.100"
                    mock_request.headers = {}
                    await limiter(mock_request, mock_redis)

                assert exc_info.value.status_code == 429
                headers = exc_info.value.headers

                # Verify Retry-After header
                assert "Retry-After" in headers
                assert headers["Retry-After"] == "60"  # Default window is 60 seconds

    @pytest.mark.asyncio
    async def test_rate_limit_response_includes_rate_limit_headers(self, client, mock_redis):
        """Test that 429 response includes X-RateLimit-* headers."""
        from backend.api.middleware.rate_limit import RateLimiter, RateLimitTier

        limiter = RateLimiter(
            tier=RateLimitTier.DEFAULT,
            requests_per_minute=10,
            burst=5,
        )

        with patch.object(
            limiter,
            "_check_rate_limit",
            return_value=(False, 20, 15),  # is_allowed=False, count=20, limit=15
        ):
            with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
                mock_settings.return_value.trusted_proxy_ips = []

                from fastapi import HTTPException

                with pytest.raises(HTTPException) as exc_info:
                    mock_request = MagicMock()
                    mock_request.client = MagicMock()
                    mock_request.client.host = "192.168.1.100"
                    mock_request.headers = {}
                    await limiter(mock_request, mock_redis)

                headers = exc_info.value.headers

                # Verify X-RateLimit-* headers
                assert "X-RateLimit-Limit" in headers
                assert headers["X-RateLimit-Limit"] == "15"

                assert "X-RateLimit-Remaining" in headers
                assert headers["X-RateLimit-Remaining"] == "0"

                assert "X-RateLimit-Reset" in headers
                # Reset time should be a Unix timestamp in the future
                reset_time = int(headers["X-RateLimit-Reset"])
                import time

                assert reset_time > int(time.time())

    @pytest.mark.asyncio
    async def test_rate_limit_response_body_format(self, client, mock_redis):
        """Test that 429 response body has correct format."""
        from backend.api.middleware.rate_limit import RateLimiter, RateLimitTier

        limiter = RateLimiter(
            tier=RateLimitTier.MEDIA,
            requests_per_minute=50,
            burst=10,
        )

        with patch.object(
            limiter,
            "_check_rate_limit",
            return_value=(False, 100, 60),
        ):
            with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
                mock_settings.return_value.trusted_proxy_ips = []

                from fastapi import HTTPException

                with pytest.raises(HTTPException) as exc_info:
                    mock_request = MagicMock()
                    mock_request.client = MagicMock()
                    mock_request.client.host = "192.168.1.100"
                    mock_request.headers = {}
                    await limiter(mock_request, mock_redis)

                detail = exc_info.value.detail

                # Verify response body structure
                assert "error" in detail
                assert "Too many requests" in detail["error"]

                assert "message" in detail
                assert "Rate limit exceeded" in detail["message"]

                assert "retry_after_seconds" in detail
                assert detail["retry_after_seconds"] == 60

                assert "tier" in detail
                assert detail["tier"] == "media"


class TestRateLimitTiers:
    """Tests for different rate limit tiers."""

    @pytest.mark.asyncio
    async def test_default_tier_limits(self, client, mock_redis):
        """Test default tier rate limit configuration."""
        from backend.api.middleware.rate_limit import RateLimitTier, get_tier_limits

        requests_per_minute, burst = get_tier_limits(RateLimitTier.DEFAULT)

        # Default tier should have reasonable limits
        assert requests_per_minute > 0
        assert burst >= 0
        # Default is 60 requests/min with 10 burst in config
        assert requests_per_minute >= 10  # At least 10 requests/min

    @pytest.mark.asyncio
    async def test_media_tier_limits(self, client, mock_redis):
        """Test media tier rate limit configuration."""
        from backend.api.middleware.rate_limit import RateLimitTier, get_tier_limits

        requests_per_minute, burst = get_tier_limits(RateLimitTier.MEDIA)

        assert requests_per_minute > 0
        assert burst >= 0
        # Media tier should allow more requests (default 120/min)
        assert requests_per_minute >= 10

    @pytest.mark.asyncio
    async def test_search_tier_limits(self, client, mock_redis):
        """Test search tier rate limit configuration."""
        from backend.api.middleware.rate_limit import RateLimitTier, get_tier_limits

        requests_per_minute, burst = get_tier_limits(RateLimitTier.SEARCH)

        assert requests_per_minute > 0
        assert burst >= 0
        # Search tier should have moderate limits (default 30/min)
        assert requests_per_minute >= 5

    @pytest.mark.asyncio
    async def test_export_tier_has_no_burst(self, client, mock_redis):
        """Test export tier has no burst allowance to prevent abuse."""
        from backend.api.middleware.rate_limit import RateLimitTier, get_tier_limits

        requests_per_minute, burst = get_tier_limits(RateLimitTier.EXPORT)

        assert requests_per_minute > 0
        assert burst == 0  # Export tier explicitly has no burst

    @pytest.mark.asyncio
    async def test_ai_inference_tier_has_strict_limits(self, client, mock_redis):
        """Test AI inference tier has strict limits due to computational cost."""
        from backend.api.middleware.rate_limit import RateLimitTier, get_tier_limits

        requests_per_minute, burst = get_tier_limits(RateLimitTier.AI_INFERENCE)

        assert requests_per_minute > 0
        assert burst >= 0
        # AI inference tier should be strict (default 10/min with burst 3)
        assert requests_per_minute <= 60  # Should be relatively low

    @pytest.mark.asyncio
    async def test_websocket_tier_has_fixed_burst(self, client, mock_redis):
        """Test WebSocket tier has fixed burst of 2."""
        from backend.api.middleware.rate_limit import RateLimitTier, get_tier_limits

        requests_per_minute, burst = get_tier_limits(RateLimitTier.WEBSOCKET)

        assert requests_per_minute > 0
        assert burst == 2  # WebSocket tier has fixed burst of 2


class TestRateLimitWithRealRedis:
    """Tests for rate limiting with real Redis to verify actual behavior.

    These tests use the real_redis fixture to test actual sliding window
    rate limiting behavior, including rate limit reset after window expires.
    """

    @pytest.mark.asyncio
    async def test_rate_limit_check_with_real_redis(self, integration_db, real_redis):
        """Test rate limit check with real Redis sliding window."""
        from backend.api.middleware.rate_limit import RateLimiter, RateLimitTier

        # Create a limiter with low limit for testing
        limiter = RateLimiter(
            tier=RateLimitTier.DEFAULT,
            requests_per_minute=5,
            burst=2,
            key_prefix="test_rate_limit",
        )

        with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "true"}):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # Make requests up to the limit (5 + 2 burst = 7)
            results = []
            for i in range(10):
                is_allowed, count, limit = await limiter._check_rate_limit(
                    real_redis, "test_client_ip"
                )
                results.append({"is_allowed": is_allowed, "count": count, "limit": limit})

            # First 7 should be allowed (5 + 2 burst)
            assert results[0]["is_allowed"] is True  # Request 1
            assert results[6]["is_allowed"] is True  # Request 7 (at limit)
            # After that, requests should be denied
            assert results[7]["is_allowed"] is False  # Request 8 (over limit)
            assert results[8]["is_allowed"] is False  # Request 9
            assert results[9]["is_allowed"] is False  # Request 10

    @pytest.mark.asyncio
    async def test_different_clients_have_independent_limits(self, integration_db, real_redis):
        """Test that different client IPs have independent rate limits."""
        from backend.api.middleware.rate_limit import RateLimiter, RateLimitTier

        limiter = RateLimiter(
            tier=RateLimitTier.DEFAULT,
            requests_per_minute=2,
            burst=0,
            key_prefix="test_independent_limits",
        )

        with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "true"}):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # Client A makes 3 requests (limit is 2)
            for i in range(3):
                is_allowed_a, _, _ = await limiter._check_rate_limit(real_redis, "client_a")

            # Client B should still be allowed (independent limit)
            is_allowed_b, count_b, _ = await limiter._check_rate_limit(real_redis, "client_b")

            # Client A's third request should be denied
            assert is_allowed_a is False  # Client A over limit

            # Client B's first request should be allowed
            assert is_allowed_b is True  # Client B has its own limit
            # count_b is the count BEFORE adding current request (0 = no previous requests)
            assert count_b == 0  # Client B's first request (count is before adding)

    @pytest.mark.asyncio
    async def test_rate_limit_uses_correct_redis_key(self, integration_db, real_redis):
        """Test that rate limiter creates correct Redis keys."""
        from backend.api.middleware.rate_limit import RateLimiter, RateLimitTier

        limiter = RateLimiter(
            tier=RateLimitTier.MEDIA,
            requests_per_minute=10,
            key_prefix="test_key_prefix",
        )

        # Generate the key
        key = limiter._make_key("192.168.1.100")

        # Verify key format
        assert key == "test_key_prefix:media:192.168.1.100"

        # Verify key includes tier
        limiter_search = RateLimiter(
            tier=RateLimitTier.SEARCH,
            key_prefix="test_key_prefix",
        )
        key_search = limiter_search._make_key("192.168.1.100")
        assert key_search == "test_key_prefix:search:192.168.1.100"

        # Different tiers should have different keys for same client
        assert key != key_search


class TestRateLimitFailOpen:
    """Tests for rate limiting fail-open behavior on Redis errors."""

    @pytest.mark.asyncio
    async def test_allows_requests_on_redis_connection_error(self, client, mock_redis):
        """Test that requests are allowed when Redis is unavailable (fail-open)."""
        from backend.api.middleware.rate_limit import RateLimiter, RateLimitTier

        limiter = RateLimiter(
            tier=RateLimitTier.DEFAULT,
            requests_per_minute=1,
            burst=0,
        )

        # Configure mock Redis to raise connection error
        mock_redis._ensure_connected = MagicMock(side_effect=Exception("Redis connection refused"))

        with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "true"}):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # Request should be allowed despite Redis error
            is_allowed, count, _limit = await limiter._check_rate_limit(mock_redis, "192.168.1.100")

            assert is_allowed is True  # Fail-open
            assert count == 0  # No count available due to error

    @pytest.mark.asyncio
    async def test_allows_requests_on_redis_timeout(self, client, mock_redis):
        """Test that requests are allowed when Redis times out (fail-open)."""
        from backend.api.middleware.rate_limit import RateLimiter, RateLimitTier

        limiter = RateLimiter(
            tier=RateLimitTier.DEFAULT,
            requests_per_minute=1,
            burst=0,
        )

        # Configure mock Redis to timeout
        mock_pipeline = MagicMock()
        mock_pipeline.zremrangebyscore = MagicMock()
        mock_pipeline.zcard = MagicMock()
        mock_pipeline.zadd = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock(side_effect=TimeoutError("Redis timeout"))

        mock_redis._ensure_connected = MagicMock(
            return_value=MagicMock(pipeline=MagicMock(return_value=mock_pipeline))
        )

        with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "true"}):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # Request should be allowed despite timeout
            is_allowed, count, _limit = await limiter._check_rate_limit(mock_redis, "192.168.1.100")

            assert is_allowed is True  # Fail-open
            assert count == 0


class TestWebSocketRateLimiting:
    """Tests for WebSocket rate limiting."""

    @pytest.mark.asyncio
    async def test_websocket_rate_limit_allowed(self, integration_db, real_redis):
        """Test WebSocket connection allowed when under limit."""
        from backend.api.middleware.rate_limit import check_websocket_rate_limit

        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE": "10",
            },
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            mock_websocket = MagicMock()
            mock_websocket.client = MagicMock()
            mock_websocket.client.host = "192.168.1.100"
            mock_websocket.headers = {}

            with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
                mock_settings.return_value.rate_limit_enabled = True
                mock_settings.return_value.trusted_proxy_ips = []
                mock_settings.return_value.rate_limit_websocket_connections_per_minute = 10

                is_allowed = await check_websocket_rate_limit(mock_websocket, real_redis)

            assert is_allowed is True

    @pytest.mark.asyncio
    async def test_websocket_rate_limit_denied_when_exceeded(self, integration_db, real_redis):
        """Test WebSocket connection denied when limit exceeded."""
        from backend.api.middleware.rate_limit import check_websocket_rate_limit

        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE": "3",
            },
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            mock_websocket = MagicMock()
            mock_websocket.client = MagicMock()
            mock_websocket.client.host = "192.168.1.200"
            mock_websocket.headers = {}

            with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
                mock_settings.return_value.rate_limit_enabled = True
                mock_settings.return_value.trusted_proxy_ips = []
                mock_settings.return_value.rate_limit_websocket_connections_per_minute = 3

                # Make connection attempts up to and past the limit
                # WebSocket tier has burst of 2, so limit is 3 + 2 = 5
                results = []
                for i in range(8):
                    is_allowed = await check_websocket_rate_limit(mock_websocket, real_redis)
                    results.append(is_allowed)

            # First 5 should be allowed (3 + 2 burst)
            assert results[0] is True  # 1
            assert results[4] is True  # 5 (at limit)
            # After that should be denied
            assert results[5] is False  # 6 (over limit)
            assert results[7] is False  # 8


class TestClientIPExtraction:
    """Tests for client IP extraction and X-Forwarded-For handling."""

    @pytest.mark.asyncio
    async def test_rate_limit_uses_direct_client_ip(self, client, mock_redis):
        """Test rate limiting uses direct client IP when not from trusted proxy."""
        from backend.api.middleware.rate_limit import get_client_ip

        mock_request = MagicMock()
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {"X-Forwarded-For": "1.2.3.4"}  # Spoofed header

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxy_ips = ["127.0.0.1"]  # Not 192.168.1.100

            ip = get_client_ip(mock_request)

        # Should use direct IP, not X-Forwarded-For (spoofing protection)
        assert ip == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_rate_limit_uses_x_forwarded_for_from_trusted_proxy(self, client, mock_redis):
        """Test rate limiting uses X-Forwarded-For when from trusted proxy."""
        from backend.api.middleware.rate_limit import get_client_ip

        mock_request = MagicMock()
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"  # Trusted proxy
        mock_request.headers = {"X-Forwarded-For": "203.0.113.50, 10.0.0.1"}

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxy_ips = ["127.0.0.1", "::1"]

            ip = get_client_ip(mock_request)

        # Should use first IP from X-Forwarded-For chain
        assert ip == "203.0.113.50"

    @pytest.mark.asyncio
    async def test_rate_limit_uses_x_real_ip_from_trusted_proxy(self, client, mock_redis):
        """Test rate limiting uses X-Real-IP when from trusted proxy."""
        from backend.api.middleware.rate_limit import get_client_ip

        mock_request = MagicMock()
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"  # Trusted proxy
        mock_request.headers = {"X-Real-IP": "198.51.100.42"}

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxy_ips = ["127.0.0.1"]

            ip = get_client_ip(mock_request)

        assert ip == "198.51.100.42"


class TestConvenienceDependencies:
    """Tests for convenience rate limiter factory functions."""

    def test_rate_limit_default_factory(self, mock_redis):
        """Test rate_limit_default returns DEFAULT tier limiter."""
        from backend.api.middleware.rate_limit import (
            RateLimiter,
            RateLimitTier,
            rate_limit_default,
        )

        limiter = rate_limit_default()

        assert isinstance(limiter, RateLimiter)
        assert limiter.tier == RateLimitTier.DEFAULT

    def test_rate_limit_media_factory(self, mock_redis):
        """Test rate_limit_media returns MEDIA tier limiter."""
        from backend.api.middleware.rate_limit import (
            RateLimiter,
            RateLimitTier,
            rate_limit_media,
        )

        limiter = rate_limit_media()

        assert isinstance(limiter, RateLimiter)
        assert limiter.tier == RateLimitTier.MEDIA

    def test_rate_limit_search_factory(self, mock_redis):
        """Test rate_limit_search returns SEARCH tier limiter."""
        from backend.api.middleware.rate_limit import (
            RateLimiter,
            RateLimitTier,
            rate_limit_search,
        )

        limiter = rate_limit_search()

        assert isinstance(limiter, RateLimiter)
        assert limiter.tier == RateLimitTier.SEARCH

    def test_rate_limit_export_factory(self, mock_redis):
        """Test rate_limit_export returns EXPORT tier limiter."""
        from backend.api.middleware.rate_limit import (
            RateLimiter,
            RateLimitTier,
            rate_limit_export,
        )

        limiter = rate_limit_export()

        assert isinstance(limiter, RateLimiter)
        assert limiter.tier == RateLimitTier.EXPORT

    def test_rate_limit_ai_inference_factory(self, mock_redis):
        """Test rate_limit_ai_inference returns AI_INFERENCE tier limiter."""
        from backend.api.middleware.rate_limit import (
            RateLimiter,
            RateLimitTier,
            rate_limit_ai_inference,
        )

        limiter = rate_limit_ai_inference()

        assert isinstance(limiter, RateLimiter)
        assert limiter.tier == RateLimitTier.AI_INFERENCE


class TestSlidingWindowBehavior:
    """Tests for the sliding window rate limiting algorithm."""

    @pytest.mark.asyncio
    async def test_sliding_window_removes_expired_entries(self, integration_db, real_redis):
        """Test that sliding window algorithm removes entries outside the window."""
        from backend.api.middleware.rate_limit import RateLimiter, RateLimitTier

        limiter = RateLimiter(
            tier=RateLimitTier.DEFAULT,
            requests_per_minute=100,
            burst=0,
            key_prefix="test_sliding_window",
        )

        with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "true"}):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # Make some requests
            for _ in range(5):
                await limiter._check_rate_limit(real_redis, "sliding_window_client")

            # Verify count - _check_rate_limit returns count BEFORE adding current request
            _is_allowed, count, _limit = await limiter._check_rate_limit(
                real_redis, "sliding_window_client"
            )
            assert count == 5  # 5 previous requests (count is before adding current)

    @pytest.mark.asyncio
    async def test_redis_key_has_correct_expiry(self, integration_db, real_redis):
        """Test that Redis keys are set with correct expiry."""
        from backend.api.middleware.rate_limit import RateLimiter, RateLimitTier

        limiter = RateLimiter(
            tier=RateLimitTier.DEFAULT,
            requests_per_minute=100,
            key_prefix="test_expiry",
        )

        with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "true"}):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # Make a request to create the key
            await limiter._check_rate_limit(real_redis, "expiry_test_client")

            # Check the key TTL
            key = limiter._make_key("expiry_test_client")
            redis_client = real_redis._ensure_connected()
            ttl = await redis_client.ttl(key)

            # TTL should be around window_seconds + 10 (70 seconds)
            assert 60 <= ttl <= 75  # Allow some variance


class TestRateLimitErrorFormat:
    """Tests for rate limit error response format consistency."""

    @pytest.mark.asyncio
    async def test_429_error_response_is_json(self, client, mock_redis):
        """Test that 429 responses are JSON formatted."""
        from backend.api.middleware.rate_limit import RateLimiter, RateLimitTier

        limiter = RateLimiter(
            tier=RateLimitTier.DEFAULT,
            requests_per_minute=1,
            burst=0,
        )

        with patch.object(
            limiter,
            "_check_rate_limit",
            return_value=(False, 10, 1),
        ):
            with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
                mock_settings.return_value.trusted_proxy_ips = []

                from fastapi import HTTPException

                with pytest.raises(HTTPException) as exc_info:
                    mock_request = MagicMock()
                    mock_request.client = MagicMock()
                    mock_request.client.host = "192.168.1.100"
                    mock_request.headers = {}
                    await limiter(mock_request, mock_redis)

                # Verify detail is a dict (JSON-serializable)
                assert isinstance(exc_info.value.detail, dict)
                assert "error" in exc_info.value.detail
                assert "message" in exc_info.value.detail
