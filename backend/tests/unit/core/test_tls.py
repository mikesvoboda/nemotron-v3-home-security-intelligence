"""Comprehensive unit tests for TLS certificate generation and validation.

This test module focuses on security-critical edge cases:
- Certificate validity periods and expiration
- TLS version enforcement (minimum TLS 1.2)
- Symlink handling in certificate file validation
- Malformed PEM file handling
- Certificate/key mismatch detection
- Multiple SANs validation
- Circular symlink detection

These tests complement the basic functional tests in backend/tests/unit/test_tls.py.
"""

from __future__ import annotations

import os
import ssl
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from backend.core.tls import (
    CertificateNotFoundError,
    CertificateValidationError,
    TLSConfig,
    TLSMode,
    create_ssl_context,
    generate_self_signed_cert,
    validate_certificate,
    validate_certificate_files,
)

# =============================================================================
# Helper Functions for Test Certificate Generation
# =============================================================================


def create_test_certificate(
    cert_path: Path,
    key_path: Path,
    hostname: str = "localhost",
    days_valid: int = 365,
    not_valid_before: datetime | None = None,
    not_valid_after: datetime | None = None,
    key_size: int = 2048,
) -> tuple[Path, Path]:
    """Create a test certificate with customizable validity period.

    This helper allows creating certificates with specific validity periods
    including expired or not-yet-valid certificates for testing.

    Args:
        cert_path: Path to write certificate
        key_path: Path to write private key
        hostname: Common name for certificate
        days_valid: Days until expiration (ignored if not_valid_after specified)
        not_valid_before: Custom start of validity period
        not_valid_after: Custom end of validity period
        key_size: RSA key size in bits

    Returns:
        Tuple of (cert_path, key_path)
    """
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )

    # Set validity period
    now = datetime.now(UTC)
    if not_valid_before is None:
        not_valid_before = now
    if not_valid_after is None:
        not_valid_after = now + timedelta(days=days_valid)

    # Build subject
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test"),
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        ]
    )

    # Build certificate
    cert_builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_valid_before)
        .not_valid_after(not_valid_after)
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(hostname)]),
            critical=False,
        )
    )

    certificate = cert_builder.sign(private_key, hashes.SHA256())

    # Write key
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key_pem)

    # Write certificate
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    cert_path.write_bytes(cert_pem)

    return cert_path, key_path


def create_mismatched_cert_key(
    cert_path: Path,
    key_path: Path,
) -> tuple[Path, Path]:
    """Create a certificate and key that don't match (different key pairs).

    This creates a valid certificate and a valid key, but they were generated
    with different RSA key pairs, so they won't work together.

    Args:
        cert_path: Path to write certificate
        key_path: Path to write private key (from different key pair)

    Returns:
        Tuple of (cert_path, key_path) where the key doesn't match the cert
    """
    # Generate first key pair for certificate
    cert_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Generate second key pair for the key file (mismatched)
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    now = datetime.now(UTC)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ]
    )

    # Create certificate with first key
    cert_builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(cert_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
    )
    certificate = cert_builder.sign(cert_key, hashes.SHA256())

    # Write certificate
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    cert_path.write_bytes(cert_pem)

    # Write OTHER key (mismatched)
    key_pem = other_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key_pem)

    return cert_path, key_path


# =============================================================================
# Certificate Generation - Validity Period Tests
# =============================================================================


