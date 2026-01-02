"""Unit tests for URL validation and SSRF protection.

Tests cover:
- validate_ai_service_urls() - Trailing slash normalization, URL format validation
- validate_vision_service_urls() - URL format with ports
- validate_webhook_url() - SSRF validation including:
  - Cloud metadata endpoints (169.254.169.254)
  - Private IP ranges (10.x, 172.16.x, 192.168.x)
  - Localhost variations
  - File:// and other scheme attacks
  - DNS rebinding protection

Security test cases based on OWASP SSRF guidelines.
"""

from unittest.mock import patch

import pytest

from backend.core.url_validation import (
    BLOCKED_HOSTNAMES,
    BLOCKED_IP_NETWORKS,
    BLOCKED_IPS,
    LOCALHOST_PATTERNS,
    SSRFValidationError,
    is_blocked_hostname,
    is_blocked_ip,
    is_private_ip,
    resolve_hostname,
    validate_webhook_url,
    validate_webhook_url_for_request,
)

# =============================================================================
# SSRFValidationError Tests
# =============================================================================


class TestSSRFValidationError:
    """Tests for SSRFValidationError exception class."""

    def test_ssrf_error_is_exception(self) -> None:
        """Test that SSRFValidationError inherits from Exception."""
        assert issubclass(SSRFValidationError, Exception)

    def test_ssrf_error_not_value_error(self) -> None:
        """Test that SSRFValidationError is not caught by except ValueError."""
        # This is important for security - ValueError exceptions from IP parsing
        # should not mask SSRF validation errors
        with pytest.raises(SSRFValidationError):
            raise SSRFValidationError("test message")

        # Verify it's not caught by ValueError
        try:
            raise SSRFValidationError("test")
        except ValueError:
            pytest.fail("SSRFValidationError should not be caught by except ValueError")
        except SSRFValidationError:
            pass  # Expected

    def test_ssrf_error_message(self) -> None:
        """Test that error message is preserved."""
        error = SSRFValidationError("blocked for security reasons")
        assert str(error) == "blocked for security reasons"


# =============================================================================
# is_private_ip Tests
# =============================================================================


class TestIsPrivateIP:
    """Tests for is_private_ip function."""

    # RFC 1918 Private Networks
    @pytest.mark.parametrize(
        "ip",
        [
            "10.0.0.1",
            "10.255.255.255",
            "10.10.10.10",
            "172.16.0.1",
            "172.31.255.255",
            "172.20.0.1",
            "192.168.0.1",
            "192.168.255.255",
            "192.168.1.100",
        ],
    )
    def test_rfc1918_private_networks(self, ip: str) -> None:
        """Test RFC 1918 private IP ranges are detected."""
        assert is_private_ip(ip) is True

    # Loopback (RFC 990)
    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",
            "127.0.0.2",
            "127.255.255.255",
        ],
    )
    def test_loopback_addresses(self, ip: str) -> None:
        """Test loopback addresses are detected."""
        assert is_private_ip(ip) is True

    # Link-local (RFC 3927)
    @pytest.mark.parametrize(
        "ip",
        [
            "169.254.0.1",
            "169.254.255.255",
            "169.254.169.254",  # Cloud metadata
        ],
    )
    def test_link_local_addresses(self, ip: str) -> None:
        """Test link-local addresses are detected."""
        assert is_private_ip(ip) is True

    # Carrier-Grade NAT (RFC 6598)
    @pytest.mark.parametrize(
        "ip",
        [
            "100.64.0.1",
            "100.127.255.255",
        ],
    )
    def test_cgnat_addresses(self, ip: str) -> None:
        """Test Carrier-Grade NAT addresses are detected."""
        assert is_private_ip(ip) is True

    # Documentation IPs (RFC 5737)
    @pytest.mark.parametrize(
        "ip",
        [
            "192.0.2.1",
            "198.51.100.1",
            "203.0.113.1",
        ],
    )
    def test_documentation_addresses(self, ip: str) -> None:
        """Test documentation addresses are detected."""
        assert is_private_ip(ip) is True

    # IPv6 addresses
    @pytest.mark.parametrize(
        "ip",
        [
            "::1",  # Loopback
            "fe80::1",  # Link-local
            "fc00::1",  # Unique local
            "fd00::1",  # Unique local
        ],
    )
    def test_ipv6_private_addresses(self, ip: str) -> None:
        """Test IPv6 private/reserved addresses are detected."""
        assert is_private_ip(ip) is True

    # Public IPs should return False
    @pytest.mark.parametrize(
        "ip",
        [
            "8.8.8.8",  # Google DNS
            "1.1.1.1",  # Cloudflare DNS
            "142.250.80.46",  # google.com
            "151.101.1.69",  # reddit.com
            "2607:f8b0:4004:800::200e",  # IPv6 public
        ],
    )
    def test_public_ips_not_private(self, ip: str) -> None:
        """Test public IPs are not detected as private."""
        assert is_private_ip(ip) is False

    def test_invalid_ip_returns_false(self) -> None:
        """Test invalid IP string returns False (not an error)."""
        assert is_private_ip("not-an-ip") is False
        assert is_private_ip("example.com") is False
        assert is_private_ip("") is False


