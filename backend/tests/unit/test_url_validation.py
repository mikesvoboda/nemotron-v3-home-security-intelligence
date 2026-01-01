"""Unit tests for URL validation with SSRF protection.

Tests cover:
- Private IP range blocking (10.x, 172.16-31.x, 192.168.x, 127.x)
- Cloud metadata endpoint blocking (169.254.169.254)
- Link-local address blocking (169.254.x.x)
- IPv6 private/loopback blocking
- Scheme validation (HTTPS required, HTTP only for localhost in dev)
- DNS resolution and validation
- URL parsing edge cases
- Embedded credentials blocking
"""

from unittest.mock import patch

import pytest

from backend.core.url_validation import (
    BLOCKED_HOSTNAMES,
    BLOCKED_IP_NETWORKS,
    BLOCKED_IPS,
    SSRFValidationError,
    is_blocked_hostname,
    is_blocked_ip,
    is_private_ip,
    resolve_hostname,
    validate_webhook_url,
    validate_webhook_url_for_request,
)


class TestIsPrivateIP:
    """Tests for is_private_ip function."""

    @pytest.mark.parametrize(
        "ip",
        [
            # Class A private (10.0.0.0/8)
            "10.0.0.1",
            "10.255.255.255",
            "10.1.2.3",
            # Class B private (172.16.0.0/12)
            "172.16.0.1",
            "172.31.255.255",
            "172.20.5.10",
            # Class C private (192.168.0.0/16)
            "192.168.0.1",
            "192.168.255.255",
            "192.168.1.100",
            # Loopback (127.0.0.0/8)
            "127.0.0.1",
            "127.255.255.255",
            "127.0.0.2",
            # Link-local (169.254.0.0/16)
            "169.254.0.1",
            "169.254.169.254",
            "169.254.255.255",
            # Carrier-Grade NAT (100.64.0.0/10)
            "100.64.0.1",
            "100.127.255.255",
            # Documentation ranges
            "192.0.2.1",
            "198.51.100.1",
            "203.0.113.1",
            # Benchmarking
            "198.18.0.1",
            "198.19.255.255",
        ],
    )
    def test_private_ips_are_detected(self, ip: str):
        """Test that private IPs are correctly identified."""
        assert is_private_ip(ip) is True

    @pytest.mark.parametrize(
        "ip",
        [
            # Public IPs
            "8.8.8.8",
            "1.1.1.1",
            "93.184.216.34",  # example.com
            "142.250.185.206",  # google.com
            "13.107.42.14",  # microsoft.com
            # Just outside private ranges
            "9.255.255.255",
            "11.0.0.1",
            "172.15.255.255",
            "172.32.0.1",
            "192.167.255.255",
            "192.169.0.1",
        ],
    )
    def test_public_ips_are_allowed(self, ip: str):
        """Test that public IPs are not blocked."""
        assert is_private_ip(ip) is False

    def test_invalid_ip_returns_false(self):
        """Test that invalid IPs return False (not an error)."""
        assert is_private_ip("not-an-ip") is False
        assert is_private_ip("example.com") is False
        assert is_private_ip("") is False

    @pytest.mark.parametrize(
        "ip",
        [
            # IPv6 loopback
            "::1",
            # IPv6 link-local
            "fe80::1",
            "fe80::dead:beef",
            # IPv6 unique local
            "fc00::1",
            "fd00::1",
        ],
    )
    def test_ipv6_private_ips_are_detected(self, ip: str):
        """Test that IPv6 private/loopback addresses are blocked."""
        assert is_private_ip(ip) is True


class TestIsBlockedIP:
    """Tests for is_blocked_ip function."""

    def test_cloud_metadata_ips_are_blocked(self):
        """Test that cloud metadata IPs are blocked."""
        assert is_blocked_ip("169.254.169.254") is True
        assert is_blocked_ip("169.254.170.2") is True
        assert is_blocked_ip("169.254.169.253") is True

    def test_regular_ips_are_not_blocked(self):
        """Test that regular IPs are not in the blocked list."""
        assert is_blocked_ip("8.8.8.8") is False
        assert is_blocked_ip("10.0.0.1") is False  # Private but not in BLOCKED_IPS


class TestIsBlockedHostname:
    """Tests for is_blocked_hostname function."""

    def test_metadata_hostnames_are_blocked(self):
        """Test that cloud metadata hostnames are blocked."""
        assert is_blocked_hostname("metadata.google.internal") is True
        assert is_blocked_hostname("metadata") is True
        assert is_blocked_hostname("instance-data") is True

    def test_case_insensitive_blocking(self):
        """Test that hostname blocking is case-insensitive."""
        assert is_blocked_hostname("METADATA.GOOGLE.INTERNAL") is True
        assert is_blocked_hostname("Metadata") is True

    def test_regular_hostnames_are_not_blocked(self):
        """Test that regular hostnames are not blocked."""
        assert is_blocked_hostname("example.com") is False
        assert is_blocked_hostname("hooks.slack.com") is False