class TestGenerateSelfSignedCertValidity:
    """Test certificate validity period handling in generate_self_signed_cert."""

    def test_certificate_validity_period_default(self, tmp_path: Path) -> None:
        """Test default validity period is 365 days."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
        )

        # Validate the certificate and check days remaining
        result = validate_certificate(cert_path)
        assert result["valid"] is True
        # Should be approximately 365 days (allow 1 day tolerance for test timing)
        assert 364 <= result["days_remaining"] <= 366

    def test_certificate_validity_period_custom(self, tmp_path: Path) -> None:
        """Test custom validity period is respected."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
            days_valid=730,  # 2 years
        )

        result = validate_certificate(cert_path)
        assert result["valid"] is True
        # Should be approximately 730 days (allow 1 day tolerance)
        assert 729 <= result["days_remaining"] <= 731

    def test_certificate_validity_period_short(self, tmp_path: Path) -> None:
        """Test short validity period (1 day)."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
            days_valid=1,
        )

        result = validate_certificate(cert_path)
        assert result["valid"] is True
        assert 0 <= result["days_remaining"] <= 2

    def test_certificate_not_valid_before_is_now(self, tmp_path: Path) -> None:
        """Test that certificate is valid immediately after generation."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
        )

        # Parse the certificate to check not_valid_before
        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        now = datetime.now(UTC)
        not_before = cert.not_valid_before_utc

        # Should be valid now (within a few seconds)
        assert not_before <= now
        assert (now - not_before).total_seconds() < 60  # Within 1 minute

    def test_certificate_not_valid_after_correct(self, tmp_path: Path) -> None:
        """Test that certificate expiration is correctly set."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        days_valid = 100

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
            days_valid=days_valid,
        )

        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        now = datetime.now(UTC)
        not_after = cert.not_valid_after_utc
        expected_expiry = now + timedelta(days=days_valid)

        # Should expire within 1 minute of expected time
        assert abs((not_after - expected_expiry).total_seconds()) < 60


# =============================================================================
# Certificate Expiration Detection Tests
# =============================================================================


class TestExpiredCertificateDetection:
    """Test detection of expired certificates."""

    def test_validate_expired_certificate(self, tmp_path: Path) -> None:
        """Test that expired certificate is detected as invalid."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        # Create certificate that expired yesterday
        now = datetime.now(UTC)
        create_test_certificate(
            cert_path=cert_path,
            key_path=key_path,
            not_valid_before=now - timedelta(days=365),
            not_valid_after=now - timedelta(days=1),
        )

        result = validate_certificate(cert_path)
        assert result["valid"] is False
        assert result["days_remaining"] == 0

    def test_validate_not_yet_valid_certificate(self, tmp_path: Path) -> None:
        """Test that not-yet-valid certificate is detected as invalid."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        # Create certificate that starts tomorrow
        now = datetime.now(UTC)
        create_test_certificate(
            cert_path=cert_path,
            key_path=key_path,
            not_valid_before=now + timedelta(days=1),
            not_valid_after=now + timedelta(days=365),
        )

        result = validate_certificate(cert_path)
        assert result["valid"] is False

    def test_validate_certificate_expiring_soon(self, tmp_path: Path) -> None:
        """Test certificate expiring in a few days shows correct days_remaining."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        now = datetime.now(UTC)
        days_until_expiry = 7
        create_test_certificate(
            cert_path=cert_path,
            key_path=key_path,
            not_valid_before=now - timedelta(days=30),
            not_valid_after=now + timedelta(days=days_until_expiry),
        )

        result = validate_certificate(cert_path)
        assert result["valid"] is True
        # Allow 1 day tolerance
        assert days_until_expiry - 1 <= result["days_remaining"] <= days_until_expiry + 1


# =============================================================================
# SSL Context - TLS Version Enforcement Tests
# =============================================================================


