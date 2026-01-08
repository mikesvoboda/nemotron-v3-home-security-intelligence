"""Unit tests for rate limiting middleware.

Tests for Redis-based sliding window rate limiting with support for
multiple tiers, trusted proxy detection, and IP spoofing protection.

Tests follow TDD methodology.
"""

import ipaddress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request, WebSocket, status
from starlette.datastructures import Headers

from backend.api.middleware.rate_limit import (
    RateLimiter,
    RateLimitTier,
    check_websocket_rate_limit,
    clear_trusted_proxy_cache,
    get_client_ip,
    get_tier_limits,
    rate_limit_ai_inference,
    rate_limit_default,
    rate_limit_export,
    rate_limit_media,
    rate_limit_search,
)

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestMaskIpForLogging:
    """Tests for _mask_ip_for_logging helper function."""

    def test_mask_ipv4_address(self):
        """Test masking IPv4 addresses preserves first octet."""
        from backend.api.middleware.rate_limit import _mask_ip_for_logging

        assert _mask_ip_for_logging("192.168.1.100") == "192.xxx.xxx.xxx"
        assert _mask_ip_for_logging("10.0.0.1") == "10.xxx.xxx.xxx"

    def test_mask_ipv4_cidr(self):
        """Test masking IPv4 CIDR notation strips suffix."""
        from backend.api.middleware.rate_limit import _mask_ip_for_logging

        assert _mask_ip_for_logging("192.168.0.0/16") == "192.xxx.xxx.xxx"
        assert _mask_ip_for_logging("10.0.0.0/8") == "10.xxx.xxx.xxx"

    def test_mask_ipv6_address(self):
        """Test masking IPv6 addresses preserves first segment."""
        from backend.api.middleware.rate_limit import _mask_ip_for_logging

        assert _mask_ip_for_logging("2001:0db8:85a3::8a2e:0370:7334") == "2001:xxx:..."
        assert _mask_ip_for_logging("fe80::1") == "fe80:xxx:..."

    def test_mask_ipv6_cidr(self):
        """Test masking IPv6 CIDR notation strips suffix."""
        from backend.api.middleware.rate_limit import _mask_ip_for_logging

        assert _mask_ip_for_logging("2001:db8::/32") == "2001:xxx:..."

    def test_mask_empty_string(self):
        """Test masking empty or invalid strings."""
        from backend.api.middleware.rate_limit import _mask_ip_for_logging

        # Empty parts should return placeholder (empty first octet becomes "")
        assert _mask_ip_for_logging("") == ".xxx.xxx.xxx"


