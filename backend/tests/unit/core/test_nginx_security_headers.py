"""Tests for nginx security header configuration.

This module validates that security headers are properly configured in the nginx
configuration, including inheritance rules for location blocks.

IMPORTANT: In nginx, when a location block contains ANY add_header directive,
it does NOT inherit add_header directives from the parent server/http context.
This is a common source of security vulnerabilities where static asset locations
may lack security headers.

See: https://nginx.org/en/docs/http/ngx_http_headers_module.html
"There could be several add_header directives. These directives are inherited
from the previous configuration level if and only if there are no add_header
directives defined on the current level."

This test suite ensures:
1. Security headers are defined at the server level
2. Static asset locations include security headers (not just Cache-Control)
3. All response codes get headers (using 'always' parameter)
"""

import re
from pathlib import Path

import pytest

# Security headers that MUST be present on ALL responses (including static assets)
REQUIRED_SECURITY_HEADERS = [
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "SAMEORIGIN"),
    ("X-XSS-Protection", "1; mode=block"),
    ("Referrer-Policy", "strict-origin-when-cross-origin"),
    ("Cross-Origin-Opener-Policy", "same-origin"),
    ("Cross-Origin-Resource-Policy", "same-origin"),
]

# Static asset file extensions that should have security headers
STATIC_ASSET_EXTENSIONS = [
    "js",
    "css",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "ico",
    "svg",
    "woff",
    "woff2",
    "ttf",
    "eot",
]


class TestNginxSecurityHeadersConfig:
    """Tests for nginx.conf security header configuration."""

    @pytest.fixture
    def nginx_conf_path(self) -> Path:
        """Get the path to nginx.conf."""
        return Path(__file__).parent.parent.parent.parent.parent / "frontend" / "nginx.conf"

    @pytest.fixture
    def nginx_conf_content(self, nginx_conf_path: Path) -> str:
        """Read the nginx.conf content."""
        if not nginx_conf_path.exists():
            pytest.skip(f"nginx.conf not found at {nginx_conf_path}")
        return nginx_conf_path.read_text()

    def test_nginx_conf_exists(self, nginx_conf_path: Path) -> None:
        """Test that nginx.conf exists."""
        assert nginx_conf_path.exists(), f"nginx.conf not found at {nginx_conf_path}"

    def test_server_level_security_headers_present(self, nginx_conf_content: str) -> None:
        """Test that required security headers are defined at the server level."""
        for header_name, _ in REQUIRED_SECURITY_HEADERS:
            assert header_name in nginx_conf_content, (
                f"nginx.conf missing security header: {header_name}. "
                "Add 'add_header {header_name} \"value\" always;' to the server block."
            )

    def test_security_headers_use_always_parameter(self, nginx_conf_content: str) -> None:
        """Test that security headers use 'always' parameter.

        The 'always' parameter ensures headers are sent for ALL response codes,
        including error responses (4xx, 5xx). Without it, headers are only sent
        for 2xx and 3xx responses.
        """
        for header_name, _ in REQUIRED_SECURITY_HEADERS:
            # Find add_header directives for this header
            pattern = rf"add_header\s+{re.escape(header_name)}\s+"
            matches = re.finditer(pattern, nginx_conf_content)

            for match in matches:
                # Get the full line
                start = nginx_conf_content.rfind("\n", 0, match.start()) + 1
                end = nginx_conf_content.find("\n", match.end())
                line = nginx_conf_content[start:end]

                # Skip comment lines
                if line.strip().startswith("#"):
                    continue

                assert "always" in line, (
                    f"Security header {header_name} missing 'always' parameter. "
                    f"Line: {line.strip()}\n"
                    "Add 'always' at the end: add_header X-Header \"value\" always;"
                )


