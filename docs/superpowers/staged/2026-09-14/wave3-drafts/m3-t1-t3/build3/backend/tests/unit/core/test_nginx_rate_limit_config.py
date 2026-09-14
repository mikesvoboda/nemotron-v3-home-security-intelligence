"""Tests to validate nginx rate limiting configuration.

This module tests critical security configuration for nginx rate limiting
to prevent API abuse, DoS attacks, and resource exhaustion.

The nginx configuration uses limit_req_zone and limit_req directives to
enforce rate limits on different types of traffic:
- API endpoints: 10r/s with burst handling
- WebSocket connections: 5r/s with burst handling
- General requests: 30r/s with burst handling

Rate limits are based on client IP address ($binary_remote_addr) which
requires nginx to receive actual client IP via X-Forwarded-For header
from any upstream proxy.

References:
- nginx limit_req_module: https://nginx.org/en/docs/http/ngx_http_limit_req_module.html
- OWASP Rate Limiting: https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html
"""

import re
from pathlib import Path

import pytest


class TestNginxRateLimitZones:
    """Tests for nginx rate limit zone definitions.

    Rate limit zones define the shared memory zones used to track
    request rates per client IP. These must be defined in the http
    context of the nginx configuration.
    """

    @pytest.fixture
    def docker_entrypoint_path(self) -> Path:
        """Get the path to the docker-entrypoint.sh file."""
        # Navigate from tests/unit/core/ to frontend/docker-entrypoint.sh
        return (
            Path(__file__).parent.parent.parent.parent.parent / "frontend" / "docker-entrypoint.sh"
        )

    @pytest.fixture
    def nginx_conf_path(self) -> Path:
        """Get the path to the nginx.conf file."""
        return Path(__file__).parent.parent.parent.parent.parent / "frontend" / "nginx.conf"

    @pytest.fixture
    def docker_entrypoint_content(self, docker_entrypoint_path: Path) -> str:
        """Read the docker-entrypoint.sh content."""
        if not docker_entrypoint_path.exists():
            pytest.skip(f"docker-entrypoint.sh not found at {docker_entrypoint_path}")
        return docker_entrypoint_path.read_text()

    @pytest.fixture
    def nginx_conf_content(self, nginx_conf_path: Path) -> str:
        """Read the nginx.conf content."""
        if not nginx_conf_path.exists():
            pytest.skip(f"nginx.conf not found at {nginx_conf_path}")
        return nginx_conf_path.read_text()

    @pytest.fixture
    def combined_nginx_content(
        self, nginx_conf_content: str, docker_entrypoint_content: str
    ) -> str:
        """Combine nginx.conf and docker-entrypoint.sh for comprehensive testing.

        The nginx configuration is split between nginx.conf (base config)
        and docker-entrypoint.sh (runtime injections). We need to test both.
        """
        return nginx_conf_content + "\n" + docker_entrypoint_content

    def test_api_rate_limit_zone_defined(self, combined_nginx_content: str) -> None:
        """Test that API rate limit zone is defined with correct parameters.

        The API zone should:
        - Use $binary_remote_addr as the key (client IP)
        - Have adequate shared memory (10m = ~160,000 IP addresses)
        - Set rate to 10 requests per second

        This protects API endpoints from abuse while allowing legitimate
        burst traffic with the limit_req burst parameter.
        """
        # Pattern to match: limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
        pattern = r"limit_req_zone\s+\$binary_remote_addr\s+zone=api:\d+m\s+rate=\d+r/s"
        match = re.search(pattern, combined_nginx_content)

        assert match is not None, (
            "API rate limit zone not defined. "
            "Expected: limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s; "
            "Add this directive to the nginx configuration."
        )

    def test_api_rate_limit_zone_rate(self, combined_nginx_content: str) -> None:
        """Test that API rate limit is set to 10 requests per second."""
        pattern = r"limit_req_zone\s+\$binary_remote_addr\s+zone=api:\d+m\s+rate=(\d+)r/s"
        match = re.search(pattern, combined_nginx_content)

        assert match is not None, "API rate limit zone not found"
        rate = int(match.group(1))
        assert rate == 10, (
            f"API rate limit is {rate}r/s, expected 10r/s. "
            "This rate allows 10 requests per second per IP address."
        )

    def test_websocket_rate_limit_zone_defined(self, combined_nginx_content: str) -> None:
        """Test that WebSocket rate limit zone is defined.

        WebSocket connections are rate-limited more strictly because:
        - Each connection is long-lived and consumes server resources
        - Connection storms can exhaust file descriptors
        - 5r/s is sufficient for legitimate reconnection scenarios
        """
        pattern = r"limit_req_zone\s+\$binary_remote_addr\s+zone=ws:\d+m\s+rate=\d+r/s"
        match = re.search(pattern, combined_nginx_content)

        assert match is not None, (
            "WebSocket rate limit zone not defined. "
            "Expected: limit_req_zone $binary_remote_addr zone=ws:10m rate=5r/s; "
            "Add this directive to the nginx configuration."
        )

    def test_websocket_rate_limit_zone_rate(self, combined_nginx_content: str) -> None:
        """Test that WebSocket rate limit is set to 5 requests per second."""
        pattern = r"limit_req_zone\s+\$binary_remote_addr\s+zone=ws:\d+m\s+rate=(\d+)r/s"
        match = re.search(pattern, combined_nginx_content)

        assert match is not None, "WebSocket rate limit zone not found"
        rate = int(match.group(1))
        assert rate == 5, (
            f"WebSocket rate limit is {rate}r/s, expected 5r/s. "
            "This rate prevents connection storm attacks while allowing reconnections."
        )

    def test_general_rate_limit_zone_defined(self, combined_nginx_content: str) -> None:
        """Test that general rate limit zone is defined.

        The general zone applies to static assets and other non-API requests.
        Higher rate limit (30r/s) because:
        - Static assets are cached and cheap to serve
        - Browser prefetch may request multiple assets
        - Lower priority than API protection
        """
        pattern = r"limit_req_zone\s+\$binary_remote_addr\s+zone=general:\d+m\s+rate=\d+r/s"
        match = re.search(pattern, combined_nginx_content)

        assert match is not None, (
            "General rate limit zone not defined. "
            "Expected: limit_req_zone $binary_remote_addr zone=general:10m rate=30r/s; "
            "Add this directive to the nginx configuration."
        )

    def test_general_rate_limit_zone_rate(self, combined_nginx_content: str) -> None:
        """Test that general rate limit is set to 30 requests per second."""
        pattern = r"limit_req_zone\s+\$binary_remote_addr\s+zone=general:\d+m\s+rate=(\d+)r/s"
        match = re.search(pattern, combined_nginx_content)

        assert match is not None, "General rate limit zone not found"
        rate = int(match.group(1))
        assert rate == 30, (
            f"General rate limit is {rate}r/s, expected 30r/s. "
            "This rate allows reasonable static asset loading while preventing abuse."
        )