class TestGetCompiledTrustedProxies:
    """Tests for _get_compiled_trusted_proxies caching function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_trusted_proxy_cache()

    def test_compile_individual_ips(self):
        """Test compiling list of individual IPs."""
        from backend.api.middleware.rate_limit import _get_compiled_trusted_proxies

        trusted_ips = ["127.0.0.1", "192.168.1.1", "::1"]
        networks, ips = _get_compiled_trusted_proxies(trusted_ips)

        assert len(networks) == 0
        assert len(ips) == 3
        assert ipaddress.ip_address("127.0.0.1") in ips
        assert ipaddress.ip_address("192.168.1.1") in ips
        assert ipaddress.ip_address("::1") in ips

    def test_compile_cidr_networks(self):
        """Test compiling CIDR notation networks."""
        from backend.api.middleware.rate_limit import _get_compiled_trusted_proxies

        trusted_ips = ["10.0.0.0/8", "192.168.0.0/16"]
        networks, ips = _get_compiled_trusted_proxies(trusted_ips)

        assert len(networks) == 2
        assert len(ips) == 0
        # Check networks contain expected IPs
        network_strs = [str(net) for net in networks]
        assert "10.0.0.0/8" in network_strs
        assert "192.168.0.0/16" in network_strs

    def test_compile_mixed_ips_and_networks(self):
        """Test compiling mixed IPs and CIDR networks."""
        from backend.api.middleware.rate_limit import _get_compiled_trusted_proxies

        trusted_ips = ["127.0.0.1", "10.0.0.0/8", "192.168.1.1"]
        networks, ips = _get_compiled_trusted_proxies(trusted_ips)

        assert len(networks) == 1
        assert len(ips) == 2

    def test_cache_hit_returns_same_result(self):
        """Test that cache returns same compiled result."""
        from backend.api.middleware.rate_limit import _get_compiled_trusted_proxies

        trusted_ips = ["127.0.0.1", "10.0.0.0/8"]
        networks1, ips1 = _get_compiled_trusted_proxies(trusted_ips)
        networks2, ips2 = _get_compiled_trusted_proxies(trusted_ips)

        # Should be exact same objects (cached)
        assert networks1 is networks2
        assert ips1 is ips2

    def test_cache_invalidates_on_config_change(self):
        """Test that cache invalidates when trusted IPs list changes."""
        from backend.api.middleware.rate_limit import _get_compiled_trusted_proxies

        trusted_ips1 = ["127.0.0.1"]
        networks1, ips1 = _get_compiled_trusted_proxies(trusted_ips1)

        trusted_ips2 = ["192.168.1.1"]
        networks2, ips2 = _get_compiled_trusted_proxies(trusted_ips2)

        # Should be different objects (cache miss)
        assert networks1 is not networks2
        assert ips1 is not ips2

    def test_invalid_ip_is_skipped(self, caplog):
        """Test that invalid IP entries are skipped with warning."""
        from backend.api.middleware.rate_limit import _get_compiled_trusted_proxies

        trusted_ips = ["127.0.0.1", "invalid-ip", "192.168.1.1"]
        _networks, ips = _get_compiled_trusted_proxies(trusted_ips)

        # Should skip invalid entry
        assert len(ips) == 2
        assert ipaddress.ip_address("127.0.0.1") in ips
        assert ipaddress.ip_address("192.168.1.1") in ips

        # Should log warning
        assert "Invalid CIDR notation" in caplog.text

    def test_clear_cache(self):
        """Test clearing the cache."""
        from backend.api.middleware.rate_limit import _get_compiled_trusted_proxies

        trusted_ips = ["127.0.0.1"]
        _get_compiled_trusted_proxies(trusted_ips)

        clear_trusted_proxy_cache()

        # Cache should be empty
        from backend.api.middleware.rate_limit import _trusted_proxy_cache

        assert len(_trusted_proxy_cache) == 0


class TestIsIpTrusted:
    """Tests for _is_ip_trusted function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_trusted_proxy_cache()

    def test_trusted_individual_ip(self):
        """Test checking against individual trusted IP."""
        from backend.api.middleware.rate_limit import _is_ip_trusted

        trusted_ips = ["127.0.0.1", "192.168.1.1"]
        assert _is_ip_trusted("127.0.0.1", trusted_ips) is True
        assert _is_ip_trusted("192.168.1.1", trusted_ips) is True

    def test_untrusted_ip(self):
        """Test checking against untrusted IP."""
        from backend.api.middleware.rate_limit import _is_ip_trusted

        trusted_ips = ["127.0.0.1"]
        assert _is_ip_trusted("192.168.1.100", trusted_ips) is False

    def test_trusted_cidr_network(self):
        """Test checking IP within CIDR network."""
        from backend.api.middleware.rate_limit import _is_ip_trusted

        trusted_ips = ["10.0.0.0/8"]
        assert _is_ip_trusted("10.5.10.20", trusted_ips) is True
        assert _is_ip_trusted("10.255.255.255", trusted_ips) is True
        assert _is_ip_trusted("192.168.1.1", trusted_ips) is False

    def test_ipv6_trusted(self):
        """Test checking IPv6 addresses."""
        from backend.api.middleware.rate_limit import _is_ip_trusted

        trusted_ips = ["::1", "fe80::/10"]
        assert _is_ip_trusted("::1", trusted_ips) is True
        assert _is_ip_trusted("fe80::1", trusted_ips) is True
        assert _is_ip_trusted("2001:db8::1", trusted_ips) is False

    def test_invalid_client_ip_is_untrusted(self):
        """Test that invalid client IP returns False."""
        from backend.api.middleware.rate_limit import _is_ip_trusted

        trusted_ips = ["127.0.0.1"]
        assert _is_ip_trusted("not-an-ip", trusted_ips) is False