# =============================================================================
# is_blocked_ip Tests
# =============================================================================


class TestIsBlockedIP:
    """Tests for is_blocked_ip function."""

    @pytest.mark.parametrize(
        "ip",
        [
            "169.254.169.254",  # AWS/GCP/Azure metadata
            "169.254.170.2",  # AWS ECS metadata
            "169.254.169.253",  # Azure IMDS
        ],
    )
    def test_cloud_metadata_endpoints_blocked(self, ip: str) -> None:
        """Test cloud metadata endpoints are blocked."""
        assert is_blocked_ip(ip) is True

    def test_public_ip_not_blocked(self) -> None:
        """Test public IPs are not in blocked list."""
        assert is_blocked_ip("8.8.8.8") is False
        assert is_blocked_ip("1.1.1.1") is False

    def test_private_ip_not_in_blocked_list(self) -> None:
        """Test private IPs are not in explicitly blocked list."""
        # Note: These are still blocked by is_private_ip
        assert is_blocked_ip("10.0.0.1") is False
        assert is_blocked_ip("192.168.1.1") is False


# =============================================================================
# is_blocked_hostname Tests
# =============================================================================


class TestIsBlockedHostname:
    """Tests for is_blocked_hostname function."""

    @pytest.mark.parametrize(
        "hostname",
        [
            "metadata.google.internal",
            "METADATA.GOOGLE.INTERNAL",  # Case insensitive
            "Metadata.Google.Internal",
            "metadata",
            "METADATA",
            "instance-data",
            "INSTANCE-DATA",
        ],
    )
    def test_blocked_hostnames(self, hostname: str) -> None:
        """Test known blocked hostnames are detected."""
        assert is_blocked_hostname(hostname) is True

    @pytest.mark.parametrize(
        "hostname",
        [
            "example.com",
            "hooks.slack.com",
            "webhook.example.org",
            "localhost",  # Not in hostname blocklist
            "metadata.example.com",  # Partial match shouldn't block
        ],
    )
    def test_allowed_hostnames(self, hostname: str) -> None:
        """Test allowed hostnames are not blocked."""
        assert is_blocked_hostname(hostname) is False


# =============================================================================
# resolve_hostname Tests
# =============================================================================


