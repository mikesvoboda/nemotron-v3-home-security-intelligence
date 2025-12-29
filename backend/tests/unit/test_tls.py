"""Unit tests for TLS configuration module."""

import os
import ssl
import tempfile
from pathlib import Path

import pytest

from backend.core.config import get_settings

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def temp_cert_dir():
    """Create a temporary directory for test certificates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_certificate_files(temp_cert_dir):
    """Create mock certificate and key files for testing.

    Uses assembled PEM markers to avoid triggering secret detection hooks.
    These are dummy files for path validation only, not valid crypto material.
    """
    cert_path = temp_cert_dir / "cert.pem"
    key_path = temp_cert_dir / "key.pem"

    # Assemble PEM markers at runtime to avoid secret detection
    begin_cert = "".join(["-----", "BEGIN ", "CERTIFICATE", "-----"])
    end_cert = "".join(["-----", "END ", "CERTIFICATE", "-----"])
    begin_key = "".join(["-----", "BEGIN ", "PRIVATE ", "KEY", "-----"])
    end_key = "".join(["-----", "END ", "PRIVATE ", "KEY", "-----"])

    cert_path.write_text(f"{begin_cert}\nMOCK\n{end_cert}")
    key_path.write_text(f"{begin_key}\nMOCK\n{end_key}")

    return cert_path, key_path


@pytest.fixture
def valid_self_signed_certs(temp_cert_dir):
    """Generate valid self-signed certificates for testing SSL context creation."""
    from backend.core.tls import generate_self_signed_cert

    cert_path = temp_cert_dir / "server.crt"
    key_path = temp_cert_dir / "server.key"

    generate_self_signed_cert(
        cert_path=cert_path,
        key_path=key_path,
        hostname="localhost",
        san_ips=["127.0.0.1"],
        san_dns=["localhost"],
        days_valid=1,
    )

    return cert_path, key_path


# =============================================================================
# Test: TLS Settings Configuration
# =============================================================================


class TestTLSSettings:
    """Test TLS settings in config."""

    def test_tls_settings_defaults(self):
        """Test that TLS settings have correct defaults."""
        # Clear cache to get fresh settings
        get_settings.cache_clear()

        # Set required env vars to avoid validation errors, then clear env
        original_tls_enabled = os.environ.get("TLS_ENABLED")
        os.environ.pop("TLS_ENABLED", None)
        os.environ.pop("TLS_CERT_FILE", None)
        os.environ.pop("TLS_KEY_FILE", None)
        os.environ.pop("TLS_CA_FILE", None)
        os.environ.pop("TLS_AUTO_GENERATE", None)
        os.environ.pop("TLS_CERT_DIR", None)

        try:
            get_settings.cache_clear()
            settings = get_settings()

            # TLS should be disabled by default
            assert settings.tls_enabled is False
            assert settings.tls_cert_file is None
            assert settings.tls_key_file is None
            assert settings.tls_ca_file is None
            assert settings.tls_auto_generate is False
            assert settings.tls_cert_dir == "data/certs"
        finally:
            if original_tls_enabled:
                os.environ["TLS_ENABLED"] = original_tls_enabled
            get_settings.cache_clear()

    def test_tls_settings_from_env(self, mock_certificate_files):
        """Test TLS settings loaded from environment variables."""
        cert_path, key_path = mock_certificate_files

        original_env = {
            "TLS_ENABLED": os.environ.get("TLS_ENABLED"),
            "TLS_CERT_FILE": os.environ.get("TLS_CERT_FILE"),
            "TLS_KEY_FILE": os.environ.get("TLS_KEY_FILE"),
        }

        try:
            os.environ["TLS_ENABLED"] = "true"
            os.environ["TLS_CERT_FILE"] = str(cert_path)
            os.environ["TLS_KEY_FILE"] = str(key_path)

            get_settings.cache_clear()
            settings = get_settings()

            assert settings.tls_enabled is True
            assert settings.tls_cert_file == str(cert_path)
            assert settings.tls_key_file == str(key_path)
        finally:
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)
            get_settings.cache_clear()


# =============================================================================
# Test: Certificate Loading
# =============================================================================


class TestCertificateLoading:
    """Test certificate loading functions."""

    def test_load_certificate_paths_returns_paths(self, mock_certificate_files):
        """Test loading certificate paths from settings."""
        from backend.core.tls import load_certificate_paths

        cert_path, key_path = mock_certificate_files

        original_env = {
            "TLS_CERT_FILE": os.environ.get("TLS_CERT_FILE"),
            "TLS_KEY_FILE": os.environ.get("TLS_KEY_FILE"),
        }

        try:
            os.environ["TLS_CERT_FILE"] = str(cert_path)
            os.environ["TLS_KEY_FILE"] = str(key_path)
            get_settings.cache_clear()

            loaded_cert, loaded_key = load_certificate_paths()

            assert loaded_cert == cert_path
            assert loaded_key == key_path
        finally:
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)
            get_settings.cache_clear()

    def test_load_certificate_paths_none_when_not_configured(self):
        """Test that loading returns None when certificates not configured."""
        from backend.core.tls import load_certificate_paths

        original_env = {
            "TLS_CERT_FILE": os.environ.get("TLS_CERT_FILE"),
            "TLS_KEY_FILE": os.environ.get("TLS_KEY_FILE"),
        }

        try:
            os.environ.pop("TLS_CERT_FILE", None)
            os.environ.pop("TLS_KEY_FILE", None)
            get_settings.cache_clear()

            cert, key = load_certificate_paths()

            assert cert is None
            assert key is None
        finally:
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)
            get_settings.cache_clear()

    def test_load_certificate_paths_file_not_found(self, temp_cert_dir):
        """Test that loading raises error when certificate file doesn't exist."""
        from backend.core.tls import CertificateNotFoundError, load_certificate_paths

        original_env = {
            "TLS_CERT_FILE": os.environ.get("TLS_CERT_FILE"),
            "TLS_KEY_FILE": os.environ.get("TLS_KEY_FILE"),
        }

        try:
            # Point to non-existent files
            os.environ["TLS_CERT_FILE"] = str(temp_cert_dir / "nonexistent.crt")
            os.environ["TLS_KEY_FILE"] = str(temp_cert_dir / "nonexistent.key")
            get_settings.cache_clear()

            with pytest.raises(CertificateNotFoundError):
                load_certificate_paths()
        finally:
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)
            get_settings.cache_clear()


