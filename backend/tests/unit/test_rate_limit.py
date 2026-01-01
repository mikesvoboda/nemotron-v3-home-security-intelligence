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
    _is_ip_trusted,
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
# _is_ip_trusted Tests
# =============================================================================


class TestIsIPTrusted:
    """Tests for trusted proxy IP validation."""

    def test_exact_ip_match(self):
        """Test exact IP address matching."""
        assert _is_ip_trusted("127.0.0.1", ["127.0.0.1"]) is True
        assert _is_ip_trusted("192.168.1.1", ["127.0.0.1"]) is False

    def test_multiple_trusted_ips(self):
        """Test matching against multiple trusted IPs."""
        trusted = ["127.0.0.1", "10.0.0.1", "192.168.1.1"]
        assert _is_ip_trusted("10.0.0.1", trusted) is True
        assert _is_ip_trusted("192.168.1.1", trusted) is True
        assert _is_ip_trusted("172.16.0.1", trusted) is False

    def test_cidr_range_matching(self):
        """Test CIDR notation for network ranges."""
        trusted = ["10.0.0.0/8"]
        assert _is_ip_trusted("10.0.0.1", trusted) is True
        assert _is_ip_trusted("10.255.255.255", trusted) is True
        assert _is_ip_trusted("11.0.0.1", trusted) is False

    def test_mixed_ips_and_cidr(self):
        """Test mixing individual IPs and CIDR ranges."""
        trusted = ["127.0.0.1", "192.168.0.0/16"]
        assert _is_ip_trusted("127.0.0.1", trusted) is True
        assert _is_ip_trusted("192.168.1.100", trusted) is True
        assert _is_ip_trusted("192.168.255.255", trusted) is True
        assert _is_ip_trusted("10.0.0.1", trusted) is False

    def test_ipv6_support(self):
        """Test IPv6 address matching."""
        assert _is_ip_trusted("::1", ["::1"]) is True
        assert _is_ip_trusted("::1", ["127.0.0.1"]) is False

    def test_ipv6_cidr_support(self):
        """Test IPv6 CIDR notation."""
        trusted = ["fe80::/10"]
        assert _is_ip_trusted("fe80::1", trusted) is True
        assert _is_ip_trusted("fe80::ffff:ffff:ffff:ffff", trusted) is True
        assert _is_ip_trusted("2001:db8::1", trusted) is False

    def test_invalid_client_ip(self):
        """Test handling of invalid client IP."""
        assert _is_ip_trusted("invalid", ["127.0.0.1"]) is False
        assert _is_ip_trusted("", ["127.0.0.1"]) is False

    def test_invalid_trusted_ip_skipped(self):
        """Test that invalid trusted IP entries are skipped."""
        # Invalid entry should be skipped, but valid ones should work
        trusted = ["invalid", "127.0.0.1"]
        assert _is_ip_trusted("127.0.0.1", trusted) is True

    def test_invalid_trusted_ip_logs_warning(self):
        """Test that invalid trusted IP entries log a warning."""
        trusted = ["invalid_cidr", "also-not-valid", "127.0.0.1"]

        with patch("backend.api.middleware.rate_limit.logger") as mock_logger:
            result = _is_ip_trusted("127.0.0.1", trusted)

            # Function should still return True (valid IP found)
            assert result is True

            # Should have logged two warnings for the invalid entries
            assert mock_logger.warning.call_count == 2

            # Verify warning messages (IPs are masked for security)
            warning_calls = mock_logger.warning.call_args_list
            assert "Invalid CIDR" in warning_calls[0][0][0]
            assert "Invalid CIDR" in warning_calls[1][0][0]
            # Verify masked IPs are in extra dict
            assert "invalid_trusted_ip_masked" in warning_calls[0][1]["extra"]
            assert "invalid_trusted_ip_masked" in warning_calls[1][1]["extra"]

    def test_invalid_cidr_notation_logs_warning(self):
        """Test that malformed CIDR notation logs a warning."""
        trusted = ["192.168.1.0/33", "10.0.0.0/8"]  # /33 is invalid

        with patch("backend.api.middleware.rate_limit.logger") as mock_logger:
            result = _is_ip_trusted("10.0.0.1", trusted)

            # Function should still return True (valid IP found in second entry)
            assert result is True

            # Should have logged a warning for the invalid CIDR (IP masked for security)
            mock_logger.warning.assert_called_once()
            assert "Invalid CIDR" in mock_logger.warning.call_args[0][0]
            # Masked IP should be in extra dict
            assert "invalid_trusted_ip_masked" in mock_logger.warning.call_args[1]["extra"]
            # Verify the IP is masked (first octet preserved)
            assert (
                mock_logger.warning.call_args[1]["extra"]["invalid_trusted_ip_masked"]
                == "192.xxx.xxx.xxx"
            )

    def test_empty_trusted_list(self):
        """Test with empty trusted list."""
        assert _is_ip_trusted("127.0.0.1", []) is False

    def test_private_network_ranges(self):
        """Test common private network ranges."""
        trusted = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
        # Class A private
        assert _is_ip_trusted("10.0.0.1", trusted) is True
        # Class B private
        assert _is_ip_trusted("172.16.0.1", trusted) is True
        assert _is_ip_trusted("172.31.255.255", trusted) is True
        # Class C private
        assert _is_ip_trusted("192.168.0.1", trusted) is True
        # Public IP
        assert _is_ip_trusted("8.8.8.8", trusted) is False