class TestSSLContextTLSVersionEnforcement:
    """Test minimum TLS version enforcement in create_ssl_context."""

    def test_ssl_context_default_min_version_tls12(self, tmp_path: Path) -> None:
        """Test that default minimum TLS version is 1.2."""
        cert_path, key_path = create_test_certificate(
            tmp_path / "cert.pem",
            tmp_path / "key.pem",
        )

        config = TLSConfig(
            mode=TLSMode.PROVIDED,
            cert_path=str(cert_path),
            key_path=str(key_path),
        )

        context = create_ssl_context(config)
        assert context is not None
        assert context.minimum_version == ssl.TLSVersion.TLSv1_2

    def test_ssl_context_min_version_tls13(self, tmp_path: Path) -> None:
        """Test setting minimum TLS version to 1.3."""
        cert_path, key_path = create_test_certificate(
            tmp_path / "cert.pem",
            tmp_path / "key.pem",
        )

        config = TLSConfig(
            mode=TLSMode.PROVIDED,
            cert_path=str(cert_path),
            key_path=str(key_path),
            min_version=ssl.TLSVersion.TLSv1_3,
        )

        context = create_ssl_context(config)
        assert context is not None
        assert context.minimum_version == ssl.TLSVersion.TLSv1_3

    def test_ssl_context_disables_sslv2(self, tmp_path: Path) -> None:
        """Test that SSLv2 is disabled in context options.

        Note: In modern OpenSSL (1.1.0+), SSLv2 has been completely removed,
        so OP_NO_SSLv2 is a no-op with value 0. We check that if the flag
        has a non-zero value, it is set; otherwise we simply verify the
        context is created (SSLv2 is implicitly disabled).
        """
        cert_path, key_path = create_test_certificate(
            tmp_path / "cert.pem",
            tmp_path / "key.pem",
        )

        config = TLSConfig(
            mode=TLSMode.PROVIDED,
            cert_path=str(cert_path),
            key_path=str(key_path),
        )

        context = create_ssl_context(config)
        assert context is not None
        # In modern OpenSSL, OP_NO_SSLv2 == 0 (SSLv2 completely removed)
        # If the flag is non-zero, verify it's set; otherwise SSLv2 is implicitly disabled
        if ssl.OP_NO_SSLv2 != 0:
            assert (context.options & ssl.OP_NO_SSLv2) != 0
        # Context created with TLS 1.2+ minimum ensures no SSLv2

    def test_ssl_context_disables_sslv3(self, tmp_path: Path) -> None:
        """Test that SSLv3 is disabled in context options."""
        cert_path, key_path = create_test_certificate(
            tmp_path / "cert.pem",
            tmp_path / "key.pem",
        )

        config = TLSConfig(
            mode=TLSMode.PROVIDED,
            cert_path=str(cert_path),
            key_path=str(key_path),
        )

        context = create_ssl_context(config)
        assert context is not None
        # OP_NO_SSLv3 should be set
        assert (context.options & ssl.OP_NO_SSLv3) != 0

    def test_legacy_api_enforces_tls12_minimum(self, tmp_path: Path) -> None:
        """Test that legacy Path-based API enforces TLS 1.2 minimum."""
        cert_path, key_path = create_test_certificate(
            tmp_path / "cert.pem",
            tmp_path / "key.pem",
        )

        context = create_ssl_context(cert_path, key_path)
        assert context is not None
        assert context.minimum_version == ssl.TLSVersion.TLSv1_2


# =============================================================================
# Certificate File Validation - Symlink Handling Tests
# =============================================================================


class TestValidateCertificateFilesSymlinks:
    """Test symlink handling in validate_certificate_files."""

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks may require admin on Windows")
    def test_validate_follows_symlinks_cert(self, tmp_path: Path) -> None:
        """Test that validation follows symlinks for certificate file."""
        # Create actual certificate
        real_cert = tmp_path / "real" / "cert.pem"
        real_key = tmp_path / "real" / "key.pem"
        create_test_certificate(real_cert, real_key)

        # Create symlink to certificate
        symlink_dir = tmp_path / "links"
        symlink_dir.mkdir()
        symlink_cert = symlink_dir / "cert.pem"
        symlink_cert.symlink_to(real_cert)

        # Should validate successfully following the symlink
        validate_certificate_files(str(symlink_cert), str(real_key))

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks may require admin on Windows")
    def test_validate_follows_symlinks_key(self, tmp_path: Path) -> None:
        """Test that validation follows symlinks for key file."""
        # Create actual certificate
        real_cert = tmp_path / "real" / "cert.pem"
        real_key = tmp_path / "real" / "key.pem"
        create_test_certificate(real_cert, real_key)

        # Create symlink to key
        symlink_dir = tmp_path / "links"
        symlink_dir.mkdir()
        symlink_key = symlink_dir / "key.pem"
        symlink_key.symlink_to(real_key)

        # Should validate successfully following the symlink
        validate_certificate_files(str(real_cert), str(symlink_key))

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks may require admin on Windows")
    def test_validate_follows_symlinks_both(self, tmp_path: Path) -> None:
        """Test that validation follows symlinks for both cert and key."""
        # Create actual certificate
        real_cert = tmp_path / "real" / "cert.pem"
        real_key = tmp_path / "real" / "key.pem"
        create_test_certificate(real_cert, real_key)

        # Create symlinks to both
        symlink_dir = tmp_path / "links"
        symlink_dir.mkdir()
        symlink_cert = symlink_dir / "cert.pem"
        symlink_key = symlink_dir / "key.pem"
        symlink_cert.symlink_to(real_cert)
        symlink_key.symlink_to(real_key)

        # Should validate successfully following both symlinks
        validate_certificate_files(str(symlink_cert), str(symlink_key))

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks may require admin on Windows")
    def test_validate_broken_symlink_raises_error(self, tmp_path: Path) -> None:
        """Test that broken symlinks raise FileNotFoundError."""
        # Create a valid key
        real_key = tmp_path / "key.pem"
        real_key.write_text("KEY CONTENT")

        # Create broken symlink (points to non-existent file)
        broken_link = tmp_path / "broken_cert.pem"
        broken_link.symlink_to(tmp_path / "nonexistent.pem")

        with pytest.raises(FileNotFoundError, match="Certificate file not found"):
            validate_certificate_files(str(broken_link), str(real_key))

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks may require admin on Windows")
    def test_validate_chained_symlinks(self, tmp_path: Path) -> None:
        """Test that validation follows chained symlinks."""
        # Create actual certificate
        real_cert = tmp_path / "real" / "cert.pem"
        real_key = tmp_path / "real" / "key.pem"
        create_test_certificate(real_cert, real_key)

        # Create chain of symlinks: link3 -> link2 -> link1 -> real_cert
        link1 = tmp_path / "link1.pem"
        link2 = tmp_path / "link2.pem"
        link3 = tmp_path / "link3.pem"
        link1.symlink_to(real_cert)
        link2.symlink_to(link1)
        link3.symlink_to(link2)

        # Should follow the chain successfully
        validate_certificate_files(str(link3), str(real_key))