class TestDockerEntrypointSecurityHeaders:
    """Tests for docker-entrypoint.sh nginx configuration generation.

    The docker-entrypoint.sh script generates nginx location blocks at runtime.
    These tests ensure that static asset locations include security headers.
    """

    @pytest.fixture
    def entrypoint_path(self) -> Path:
        """Get the path to docker-entrypoint.sh."""
        return (
            Path(__file__).parent.parent.parent.parent.parent / "frontend" / "docker-entrypoint.sh"
        )

    @pytest.fixture
    def entrypoint_content(self, entrypoint_path: Path) -> str:
        """Read the docker-entrypoint.sh content."""
        if not entrypoint_path.exists():
            pytest.skip(f"docker-entrypoint.sh not found at {entrypoint_path}")
        return entrypoint_path.read_text()

    def test_entrypoint_exists(self, entrypoint_path: Path) -> None:
        """Test that docker-entrypoint.sh exists."""
        assert entrypoint_path.exists(), f"docker-entrypoint.sh not found at {entrypoint_path}"

    def test_http_static_assets_location_has_security_headers(
        self, entrypoint_content: str
    ) -> None:
        """Test that HTTP_LOCATIONS static asset block includes security headers.

        Due to nginx inheritance rules, when a location block has ANY add_header
        directive, it does NOT inherit headers from parent blocks. Therefore,
        static asset locations with Cache-Control must also explicitly include
        security headers.
        """
        # Find the static assets location block directly in the file
        # The block is: location ~* \.(js|css|...)$ { ... }
        # We need to find this pattern and extract its contents

        # Match the static assets location block
        # The pattern matches:
        # - "location ~* \." (the regex location directive)
        # - File extensions in parentheses
        # - "$ {" (end of regex and opening brace)
        # - Content up to the closing brace (non-greedy)
        static_pattern = r"location\s+~\*\s+\\\.\([^)]+\)\$\s*\{([^}]+)\}"
        static_matches = re.findall(static_pattern, entrypoint_content)

        assert len(static_matches) >= 1, (
            "Could not find static assets location block in docker-entrypoint.sh. "
            "Expected pattern: location ~* \\.(js|css|...)$ { ... }"
        )

        # Check the first match (HTTP_LOCATIONS block)
        static_block = static_matches[0]

        # Verify security headers are present
        for header_name, expected_value in REQUIRED_SECURITY_HEADERS:
            assert header_name in static_block, (
                f"HTTP_LOCATIONS static assets location missing security header: {header_name}. "
                "Due to nginx inheritance rules, add_header directives in a location block "
                "do NOT inherit from parent server block. Add security headers explicitly.\n"
                f"Static block content:\n{static_block}"
            )

            # Also check that 'always' is used
            header_pattern = rf"add_header\s+{re.escape(header_name)}\s+.*always"
            assert re.search(header_pattern, static_block), (
                f"Security header {header_name} in static assets location should use 'always' parameter."
            )

    def test_https_redirect_has_no_static_assets_headers_issue(
        self, entrypoint_content: str
    ) -> None:
        """Test that HTTPS_REDIRECT block handles static assets correctly.

        In HTTPS redirect mode, static assets should be served over HTTPS,
        so HTTP redirect is acceptable. However, if there IS a static asset
        location, it must have security headers.
        """
        # Find the HTTPS_REDIRECT block
        https_redirect_match = re.search(r"HTTPS_REDIRECT='(.*?)'", entrypoint_content, re.DOTALL)

        if https_redirect_match is None:
            pytest.skip("No HTTPS_REDIRECT block found - may not be applicable")

        https_redirect = https_redirect_match.group(1)

        # Check if there's a static assets location in HTTPS_REDIRECT
        static_pattern = r"location\s+~\*\s+\\\.\(.*?\)\$"
        if re.search(static_pattern, https_redirect):
            # If static assets location exists, it should have security headers
            static_match = re.search(
                r"location\s+~\*\s+\\\.\(.*?\)\$\s*\{(.*?)\}", https_redirect, re.DOTALL
            )
            if static_match:
                static_block = static_match.group(1)
                for header_name, _ in REQUIRED_SECURITY_HEADERS:
                    assert header_name in static_block, (
                        f"HTTPS_REDIRECT static assets location missing security header: {header_name}."
                    )

    def test_ssl_server_block_static_assets_has_security_headers(
        self, entrypoint_content: str
    ) -> None:
        """Test that SSL_SERVER_BLOCK static asset location includes security headers.

        The SSL server block is generated when SSL_ENABLED=true. Static asset
        locations within this block must include security headers.
        """
        # Find the SSL_SERVER_BLOCK (double-quoted heredoc with escaped characters)
        ssl_block_match = re.search(
            r'SSL_SERVER_BLOCK="(.*?)"$', entrypoint_content, re.DOTALL | re.MULTILINE
        )

        if ssl_block_match is None:
            pytest.skip("No SSL_SERVER_BLOCK found - may not be applicable")

        ssl_block = ssl_block_match.group(1)

        # Find static assets location in SSL block (uses \$ for escaping the $)
        # Pattern: location ~* \.(js|css|...)\$ { ... }
        static_pattern = r"location\s+~\*\s+\\\.\([^)]+\)\\\$\s*\{([^}]+)\}"
        static_match = re.search(static_pattern, ssl_block)

        if static_match is None:
            pytest.skip("No static assets location in SSL_SERVER_BLOCK")

        static_block = static_match.group(1)

        # Verify security headers are present (escaped for shell heredoc)
        for header_name, expected_value in REQUIRED_SECURITY_HEADERS:
            assert header_name in static_block, (
                f"SSL_SERVER_BLOCK static assets location missing security header: {header_name}. "
                "Due to nginx inheritance rules, add_header directives must be repeated "
                "in location blocks that define their own headers.\n"
                f"Static block content:\n{static_block}"
            )


