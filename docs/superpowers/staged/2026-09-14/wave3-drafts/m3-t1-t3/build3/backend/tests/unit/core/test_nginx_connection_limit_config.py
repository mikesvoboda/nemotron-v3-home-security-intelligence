"""Tests to validate nginx connection limiting configuration.

This module tests critical security configuration for nginx connection limiting
to prevent slowloris attacks, connection exhaustion, and DoS attacks.

The nginx configuration uses limit_conn_zone and limit_conn directives to
enforce connection limits on different scopes:
- Per IP address: Limits connections from a single client
- Per server: Limits total connections to the server

Connection limits complement rate limits (limit_req) by preventing slow
connection attacks where attackers open many connections slowly without
triggering rate limits.

References:
- nginx limit_conn_module: https://nginx.org/en/docs/http/ngx_http_limit_conn_module.html
- OWASP Slowloris: https://owasp.org/www-community/attacks/Slowloris_(HTTP)
- OWASP DoS Prevention: https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html
"""

import re
from pathlib import Path

import pytest


class TestNginxConnectionLimitZones:
    """Tests for nginx connection limit zone definitions.

    Connection limit zones define the shared memory zones used to track
    active connections per client IP or per server. These must be defined
    in the http context of the nginx configuration.
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

    def test_per_ip_connection_limit_zone_defined(self, nginx_conf_content: str) -> None:
        """Test that per-IP connection limit zone is defined with correct parameters.

        The per-IP zone should:
        - Use $binary_remote_addr as the key (client IP in binary format, 4-16 bytes)
        - Have adequate shared memory (10m = ~160,000 IP addresses)

        This protects against slowloris attacks where a single IP opens many
        connections slowly to exhaust server resources.
        """
        # Pattern to match: limit_conn_zone $binary_remote_addr zone=perip:10m;
        pattern = r"limit_conn_zone\s+\$binary_remote_addr\s+zone=perip:\d+m"
        match = re.search(pattern, nginx_conf_content)

        assert match is not None, (
            "Per-IP connection limit zone not defined. "
            "Expected: limit_conn_zone $binary_remote_addr zone=perip:10m; "
            "Add this directive to the nginx http context."
        )

    def test_per_ip_zone_memory_size(self, nginx_conf_content: str) -> None:
        """Test that per-IP zone has adequate memory (at least 10m)."""
        pattern = r"limit_conn_zone\s+\$binary_remote_addr\s+zone=perip:(\d+)m"
        match = re.search(pattern, nginx_conf_content)

        assert match is not None, "Per-IP connection limit zone not found"
        memory_mb = int(match.group(1))
        assert memory_mb >= 10, (
            f"Per-IP zone memory is {memory_mb}m, expected at least 10m. "
            "Each entry is 32-64 bytes, so 10m stores ~160,000 IPs."
        )

    def test_per_server_connection_limit_zone_defined(self, nginx_conf_content: str) -> None:
        """Test that per-server connection limit zone is defined.

        The per-server zone should:
        - Use $server_name as the key (virtual host name)
        - Have adequate shared memory

        This provides an overall connection limit to protect against
        distributed attacks from many IPs.
        """
        # Pattern to match: limit_conn_zone $server_name zone=perserver:10m;
        pattern = r"limit_conn_zone\s+\$server_name\s+zone=perserver:\d+m"
        match = re.search(pattern, nginx_conf_content)

        assert match is not None, (
            "Per-server connection limit zone not defined. "
            "Expected: limit_conn_zone $server_name zone=perserver:10m; "
            "Add this directive to the nginx http context."
        )

    def test_per_server_zone_memory_size(self, nginx_conf_content: str) -> None:
        """Test that per-server zone has adequate memory (at least 10m)."""
        pattern = r"limit_conn_zone\s+\$server_name\s+zone=perserver:(\d+)m"
        match = re.search(pattern, nginx_conf_content)

        assert match is not None, "Per-server connection limit zone not found"
        memory_mb = int(match.group(1))
        assert memory_mb >= 10, (
            f"Per-server zone memory is {memory_mb}m, expected at least 10m. "
            "This provides tracking for server-wide connection limits."
        )


class TestNginxConnectionLimitApplication:
    """Tests for nginx connection limit application to server blocks.

    Connection limits must be applied using the limit_conn directive with
    appropriate values for per-IP and per-server limits.
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
        """Combine nginx.conf and docker-entrypoint.sh for comprehensive testing."""
        return nginx_conf_content + "\n" + docker_entrypoint_content

    def test_per_ip_connection_limit_applied(self, combined_nginx_content: str) -> None:
        """Test that per-IP connection limit is applied.

        The limit_conn perip directive limits the number of connections
        from a single IP address. A reasonable limit is 100 connections
        per IP to allow legitimate browser behavior while preventing abuse.
        """
        # Pattern to match: limit_conn perip <number>;
        pattern = r"limit_conn\s+perip\s+\d+"
        match = re.search(pattern, combined_nginx_content)

        assert match is not None, (
            "Per-IP connection limit not applied. Add 'limit_conn perip 100;' to the server block."
        )

    def test_per_ip_connection_limit_value(self, combined_nginx_content: str) -> None:
        """Test that per-IP connection limit is set to a reasonable value.

        100 connections per IP allows:
        - Multiple browser tabs (6 connections each)
        - WebSocket connections
        - Concurrent API requests
        While preventing a single IP from monopolizing server resources.
        """
        pattern = r"limit_conn\s+perip\s+(\d+)"
        match = re.search(pattern, combined_nginx_content)

        assert match is not None, "Per-IP connection limit not found"
        limit = int(match.group(1))
        assert 50 <= limit <= 200, (
            f"Per-IP connection limit is {limit}, expected between 50-200. "
            "This allows legitimate multi-tab browsing while preventing abuse."
        )

    def test_per_server_connection_limit_applied(self, combined_nginx_content: str) -> None:
        """Test that per-server connection limit is applied.

        The limit_conn perserver directive limits the total number of
        connections to the server, protecting against distributed attacks.
        """
        pattern = r"limit_conn\s+perserver\s+\d+"
        match = re.search(pattern, combined_nginx_content)

        assert match is not None, (
            "Per-server connection limit not applied. "
            "Add 'limit_conn perserver 1000;' to the server block."
        )

    def test_per_server_connection_limit_value(self, combined_nginx_content: str) -> None:
        """Test that per-server connection limit is set to a reasonable value.

        1000 total connections is appropriate for a home security dashboard:
        - Single-user deployment (no concurrent users expected)
        - Provides headroom for WebSocket, API, and static assets
        - Protects against connection exhaustion attacks
        """
        pattern = r"limit_conn\s+perserver\s+(\d+)"
        match = re.search(pattern, combined_nginx_content)

        assert match is not None, "Per-server connection limit not found"
        limit = int(match.group(1))
        assert 500 <= limit <= 2000, (
            f"Per-server connection limit is {limit}, expected between 500-2000. "
            "This provides capacity for legitimate use while preventing exhaustion."
        )