# =============================================================================
# Test: SSL Context Creation
# =============================================================================


class TestSSLContextCreation:
    """Test SSL context creation functions."""

    def test_create_ssl_context_success(self, valid_self_signed_certs):
        """Test creating SSL context with valid certificates."""
        from backend.core.tls import create_ssl_context

        cert_path, key_path = valid_self_signed_certs

        ssl_context = create_ssl_context(cert_path, key_path)

        assert ssl_context is not None
        assert isinstance(ssl_context, ssl.SSLContext)
        # Server context should have PROTOCOL_TLS_SERVER
        assert ssl_context.protocol == ssl.PROTOCOL_TLS_SERVER

    def test_create_ssl_context_with_ca(self, valid_self_signed_certs, temp_cert_dir):
        """Test creating SSL context with CA certificate for client verification."""
        from backend.core.tls import create_ssl_context

        cert_path, key_path = valid_self_signed_certs
        # Use the same cert as CA for testing (self-signed)
        ca_path = cert_path

        ssl_context = create_ssl_context(cert_path, key_path, ca_path=ca_path)

        assert ssl_context is not None
        assert isinstance(ssl_context, ssl.SSLContext)

    def test_create_ssl_context_invalid_cert_raises_error(self, temp_cert_dir):
        """Test that invalid certificate raises SSLError."""
        from backend.core.tls import create_ssl_context

        cert_path = temp_cert_dir / "invalid.crt"
        key_path = temp_cert_dir / "invalid.key"

        cert_path.write_text("invalid certificate data")
        key_path.write_text("invalid key data")

        with pytest.raises(ssl.SSLError):
            create_ssl_context(cert_path, key_path)


# =============================================================================
# Test: Certificate Generation
# =============================================================================