class TestResolveHostname:
    """Tests for resolve_hostname function."""

    def test_resolve_hostname_success(self) -> None:
        """Test successful hostname resolution."""
        with patch("backend.core.url_validation.socket.getaddrinfo") as mock_getaddrinfo:
            # Mock getaddrinfo returns list of (family, type, proto, canonname, sockaddr)
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("93.184.216.34", 0)),
                (2, 1, 6, "", ("93.184.216.35", 0)),
            ]

            result = resolve_hostname("example.com")

            assert "93.184.216.34" in result
            assert len(result) == 2

    def test_resolve_hostname_ipv6(self) -> None:
        """Test IPv6 hostname resolution."""
        with patch("backend.core.url_validation.socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (10, 1, 6, "", ("2607:f8b0:4004:800::200e", 0, 0, 0)),
            ]

            result = resolve_hostname("ipv6.example.com")

            assert "2607:f8b0:4004:800::200e" in result

    def test_resolve_hostname_failure(self) -> None:
        """Test hostname resolution failure raises SSRFValidationError."""
        import socket

        with patch("backend.core.url_validation.socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.side_effect = socket.gaierror(8, "Name does not resolve")

            with pytest.raises(SSRFValidationError) as exc_info:
                resolve_hostname("nonexistent.invalid")

            assert "Cannot resolve hostname" in str(exc_info.value)
            assert "nonexistent.invalid" in str(exc_info.value)


# =============================================================================
# validate_webhook_url Tests - Basic Validation
# =============================================================================


class TestValidateWebhookUrlBasic:
    """Tests for basic validate_webhook_url functionality."""

    def test_empty_url_rejected(self) -> None:
        """Test empty URL is rejected."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url("")

        assert "cannot be empty" in str(exc_info.value)

    def test_none_url_rejected(self) -> None:
        """Test None URL is rejected."""
        with pytest.raises(SSRFValidationError):
            validate_webhook_url(None)  # type: ignore[arg-type]

    def test_missing_hostname_rejected(self) -> None:
        """Test URL without hostname is rejected."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url("https:///path")

        assert "must have a hostname" in str(exc_info.value)

    def test_valid_https_url_accepted(self) -> None:
        """Test valid HTTPS URL is accepted."""
        with patch("backend.core.url_validation.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = ["93.184.216.34"]

            result = validate_webhook_url("https://example.com/webhook")

            assert result == "https://example.com/webhook"

    def test_valid_https_url_with_port(self) -> None:
        """Test valid HTTPS URL with port is accepted."""
        with patch("backend.core.url_validation.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = ["93.184.216.34"]

            result = validate_webhook_url("https://example.com:8443/webhook")

            assert result == "https://example.com:8443/webhook"

    def test_returns_unchanged_url(self) -> None:
        """Test that valid URL is returned unchanged."""
        with patch("backend.core.url_validation.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = ["93.184.216.34"]

            original = "https://hooks.slack.com/services/T00/B00/XXX"
            result = validate_webhook_url(original)

            assert result == original


# =============================================================================
# validate_webhook_url Tests - Scheme Validation
# =============================================================================


class TestValidateWebhookUrlSchemes:
    """Tests for URL scheme validation."""

    def test_http_rejected_in_production_mode(self) -> None:
        """Test HTTP is rejected when allow_dev_http=False."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url("http://example.com/webhook", allow_dev_http=False)

        assert "scheme" in str(exc_info.value).lower()
        assert "https" in str(exc_info.value).lower()

    def test_http_localhost_allowed_in_dev_mode(self) -> None:
        """Test HTTP localhost is allowed in dev mode."""
        result = validate_webhook_url(
            "http://localhost:8080/webhook",
            allow_dev_http=True,
            resolve_dns=False,
        )

        assert result == "http://localhost:8080/webhook"

    def test_http_127_allowed_in_dev_mode(self) -> None:
        """Test HTTP 127.0.0.1 is allowed in dev mode."""
        result = validate_webhook_url(
            "http://127.0.0.1:8080/webhook",
            allow_dev_http=True,
            resolve_dns=False,
        )

        assert result == "http://127.0.0.1:8080/webhook"

    def test_http_external_rejected_in_dev_mode(self) -> None:
        """Test HTTP to external host is rejected even in dev mode."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url(
                "http://example.com/webhook",
                allow_dev_http=True,
                resolve_dns=False,
            )

        assert "only allowed for localhost" in str(exc_info.value).lower()

    @pytest.mark.parametrize(
        "scheme",
        [
            "file",
            "ftp",
            "gopher",
            "data",
            "javascript",
            "dict",
            "ldap",
            "sftp",
        ],
    )
    def test_dangerous_schemes_rejected(self, scheme: str) -> None:
        """Test dangerous URL schemes are rejected."""
        with pytest.raises(SSRFValidationError):
            validate_webhook_url(f"{scheme}://example.com/path")

    def test_file_scheme_explicitly_rejected(self) -> None:
        """Test file:// scheme is explicitly rejected.

        Note: file:///etc/passwd is rejected for missing hostname.
        URLs like file://host/path would be rejected for invalid scheme.
        Both are proper security rejections.
        """
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url("file:///etc/passwd")

        # File URLs without host get rejected for missing hostname
        # This is still a valid security rejection
        assert "hostname" in str(exc_info.value).lower() or "scheme" in str(exc_info.value).lower()


# =============================================================================
# validate_webhook_url Tests - SSRF Protection
# =============================================================================


class TestValidateWebhookUrlSSRF:
    """Tests for SSRF protection in validate_webhook_url."""

    # Cloud metadata endpoints - use HTTPS to test IP blocking specifically
    # (HTTP URLs get rejected for scheme before IP is checked)
    @pytest.mark.parametrize(
        "url",
        [
            "https://169.254.169.254/",
            "https://169.254.169.254/latest/meta-data/",
            "https://169.254.169.254/latest/user-data/",
            "https://169.254.169.254/computeMetadata/v1/",
            "https://169.254.170.2/v2/credentials/",  # AWS ECS
            "https://169.254.169.253/metadata/instance",  # Azure
        ],
    )
    def test_cloud_metadata_endpoints_blocked(self, url: str) -> None:
        """Test cloud metadata endpoints are blocked."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url(url, allow_dev_http=False)

        assert "blocked" in str(exc_info.value).lower() or "private" in str(exc_info.value).lower()

    def test_google_metadata_hostname_blocked(self) -> None:
        """Test Google Cloud metadata hostname is blocked."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url(
                "https://metadata.google.internal/computeMetadata/v1/",
                allow_dev_http=False,
            )

        assert "blocked" in str(exc_info.value).lower()

    # Private IP ranges
    @pytest.mark.parametrize(
        "ip,network",
        [
            ("10.0.0.1", "10.0.0.0/8"),
            ("10.255.255.255", "10.0.0.0/8"),
            ("172.16.0.1", "172.16.0.0/12"),
            ("172.31.255.255", "172.16.0.0/12"),
            ("192.168.0.1", "192.168.0.0/16"),
            ("192.168.255.255", "192.168.0.0/16"),
        ],
    )
    def test_rfc1918_private_ips_blocked(self, ip: str, network: str) -> None:
        """Test RFC 1918 private IP ranges are blocked."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url(f"https://{ip}/webhook")

        assert "private" in str(exc_info.value).lower()

    # Localhost variations
    @pytest.mark.parametrize(
        "url",
        [
            "https://127.0.0.1/admin",
            "https://127.0.0.2/",  # Also loopback
            "https://127.255.255.255/",  # Max loopback
        ],
    )
    def test_loopback_blocked_without_dev_mode(self, url: str) -> None:
        """Test loopback addresses blocked without dev mode."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url(url, allow_dev_http=False)

        assert "private" in str(exc_info.value).lower()

    @pytest.mark.parametrize(
        "url",
        [
            "https://[::1]/admin",  # IPv6 localhost
            "https://[fe80::1]/admin",  # IPv6 link-local
            "https://[fc00::1]/admin",  # IPv6 unique local
        ],
    )
    def test_ipv6_private_blocked(self, url: str) -> None:
        """Test IPv6 private addresses are blocked."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url(url, allow_dev_http=False)

        assert "private" in str(exc_info.value).lower()

    # Carrier-Grade NAT
    @pytest.mark.parametrize(
        "ip",
        [
            "100.64.0.1",
            "100.100.100.100",
            "100.127.255.255",
        ],
    )
    def test_cgnat_blocked(self, ip: str) -> None:
        """Test Carrier-Grade NAT addresses are blocked."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url(f"https://{ip}/webhook")

        assert "private" in str(exc_info.value).lower()


# =============================================================================
# validate_webhook_url Tests - URL Attack Patterns
# =============================================================================


class TestValidateWebhookUrlAttacks:
    """Tests for URL-based attack pattern detection."""

    def test_credentials_in_url_rejected(self) -> None:
        """Test URLs with embedded credentials are rejected."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url("https://user:pass@example.com/webhook")

        assert "credentials" in str(exc_info.value).lower()

    def test_username_only_rejected(self) -> None:
        """Test URLs with username (no password) are rejected."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_webhook_url("https://user@example.com/webhook")

        assert "credentials" in str(exc_info.value).lower()

    def test_at_sign_bypass_attack_blocked(self) -> None:
        """Test URL at-sign bypass attack is blocked.

        Attack: http://evil.com@169.254.169.254/
        Some parsers might interpret this as user=evil.com, host=169.254.169.254
        """
        with pytest.raises(SSRFValidationError):
            validate_webhook_url(
                "http://evil.com@169.254.169.254/",
                allow_dev_http=True,
            )


# =============================================================================
# validate_webhook_url Tests - DNS Resolution
# =============================================================================


class TestValidateWebhookUrlDNS:
    """Tests for DNS resolution and validation."""

    def test_dns_resolves_to_private_ip_blocked(self) -> None:
        """Test hostname that resolves to private IP is blocked."""
        with patch("backend.core.url_validation.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = ["10.0.0.1"]

            with pytest.raises(SSRFValidationError) as exc_info:
                validate_webhook_url("https://internal.example.com/webhook")

            assert "private" in str(exc_info.value).lower()
            assert "10.0.0.1" in str(exc_info.value)

    def test_dns_resolves_to_metadata_ip_blocked(self) -> None:
        """Test hostname that resolves to cloud metadata IP is blocked."""
        with patch("backend.core.url_validation.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = ["169.254.169.254"]

            with pytest.raises(SSRFValidationError) as exc_info:
                validate_webhook_url("https://sneaky.example.com/webhook")

            assert "blocked" in str(exc_info.value).lower()

    def test_dns_resolves_to_multiple_ips_all_checked(self) -> None:
        """Test all resolved IPs are checked (not just first)."""
        with patch("backend.core.url_validation.resolve_hostname") as mock_resolve:
            # First IP is public, second is private
            mock_resolve.return_value = ["93.184.216.34", "10.0.0.1"]

            with pytest.raises(SSRFValidationError) as exc_info:
                validate_webhook_url("https://multi-homed.example.com/webhook")

            assert "private" in str(exc_info.value).lower()

    def test_skip_dns_resolution_when_disabled(self) -> None:
        """Test DNS resolution can be skipped."""
        with patch("backend.core.url_validation.resolve_hostname") as mock_resolve:
            result = validate_webhook_url(
                "https://example.com/webhook",
                resolve_dns=False,
            )

            mock_resolve.assert_not_called()
            assert result == "https://example.com/webhook"

    def test_dns_failure_logged_not_blocked(self) -> None:
        """Test DNS resolution failure is logged but doesn't block."""
        import socket

        with patch("backend.core.url_validation.resolve_hostname") as mock_resolve:
            mock_resolve.side_effect = socket.gaierror(8, "Name does not resolve")

            # Should not raise - DNS failure is logged as warning
            result = validate_webhook_url("https://example.com/webhook")

            assert result == "https://example.com/webhook"


# =============================================================================
# validate_webhook_url_for_request Tests
# =============================================================================


class TestValidateWebhookUrlForRequest:
    """Tests for validate_webhook_url_for_request function."""

    def test_always_resolves_dns(self) -> None:
        """Test that request-time validation always resolves DNS."""
        with patch("backend.core.url_validation.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = ["93.184.216.34"]

            validate_webhook_url_for_request("https://example.com/webhook")

            mock_resolve.assert_called_once()

    def test_dev_mode_allows_localhost_http(self) -> None:
        """Test development mode allows HTTP for localhost."""
        with patch("backend.core.url_validation.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = ["127.0.0.1"]

            result = validate_webhook_url_for_request(
                "http://localhost:8080/webhook",
                is_development=True,
            )

            assert result == "http://localhost:8080/webhook"

    def test_prod_mode_rejects_http(self) -> None:
        """Test production mode rejects HTTP."""
        with pytest.raises(SSRFValidationError):
            validate_webhook_url_for_request(
                "http://example.com/webhook",
                is_development=False,
            )


# =============================================================================
# Settings Integration Tests - validate_ai_service_urls
# =============================================================================


class TestValidateAIServiceUrls:
    """Tests for validate_ai_service_urls in Settings class."""

    def test_trailing_slash_normalized(self) -> None:
        """Test trailing slashes are removed from AI service URLs."""
        from backend.core.config import Settings

        # Create settings with trailing slash
        with patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
                "RTDETR_URL": "http://localhost:8090/",
                "NEMOTRON_URL": "http://localhost:8091/",
            },
        ):
            settings = Settings(
                database_url="postgresql+asyncpg://test:test@localhost:5432/test",
                rtdetr_url="http://localhost:8090/",
                nemotron_url="http://localhost:8091/",
            )

            assert settings.rtdetr_url == "http://localhost:8090"
            assert settings.nemotron_url == "http://localhost:8091"

    def test_multiple_trailing_slashes_normalized(self) -> None:
        """Test multiple trailing slashes are removed."""
        from backend.core.config import Settings

        settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost:5432/test",
            rtdetr_url="http://localhost:8090///",
            nemotron_url="http://localhost:8091///",
        )

        # Note: Pydantic AnyHttpUrl normalizes to single slash, then we strip
        assert not settings.rtdetr_url.endswith("/")
        assert not settings.nemotron_url.endswith("/")

    def test_valid_urls_accepted(self) -> None:
        """Test valid HTTP/HTTPS URLs are accepted."""
        from backend.core.config import Settings

        settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost:5432/test",
            rtdetr_url="http://ai-server:8090",
            nemotron_url="https://secure-ai:8091",
        )

        assert settings.rtdetr_url == "http://ai-server:8090"
        assert settings.nemotron_url == "https://secure-ai:8091"

    def test_invalid_url_rejected(self) -> None:
        """Test invalid URLs are rejected."""
        from pydantic import ValidationError

        from backend.core.config import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                database_url="postgresql+asyncpg://test:test@localhost:5432/test",
                rtdetr_url="not-a-url",
            )

        assert "rtdetr_url" in str(exc_info.value)

    def test_none_url_rejected(self) -> None:
        """Test None URLs are rejected."""
        from pydantic import ValidationError

        from backend.core.config import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                database_url="postgresql+asyncpg://test:test@localhost:5432/test",
                rtdetr_url=None,  # type: ignore[arg-type]
            )

        assert "rtdetr_url" in str(exc_info.value).lower() or "cannot be None" in str(
            exc_info.value
        )