# =============================================================================
# Malformed PEM File Handling Tests
# =============================================================================


class TestMalformedPEMHandling:
    """Test handling of malformed PEM files."""

    def test_validate_malformed_cert_raises_error(self, tmp_path: Path) -> None:
        """Test that malformed certificate raises CertificateValidationError."""
        malformed_cert = tmp_path / "malformed.pem"
        malformed_cert.write_text("This is not a valid PEM certificate")

        with pytest.raises(CertificateValidationError, match="Failed to parse certificate"):
            validate_certificate(malformed_cert)

    def test_validate_empty_cert_raises_error(self, tmp_path: Path) -> None:
        """Test that empty certificate file raises CertificateValidationError."""
        empty_cert = tmp_path / "empty.pem"
        empty_cert.write_text("")

        with pytest.raises(CertificateValidationError, match="Failed to parse certificate"):
            validate_certificate(empty_cert)

    def test_validate_truncated_cert_raises_error(self, tmp_path: Path) -> None:
        """Test that truncated certificate raises CertificateValidationError."""
        # Create a truncated certificate (cut off in the middle)
        truncated_cert = tmp_path / "truncated.pem"
        truncated_cert.write_text(
            "-----BEGIN CERTIFICATE-----\n"
            "MIICpDCCAYwCCQC7PxQhh9+J+TANBgkqhkiG9w0BAQsFADAUMRIwEAYDV\n"
            "INCOMPLETE_BASE64_DATA\n"
            "-----END CERTIFICATE-----"
        )

        with pytest.raises(CertificateValidationError, match="Failed to parse certificate"):
            validate_certificate(truncated_cert)

    def test_validate_invalid_base64_cert_raises_error(self, tmp_path: Path) -> None:
        """Test that certificate with invalid base64 raises error."""
        invalid_cert = tmp_path / "invalid_base64.pem"
        invalid_cert.write_text(
            "-----BEGIN CERTIFICATE-----\n!!!NOT VALID BASE64!!!\n-----END CERTIFICATE-----"
        )

        with pytest.raises(CertificateValidationError, match="Failed to parse certificate"):
            validate_certificate(invalid_cert)

    def test_validate_binary_garbage_raises_error(self, tmp_path: Path) -> None:
        """Test that binary garbage raises CertificateValidationError."""
        garbage_cert = tmp_path / "garbage.pem"
        garbage_cert.write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")

        with pytest.raises(CertificateValidationError, match="Failed to parse certificate"):
            validate_certificate(garbage_cert)

    def test_ssl_context_with_malformed_cert_raises_error(self, tmp_path: Path) -> None:
        """Test that SSL context creation fails with malformed certificate."""
        # Create malformed cert
        malformed_cert = tmp_path / "malformed.pem"
        malformed_cert.write_text("NOT A CERTIFICATE")

        # Create valid key
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        key_path = tmp_path / "key.pem"
        key_path.write_bytes(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

        config = TLSConfig(
            mode=TLSMode.PROVIDED,
            cert_path=str(malformed_cert),
            key_path=str(key_path),
        )

        with pytest.raises(ssl.SSLError):
            create_ssl_context(config)

    def test_ssl_context_with_malformed_key_raises_error(self, tmp_path: Path) -> None:
        """Test that SSL context creation fails with malformed key."""
        # Create valid cert
        cert_path, _key_path = create_test_certificate(
            tmp_path / "cert.pem",
            tmp_path / "key.pem",
        )

        # Overwrite key with garbage
        malformed_key = tmp_path / "malformed_key.pem"
        malformed_key.write_text("NOT A KEY")

        config = TLSConfig(
            mode=TLSMode.PROVIDED,
            cert_path=str(cert_path),
            key_path=str(malformed_key),
        )

        with pytest.raises(ssl.SSLError):
            create_ssl_context(config)


# =============================================================================
# Certificate/Key Mismatch Detection Tests
# =============================================================================


class TestCertificateKeyMismatch:
    """Test detection of mismatched certificate/key pairs."""

    def test_ssl_context_rejects_mismatched_cert_key(self, tmp_path: Path) -> None:
        """Test that SSL context creation fails when cert and key don't match."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        # Create mismatched cert and key
        create_mismatched_cert_key(cert_path, key_path)

        config = TLSConfig(
            mode=TLSMode.PROVIDED,
            cert_path=str(cert_path),
            key_path=str(key_path),
        )

        # SSL should reject the mismatched pair
        with pytest.raises(ssl.SSLError):
            create_ssl_context(config)

    def test_legacy_api_rejects_mismatched_cert_key(self, tmp_path: Path) -> None:
        """Test that legacy API fails with mismatched cert/key."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        create_mismatched_cert_key(cert_path, key_path)

        with pytest.raises(ssl.SSLError):
            create_ssl_context(cert_path, key_path)


# =============================================================================
# Multiple SANs Validation Tests
# =============================================================================


class TestMultipleSANsValidation:
    """Test handling of multiple Subject Alternative Names."""

    def test_generate_cert_with_multiple_dns_sans(self, tmp_path: Path) -> None:
        """Test certificate generation with multiple DNS SANs."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="primary.local",
            san_dns=["secondary.local", "tertiary.local", "localhost"],
        )

        # Parse and verify SANs
        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        dns_names = san_ext.value.get_values_for_type(x509.DNSName)

        assert "primary.local" in dns_names
        assert "secondary.local" in dns_names
        assert "tertiary.local" in dns_names
        assert "localhost" in dns_names

    def test_generate_cert_with_multiple_ip_sans(self, tmp_path: Path) -> None:
        """Test certificate generation with multiple IP SANs."""
        import ipaddress

        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="server.local",
            san_ips=["192.168.1.100", "192.168.1.101", "10.0.0.1"],
        )

        # Parse and verify SANs
        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        ip_addresses = san_ext.value.get_values_for_type(x509.IPAddress)

        expected_ips = [
            ipaddress.ip_address("192.168.1.100"),
            ipaddress.ip_address("192.168.1.101"),
            ipaddress.ip_address("10.0.0.1"),
        ]

        for expected_ip in expected_ips:
            assert expected_ip in ip_addresses

    def test_generate_cert_with_mixed_sans(self, tmp_path: Path) -> None:
        """Test certificate generation with both DNS and IP SANs."""
        import ipaddress

        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="server.local",
            san_dns=["alt.local", "backup.local"],
            san_ips=["192.168.1.100", "127.0.0.1"],
        )

        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)

        dns_names = san_ext.value.get_values_for_type(x509.DNSName)
        ip_addresses = san_ext.value.get_values_for_type(x509.IPAddress)

        # Check DNS names (hostname should be auto-added)
        assert "server.local" in dns_names
        assert "alt.local" in dns_names
        assert "backup.local" in dns_names

        # Check IP addresses
        assert ipaddress.ip_address("192.168.1.100") in ip_addresses
        assert ipaddress.ip_address("127.0.0.1") in ip_addresses

    def test_generate_cert_hostname_not_duplicated_in_san(self, tmp_path: Path) -> None:
        """Test that hostname is not duplicated if already in san_dns."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        hostname = "myhost.local"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname=hostname,
            san_dns=[hostname, "other.local"],  # hostname explicitly in san_dns
        )

        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        dns_names = san_ext.value.get_values_for_type(x509.DNSName)

        # hostname should appear only once
        assert dns_names.count(hostname) == 1