class TestGetTierLimits:
    """Tests for get_tier_limits function."""

    def test_get_default_tier_limits(self):
        """Test getting default tier limits."""
        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_requests_per_minute = 100
            mock_settings.return_value.rate_limit_burst = 20

            requests, burst = get_tier_limits(RateLimitTier.DEFAULT)
            assert requests == 100
            assert burst == 20

    def test_get_media_tier_limits(self):
        """Test getting media tier limits."""
        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_media_requests_per_minute = 50
            mock_settings.return_value.rate_limit_burst = 10

            requests, burst = get_tier_limits(RateLimitTier.MEDIA)
            assert requests == 50
            assert burst == 10

    def test_get_websocket_tier_limits(self):
        """Test getting websocket tier limits (fixed burst of 2)."""
        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_websocket_connections_per_minute = 30

            requests, burst = get_tier_limits(RateLimitTier.WEBSOCKET)
            assert requests == 30
            assert burst == 2

    def test_get_search_tier_limits(self):
        """Test getting search tier limits."""
        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_search_requests_per_minute = 60
            mock_settings.return_value.rate_limit_burst = 15

            requests, burst = get_tier_limits(RateLimitTier.SEARCH)
            assert requests == 60
            assert burst == 15

    def test_get_export_tier_limits(self):
        """Test getting export tier limits (no burst)."""
        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_export_requests_per_minute = 10

            requests, burst = get_tier_limits(RateLimitTier.EXPORT)
            assert requests == 10
            assert burst == 0

    def test_get_ai_inference_tier_limits(self):
        """Test getting AI inference tier limits."""
        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_ai_inference_requests_per_minute = 10
            mock_settings.return_value.rate_limit_ai_inference_burst = 3

            requests, burst = get_tier_limits(RateLimitTier.AI_INFERENCE)
            assert requests == 10
            assert burst == 3