class TestNginxRateLimitApplication:
    """Tests for nginx rate limit application to location blocks.

    Rate limits must be applied to specific location blocks using
    the limit_req directive with appropriate burst and nodelay options.
    """

    @pytest.fixture
    def docker_entrypoint_path(self) -> Path:
        """Get the path to the docker-entrypoint.sh file."""
        return (
            Path(__file__).parent.parent.parent.parent.parent / "frontend" / "docker-entrypoint.sh"
        )

    @pytest.fixture
    def docker_entrypoint_content(self, docker_entrypoint_path: Path) -> str:
        """Read the docker-entrypoint.sh content."""
        if not docker_entrypoint_path.exists():
            pytest.skip(f"docker-entrypoint.sh not found at {docker_entrypoint_path}")
        return docker_entrypoint_path.read_text()

    def test_api_location_has_rate_limit(self, docker_entrypoint_content: str) -> None:
        """Test that /api location block has rate limiting applied.

        The API location should use the 'api' zone with burst handling
        to allow short traffic spikes while enforcing overall rate limits.
        """
        # Look for location /api block with limit_req
        # The location might be /api or ^~ /api
        api_location_pattern = r"location\s+[\^~\s]*/api\s*\{[^}]*limit_req\s+zone=api"
        match = re.search(api_location_pattern, docker_entrypoint_content, re.DOTALL)

        assert match is not None, (
            "API location block missing rate limiting. "
            "Add 'limit_req zone=api burst=20 nodelay;' to location /api { ... }"
        )

    def test_api_location_burst_configured(self, docker_entrypoint_content: str) -> None:
        """Test that API location has burst parameter configured.

        Burst allows a short spike of requests before rate limiting kicks in.
        A burst of 20 allows handling of legitimate request batches.
        """
        api_location_pattern = (
            r"location\s+[\^~\s]*/api\s*\{[^}]*limit_req\s+zone=api\s+burst=(\d+)"
        )
        match = re.search(api_location_pattern, docker_entrypoint_content, re.DOTALL)

        assert match is not None, "API rate limit burst not configured"
        burst = int(match.group(1))
        assert burst >= 10, (
            f"API burst is {burst}, expected at least 10. "
            "This allows legitimate request batches before rate limiting."
        )

    def test_api_location_nodelay_configured(self, docker_entrypoint_content: str) -> None:
        """Test that API location uses nodelay option.

        The nodelay option serves burst requests immediately rather than
        queuing them, which provides better user experience for legitimate
        traffic while still enforcing rate limits.
        """
        api_location_pattern = (
            r"location\s+[\^~\s]*/api\s*\{[^}]*limit_req\s+zone=api\s+burst=\d+\s+nodelay"
        )
        match = re.search(api_location_pattern, docker_entrypoint_content, re.DOTALL)

        assert match is not None, (
            "API rate limit missing 'nodelay' option. "
            "Add 'nodelay' to 'limit_req zone=api burst=20 nodelay;'"
        )

    def test_websocket_location_has_rate_limit(self, docker_entrypoint_content: str) -> None:
        """Test that /ws location block has rate limiting applied."""
        ws_location_pattern = r"location\s+[\^~\s]*/ws\s*\{[^}]*limit_req\s+zone=ws"
        match = re.search(ws_location_pattern, docker_entrypoint_content, re.DOTALL)

        assert match is not None, (
            "WebSocket location block missing rate limiting. "
            "Add 'limit_req zone=ws burst=10 nodelay;' to location /ws { ... }"
        )

    def test_websocket_location_burst_configured(self, docker_entrypoint_content: str) -> None:
        """Test that WebSocket location has burst parameter configured."""
        ws_location_pattern = r"location\s+[\^~\s]*/ws\s*\{[^}]*limit_req\s+zone=ws\s+burst=(\d+)"
        match = re.search(ws_location_pattern, docker_entrypoint_content, re.DOTALL)

        assert match is not None, "WebSocket rate limit burst not configured"
        burst = int(match.group(1))
        assert burst >= 5, (
            f"WebSocket burst is {burst}, expected at least 5. "
            "This allows legitimate reconnection attempts."
        )

    def test_general_location_has_rate_limit(self, docker_entrypoint_content: str) -> None:
        """Test that general location block (/) has rate limiting applied."""
        general_location_pattern = r"location\s+/\s*\{[^}]*limit_req\s+zone=general"
        match = re.search(general_location_pattern, docker_entrypoint_content, re.DOTALL)

        assert match is not None, (
            "General location block missing rate limiting. "
            "Add 'limit_req zone=general burst=50 nodelay;' to location / { ... }"
        )