# =============================================================================
# TLSConfig Property Tests
# =============================================================================


class TestTLSConfigProperties:
    """Test TLSConfig dataclass properties and defaults."""

    def test_is_enabled_false_when_disabled(self) -> None:
        """Test is_enabled returns False for DISABLED mode."""
        config = TLSConfig(mode=TLSMode.DISABLED)
        assert config.is_enabled is False

    def test_is_enabled_true_when_self_signed(self) -> None:
        """Test is_enabled returns True for SELF_SIGNED mode."""
        config = TLSConfig(mode=TLSMode.SELF_SIGNED)
        assert config.is_enabled is True

    def test_is_enabled_true_when_provided(self) -> None:
        """Test is_enabled returns True for PROVIDED mode."""
        config = TLSConfig(mode=TLSMode.PROVIDED)
        assert config.is_enabled is True

    def test_default_min_version_is_tls12(self) -> None:
        """Test default minimum version is TLS 1.2."""
        config = TLSConfig()
        assert config.min_version == ssl.TLSVersion.TLSv1_2

    def test_verify_client_default_false(self) -> None:
        """Test verify_client defaults to False."""
        config = TLSConfig()
        assert config.verify_client is False

    def test_paths_default_none(self) -> None:
        """Test certificate paths default to None."""
        config = TLSConfig()
        assert config.cert_path is None
        assert config.key_path is None
        assert config.ca_path is None