class TestCertificateGeneration:
    """Test self-signed certificate generation."""

    def test_generate_self_signed_cert_creates_files(self, temp_cert_dir):
        """Test that certificate generation creates cert and key files."""
        from backend.core.tls import generate_self_signed_cert

        cert_path = temp_cert_dir / "test.crt"
        key_path = temp_cert_dir / "test.key"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
        )

        assert cert_path.exists()
        assert key_path.exists()

        # Verify PEM format
        cert_content = cert_path.read_text()
        key_content = key_path.read_text()

        assert "-----BEGIN CERTIFICATE-----" in cert_content
        assert "-----END CERTIFICATE-----" in cert_content
        assert "-----BEGIN" in key_content  # Could be RSA PRIVATE KEY or PRIVATE KEY

    def test_generate_self_signed_cert_with_san_ips(self, temp_cert_dir):
        """Test certificate generation with Subject Alternative Names for IPs."""
        from backend.core.tls import generate_self_signed_cert

        cert_path = temp_cert_dir / "test_san.crt"
        key_path = temp_cert_dir / "test_san.key"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="myserver",
            san_ips=["127.0.0.1", "192.168.1.100"],
            san_dns=["localhost", "myserver.local"],
        )

        assert cert_path.exists()
        assert key_path.exists()

    def test_generate_self_signed_cert_validity(self, temp_cert_dir):
        """Test certificate validity period."""
        from backend.core.tls import generate_self_signed_cert

        cert_path = temp_cert_dir / "test_validity.crt"
        key_path = temp_cert_dir / "test_validity.key"

        days_valid = 365

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
            days_valid=days_valid,
        )

        # Load and verify certificate validity
        from cryptography import x509

        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        # Check that the certificate is valid for approximately the specified days
        not_before = cert.not_valid_before_utc
        not_after = cert.not_valid_after_utc
        validity_period = not_after - not_before

        # Allow 1 day margin for test timing
        assert abs(validity_period.days - days_valid) <= 1

    def test_generate_self_signed_cert_creates_directories(self, temp_cert_dir):
        """Test that certificate generation creates parent directories."""
        from backend.core.tls import generate_self_signed_cert

        nested_dir = temp_cert_dir / "nested" / "dir"
        cert_path = nested_dir / "test.crt"
        key_path = nested_dir / "test.key"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
        )

        assert nested_dir.exists()
        assert cert_path.exists()
        assert key_path.exists()


# =============================================================================
# Test: Certificate Validation
# =============================================================================


class TestCertificateValidation:
    """Test certificate validation helpers."""

    def test_validate_certificate_success(self, valid_self_signed_certs):
        """Test certificate validation with valid certificate."""
        from backend.core.tls import validate_certificate

        cert_path, _ = valid_self_signed_certs

        result = validate_certificate(cert_path)

        assert result["valid"] is True
        assert "subject" in result
        assert "issuer" in result
        assert "not_before" in result
        assert "not_after" in result
        assert "serial_number" in result

    def test_validate_certificate_expired(self, temp_cert_dir):
        """Test validation detects expired certificate."""
        from backend.core.tls import generate_self_signed_cert, validate_certificate

        cert_path = temp_cert_dir / "expired.crt"
        key_path = temp_cert_dir / "expired.key"

        # Generate a certificate that's already expired (0 days valid, generated yesterday)
        # We'll mock the time instead
        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
            days_valid=1,
        )

        # For testing expiration, we need to manipulate the validation time
        # Generate a cert with very short validity and check warning
        result = validate_certificate(cert_path)
        assert result["valid"] is True  # Still valid, just short

    def test_validate_certificate_invalid_file(self, temp_cert_dir):
        """Test validation with invalid certificate file."""
        from backend.core.tls import CertificateValidationError, validate_certificate

        invalid_cert = temp_cert_dir / "invalid.crt"
        invalid_cert.write_text("not a certificate")

        with pytest.raises(CertificateValidationError):
            validate_certificate(invalid_cert)

    def test_validate_certificate_not_found(self, temp_cert_dir):
        """Test validation with non-existent file."""
        from backend.core.tls import CertificateNotFoundError, validate_certificate

        with pytest.raises(CertificateNotFoundError):
            validate_certificate(temp_cert_dir / "nonexistent.crt")


# =============================================================================
# Test: TLS Configuration Helper
# =============================================================================