class TestNginxStaticAssetCaching:
    """Tests for static asset caching configuration."""

    @pytest.fixture
    def entrypoint_content(self) -> str:
        """Read the docker-entrypoint.sh content."""
        path = (
            Path(__file__).parent.parent.parent.parent.parent / "frontend" / "docker-entrypoint.sh"
        )
        if not path.exists():
            pytest.skip(f"docker-entrypoint.sh not found at {path}")
        return path.read_text()

    def test_static_assets_have_cache_control(self, entrypoint_content: str) -> None:
        """Test that static assets have Cache-Control header."""
        assert "Cache-Control" in entrypoint_content, (
            "Static assets should have Cache-Control header for browser caching."
        )

        # Verify immutable is used for hashed assets
        assert "immutable" in entrypoint_content, (
            "Static assets should use 'immutable' Cache-Control directive "
            "since Vite adds content hashes to filenames."
        )

    def test_static_assets_cache_control_uses_always(self, entrypoint_content: str) -> None:
        """Test that Cache-Control header uses 'always' parameter.

        Note: Shell heredocs use escaped quotes (\\" or plain ") depending on context.
        """
        # Find Cache-Control add_header lines - match both escaped and plain quotes
        # Also match the case where the value might have escaped or plain quotes
        cache_control_pattern = r'add_header\s+Cache-Control\s+[\\"]?[^;]+[\\"]?\s*;'
        matches = re.findall(cache_control_pattern, entrypoint_content)

        # All Cache-Control headers should use 'always'
        cache_control_always_pattern = (
            r'add_header\s+Cache-Control\s+[\\"]?[^;]+[\\"]?\s+always\s*;'
        )
        matches_with_always = re.findall(cache_control_always_pattern, entrypoint_content)

        assert len(matches_with_always) >= len(matches), (
            f"Not all Cache-Control headers use 'always' parameter. "
            f"Found {len(matches)} total, {len(matches_with_always)} with 'always'. "
            "Add 'always' to ensure headers are sent for all response codes."
        )