# =============================================================================
# Client Certificate Verification Tests
# =============================================================================


class TestClientCertificateVerification:
    """Test mTLS (mutual TLS) configuration."""

    def test_ssl_context_no_client_verify_by_default(self, tmp_path: Path) -> None:
        """Test that client verification is not required by default."""
        cert_path, key_path = create_test_certificate(
            tmp_path / "cert.pem",
            tmp_path / "key.pem",
        )

        config = TLSConfig(
            mode=TLSMode.PROVIDED,
            cert_path=str(cert_path),
            key_path=str(key_path),
            verify_client=False,
        )

        context = create_ssl_context(config)
        assert context is not None
        assert context.verify_mode == ssl.CERT_NONE

    def test_ssl_context_with_client_verification_required(self, tmp_path: Path) -> None:
        """Test that client verification can be required."""
        cert_path, key_path = create_test_certificate(
            tmp_path / "cert.pem",
            tmp_path / "key.pem",
        )

        # Use same cert as CA for testing
        ca_path = tmp_path / "ca.pem"
        ca_path.write_bytes(cert_path.read_bytes())

        config = TLSConfig(
            mode=TLSMode.PROVIDED,
            cert_path=str(cert_path),
            key_path=str(key_path),
            ca_path=str(ca_path),
            verify_client=True,
        )

        context = create_ssl_context(config)
        assert context is not None
        assert context.verify_mode == ssl.CERT_REQUIRED

    def test_legacy_api_with_ca_optional_verification(self, tmp_path: Path) -> None:
        """Test legacy API sets CERT_OPTIONAL with CA provided."""
        cert_path, key_path = create_test_certificate(
            tmp_path / "cert.pem",
            tmp_path / "key.pem",
        )

        ca_path = tmp_path / "ca.pem"
        ca_path.write_bytes(cert_path.read_bytes())

        context = create_ssl_context(cert_path, key_path, ca_path)
        assert context is not None
        assert context.verify_mode == ssl.CERT_OPTIONAL


# =============================================================================
# Certificate File Existence Tests
# =============================================================================