# =============================================================================
# Settings Integration Tests - validate_vision_service_urls
# =============================================================================


class TestValidateVisionServiceUrls:
    """Tests for validate_vision_service_urls in Settings class."""

    def test_trailing_slash_normalized(self) -> None:
        """Test trailing slashes are removed from vision service URLs."""
        from backend.core.config import Settings

        settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost:5432/test",
            florence_url="http://localhost:8092/",
            clip_url="http://localhost:8093/",
            enrichment_url="http://localhost:8094/",
        )

        assert settings.florence_url == "http://localhost:8092"
        assert settings.clip_url == "http://localhost:8093"
        assert settings.enrichment_url == "http://localhost:8094"

    def test_url_with_port_accepted(self) -> None:
        """Test URLs with explicit ports are accepted."""
        from backend.core.config import Settings

        settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost:5432/test",
            florence_url="http://vision-server:9000",
            clip_url="https://ml-cluster:8443",  # Non-default port (443 gets normalized away)
            enrichment_url="http://192.168.1.100:5000",
        )

        assert ":9000" in settings.florence_url
        assert ":8443" in settings.clip_url
        assert ":5000" in settings.enrichment_url

    def test_ipv4_url_accepted(self) -> None:
        """Test URLs with IPv4 addresses are accepted."""
        from backend.core.config import Settings

        settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost:5432/test",
            florence_url="http://192.168.1.100:8092",
        )

        assert settings.florence_url == "http://192.168.1.100:8092"