class TestSecurityHeaderValues:
    """Tests for security header values in nginx configuration.

    Note: The docker-entrypoint.sh uses shell heredocs and escape sequences.
    In SSL_SERVER_BLOCK, quotes are escaped as \\" (becomes " in the final nginx config).
    In HTTP_LOCATIONS (single-quoted heredoc), quotes are plain ".
    """

    @pytest.fixture
    def nginx_conf_content(self) -> str:
        """Read the nginx.conf content (for server-level headers)."""
        path = Path(__file__).parent.parent.parent.parent.parent / "frontend" / "nginx.conf"
        if not path.exists():
            pytest.skip(f"nginx.conf not found at {path}")
        return path.read_text()

    def test_x_content_type_options_value(self, nginx_conf_content: str) -> None:
        """Test that X-Content-Type-Options is set to 'nosniff'."""
        # Allow both plain and escaped quotes
        pattern = r'add_header\s+X-Content-Type-Options\s+[\\"]?nosniff[\\"]?'
        assert re.search(pattern, nginx_conf_content), (
            "X-Content-Type-Options should be set to 'nosniff' to prevent MIME sniffing attacks."
        )

    def test_x_frame_options_value(self, nginx_conf_content: str) -> None:
        """Test that X-Frame-Options is set appropriately."""
        # Accept either DENY or SAMEORIGIN, with plain or escaped quotes
        pattern = r'add_header\s+X-Frame-Options\s+[\\"]?(DENY|SAMEORIGIN)[\\"]?'
        assert re.search(pattern, nginx_conf_content), (
            "X-Frame-Options should be set to 'DENY' or 'SAMEORIGIN' to prevent clickjacking."
        )

    def test_x_xss_protection_value(self, nginx_conf_content: str) -> None:
        """Test that X-XSS-Protection is set correctly."""
        # Allow plain or escaped quotes
        pattern = r'add_header\s+X-XSS-Protection\s+[\\"]?1;\s*mode=block[\\"]?'
        assert re.search(pattern, nginx_conf_content), (
            "X-XSS-Protection should be '1; mode=block' to enable XSS filter in blocking mode."
        )

    def test_referrer_policy_value(self, nginx_conf_content: str) -> None:
        """Test that Referrer-Policy is set to a secure value."""
        # Accept secure referrer policies, with plain or escaped quotes
        pattern = r'add_header\s+Referrer-Policy\s+[\\"]?(strict-origin-when-cross-origin|strict-origin|no-referrer|same-origin)[\\"]?'
        assert re.search(pattern, nginx_conf_content), (
            "Referrer-Policy should be set to a secure value like 'strict-origin-when-cross-origin'."
        )


class TestNginxServerTokensConfig:
    """Tests for nginx server_tokens configuration (NEM-5041).

    The server_tokens directive controls whether nginx exposes its version
    in error pages and the 'Server' response header. Hiding the version
    prevents attackers from targeting known vulnerabilities in specific
    nginx versions.

    Security best practice: server_tokens off;
    See: https://nginx.org/en/docs/http/ngx_http_core_module.html#server_tokens
    """

    @pytest.fixture
    def nginx_conf_path(self) -> Path:
        """Get the path to nginx.conf."""
        return Path(__file__).parent.parent.parent.parent.parent / "frontend" / "nginx.conf"

    @pytest.fixture
    def nginx_conf_content(self, nginx_conf_path: Path) -> str:
        """Read the nginx.conf content."""
        if not nginx_conf_path.exists():
            pytest.skip(f"nginx.conf not found at {nginx_conf_path}")
        return nginx_conf_path.read_text()

    def test_server_tokens_off_present(self, nginx_conf_content: str) -> None:
        """Test that server_tokens is set to 'off' to hide nginx version.

        Without 'server_tokens off', nginx exposes its version number in:
        - The 'Server' response header (e.g., 'Server: nginx/1.25.3')
        - Error pages (404, 500, etc.)

        This information aids attackers in identifying exploitable vulnerabilities.
        """
        # Match server_tokens off; with optional whitespace
        pattern = r"server_tokens\s+off\s*;"
        assert re.search(pattern, nginx_conf_content), (
            "nginx.conf must include 'server_tokens off;' to hide nginx version. "
            "This prevents version disclosure in error pages and Server header. "
            "Add 'server_tokens off;' to the http or server block."
        )

    def test_server_tokens_not_on(self, nginx_conf_content: str) -> None:
        """Test that server_tokens is not explicitly set to 'on'.

        While nginx defaults to 'server_tokens on', explicitly setting it to 'on'
        in the config indicates intentional version disclosure, which is a security risk.
        """
        # Check for explicit server_tokens on (which would be a security issue)
        pattern = r"server_tokens\s+on\s*;"
        lines = nginx_conf_content.split("\n")
        for i, line in enumerate(lines, 1):
            # Skip comment lines
            if line.strip().startswith("#"):
                continue
            assert not re.search(pattern, line), (
                f"Line {i} has 'server_tokens on' which exposes nginx version. "
                "Change to 'server_tokens off;' to hide version information."
            )