class TestGetClientIp:
    """Tests for get_client_ip function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_trusted_proxy_cache()

    def test_get_direct_client_ip(self):
        """Test extracting direct client IP when no proxy headers."""
        mock_request = MagicMock(spec=Request)
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = Headers({})

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxy_ips = []
            ip = get_client_ip(mock_request)

        assert ip == "192.168.1.100"

    def test_get_ip_from_x_forwarded_for_when_trusted(self):
        """Test extracting IP from X-Forwarded-For when proxy is trusted."""
        mock_request = MagicMock(spec=Request)
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"  # Trusted proxy
        mock_request.headers = Headers({"X-Forwarded-For": "203.0.113.5, 198.51.100.10"})

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxy_ips = ["127.0.0.1"]
            ip = get_client_ip(mock_request)

        # Should extract first IP in chain (original client)
        assert ip == "203.0.113.5"

    def test_ignore_x_forwarded_for_when_untrusted(self):
        """Test ignoring X-Forwarded-For from untrusted proxy (IP spoofing protection)."""
        mock_request = MagicMock(spec=Request)
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.100"  # Untrusted
        mock_request.headers = Headers({"X-Forwarded-For": "1.2.3.4"})

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxy_ips = ["127.0.0.1"]
            ip = get_client_ip(mock_request)

        # Should use direct IP, not X-Forwarded-For
        assert ip == "192.168.1.100"

    def test_get_ip_from_x_real_ip_when_trusted(self):
        """Test extracting IP from X-Real-IP when proxy is trusted."""
        mock_request = MagicMock(spec=Request)
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"  # Trusted proxy
        mock_request.headers = Headers({"X-Real-IP": "203.0.113.10"})

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxy_ips = ["127.0.0.1"]
            ip = get_client_ip(mock_request)

        assert ip == "203.0.113.10"

    def test_x_forwarded_for_takes_precedence_over_x_real_ip(self):
        """Test X-Forwarded-For is checked before X-Real-IP."""
        mock_request = MagicMock(spec=Request)
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = Headers(
            {"X-Forwarded-For": "203.0.113.5", "X-Real-IP": "203.0.113.10"}
        )

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxy_ips = ["127.0.0.1"]
            ip = get_client_ip(mock_request)

        assert ip == "203.0.113.5"

    def test_return_unknown_when_no_client(self):
        """Test returning 'unknown' when request has no client."""
        mock_request = MagicMock(spec=Request)
        mock_request.client = None
        mock_request.headers = Headers({})

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxy_ips = []
            ip = get_client_ip(mock_request)

        assert ip == "unknown"

    def test_websocket_get_client_ip(self):
        """Test extracting client IP from WebSocket."""
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.client = MagicMock()
        mock_websocket.client.host = "192.168.1.200"
        mock_websocket.headers = Headers({})

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxy_ips = []
            ip = get_client_ip(mock_websocket)

        assert ip == "192.168.1.200"

    def test_cidr_trusted_proxy(self):
        """Test trusting proxy by CIDR range."""
        mock_request = MagicMock(spec=Request)
        mock_request.client = MagicMock()
        mock_request.client.host = "10.5.10.20"  # Within 10.0.0.0/8
        mock_request.headers = Headers({"X-Forwarded-For": "203.0.113.5"})

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxy_ips = ["10.0.0.0/8"]
            ip = get_client_ip(mock_request)

        assert ip == "203.0.113.5"


class TestRateLimiterInit:
    """Tests for RateLimiter initialization."""

    def test_init_with_tier_default(self):
        """Test initializing with tier uses tier defaults."""
        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_requests_per_minute = 100
            mock_settings.return_value.rate_limit_burst = 20

            limiter = RateLimiter(tier=RateLimitTier.DEFAULT)

            assert limiter.tier == RateLimitTier.DEFAULT
            assert limiter.requests_per_minute == 100
            assert limiter.burst == 20

    def test_init_with_explicit_limits(self):
        """Test initializing with explicit limits overrides tier defaults."""
        limiter = RateLimiter(tier=RateLimitTier.DEFAULT, requests_per_minute=50, burst=5)

        assert limiter.requests_per_minute == 50
        assert limiter.burst == 5

    def test_init_with_custom_key_prefix(self):
        """Test initializing with custom Redis key prefix."""
        limiter = RateLimiter(key_prefix="custom_limit")
        assert limiter.key_prefix == "custom_limit"

    def test_make_key(self):
        """Test Redis key generation."""
        limiter = RateLimiter(tier=RateLimitTier.MEDIA)
        key = limiter._make_key("192.168.1.100")
        assert key == "rate_limit:media:192.168.1.100"


class TestRateLimiterCheckRateLimit:
    """Tests for RateLimiter._check_rate_limit method."""

    @pytest.mark.asyncio
    async def test_allow_request_under_limit(self, mock_redis_client):
        """Test allowing request when under rate limit."""
        # Mock Redis pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.zremrangebyscore = MagicMock()
        mock_pipeline.zcard = MagicMock()
        mock_pipeline.zadd = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock(return_value=[0, 5, 1, True])  # 5 current requests

        mock_redis_client._ensure_connected = MagicMock(
            return_value=MagicMock(pipeline=MagicMock(return_value=mock_pipeline))
        )

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=10, burst=2)
            is_allowed, current_count, limit = await limiter._check_rate_limit(
                mock_redis_client, "192.168.1.100"
            )

        assert is_allowed is True
        assert current_count == 5
        assert limit == 12  # 10 + 2 burst

    @pytest.mark.asyncio
    async def test_block_request_over_limit(self, mock_redis_client):
        """Test blocking request when over rate limit."""
        # Mock Redis pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.zremrangebyscore = MagicMock()
        mock_pipeline.zcard = MagicMock()
        mock_pipeline.zadd = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock(return_value=[0, 15, 1, True])  # 15 current requests

        mock_redis_client._ensure_connected = MagicMock(
            return_value=MagicMock(pipeline=MagicMock(return_value=mock_pipeline))
        )

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=10, burst=2)
            is_allowed, current_count, limit = await limiter._check_rate_limit(
                mock_redis_client, "192.168.1.100"
            )

        assert is_allowed is False
        assert current_count == 15
        assert limit == 12

    @pytest.mark.asyncio
    async def test_skip_when_rate_limiting_disabled(self, mock_redis_client):
        """Test skipping rate limit check when disabled."""
        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_enabled = False

            limiter = RateLimiter(requests_per_minute=10)
            is_allowed, current_count, limit = await limiter._check_rate_limit(
                mock_redis_client, "192.168.1.100"
            )

        assert is_allowed is True
        assert current_count == 0
        assert limit == 10

    @pytest.mark.asyncio
    async def test_fail_open_on_redis_error(self, mock_redis_client):
        """Test failing open (allowing request) when Redis errors."""
        mock_redis_client._ensure_connected = MagicMock(
            side_effect=Exception("Redis connection failed")
        )

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=10)
            is_allowed, current_count, _limit = await limiter._check_rate_limit(
                mock_redis_client, "192.168.1.100"
            )

        # Should allow request despite error
        assert is_allowed is True
        assert current_count == 0

    @pytest.mark.asyncio
    async def test_sliding_window_removes_expired_entries(self, mock_redis_client):
        """Test that sliding window removes entries outside time window."""
        mock_pipeline = MagicMock()
        mock_pipeline.zremrangebyscore = MagicMock()
        mock_pipeline.zcard = MagicMock()
        mock_pipeline.zadd = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock(return_value=[5, 10, 1, True])  # Removed 5 entries

        mock_redis_client._ensure_connected = MagicMock(
            return_value=MagicMock(pipeline=MagicMock(return_value=mock_pipeline))
        )

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=20)
            await limiter._check_rate_limit(mock_redis_client, "192.168.1.100")

        # Verify zremrangebyscore was called (removes expired entries)
        mock_pipeline.zremrangebyscore.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_key_expiry_set(self, mock_redis_client):
        """Test that Redis key expiry is set to prevent memory leaks."""
        mock_pipeline = MagicMock()
        mock_pipeline.zremrangebyscore = MagicMock()
        mock_pipeline.zcard = MagicMock()
        mock_pipeline.zadd = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock(return_value=[0, 5, 1, True])

        mock_redis_client._ensure_connected = MagicMock(
            return_value=MagicMock(pipeline=MagicMock(return_value=mock_pipeline))
        )

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=10)
            await limiter._check_rate_limit(mock_redis_client, "192.168.1.100")

        # Verify expire was called with window_seconds + 10
        mock_pipeline.expire.assert_called_once()
        args = mock_pipeline.expire.call_args[0]
        assert args[1] == 70  # 60 seconds + 10


class TestRateLimiterCall:
    """Tests for RateLimiter.__call__ dependency method."""

    @pytest.mark.asyncio
    async def test_allow_request_under_limit(self, mock_redis_client):
        """Test allowing request when under limit."""
        mock_request = MagicMock(spec=Request)
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = Headers({})

        limiter = RateLimiter(requests_per_minute=10, burst=2)

        with (
            patch.object(
                limiter,
                "_check_rate_limit",
                return_value=(True, 5, 12),
            ) as mock_check,
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.trusted_proxy_ips = []
            # Should not raise exception
            await limiter(mock_request, mock_redis_client)

        mock_check.assert_called_once_with(mock_redis_client, "192.168.1.100")

    @pytest.mark.asyncio
    async def test_raise_429_when_over_limit(self, mock_redis_client):
        """Test raising 429 Too Many Requests when over limit."""
        mock_request = MagicMock(spec=Request)
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = Headers({})

        limiter = RateLimiter(requests_per_minute=10, burst=2)

        with (
            patch.object(
                limiter,
                "_check_rate_limit",
                return_value=(False, 15, 12),
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.trusted_proxy_ips = []

            with pytest.raises(HTTPException) as exc_info:
                await limiter(mock_request, mock_redis_client)

        # Verify exception details
        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "Retry-After" in exc_info.value.headers
        assert "X-RateLimit-Limit" in exc_info.value.headers
        assert "X-RateLimit-Remaining" in exc_info.value.headers
        assert "X-RateLimit-Reset" in exc_info.value.headers

    @pytest.mark.asyncio
    async def test_exception_includes_tier_info(self, mock_redis_client):
        """Test that 429 exception includes tier information."""
        mock_request = MagicMock(spec=Request)
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = Headers({})

        limiter = RateLimiter(tier=RateLimitTier.MEDIA)

        with (
            patch.object(
                limiter,
                "_check_rate_limit",
                return_value=(False, 15, 12),
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.trusted_proxy_ips = []

            with pytest.raises(HTTPException) as exc_info:
                await limiter(mock_request, mock_redis_client)

        # Verify tier is in error detail
        assert exc_info.value.detail["tier"] == "media"

    @pytest.mark.asyncio
    async def test_retry_after_header_set(self, mock_redis_client):
        """Test that Retry-After header is set correctly."""
        mock_request = MagicMock(spec=Request)
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = Headers({})

        limiter = RateLimiter(requests_per_minute=10)

        with (
            patch.object(
                limiter,
                "_check_rate_limit",
                return_value=(False, 15, 10),
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.trusted_proxy_ips = []

            with pytest.raises(HTTPException) as exc_info:
                await limiter(mock_request, mock_redis_client)

        assert exc_info.value.headers["Retry-After"] == "60"


class TestCheckWebsocketRateLimit:
    """Tests for check_websocket_rate_limit function."""

    @pytest.mark.asyncio
    async def test_allow_websocket_under_limit(self, mock_redis_client):
        """Test allowing WebSocket connection under limit."""
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.client = MagicMock()
        mock_websocket.client.host = "192.168.1.100"
        mock_websocket.headers = Headers({})

        # Mock Redis pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.zremrangebyscore = MagicMock()
        mock_pipeline.zcard = MagicMock()
        mock_pipeline.zadd = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock(return_value=[0, 5, 1, True])

        mock_redis_client._ensure_connected = MagicMock(
            return_value=MagicMock(pipeline=MagicMock(return_value=mock_pipeline))
        )

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_enabled = True
            mock_settings.return_value.trusted_proxy_ips = []
            mock_settings.return_value.rate_limit_websocket_connections_per_minute = 30

            is_allowed = await check_websocket_rate_limit(mock_websocket, mock_redis_client)

        assert is_allowed is True

    @pytest.mark.asyncio
    async def test_block_websocket_over_limit(self, mock_redis_client):
        """Test blocking WebSocket connection over limit."""
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.client = MagicMock()
        mock_websocket.client.host = "192.168.1.100"
        mock_websocket.headers = Headers({})

        # Mock Redis pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.zremrangebyscore = MagicMock()
        mock_pipeline.zcard = MagicMock()
        mock_pipeline.zadd = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock(return_value=[0, 35, 1, True])  # Over limit

        mock_redis_client._ensure_connected = MagicMock(
            return_value=MagicMock(pipeline=MagicMock(return_value=mock_pipeline))
        )

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_enabled = True
            mock_settings.return_value.trusted_proxy_ips = []
            mock_settings.return_value.rate_limit_websocket_connections_per_minute = 30

            is_allowed = await check_websocket_rate_limit(mock_websocket, mock_redis_client)

        assert is_allowed is False

    @pytest.mark.asyncio
    async def test_skip_when_rate_limiting_disabled(self, mock_redis_client):
        """Test skipping WebSocket rate limit when disabled."""
        mock_websocket = MagicMock(spec=WebSocket)

        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_enabled = False

            is_allowed = await check_websocket_rate_limit(mock_websocket, mock_redis_client)

        assert is_allowed is True


class TestConvenienceDependencies:
    """Tests for convenience dependency factory functions."""

    def test_rate_limit_default(self):
        """Test rate_limit_default factory."""
        limiter = rate_limit_default()
        assert isinstance(limiter, RateLimiter)
        assert limiter.tier == RateLimitTier.DEFAULT

    def test_rate_limit_media(self):
        """Test rate_limit_media factory."""
        limiter = rate_limit_media()
        assert isinstance(limiter, RateLimiter)
        assert limiter.tier == RateLimitTier.MEDIA

    def test_rate_limit_search(self):
        """Test rate_limit_search factory."""
        limiter = rate_limit_search()
        assert isinstance(limiter, RateLimiter)
        assert limiter.tier == RateLimitTier.SEARCH

    def test_rate_limit_export(self):
        """Test rate_limit_export factory."""
        limiter = rate_limit_export()
        assert isinstance(limiter, RateLimiter)
        assert limiter.tier == RateLimitTier.EXPORT

    def test_rate_limit_ai_inference(self):
        """Test rate_limit_ai_inference factory."""
        limiter = rate_limit_ai_inference()
        assert isinstance(limiter, RateLimiter)
        assert limiter.tier == RateLimitTier.AI_INFERENCE