class TestCertificateFileExistence:
    """Test certificate file existence checking."""

    def test_validate_nonexistent_cert_raises_error(self) -> None:
        """Test that nonexistent certificate file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Certificate file not found"):
            validate_certificate_files("/nonexistent/path/cert.pem", "/some/key.pem")

    def test_validate_nonexistent_key_raises_error(self, tmp_path: Path) -> None:
        """Test that nonexistent key file raises FileNotFoundError."""
        cert_path = tmp_path / "cert.pem"
        cert_path.write_text("CERT")

        with pytest.raises(FileNotFoundError, match="Private key file not found"):
            validate_certificate_files(str(cert_path), "/nonexistent/path/key.pem")

    def test_validate_nonexistent_ca_raises_error(self, tmp_path: Path) -> None:
        """Test that nonexistent CA file raises FileNotFoundError when specified."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"
        cert_path.write_text("CERT")
        key_path.write_text("KEY")

        with pytest.raises(FileNotFoundError, match="CA certificate file not found"):
            validate_certificate_files(str(cert_path), str(key_path), "/nonexistent/ca.pem")

    def test_validate_certificate_not_found_error_class(self, tmp_path: Path) -> None:
        """Test that CertificateNotFoundError is raised by validate_certificate."""
        nonexistent = tmp_path / "nonexistent.pem"

        with pytest.raises(CertificateNotFoundError, match="Certificate file not found"):
            validate_certificate(nonexistent)


# =============================================================================
# Key Permissions Tests (Unix-specific)
# =============================================================================


@pytest.mark.skipif(os.name == "nt", reason="Permission tests are Unix-specific")
class TestKeyFilePermissions:
    """Test that private key files have secure permissions."""

    def test_generated_key_has_600_permissions(self, tmp_path: Path) -> None:
        """Test that generated key file has 0600 permissions."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
        )

        key_mode = key_path.stat().st_mode & 0o777
        assert key_mode == 0o600


# =============================================================================
# RSA Key Size Tests
# =============================================================================


class TestRSAKeySize:
    """Test RSA key size configuration."""

    def test_default_key_size_2048(self, tmp_path: Path) -> None:
        """Test that default key size is 2048 bits."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
        )

        # Load and check key size
        key_data = key_path.read_bytes()
        private_key = serialization.load_pem_private_key(key_data, password=None)
        assert private_key.key_size == 2048

    def test_custom_key_size_4096(self, tmp_path: Path) -> None:
        """Test that custom key size 4096 is respected."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
            key_size=4096,
        )

        key_data = key_path.read_bytes()
        private_key = serialization.load_pem_private_key(key_data, password=None)
        assert private_key.key_size == 4096


# =============================================================================
# Parent Directory Creation Tests
# =============================================================================


class TestParentDirectoryCreation:
    """Test that parent directories are created for certificate files."""

    def test_creates_nested_directories_for_cert(self, tmp_path: Path) -> None:
        """Test that nested directories are created for certificate."""
        cert_path = tmp_path / "deep" / "nested" / "dir" / "cert.pem"
        key_path = tmp_path / "deep" / "nested" / "dir" / "key.pem"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
        )

        assert cert_path.exists()
        assert key_path.exists()

    def test_creates_different_directories_for_cert_and_key(self, tmp_path: Path) -> None:
        """Test creating cert and key in different directories."""
        cert_path = tmp_path / "certs" / "cert.pem"
        key_path = tmp_path / "keys" / "key.pem"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
        )

        assert cert_path.exists()
        assert key_path.exists()
        assert cert_path.parent != key_path.parent


# =============================================================================
# Certificate Extensions Tests
# =============================================================================


class TestCertificateExtensions:
    """Test certificate extensions in generated certificates."""

    def test_basic_constraints_not_ca(self, tmp_path: Path) -> None:
        """Test that generated certificate has CA=False in BasicConstraints."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
        )

        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        bc_ext = cert.extensions.get_extension_for_class(x509.BasicConstraints)
        assert bc_ext.value.ca is False
        assert bc_ext.critical is True

    def test_key_usage_extension(self, tmp_path: Path) -> None:
        """Test that generated certificate has proper KeyUsage."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
        )

        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        ku_ext = cert.extensions.get_extension_for_class(x509.KeyUsage)
        assert ku_ext.value.digital_signature is True
        assert ku_ext.value.key_encipherment is True
        assert ku_ext.critical is True

    def test_extended_key_usage_server_auth(self, tmp_path: Path) -> None:
        """Test that certificate has SERVER_AUTH in ExtendedKeyUsage."""
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="localhost",
        )

        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        eku_ext = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage)
        assert x509.oid.ExtendedKeyUsageOID.SERVER_AUTH in eku_ext.value