class TestNginxRateLimitStatus:
    """Tests for nginx rate limit status code configuration.

    When rate limits are exceeded, nginx should return HTTP 429
    (Too Many Requests) instead of the default 503 (Service Unavailable).
    """

    @pytest.fixture
    def docker_entrypoint_path(self) -> Path:
        """Get the path to the docker-entrypoint.sh file."""
        return (
            Path(__file__).parent.parent.parent.parent.parent / "frontend" / "docker-entrypoint.sh"
        )

    @pytest.fixture
    def docker_entrypoint_content(self, docker_entrypoint_path: Path) -> str:
        """Read the docker-entrypoint.sh content."""
        if not docker_entrypoint_path.exists():
            pytest.skip(f"docker-entrypoint.sh not found at {docker_entrypoint_path}")
        return docker_entrypoint_path.read_text()

    def test_api_rate_limit_returns_429(self, docker_entrypoint_content: str) -> None:
        """Test that API rate limiting returns 429 status code.

        HTTP 429 (Too Many Requests) is the correct status code for rate
        limiting per RFC 6585. The default nginx status (503) indicates
        service unavailability which is misleading for rate limiting.
        """
        api_location_pattern = r"location\s+[\^~\s]*/api\s*\{[^}]*limit_req_status\s+429"
        match = re.search(api_location_pattern, docker_entrypoint_content, re.DOTALL)

        assert match is not None, (
            "API location missing 'limit_req_status 429;' directive. "
            "Add this to return proper HTTP status when rate limit is exceeded."
        )

    def test_websocket_rate_limit_returns_429(self, docker_entrypoint_content: str) -> None:
        """Test that WebSocket rate limiting returns 429 status code."""
        ws_location_pattern = r"location\s+[\^~\s]*/ws\s*\{[^}]*limit_req_status\s+429"
        match = re.search(ws_location_pattern, docker_entrypoint_content, re.DOTALL)

        assert match is not None, (
            "WebSocket location missing 'limit_req_status 429;' directive. "
            "Add this to return proper HTTP status when rate limit is exceeded."
        )