# =============================================================================
# Settings Integration Tests - validate_webhook_url (default_webhook_url)
# =============================================================================


class TestValidateDefaultWebhookUrl:
    """Tests for default_webhook_url validation in Settings class."""

    def test_none_accepted(self) -> None:
        """Test None/empty webhook URL is accepted (optional field)."""
        from backend.core.config import Settings

        settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost:5432/test",
            default_webhook_url=None,
        )

        assert settings.default_webhook_url is None

    def test_empty_string_converted_to_none(self) -> None:
        """Test empty string is converted to None."""
        from backend.core.config import Settings

        settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost:5432/test",
            default_webhook_url="",
        )

        assert settings.default_webhook_url is None

    def test_valid_https_url_accepted(self) -> None:
        """Test valid HTTPS webhook URL is accepted."""
        from backend.core.config import Settings

        settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost:5432/test",
            default_webhook_url="https://hooks.slack.com/services/T00/B00/XXX",
        )

        assert settings.default_webhook_url == "https://hooks.slack.com/services/T00/B00/XXX"

    def test_http_localhost_allowed_in_config(self) -> None:
        """Test HTTP localhost is allowed in config (dev mode enabled)."""
        from backend.core.config import Settings

        settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost:5432/test",
            default_webhook_url="http://localhost:8080/webhook",
        )

        assert settings.default_webhook_url == "http://localhost:8080/webhook"

    def test_cloud_metadata_blocked(self) -> None:
        """Test cloud metadata endpoints are blocked in webhook URL."""
        from pydantic import ValidationError

        from backend.core.config import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                database_url="postgresql+asyncpg://test:test@localhost:5432/test",
                default_webhook_url="http://169.254.169.254/latest/meta-data/",
            )

        error_str = str(exc_info.value).lower()
        assert "webhook" in error_str or "security" in error_str or "blocked" in error_str

    def test_private_ip_blocked(self) -> None:
        """Test private IPs are blocked in webhook URL."""
        from pydantic import ValidationError

        from backend.core.config import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                database_url="postgresql+asyncpg://test:test@localhost:5432/test",
                default_webhook_url="https://10.0.0.1/webhook",
            )

        error_str = str(exc_info.value).lower()
        assert "private" in error_str or "security" in error_str or "blocked" in error_str