class TestValidateWebhookUrl:
    """Tests for validate_webhook_url function."""

    # Valid URLs

    def test_valid_https_url(self):
        """Test that valid HTTPS URLs pass validation."""
        url = "https://example.com/webhook"
        assert validate_webhook_url(url, resolve_dns=False) == url

    def test_valid_https_url_with_port(self):
        """Test that HTTPS URLs with ports are allowed."""
        url = "https://example.com:8443/webhook"
        assert validate_webhook_url(url, resolve_dns=False) == url

    def test_valid_https_url_with_path(self):
        """Test that HTTPS URLs with paths are allowed."""
        url = "https://api.example.com/v1/hooks/incoming"
        assert validate_webhook_url(url, resolve_dns=False) == url

    def test_valid_https_url_with_query_params(self):
        """Test that HTTPS URLs with query params are allowed."""
        url = "https://example.com/webhook?token=abc123"
        assert validate_webhook_url(url, resolve_dns=False) == url

    # Scheme validation

    def test_http_blocked_in_production(self):
        """Test that HTTP is blocked when not in dev mode."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url("http://example.com/webhook", allow_dev_http=False)
        assert "HTTPS" in str(exc_info.value)

    def test_http_allowed_for_localhost_in_dev(self):
        """Test that HTTP is allowed for localhost in dev mode."""
        url = "http://localhost:8000/webhook"
        assert validate_webhook_url(url, allow_dev_http=True, resolve_dns=False) == url

        url = "http://127.0.0.1:8000/webhook"
        assert validate_webhook_url(url, allow_dev_http=True, resolve_dns=False) == url

    def test_http_blocked_for_external_in_dev(self):
        """Test that HTTP is blocked for external URLs even in dev mode."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url("http://example.com/webhook", allow_dev_http=True)
        assert "localhost" in str(exc_info.value).lower()

    def test_ftp_scheme_blocked(self):
        """Test that FTP scheme is blocked."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url("ftp://example.com/file")
        assert "scheme" in str(exc_info.value).lower()

    def test_file_scheme_blocked(self):
        """Test that file:// scheme is blocked."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url("file:///etc/passwd")
        # file:// URLs have no hostname, so they're blocked either way
        error_msg = str(exc_info.value).lower()
        assert "scheme" in error_msg or "hostname" in error_msg

    # Private IP blocking

    @pytest.mark.parametrize(
        "ip",
        [
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "127.0.0.2",  # loopback but not 127.0.0.1
        ],
    )
    def test_private_ips_blocked(self, ip: str):
        """Test that private IPs are blocked."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url(f"https://{ip}/webhook")
        assert "private" in str(exc_info.value).lower() or "reserved" in str(exc_info.value).lower()

    def test_localhost_ip_blocked_in_production(self):
        """Test that 127.0.0.1 is blocked in production mode."""
        with pytest.raises(SSRFValidationError):
            validate_webhook_url("https://127.0.0.1/webhook", allow_dev_http=False)

    def test_localhost_allowed_in_dev(self):
        """Test that localhost is allowed in dev mode."""
        url = validate_webhook_url(
            "http://127.0.0.1:8000/webhook",
            allow_dev_http=True,
            resolve_dns=False,
        )
        assert url == "http://127.0.0.1:8000/webhook"

    # Cloud metadata blocking

    def test_aws_metadata_ip_blocked(self):
        """Test that AWS metadata IP is blocked."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url("https://169.254.169.254/latest/meta-data/")
        assert "blocked" in str(exc_info.value).lower() or "metadata" in str(exc_info.value).lower()

    def test_aws_ecs_metadata_blocked(self):
        """Test that AWS ECS metadata IP is blocked."""
        with pytest.raises(SSRFValidationError):
            validate_webhook_url("https://169.254.170.2/v3/metadata")

    def test_metadata_hostname_blocked(self):
        """Test that metadata hostnames are blocked."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url("https://metadata.google.internal/v1/")
        assert "blocked" in str(exc_info.value).lower()

    # URL format validation

    def test_empty_url_blocked(self):
        """Test that empty URL is blocked."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url("")
        assert "empty" in str(exc_info.value).lower()

    def test_url_without_hostname_blocked(self):
        """Test that URL without hostname is blocked."""
        with pytest.raises(SSRFValidationError):
            validate_webhook_url("https:///path")

    def test_embedded_credentials_blocked(self):
        """Test that URLs with embedded credentials are blocked."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url("https://user:pass@example.com/webhook")
        assert "credentials" in str(exc_info.value).lower()

    def test_embedded_username_blocked(self):
        """Test that URLs with username are blocked (potential SSRF bypass)."""
        # URL with username targeting metadata IP - caught by IP blocking or credentials check
        with pytest.raises(SSRFValidationError):
            validate_webhook_url("https://evil.com@169.254.169.254/")

        # URL with credentials targeting a valid external host - caught by credentials check
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url("https://user@example.com/webhook", resolve_dns=False)
        assert "credentials" in str(exc_info.value).lower()

    # DNS resolution

    def test_dns_resolution_validates_ips(self):
        """Test that DNS-resolved IPs are validated."""
        with patch("backend.core.url_validation.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = ["10.0.0.1"]  # Private IP
            with pytest.raises(SSRFValidationError) as exc_info:
                validate_webhook_url("https://evil.example.com/webhook", resolve_dns=True)
            assert "private" in str(exc_info.value).lower()

    def test_dns_resolution_catches_metadata_redirect(self):
        """Test that DNS resolving to metadata IP is blocked."""
        with patch("backend.core.url_validation.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = ["169.254.169.254"]
            with pytest.raises(SSRFValidationError):
                validate_webhook_url("https://evil.example.com/webhook", resolve_dns=True)

    def test_skip_dns_resolution(self):
        """Test that DNS resolution can be skipped for schema validation."""
        with patch("backend.core.url_validation.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = ["10.0.0.1"]
            # Should NOT raise because resolve_dns=False
            url = validate_webhook_url(
                "https://example.com/webhook",
                resolve_dns=False,
            )
            assert url == "https://example.com/webhook"
            mock_resolve.assert_not_called()


class TestValidateWebhookUrlForRequest:
    """Tests for validate_webhook_url_for_request function."""

    def test_always_resolves_dns(self):
        """Test that this function always resolves DNS."""
        with patch("backend.core.url_validation.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = ["93.184.216.34"]  # example.com
            validate_webhook_url_for_request("https://example.com/webhook")
            mock_resolve.assert_called_once()

    def test_blocks_dns_rebinding(self):
        """Test that DNS rebinding attacks are blocked at request time."""
        with patch("backend.core.url_validation.resolve_hostname") as mock_resolve:
            # Simulate DNS rebinding: hostname now resolves to private IP
            mock_resolve.return_value = ["192.168.1.1"]
            with pytest.raises(SSRFValidationError):
                validate_webhook_url_for_request("https://evil.com/webhook")


class TestResolveHostname:
    """Tests for resolve_hostname function."""

    def test_resolve_known_hostname(self):
        """Test resolving a known hostname."""
        # This test requires network access
        ips = resolve_hostname("localhost")
        assert len(ips) > 0
        assert any(ip in ("127.0.0.1", "::1") for ip in ips)

    def test_resolve_invalid_hostname_raises(self):
        """Test that invalid hostname raises SSRFValidationError."""
        with pytest.raises(SSRFValidationError) as exc_info:
            resolve_hostname("this-hostname-does-not-exist-12345.invalid")
        assert "Cannot resolve" in str(exc_info.value)


class TestBlockedNetworks:
    """Tests for BLOCKED_IP_NETWORKS constant."""

    def test_all_networks_are_valid(self):
        """Test that all blocked networks are valid IPv4/IPv6 networks."""
        for network in BLOCKED_IP_NETWORKS:
            assert network.version in (4, 6)

    def test_contains_private_networks(self):
        """Test that all RFC 1918 private networks are included."""
        network_strs = [str(n) for n in BLOCKED_IP_NETWORKS]
        assert "10.0.0.0/8" in network_strs
        assert "172.16.0.0/12" in network_strs
        assert "192.168.0.0/16" in network_strs

    def test_contains_loopback(self):
        """Test that loopback networks are included."""
        network_strs = [str(n) for n in BLOCKED_IP_NETWORKS]
        assert "127.0.0.0/8" in network_strs
        assert "::1/128" in network_strs


class TestBlockedIPs:
    """Tests for BLOCKED_IPS constant."""

    def test_contains_aws_metadata(self):
        """Test that AWS metadata IP is blocked."""
        assert "169.254.169.254" in BLOCKED_IPS

    def test_contains_aws_ecs_metadata(self):
        """Test that AWS ECS metadata IP is blocked."""
        assert "169.254.170.2" in BLOCKED_IPS


class TestBlockedHostnames:
    """Tests for BLOCKED_HOSTNAMES constant."""

    def test_contains_gcp_metadata(self):
        """Test that GCP metadata hostname is blocked."""
        assert "metadata.google.internal" in BLOCKED_HOSTNAMES

    def test_contains_generic_metadata(self):
        """Test that generic metadata hostnames are blocked."""
        assert "metadata" in BLOCKED_HOSTNAMES
        assert "instance-data" in BLOCKED_HOSTNAMES


class TestSSRFValidationError:
    """Tests for SSRFValidationError exception."""

    def test_is_exception(self):
        """Test that SSRFValidationError is an Exception subclass.

        Note: SSRFValidationError intentionally does NOT inherit from ValueError
        to avoid being caught by except ValueError clauses in IP address parsing.
        """
        assert issubclass(SSRFValidationError, Exception)
        assert not issubclass(SSRFValidationError, ValueError)

    def test_message_is_preserved(self):
        """Test that error message is preserved."""
        error = SSRFValidationError("Custom error message")
        assert str(error) == "Custom error message"