class TestNginxRateLimitExclusions:
    """Tests for nginx rate limit exclusions.

    Certain endpoints should be excluded from rate limiting, such as
    health check endpoints used for container orchestration.
    """

    @pytest.fixture
    def nginx_conf_path(self) -> Path:
        """Get the path to the nginx.conf file."""
        return Path(__file__).parent.parent.parent.parent.parent / "frontend" / "nginx.conf"

    @pytest.fixture
    def nginx_conf_content(self, nginx_conf_path: Path) -> str:
        """Read the nginx.conf content."""
        if not nginx_conf_path.exists():
            pytest.skip(f"nginx.conf not found at {nginx_conf_path}")
        return nginx_conf_path.read_text()

    def test_health_endpoint_not_rate_limited(self, nginx_conf_content: str) -> None:
        """Test that /health endpoint is not rate limited.

        Health check endpoints must always be accessible for container
        orchestration (Kubernetes, Docker health checks). Rate limiting
        these could cause false-positive container restarts.

        The health endpoint uses 'location = /health' (exact match) which
        has higher priority and is defined before rate limited locations.
        """
        # Health endpoint should be exact match without rate limiting
        health_pattern = r"location\s+=\s+/health\s*\{[^}]*\}"
        match = re.search(health_pattern, nginx_conf_content, re.DOTALL)

        assert match is not None, (
            "Health endpoint location not found or not using exact match. "
            "Expected: location = /health { ... }"
        )

        health_block = match.group(0)
        assert "limit_req" not in health_block, (
            "Health endpoint should NOT have rate limiting applied. "
            "Container health checks must always succeed."
        )


class TestNginxRateLimitDocumentation:
    """Tests for nginx rate limit documentation.

    Rate limiting configuration should be documented to explain:
    - Why specific rates were chosen
    - How burst handling works
    - What happens when limits are exceeded
    """

    @pytest.fixture
    def docker_entrypoint_path(self) -> Path:
        """Get the path to the docker-entrypoint.sh file."""
        return (
            Path(__file__).parent.parent.parent.parent.parent / "frontend" / "docker-entrypoint.sh"
        )

    @pytest.fixture
    def nginx_conf_path(self) -> Path:
        """Get the path to the nginx.conf file."""
        return Path(__file__).parent.parent.parent.parent.parent / "frontend" / "nginx.conf"

    @pytest.fixture
    def combined_content(self, docker_entrypoint_path: Path, nginx_conf_path: Path) -> str:
        """Read both nginx configuration files."""
        content = ""
        if docker_entrypoint_path.exists():
            content += docker_entrypoint_path.read_text()
        if nginx_conf_path.exists():
            content += nginx_conf_path.read_text()
        if not content:
            pytest.skip("No nginx configuration files found")
        return content

    def test_rate_limit_documentation_exists(self, combined_content: str) -> None:
        """Test that rate limiting is documented in nginx configuration."""
        # Check for documentation about rate limiting
        rate_limit_terms = ["rate limit", "rate-limit", "ratelimit"]
        content_lower = combined_content.lower()

        has_documentation = any(term in content_lower for term in rate_limit_terms)
        assert has_documentation, (
            "Rate limiting should be documented in nginx configuration. "
            "Add comments explaining the rate limiting strategy."
        )