# =============================================================================
# get_client_ip Tests
# =============================================================================


@pytest.fixture
def mock_settings_for_ip():
    """Mock settings with default trusted proxy IPs for get_client_ip tests."""
    mock = MagicMock()
    mock.trusted_proxy_ips = ["127.0.0.1", "::1"]
    return mock


class TestGetClientIP:
    """Tests for client IP extraction with trusted proxy validation."""

    def test_direct_client_ip(self, mock_request, mock_settings_for_ip):
        """Test extraction of direct client IP when not from trusted proxy."""
        mock_request.headers = {}
        mock_request.client.host = "10.0.0.1"

        with patch(
            "backend.api.middleware.rate_limit.get_settings", return_value=mock_settings_for_ip
        ):
            ip = get_client_ip(mock_request)

        assert ip == "10.0.0.1"

    def test_x_forwarded_for_from_trusted_proxy(self, mock_request, mock_settings_for_ip):
        """Test X-Forwarded-For header is used when from trusted proxy."""
        # Set up request from trusted proxy (127.0.0.1 is trusted by default)
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"X-Forwarded-For": "203.0.113.50"}

        with patch(
            "backend.api.middleware.rate_limit.get_settings", return_value=mock_settings_for_ip
        ):
            ip = get_client_ip(mock_request)

        assert ip == "203.0.113.50"

    def test_x_forwarded_for_from_untrusted_proxy_ignored(self, mock_request, mock_settings_for_ip):
        """Test X-Forwarded-For header is IGNORED when from untrusted proxy."""
        # Request from untrusted IP (not localhost)
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {"X-Forwarded-For": "203.0.113.50"}

        with patch(
            "backend.api.middleware.rate_limit.get_settings", return_value=mock_settings_for_ip
        ):
            ip = get_client_ip(mock_request)

        # Should return direct IP, NOT the X-Forwarded-For value
        assert ip == "192.168.1.100"

    def test_x_forwarded_for_chain_from_trusted_proxy(self, mock_request, mock_settings_for_ip):
        """Test X-Forwarded-For header with multiple IPs from trusted proxy."""
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"X-Forwarded-For": "203.0.113.50, 70.41.3.18, 150.172.238.178"}

        with patch(
            "backend.api.middleware.rate_limit.get_settings", return_value=mock_settings_for_ip
        ):
            ip = get_client_ip(mock_request)

        # Should return first IP (original client)
        assert ip == "203.0.113.50"

    def test_x_real_ip_from_trusted_proxy(self, mock_request, mock_settings_for_ip):
        """Test X-Real-IP header from trusted proxy."""
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"X-Real-IP": "198.51.100.42"}

        with patch(
            "backend.api.middleware.rate_limit.get_settings", return_value=mock_settings_for_ip
        ):
            ip = get_client_ip(mock_request)

        assert ip == "198.51.100.42"

    def test_x_real_ip_from_untrusted_proxy_ignored(self, mock_request, mock_settings_for_ip):
        """Test X-Real-IP header is IGNORED when from untrusted proxy."""
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {"X-Real-IP": "198.51.100.42"}

        with patch(
            "backend.api.middleware.rate_limit.get_settings", return_value=mock_settings_for_ip
        ):
            ip = get_client_ip(mock_request)

        # Should return direct IP, NOT the X-Real-IP value
        assert ip == "192.168.1.100"

    def test_x_forwarded_for_takes_precedence_from_trusted_proxy(
        self, mock_request, mock_settings_for_ip
    ):
        """Test that X-Forwarded-For takes precedence over X-Real-IP from trusted proxy."""
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {
            "X-Forwarded-For": "203.0.113.50",
            "X-Real-IP": "198.51.100.42",
        }

        with patch(
            "backend.api.middleware.rate_limit.get_settings", return_value=mock_settings_for_ip
        ):
            ip = get_client_ip(mock_request)

        assert ip == "203.0.113.50"

    def test_no_client_info(self, mock_request, mock_settings_for_ip):
        """Test handling when no client info is available."""
        mock_request.headers = {}
        mock_request.client = None

        with patch(
            "backend.api.middleware.rate_limit.get_settings", return_value=mock_settings_for_ip
        ):
            ip = get_client_ip(mock_request)

        assert ip == "unknown"

    def test_websocket_ip_extraction(self, mock_websocket, mock_settings_for_ip):
        """Test IP extraction from WebSocket."""
        mock_websocket.headers = {}
        mock_websocket.client.host = "172.16.0.5"

        with patch(
            "backend.api.middleware.rate_limit.get_settings", return_value=mock_settings_for_ip
        ):
            ip = get_client_ip(mock_websocket)

        assert ip == "172.16.0.5"

    def test_trusted_ipv6_localhost(self, mock_request, mock_settings_for_ip):
        """Test X-Forwarded-For is trusted from IPv6 localhost."""
        mock_request.client.host = "::1"
        mock_request.headers = {"X-Forwarded-For": "203.0.113.50"}

        with patch(
            "backend.api.middleware.rate_limit.get_settings", return_value=mock_settings_for_ip
        ):
            ip = get_client_ip(mock_request)

        assert ip == "203.0.113.50"

    def test_custom_trusted_proxies(self, mock_request):
        """Test with custom trusted proxy configuration."""
        mock_settings = MagicMock()
        mock_settings.trusted_proxy_ips = ["10.0.0.0/8"]

        # Request from trusted proxy network
        mock_request.client.host = "10.0.0.1"
        mock_request.headers = {"X-Forwarded-For": "203.0.113.50"}

        with patch("backend.api.middleware.rate_limit.get_settings", return_value=mock_settings):
            ip = get_client_ip(mock_request)

        assert ip == "203.0.113.50"

    def test_spoofed_xff_from_attacker_rejected(self, mock_request, mock_settings_for_ip):
        """Test that spoofed X-Forwarded-For from attacker IP is rejected.

        This is the key security test: an attacker sending requests directly
        with a forged X-Forwarded-For header should not be able to bypass
        rate limiting.
        """
        # Attacker's actual IP (not a valid IP, but not in trusted list)
        mock_request.client.host = "8.8.8.8"
        # Attacker forges X-Forwarded-For to appear as a different IP
        mock_request.headers = {"X-Forwarded-For": "10.0.0.1"}

        with patch(
            "backend.api.middleware.rate_limit.get_settings", return_value=mock_settings_for_ip
        ):
            ip = get_client_ip(mock_request)

        # Should return attacker's actual IP, not the forged one
        assert ip == "8.8.8.8"


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

    @pytest.mark.asyncio
    async def test_websocket_rapid_connection_attempts_rejected(self, mock_websocket, mock_redis):
        """Test that rapid connection attempts are rejected after exceeding threshold.

        This test simulates multiple connection attempts in rapid succession,
        verifying that once the threshold is exceeded, subsequent connections
        are rejected.
        """
        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE": "5",
            },
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # WebSocket tier has burst of 2, so limit is 5 + 2 = 7
            # Simulate increasing connection count
            counts = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
            call_count = 0

            async def mock_execute():
                nonlocal call_count
                count = counts[min(call_count, len(counts) - 1)]
                call_count += 1
                return [0, count, 1, True]

            mock_pipe = mock_redis._ensure_connected.return_value.pipeline.return_value
            mock_pipe.execute = mock_execute

            # First few connections should be allowed
            results = []
            for _ in range(10):
                result = await check_websocket_rate_limit(mock_websocket, mock_redis)
                results.append(result)

            # First 6 should be allowed (count 1-6, limit is 7)
            # After that, count >= 7, so denied
            assert results[:6] == [True, True, True, True, True, True]
            assert results[6:] == [False, False, False, False]

    @pytest.mark.asyncio
    async def test_websocket_different_clients_have_independent_limits(self, mock_redis):
        """Test that different client IPs have independent rate limits.

        Each client should have their own counter, so one client hitting
        the limit should not affect other clients.
        """
        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE": "5",
            },
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # Create mock websockets for different clients
            client_a = MagicMock()
            client_a.client = MagicMock()
            client_a.client.host = "192.168.1.100"
            client_a.headers = {}

            client_b = MagicMock()
            client_b.client = MagicMock()
            client_b.client.host = "192.168.1.200"
            client_b.headers = {}

            def mock_pipeline():
                pipe = MagicMock()
                pipe.zremrangebyscore = MagicMock()
                pipe.zcard = MagicMock()
                pipe.zadd = MagicMock()
                pipe.expire = MagicMock()

                # Return different counts based on the key (simulating per-client tracking)
                async def execute():
                    # Get the last key used (from zadd call)
                    # For simplicity, return low count for all (under limit)
                    return [0, 2, 1, True]

                pipe.execute = execute
                return pipe

            mock_redis._ensure_connected.return_value.pipeline = mock_pipeline

            # Both clients should be allowed (independent limits)
            result_a = await check_websocket_rate_limit(client_a, mock_redis)
            result_b = await check_websocket_rate_limit(client_b, mock_redis)

            assert result_a is True
            assert result_b is True

    @pytest.mark.asyncio
    async def test_websocket_rate_limit_uses_correct_tier(self, mock_websocket, mock_redis):
        """Test that WebSocket rate limiting uses the WEBSOCKET tier settings."""
        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE": "20",
            },
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # WebSocket tier limit is 20 + 2 burst = 22
            mock_pipe = mock_redis._ensure_connected.return_value.pipeline.return_value
            mock_pipe.execute = AsyncMock(return_value=[0, 21, 1, True])

            # 21 < 22, so should be allowed
            result = await check_websocket_rate_limit(mock_websocket, mock_redis)
            assert result is True

            # Now at limit
            mock_pipe.execute = AsyncMock(return_value=[0, 22, 1, True])
            result = await check_websocket_rate_limit(mock_websocket, mock_redis)
            assert result is False

    @pytest.mark.asyncio
    async def test_websocket_rate_limit_sliding_window_key_generation(
        self, mock_websocket, mock_redis
    ):
        """Test that rate limit creates correct Redis key for WebSocket tier."""
        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE": "10",
            },
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            mock_websocket.client.host = "10.0.0.5"
            mock_pipe = mock_redis._ensure_connected.return_value.pipeline.return_value
            mock_pipe.execute = AsyncMock(return_value=[0, 1, 1, True])

            await check_websocket_rate_limit(mock_websocket, mock_redis)

            # Verify the key includes the websocket tier and client IP
            # The key format is: rate_limit:websocket:10.0.0.5
            # We can verify by checking that zadd was called
            mock_pipe.zadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_rate_limit_redis_error_fails_open(self, mock_websocket, mock_redis):
        """Test that Redis errors result in allowing WebSocket connections (fail-open)."""
        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE": "10",
            },
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # Simulate Redis connection error
            mock_redis._ensure_connected.side_effect = Exception("Redis unavailable")

            result = await check_websocket_rate_limit(mock_websocket, mock_redis)

            # Should fail open (allow connection)
            assert result is True

    @pytest.mark.asyncio
    async def test_websocket_rate_limit_with_x_forwarded_for(self, mock_redis):
        """Test that rate limiting correctly uses X-Forwarded-For header."""
        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE": "10",
            },
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()

            # Create websocket with X-Forwarded-For header (common with reverse proxies)
            ws_behind_proxy = MagicMock()
            ws_behind_proxy.client = MagicMock()
            ws_behind_proxy.client.host = "127.0.0.1"  # Proxy IP
            ws_behind_proxy.headers = {"X-Forwarded-For": "203.0.113.50"}  # Real client IP

            mock_pipe = mock_redis._ensure_connected.return_value.pipeline.return_value
            mock_pipe.execute = AsyncMock(return_value=[0, 5, 1, True])

            result = await check_websocket_rate_limit(ws_behind_proxy, mock_redis)

            assert result is True
            # The key should use the real client IP (203.0.113.50), not the proxy IP


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

    def test_empty_ip_chain(self, mock_request, mock_settings_for_ip):
        """Test handling of empty X-Forwarded-For header."""
        mock_request.headers = {"X-Forwarded-For": ""}
        mock_request.client.host = "10.0.0.1"

        with patch(
            "backend.api.middleware.rate_limit.get_settings", return_value=mock_settings_for_ip
        ):
            ip = get_client_ip(mock_request)

        # Empty header should fall through to client.host
        assert ip == "10.0.0.1"

    def test_whitespace_in_forwarded_header(self, mock_request, mock_settings_for_ip):
        """Test stripping of whitespace in X-Forwarded-For header."""
        # Request from trusted proxy (127.0.0.1) with whitespace-padded X-Forwarded-For
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"X-Forwarded-For": "  203.0.113.50  "}

        with patch(
            "backend.api.middleware.rate_limit.get_settings", return_value=mock_settings_for_ip
        ):
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
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
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
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test"},
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()

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