# =============================================================================
# Constant Coverage Tests
# =============================================================================


class TestConstants:
    """Tests to verify security constants are properly defined."""

    def test_blocked_ip_networks_includes_rfc1918(self) -> None:
        """Test RFC 1918 private networks are in blocked list."""

        network_strings = [str(net) for net in BLOCKED_IP_NETWORKS]

        assert "10.0.0.0/8" in network_strings
        assert "172.16.0.0/12" in network_strings
        assert "192.168.0.0/16" in network_strings

    def test_blocked_ip_networks_includes_loopback(self) -> None:
        """Test loopback is in blocked networks."""

        network_strings = [str(net) for net in BLOCKED_IP_NETWORKS]

        assert "127.0.0.0/8" in network_strings
        assert "::1/128" in network_strings

    def test_blocked_ip_networks_includes_link_local(self) -> None:
        """Test link-local is in blocked networks."""

        network_strings = [str(net) for net in BLOCKED_IP_NETWORKS]

        assert "169.254.0.0/16" in network_strings
        assert "fe80::/10" in network_strings

    def test_blocked_ips_includes_metadata(self) -> None:
        """Test cloud metadata IPs are explicitly blocked."""
        assert "169.254.169.254" in BLOCKED_IPS
        assert "169.254.170.2" in BLOCKED_IPS
        assert "169.254.169.253" in BLOCKED_IPS

    def test_blocked_hostnames_includes_metadata(self) -> None:
        """Test cloud metadata hostnames are blocked."""
        assert "metadata.google.internal" in BLOCKED_HOSTNAMES
        assert "metadata" in BLOCKED_HOSTNAMES

    def test_localhost_patterns_defined(self) -> None:
        """Test localhost patterns are defined for dev mode."""
        assert "localhost" in LOCALHOST_PATTERNS
        assert "127.0.0.1" in LOCALHOST_PATTERNS
        assert "::1" in LOCALHOST_PATTERNS