class TestNginxConnectionLimitStatus:
    """Tests for nginx connection limit error response configuration.

    When connection limits are exceeded, nginx should return HTTP 503
    (Service Unavailable) by default, but can be configured to return
    a different status code.
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

    def test_connection_limit_log_level_configured(self, nginx_conf_content: str) -> None:
        """Test that connection limit violations are logged at appropriate level.

        limit_conn_log_level can be set to control logging of connection
        limit violations. 'warn' is appropriate for monitoring without
        flooding logs during attacks.
        """
        # Check if log level is configured (optional but recommended)
        pattern = r"limit_conn_log_level\s+(info|notice|warn|error)"
        match = re.search(pattern, nginx_conf_content)

        # This is optional, so we just note it if not present
        if match is None:
            # Default is 'error' which is acceptable
            pass
        else:
            level = match.group(1)
            assert level in ("warn", "error"), (
                f"Connection limit log level is '{level}', expected 'warn' or 'error'. "
                "Lower levels may flood logs during attacks."
            )


class TestNginxSlowlorisProtection:
    """Tests for nginx configuration that protects against slowloris attacks.

    Slowloris attacks work by:
    1. Opening many connections
    2. Sending partial HTTP requests slowly
    3. Never completing requests, exhausting server connections

    Protection mechanisms:
    - Connection limits (limit_conn)
    - Timeout configuration (client_body_timeout, client_header_timeout)
    - Rate limiting (limit_req)
    """

    @pytest.fixture
    def nginx_conf_path(self) -> Path:
        """Get the path to the nginx.conf file."""
        return Path(__file__).parent.parent.parent.parent.parent / "frontend" / "nginx.conf"

    @pytest.fixture
    def docker_entrypoint_path(self) -> Path:
        """Get the path to the docker-entrypoint.sh file."""
        return (
            Path(__file__).parent.parent.parent.parent.parent / "frontend" / "docker-entrypoint.sh"
        )

    @pytest.fixture
    def combined_content(self, nginx_conf_path: Path, docker_entrypoint_path: Path) -> str:
        """Read both nginx configuration files."""
        content = ""
        if nginx_conf_path.exists():
            content += nginx_conf_path.read_text()
        if docker_entrypoint_path.exists():
            content += docker_entrypoint_path.read_text()
        if not content:
            pytest.skip("No nginx configuration files found")
        return content

    def test_connection_limits_protect_against_slowloris(self, combined_content: str) -> None:
        """Test that connection limits are configured for slowloris protection.

        Connection limits are the primary defense against slowloris attacks.
        By limiting connections per IP, a single attacker cannot exhaust
        all server connections.
        """
        # Check for both perip and perserver zones and limits
        has_perip_zone = re.search(
            r"limit_conn_zone\s+\$binary_remote_addr\s+zone=perip", combined_content
        )
        has_perip_limit = re.search(r"limit_conn\s+perip\s+\d+", combined_content)
        has_perserver_zone = re.search(
            r"limit_conn_zone\s+\$server_name\s+zone=perserver", combined_content
        )
        has_perserver_limit = re.search(r"limit_conn\s+perserver\s+\d+", combined_content)

        assert has_perip_zone and has_perip_limit, (
            "Per-IP connection limit not fully configured. "
            "Both zone definition and limit_conn directive are required for slowloris protection."
        )

        assert has_perserver_zone and has_perserver_limit, (
            "Per-server connection limit not fully configured. "
            "Both zone definition and limit_conn directive are required for distributed attack protection."
        )


class TestNginxConnectionLimitDocumentation:
    """Tests for nginx connection limit documentation.

    Connection limiting configuration should be documented to explain:
    - Why connection limits are used (slowloris protection)
    - What the limits mean
    - How they complement rate limiting
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

    def test_connection_limit_documentation_exists(self, nginx_conf_content: str) -> None:
        """Test that connection limiting is documented in nginx configuration."""
        # Check for documentation about connection limiting
        connection_limit_terms = [
            "connection limit",
            "limit_conn",
            "slowloris",
            "connection exhaustion",
        ]
        content_lower = nginx_conf_content.lower()

        has_documentation = any(term in content_lower for term in connection_limit_terms)
        assert has_documentation, (
            "Connection limiting should be documented in nginx configuration. "
            "Add comments explaining the connection limiting strategy."
        )
