"""Unit tests for rate limiting middleware.

Tests for Redis-based sliding window rate limiting with support for
multiple tiers, trusted proxy detection, and IP spoofing protection.

The rate limiter uses an atomic Lua script to ensure check-and-increment
operations are performed atomically, preventing race conditions.

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
    _execute_rate_limit_script,
    _get_script_sha,
    _load_lua_script,
    check_websocket_rate_limit,
    clear_lua_script_cache,
    clear_trusted_proxy_cache,
    get_client_ip,
    get_tier_limits,
    rate_limit_ai_inference,
    rate_limit_bulk,
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

    def test_get_bulk_tier_limits(self):
        """Test getting bulk tier limits (NEM-2600)."""
        with patch("backend.api.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_bulk_requests_per_minute = 10
            mock_settings.return_value.rate_limit_bulk_burst = 2

            requests, burst = get_tier_limits(RateLimitTier.BULK)
            assert requests == 10
            assert burst == 2


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


class TestLuaScriptLoading:
    """Tests for Lua script loading and caching."""

    def setup_method(self):
        """Clear Lua script cache before each test."""
        clear_lua_script_cache()

    def test_load_lua_script(self):
        """Test loading Lua script from disk."""
        script = _load_lua_script()
        assert script is not None
        assert "ZREMRANGEBYSCORE" in script
        assert "ZCARD" in script
        assert "ZADD" in script
        assert "EXPIRE" in script

    def test_lua_script_caching(self):
        """Test that Lua script content is cached."""
        script1 = _load_lua_script()
        script2 = _load_lua_script()
        # Should be the exact same object (cached)
        assert script1 is script2

    def test_clear_lua_script_cache(self):
        """Test clearing the Lua script cache."""
        _load_lua_script()
        clear_lua_script_cache()

        # After clearing, loading should read from disk again
        # (we can't easily verify this without mocking, but the function should work)
        script = _load_lua_script()
        assert script is not None

    @pytest.mark.asyncio
    async def test_get_script_sha_loads_script(self, mock_redis_client):
        """Test that _get_script_sha loads the script into Redis."""
        mock_client = MagicMock()
        mock_client.script_load = AsyncMock(return_value="abc123sha")
        mock_redis_client._ensure_connected = MagicMock(return_value=mock_client)

        sha = await _get_script_sha(mock_redis_client)

        assert sha == "abc123sha"
        mock_client.script_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_script_sha_caches_result(self, mock_redis_client):
        """Test that script SHA is cached after first load."""
        mock_client = MagicMock()
        mock_client.script_load = AsyncMock(return_value="abc123sha")
        mock_redis_client._ensure_connected = MagicMock(return_value=mock_client)

        sha1 = await _get_script_sha(mock_redis_client)
        sha2 = await _get_script_sha(mock_redis_client)

        assert sha1 == sha2
        # Should only be called once (cached)
        assert mock_client.script_load.call_count == 1


class TestExecuteRateLimitScript:
    """Tests for _execute_rate_limit_script function."""

    def setup_method(self):
        """Clear Lua script cache before each test."""
        clear_lua_script_cache()

    @pytest.mark.asyncio
    async def test_execute_script_allowed(self, mock_redis_client):
        """Test executing Lua script when request is allowed."""
        mock_client = MagicMock()
        mock_client.script_load = AsyncMock(return_value="abc123sha")
        mock_client.evalsha = AsyncMock(return_value=[1, 5])  # allowed, count=5
        mock_redis_client._ensure_connected = MagicMock(return_value=mock_client)

        is_allowed, count = await _execute_rate_limit_script(
            mock_redis_client, "rate_limit:default:192.168.1.100", 1706012345.0, 60, 10
        )

        assert is_allowed is True
        assert count == 5

    @pytest.mark.asyncio
    async def test_execute_script_denied(self, mock_redis_client):
        """Test executing Lua script when request is denied."""
        mock_client = MagicMock()
        mock_client.script_load = AsyncMock(return_value="abc123sha")
        mock_client.evalsha = AsyncMock(return_value=[0, 10])  # denied, count=10
        mock_redis_client._ensure_connected = MagicMock(return_value=mock_client)

        is_allowed, count = await _execute_rate_limit_script(
            mock_redis_client, "rate_limit:default:192.168.1.100", 1706012345.0, 60, 10
        )

        assert is_allowed is False
        assert count == 10

    @pytest.mark.asyncio
    async def test_execute_script_noscript_retry(self, mock_redis_client):
        """Test that NOSCRIPT error triggers reload and retry."""
        mock_client = MagicMock()
        mock_client.script_load = AsyncMock(return_value="abc123sha")
        # First call raises NOSCRIPT, second succeeds
        mock_client.evalsha = AsyncMock(
            side_effect=[Exception("NOSCRIPT No matching script"), [1, 3]]
        )
        mock_redis_client._ensure_connected = MagicMock(return_value=mock_client)

        is_allowed, count = await _execute_rate_limit_script(
            mock_redis_client, "rate_limit:default:192.168.1.100", 1706012345.0, 60, 10
        )

        assert is_allowed is True
        assert count == 3
        # Script should be reloaded
        assert mock_client.script_load.call_count == 2


class TestRateLimiterCheckRateLimit:
    """Tests for RateLimiter._check_rate_limit method."""

    def setup_method(self):
        """Clear Lua script cache before each test."""
        clear_lua_script_cache()

    @pytest.mark.asyncio
    async def test_allow_request_under_limit(self, mock_redis_client):
        """Test allowing request when under rate limit."""
        with (
            patch(
                "backend.api.middleware.rate_limit._execute_rate_limit_script",
                new_callable=AsyncMock,
                return_value=(True, 5),  # allowed, count=5
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
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
        with (
            patch(
                "backend.api.middleware.rate_limit._execute_rate_limit_script",
                new_callable=AsyncMock,
                return_value=(False, 15),  # denied, count=15
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
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
        with (
            patch(
                "backend.api.middleware.rate_limit._execute_rate_limit_script",
                new_callable=AsyncMock,
                side_effect=Exception("Redis connection failed"),
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=10)
            is_allowed, current_count, _limit = await limiter._check_rate_limit(
                mock_redis_client, "192.168.1.100"
            )

        # Should allow request despite error
        assert is_allowed is True
        assert current_count == 0

    @pytest.mark.asyncio
    async def test_lua_script_called_with_correct_args(self, mock_redis_client):
        """Test that Lua script is called with correct arguments."""
        mock_execute = AsyncMock(return_value=(True, 5))

        with (
            patch(
                "backend.api.middleware.rate_limit._execute_rate_limit_script",
                mock_execute,
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=10, burst=2)
            await limiter._check_rate_limit(mock_redis_client, "192.168.1.100")

        # Verify the script was called with correct parameters
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        assert call_args[0][0] == mock_redis_client
        assert call_args[0][1] == "rate_limit:default:192.168.1.100"  # key
        # call_args[0][2] is the timestamp (float)
        assert call_args[0][3] == 60  # window_seconds
        assert call_args[0][4] == 12  # limit (10 + 2 burst)


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

    def setup_method(self):
        """Clear caches before each test."""
        clear_lua_script_cache()

    @pytest.mark.asyncio
    async def test_allow_websocket_under_limit(self, mock_redis_client):
        """Test allowing WebSocket connection under limit."""
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.client = MagicMock()
        mock_websocket.client.host = "192.168.1.100"
        mock_websocket.headers = Headers({})

        with (
            patch(
                "backend.api.middleware.rate_limit._execute_rate_limit_script",
                new_callable=AsyncMock,
                return_value=(True, 5),  # allowed, count=5
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
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

        with (
            patch(
                "backend.api.middleware.rate_limit._execute_rate_limit_script",
                new_callable=AsyncMock,
                return_value=(False, 35),  # denied, count=35 (over limit)
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
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

    def test_rate_limit_bulk(self):
        """Test rate_limit_bulk factory (NEM-2600)."""
        limiter = rate_limit_bulk()
        assert isinstance(limiter, RateLimiter)
        assert limiter.tier == RateLimitTier.BULK


class TestRedisStressTests:
    """Stress tests for Redis rate limiting under high load and failure scenarios.

    Tests cover:
    - High-volume concurrent requests
    - Redis connection failures
    - Redis timeout behavior
    - Concurrent requests from multiple IPs

    Fail-open vs Fail-closed behavior:
    - The rate limiter implements FAIL-OPEN semantics for availability
    - When Redis is unavailable or times out, requests are allowed through
    - This prevents Redis outages from cascading to application downtime
    - Risk: rate limits are not enforced during Redis failures
    - Mitigation: Monitor Redis health and alert on failures
    """

    def setup_method(self):
        """Clear caches before each test."""
        clear_lua_script_cache()

    @pytest.mark.asyncio
    async def test_high_volume_sequential_requests(self, mock_redis_client):
        """Test rate limiter handles high volume of sequential requests.

        Simulates 100 sequential requests to verify the sliding window
        algorithm maintains accurate counts under sustained load.
        """
        # Configure mock to return incrementing counts
        # The Lua script returns (allowed, count) where count is after the request
        # So we simulate: requests 0-59 allowed (count 1-60), requests 60-99 denied (count 60)
        request_counter = {"count": 0}

        async def mock_execute(*args, **kwargs):
            current = request_counter["count"]
            if current < 60:  # Under limit (50 + 10 burst)
                request_counter["count"] += 1
                return (True, current + 1)
            else:
                return (False, current)

        with (
            patch(
                "backend.api.middleware.rate_limit._execute_rate_limit_script",
                new_callable=AsyncMock,
                side_effect=mock_execute,
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=50, burst=10)

            # Make 100 sequential requests
            allowed_count = 0
            blocked_count = 0

            for i in range(100):
                is_allowed, _current_count, _limit = await limiter._check_rate_limit(
                    mock_redis_client, "192.168.1.100"
                )
                if is_allowed:
                    allowed_count += 1
                else:
                    blocked_count += 1

        # Verify correct limiting (50 + 10 burst = 60 allowed, 40 blocked)
        assert allowed_count == 60
        assert blocked_count == 40

    @pytest.mark.asyncio
    async def test_concurrent_requests_single_ip(self, mock_redis_client):
        """Test rate limiter handles concurrent requests from single IP.

        Simulates 50 concurrent requests to verify thread-safety and
        proper handling of race conditions in the sliding window.

        Note: With atomic Lua script, race conditions are eliminated.
        """
        import asyncio

        # Use a counter to track concurrent requests
        request_counter = {"count": 0}
        lock = asyncio.Lock()

        async def mock_execute(*args, **kwargs):
            async with lock:
                current = request_counter["count"]
                if current < 35:  # Under limit (30 + 5 burst)
                    request_counter["count"] += 1
                    return (True, current + 1)
                else:
                    return (False, current)

        with (
            patch(
                "backend.api.middleware.rate_limit._execute_rate_limit_script",
                new_callable=AsyncMock,
                side_effect=mock_execute,
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=30, burst=5)

            # Create 50 concurrent requests
            tasks = [
                limiter._check_rate_limit(mock_redis_client, "192.168.1.100") for _ in range(50)
            ]

            results = await asyncio.gather(*tasks)

        # Verify all requests completed
        assert len(results) == 50

        # Count allowed vs blocked
        allowed = sum(1 for is_allowed, _count, _limit in results if is_allowed)
        blocked = sum(1 for is_allowed, _count, _limit in results if not is_allowed)

        # With 30 rpm + 5 burst = 35 allowed, 15 blocked
        assert allowed == 35
        assert blocked == 15

    @pytest.mark.asyncio
    async def test_concurrent_requests_multiple_ips(self, mock_redis_client):
        """Test rate limiter handles concurrent requests from multiple IPs.

        Simulates 10 IPs making 10 concurrent requests each to verify
        per-IP rate limiting works correctly under concurrent load.
        """
        import asyncio

        with (
            patch(
                "backend.api.middleware.rate_limit._execute_rate_limit_script",
                new_callable=AsyncMock,
                return_value=(True, 5),  # Always return allowed, count=5 (under limit)
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=20, burst=5)

            # Create tasks for 10 IPs, 10 requests each
            tasks = []
            for i in range(10):
                ip = f"192.168.1.{100 + i}"
                for _ in range(10):
                    tasks.append(limiter._check_rate_limit(mock_redis_client, ip))

            results = await asyncio.gather(*tasks)

        # Verify all 100 requests completed
        assert len(results) == 100

        # All should be allowed since we mocked count as 5 (under 25 limit)
        allowed = sum(1 for is_allowed, _count, _limit in results if is_allowed)
        assert allowed == 100

    @pytest.mark.asyncio
    async def test_redis_connection_failure_fails_open(self, mock_redis_client):
        """Test rate limiter fails open when Redis connection fails.

        FAIL-OPEN BEHAVIOR: When Redis is unavailable, the rate limiter
        allows all requests to prevent cascading failures. This prioritizes
        availability over strict rate limiting.
        """
        with (
            patch(
                "backend.api.middleware.rate_limit._execute_rate_limit_script",
                new_callable=AsyncMock,
                side_effect=ConnectionError("Redis connection refused"),
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=10, burst=2)

            # Make multiple requests during Redis outage
            for _ in range(20):
                is_allowed, current_count, _limit = await limiter._check_rate_limit(
                    mock_redis_client, "192.168.1.100"
                )

                # All requests should be allowed (fail-open)
                assert is_allowed is True
                assert current_count == 0  # Count unavailable during outage

    @pytest.mark.asyncio
    async def test_redis_timeout_fails_open(self, mock_redis_client):
        """Test rate limiter fails open when Redis operations timeout.

        Simulates Redis timeout to verify fail-open behavior maintains
        application availability even when Redis is slow or unresponsive.
        """
        with (
            patch(
                "backend.api.middleware.rate_limit._execute_rate_limit_script",
                new_callable=AsyncMock,
                side_effect=TimeoutError("Redis operation timed out"),
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=10, burst=2)

            # Request should complete quickly despite Redis timeout
            is_allowed, current_count, _limit = await limiter._check_rate_limit(
                mock_redis_client, "192.168.1.100"
            )

            # Should fail open
            assert is_allowed is True
            assert current_count == 0

    @pytest.mark.asyncio
    async def test_redis_script_execution_failure(self, mock_redis_client):
        """Test rate limiter handles Lua script execution failures.

        Simulates Lua script execution failure to verify error handling
        and fail-open behavior when Redis operations fail.
        """
        with (
            patch(
                "backend.api.middleware.rate_limit._execute_rate_limit_script",
                new_callable=AsyncMock,
                side_effect=Exception("Script execution failed"),
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=10, burst=2)

            is_allowed, current_count, _limit = await limiter._check_rate_limit(
                mock_redis_client, "192.168.1.100"
            )

            # Should fail open on script errors
            assert is_allowed is True
            assert current_count == 0

    @pytest.mark.asyncio
    async def test_redis_returns_stale_data(self, mock_redis_client):
        """Test rate limiter handles stale data from Redis.

        Simulates Redis returning stale count data (e.g., from replica lag
        or cache inconsistency) to verify the limiter handles it gracefully.
        """
        # First request shows high count (blocked), subsequent shows low (allowed)
        call_count = {"count": 0}

        async def mock_execute(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return (False, 50)  # Stale high count - blocked
            else:
                return (True, 5)  # Correct low count - allowed

        with (
            patch(
                "backend.api.middleware.rate_limit._execute_rate_limit_script",
                new_callable=AsyncMock,
                side_effect=mock_execute,
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=10, burst=2)

            # First request with stale high count
            is_allowed1, count1, _limit1 = await limiter._check_rate_limit(
                mock_redis_client, "192.168.1.100"
            )
            assert is_allowed1 is False  # Blocked due to stale high count
            assert count1 == 50

            # Second request with corrected count
            is_allowed2, count2, _limit2 = await limiter._check_rate_limit(
                mock_redis_client, "192.168.1.100"
            )
            assert is_allowed2 is True  # Allowed with correct count
            assert count2 == 5

    @pytest.mark.asyncio
    async def test_redis_connection_recovery(self, mock_redis_client):
        """Test rate limiter recovers when Redis connection is restored.

        Simulates Redis outage followed by recovery to verify the rate
        limiter resumes normal operation once Redis becomes available.
        """
        call_count = {"count": 0}

        async def mock_execute(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] <= 2:
                # First 2 calls fail (Redis down)
                raise ConnectionError("Redis unavailable")
            else:
                # Subsequent calls succeed (Redis recovered)
                return (True, 5)

        with (
            patch(
                "backend.api.middleware.rate_limit._execute_rate_limit_script",
                new_callable=AsyncMock,
                side_effect=mock_execute,
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=10, burst=2)

            # First request - Redis down, fails open
            is_allowed1, count1, _limit1 = await limiter._check_rate_limit(
                mock_redis_client, "192.168.1.100"
            )
            assert is_allowed1 is True  # Fail open
            assert count1 == 0

            # Second request - Redis still down, fails open
            is_allowed2, count2, _limit2 = await limiter._check_rate_limit(
                mock_redis_client, "192.168.1.100"
            )
            assert is_allowed2 is True  # Fail open
            assert count2 == 0

            # Third request - Redis recovered, normal operation
            is_allowed3, count3, _limit3 = await limiter._check_rate_limit(
                mock_redis_client, "192.168.1.100"
            )
            assert is_allowed3 is True  # Allowed, under limit
            assert count3 == 5  # Actual count from Redis

    @pytest.mark.asyncio
    async def test_extreme_burst_traffic(self, mock_redis_client):
        """Test rate limiter handles extreme burst traffic patterns.

        Simulates sudden burst of 200 requests to verify the limiter
        correctly blocks excess requests while allowing burst allowance.
        """
        import asyncio

        # Create counter for tracking requests (with lock for thread safety)
        request_counter = {"count": 0}
        lock = asyncio.Lock()

        async def mock_execute(*args, **kwargs):
            async with lock:
                current = request_counter["count"]
                if current < 60:  # Under limit (50 + 10 burst)
                    request_counter["count"] += 1
                    return (True, current + 1)
                else:
                    return (False, current)

        with (
            patch(
                "backend.api.middleware.rate_limit._execute_rate_limit_script",
                new_callable=AsyncMock,
                side_effect=mock_execute,
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=50, burst=10)

            # Create 200 concurrent burst requests
            tasks = [
                limiter._check_rate_limit(mock_redis_client, "192.168.1.100") for _ in range(200)
            ]

            results = await asyncio.gather(*tasks)

        # Verify correct limiting (50 + 10 burst = 60 allowed, 140 blocked)
        allowed = sum(1 for is_allowed, _count, _limit in results if is_allowed)
        blocked = sum(1 for is_allowed, _count, _limit in results if not is_allowed)

        assert allowed == 60
        assert blocked == 140

    @pytest.mark.asyncio
    async def test_redis_network_partition(self, mock_redis_client):
        """Test rate limiter handles Redis network partition scenarios.

        Simulates intermittent Redis connectivity to verify the limiter
        handles network partition gracefully with fail-open behavior.
        """
        call_count = {"count": 0}

        async def mock_execute(*args, **kwargs):
            call_count["count"] += 1
            # Fail every other call (network partition)
            if call_count["count"] % 2 == 0:
                raise ConnectionError("Network partition")
            else:
                return (True, 5)

        with (
            patch(
                "backend.api.middleware.rate_limit._execute_rate_limit_script",
                new_callable=AsyncMock,
                side_effect=mock_execute,
            ),
            patch("backend.api.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.rate_limit_enabled = True

            limiter = RateLimiter(requests_per_minute=10, burst=2)

            results = []
            for _ in range(10):
                is_allowed, current_count, _limit = await limiter._check_rate_limit(
                    mock_redis_client, "192.168.1.100"
                )
                results.append((is_allowed, current_count))

        # All requests should be allowed (fail-open during failures)
        # or correctly limited during successful connections
        allowed = sum(1 for is_allowed, _count in results if is_allowed)
        assert allowed == 10  # All allowed due to fail-open on errors