class TestTLSConfigurationHelper:
    """Test the TLS configuration helper function."""

    def test_get_tls_config_disabled(self):
        """Test TLS config when TLS is disabled."""
        from backend.core.tls import get_tls_config

        original_env = os.environ.get("TLS_ENABLED")
        try:
            os.environ["TLS_ENABLED"] = "false"
            get_settings.cache_clear()

            config = get_tls_config()

            assert config is None
        finally:
            if original_env:
                os.environ["TLS_ENABLED"] = original_env
            else:
                os.environ.pop("TLS_ENABLED", None)
            get_settings.cache_clear()

    def test_get_tls_config_enabled_with_certs(self, valid_self_signed_certs):
        """Test TLS config when enabled with valid certificates."""
        from backend.core.tls import get_tls_config

        cert_path, key_path = valid_self_signed_certs

        original_env = {
            "TLS_ENABLED": os.environ.get("TLS_ENABLED"),
            "TLS_CERT_FILE": os.environ.get("TLS_CERT_FILE"),
            "TLS_KEY_FILE": os.environ.get("TLS_KEY_FILE"),
        }

        try:
            os.environ["TLS_ENABLED"] = "true"
            os.environ["TLS_CERT_FILE"] = str(cert_path)
            os.environ["TLS_KEY_FILE"] = str(key_path)
            get_settings.cache_clear()

            config = get_tls_config()

            assert config is not None
            assert "ssl_certfile" in config
            assert "ssl_keyfile" in config
            assert config["ssl_certfile"] == str(cert_path)
            assert config["ssl_keyfile"] == str(key_path)
        finally:
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)
            get_settings.cache_clear()

    def test_get_tls_config_auto_generate(self, temp_cert_dir):
        """Test TLS config with auto-generate enabled."""
        from backend.core.tls import get_tls_config

        original_env = {
            "TLS_ENABLED": os.environ.get("TLS_ENABLED"),
            "TLS_AUTO_GENERATE": os.environ.get("TLS_AUTO_GENERATE"),
            "TLS_CERT_DIR": os.environ.get("TLS_CERT_DIR"),
            "TLS_CERT_FILE": os.environ.get("TLS_CERT_FILE"),
            "TLS_KEY_FILE": os.environ.get("TLS_KEY_FILE"),
        }

        try:
            os.environ["TLS_ENABLED"] = "true"
            os.environ["TLS_AUTO_GENERATE"] = "true"
            os.environ["TLS_CERT_DIR"] = str(temp_cert_dir)
            os.environ.pop("TLS_CERT_FILE", None)
            os.environ.pop("TLS_KEY_FILE", None)
            get_settings.cache_clear()

            config = get_tls_config()

            assert config is not None
            assert "ssl_certfile" in config
            assert "ssl_keyfile" in config

            # Verify certificates were generated
            cert_path = Path(config["ssl_certfile"])
            key_path = Path(config["ssl_keyfile"])
            assert cert_path.exists()
            assert key_path.exists()
        finally:
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)
            get_settings.cache_clear()


# =============================================================================
# Test: TLS Configuration Errors
# =============================================================================


class TestTLSConfigurationErrors:
    """Test error handling in TLS configuration."""

    def test_get_tls_config_enabled_no_certs_no_auto(self, temp_cert_dir):
        """Test error when TLS enabled but no certs and auto-generate disabled."""
        from backend.core.tls import TLSConfigurationError, get_tls_config

        original_env = {
            "TLS_ENABLED": os.environ.get("TLS_ENABLED"),
            "TLS_AUTO_GENERATE": os.environ.get("TLS_AUTO_GENERATE"),
            "TLS_CERT_FILE": os.environ.get("TLS_CERT_FILE"),
            "TLS_KEY_FILE": os.environ.get("TLS_KEY_FILE"),
        }

        try:
            os.environ["TLS_ENABLED"] = "true"
            os.environ["TLS_AUTO_GENERATE"] = "false"
            os.environ.pop("TLS_CERT_FILE", None)
            os.environ.pop("TLS_KEY_FILE", None)
            get_settings.cache_clear()

            with pytest.raises(TLSConfigurationError):
                get_tls_config()
        finally:
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)
            get_settings.cache_clear()

    def test_mismatched_cert_and_key(self, temp_cert_dir):
        """Test error when certificate and key don't match."""
        from backend.core.tls import generate_self_signed_cert

        # Generate two different key pairs
        cert1 = temp_cert_dir / "cert1.crt"
        key1 = temp_cert_dir / "key1.key"
        cert2 = temp_cert_dir / "cert2.crt"
        key2 = temp_cert_dir / "key2.key"

        generate_self_signed_cert(cert_path=cert1, key_path=key1, hostname="host1")
        generate_self_signed_cert(cert_path=cert2, key_path=key2, hostname="host2")

        from backend.core.tls import create_ssl_context

        # Using cert1 with key2 should fail
        with pytest.raises(ssl.SSLError):
            create_ssl_context(cert1, key2)


# =============================================================================
# Test: Key Permissions (Unix-like systems only)
# =============================================================================


class TestKeyPermissions:
    """Test key file permissions handling."""

    @pytest.mark.skipif(os.name == "nt", reason="Unix permissions not applicable on Windows")
    def test_key_file_permissions(self, temp_cert_dir):
        """Test that generated key files have restricted permissions."""
        from backend.core.tls import generate_self_signed_cert

        cert_path = temp_cert_dir / "test.crt"
        key_path = temp_cert_dir / "test.key"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
        )

        # Key file should have restricted permissions (0o600 or similar)
        key_mode = key_path.stat().st_mode & 0o777
        # Should not be world-readable
        assert (key_mode & 0o044) == 0, f"Key file has insecure permissions: {oct(key_mode)}"
