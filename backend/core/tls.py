"""TLS/SSL configuration module for secure communications.

This module provides:
- TLS configuration loading from settings
- Self-signed certificate generation for LAN deployments
- SSL context creation for uvicorn
- Certificate validation helpers

Usage:
    from backend.core.tls import get_tls_config, generate_self_signed_cert

    # Get TLS config for uvicorn
    tls_config = get_tls_config()
    if tls_config:
        uvicorn.run(app, **tls_config)

    # Generate self-signed certificates
    generate_self_signed_cert(
        cert_path=Path("certs/server.crt"),
        key_path=Path("certs/server.key"),
        hostname="localhost",
        san_ips=["192.168.1.100"],
    )
"""

from __future__ import annotations

import ipaddress
import os
import socket
import ssl
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================


class TLSError(Exception):
    """Base exception for TLS-related errors."""

    pass


class TLSConfigurationError(TLSError):
    """Raised when TLS configuration is invalid or incomplete."""

    pass


class CertificateNotFoundError(TLSError):
    """Raised when a certificate or key file is not found."""

    pass


class CertificateValidationError(TLSError):
    """Raised when certificate validation fails."""

    pass


# =============================================================================
# Certificate Loading
# =============================================================================


def load_certificate_paths() -> tuple[Path | None, Path | None]:
    """Load certificate and key file paths from settings.

    Returns:
        Tuple of (cert_path, key_path) or (None, None) if not configured.

    Raises:
        CertificateNotFoundError: If configured paths don't exist.
    """
    settings = get_settings()

    if not settings.tls_cert_file or not settings.tls_key_file:
        return None, None

    cert_path = Path(settings.tls_cert_file)
    key_path = Path(settings.tls_key_file)

    if not cert_path.exists():
        raise CertificateNotFoundError(f"Certificate file not found: {cert_path}")

    if not key_path.exists():
        raise CertificateNotFoundError(f"Key file not found: {key_path}")

    return cert_path, key_path


# =============================================================================
# SSL Context Creation
# =============================================================================


def create_ssl_context(
    cert_path: Path,
    key_path: Path,
    ca_path: Path | None = None,
) -> ssl.SSLContext:
    """Create an SSL context for server use.

    Args:
        cert_path: Path to the certificate file (PEM format).
        key_path: Path to the private key file (PEM format).
        ca_path: Optional path to CA certificate for client verification.

    Returns:
        Configured SSL context for server use.

    Raises:
        ssl.SSLError: If certificate or key loading fails.
    """
    # Create server-side SSL context
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # Set minimum TLS version to 1.2 for security
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

    # Load certificate chain and private key
    ssl_context.load_cert_chain(
        certfile=str(cert_path),
        keyfile=str(key_path),
    )

    # If CA certificate provided, enable client certificate verification
    if ca_path:
        ssl_context.verify_mode = ssl.CERT_OPTIONAL
        ssl_context.load_verify_locations(cafile=str(ca_path))

    # Set reasonable cipher suite
    ssl_context.set_ciphers("ECDHE+AESGCM:DHE+AESGCM:ECDHE+CHACHA20:DHE+CHACHA20")

    logger.info("SSL context created", extra={"cert_path": str(cert_path)})

    return ssl_context


# =============================================================================
# Certificate Generation
# =============================================================================


def generate_self_signed_cert(
    cert_path: Path,
    key_path: Path,
    hostname: str,
    san_ips: list[str] | None = None,
    san_dns: list[str] | None = None,
    days_valid: int = 365,
    key_size: int = 2048,
) -> None:
    """Generate a self-signed certificate for LAN deployment.

    This creates a certificate suitable for internal/LAN use. For production
    deployments exposed to the internet, use proper CA-signed certificates.

    Args:
        cert_path: Where to write the certificate (PEM format).
        key_path: Where to write the private key (PEM format).
        hostname: Common Name (CN) for the certificate.
        san_ips: List of IP addresses for Subject Alternative Names.
        san_dns: List of DNS names for Subject Alternative Names.
        days_valid: Number of days the certificate is valid.
        key_size: RSA key size in bits (default 2048).

    Note:
        The private key file is created with restricted permissions (0o600)
        to prevent unauthorized access.
    """
    san_ips = san_ips or []
    san_dns = san_dns or []

    # Create parent directories if needed
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate RSA private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )

    # Build subject and issuer (same for self-signed)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Local"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "LAN"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Home Security Intelligence"),
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        ]
    )

    # Build Subject Alternative Names (SANs)
    san_entries: list[x509.GeneralName] = []

    # Add DNS names
    for dns_name in san_dns:
        san_entries.append(x509.DNSName(dns_name))

    # Add hostname as DNS name if not already in san_dns
    if hostname not in san_dns:
        san_entries.append(x509.DNSName(hostname))

    # Add IP addresses
    for ip_str in san_ips:
        try:
            ip_addr = ipaddress.ip_address(ip_str)
            san_entries.append(x509.IPAddress(ip_addr))
        except ValueError:
            logger.warning(f"Invalid IP address in SAN: {ip_str}")

    # Calculate validity period
    now = datetime.now(UTC)
    not_before = now
    not_after = now + timedelta(days=days_valid)

    # Build certificate
    cert_builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(
            x509.SubjectAlternativeName(san_entries),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
    )

    # Sign the certificate with the private key
    certificate = cert_builder.sign(private_key, hashes.SHA256())

    # Write private key with restricted permissions
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Write key file with restricted permissions (Unix only)
    key_path.write_bytes(key_pem)
    if os.name != "nt":  # Not Windows
        key_path.chmod(0o600)

    # Write certificate
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    cert_path.write_bytes(cert_pem)

    logger.info(
        "Self-signed certificate generated",
        extra={
            "cert_path": str(cert_path),
            "hostname": hostname,
            "days_valid": days_valid,
            "san_ips": san_ips,
            "san_dns": san_dns,
        },
    )


# =============================================================================
# Certificate Validation
# =============================================================================


def validate_certificate(cert_path: Path) -> dict[str, Any]:
    """Validate a certificate and return its details.

    Args:
        cert_path: Path to the certificate file (PEM format).

    Returns:
        Dictionary with certificate details:
        - valid: bool indicating if cert is currently valid
        - subject: Subject name string
        - issuer: Issuer name string
        - not_before: Validity start datetime
        - not_after: Validity end datetime
        - serial_number: Certificate serial number
        - days_remaining: Days until expiration

    Raises:
        CertificateNotFoundError: If certificate file doesn't exist.
        CertificateValidationError: If certificate cannot be parsed.
    """
    if not cert_path.exists():
        raise CertificateNotFoundError(f"Certificate file not found: {cert_path}")

    try:
        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)
    except Exception as e:
        raise CertificateValidationError(f"Failed to parse certificate: {e}") from e

    now = datetime.now(UTC)
    not_before = cert.not_valid_before_utc
    not_after = cert.not_valid_after_utc

    # Check if certificate is currently valid
    is_valid = not_before <= now <= not_after
    days_remaining = (not_after - now).days if is_valid else 0

    # Extract subject and issuer as strings
    subject_parts = []
    for attr in cert.subject:
        subject_parts.append(f"{attr.oid._name}={attr.value}")
    subject_str = ", ".join(subject_parts)

    issuer_parts = []
    for attr in cert.issuer:
        issuer_parts.append(f"{attr.oid._name}={attr.value}")
    issuer_str = ", ".join(issuer_parts)

    return {
        "valid": is_valid,
        "subject": subject_str,
        "issuer": issuer_str,
        "not_before": not_before.isoformat(),
        "not_after": not_after.isoformat(),
        "serial_number": str(cert.serial_number),
        "days_remaining": days_remaining,
    }


# =============================================================================
# TLS Configuration Helper
# =============================================================================


def get_tls_config() -> dict[str, Any] | None:
    """Get TLS configuration for uvicorn.

    This function handles the full TLS setup workflow:
    1. Check if TLS is enabled in settings
    2. If auto-generate is enabled and no certs exist, generate them
    3. Load and validate certificates
    4. Return uvicorn-compatible configuration

    Returns:
        Dictionary with uvicorn SSL parameters, or None if TLS disabled.
        Keys include:
        - ssl_certfile: Path to certificate file
        - ssl_keyfile: Path to private key file
        - ssl_ca_certs: Path to CA certificate (optional)

    Raises:
        TLSConfigurationError: If TLS enabled but configuration is invalid.
        CertificateNotFoundError: If required certificate files don't exist.
    """
    settings = get_settings()

    if not settings.tls_enabled:
        logger.debug("TLS is disabled")
        return None

    cert_path: Path | None = None
    key_path: Path | None = None

    # Check for configured certificate paths
    if settings.tls_cert_file and settings.tls_key_file:
        cert_path = Path(settings.tls_cert_file)
        key_path = Path(settings.tls_key_file)

        if not cert_path.exists() or not key_path.exists():
            raise CertificateNotFoundError(
                f"Configured certificates not found: {cert_path}, {key_path}"
            )

    # If no certificates configured, check auto-generate
    if cert_path is None or key_path is None:
        if settings.tls_auto_generate:
            # Generate self-signed certificates
            cert_dir = Path(settings.tls_cert_dir)
            cert_path = cert_dir / "server.crt"
            key_path = cert_dir / "server.key"

            if not cert_path.exists() or not key_path.exists():
                # Get hostname and local IPs for SANs
                hostname = socket.gethostname()
                local_ips = _get_local_ips()

                generate_self_signed_cert(
                    cert_path=cert_path,
                    key_path=key_path,
                    hostname=hostname,
                    san_ips=local_ips,
                    san_dns=[hostname, "localhost"],
                    days_valid=365,
                )

                logger.info(
                    "Auto-generated self-signed certificates",
                    extra={
                        "cert_path": str(cert_path),
                        "key_path": str(key_path),
                    },
                )
        else:
            raise TLSConfigurationError(
                "TLS enabled but no certificates configured and auto-generate is disabled. "
                "Either provide TLS_CERT_FILE and TLS_KEY_FILE, or enable TLS_AUTO_GENERATE."
            )

    # Build uvicorn configuration
    config: dict[str, Any] = {
        "ssl_certfile": str(cert_path),
        "ssl_keyfile": str(key_path),
    }

    # Add CA certificate if configured (for client cert verification)
    if settings.tls_ca_file:
        ca_path = Path(settings.tls_ca_file)
        if ca_path.exists():
            config["ssl_ca_certs"] = str(ca_path)
        else:
            logger.warning(f"CA certificate file not found: {ca_path}")

    logger.info(
        "TLS configuration loaded",
        extra={
            "cert_path": str(cert_path),
            "has_ca": settings.tls_ca_file is not None,
        },
    )

    return config


def _get_local_ips() -> list[str]:
    """Get list of local IP addresses for SAN entries.

    Returns:
        List of local IP addresses (IPv4).
    """
    local_ips: list[str] = ["127.0.0.1"]

    try:
        # Get hostname-associated IP
        hostname = socket.gethostname()
        host_ip = socket.gethostbyname(hostname)
        if host_ip not in local_ips:
            local_ips.append(host_ip)

        # Try to get all network interfaces (may not work on all systems)
        try:
            import socket as sock

            # Get all addresses associated with the hostname
            addrs = sock.getaddrinfo(hostname, None, sock.AF_INET)
            for addr in addrs:
                sockaddr = addr[4]
                ip = str(sockaddr[0])
                if ip not in local_ips and not ip.startswith("127."):
                    local_ips.append(ip)
        except Exception:  # noqa: S110
            pass

    except Exception as e:
        logger.debug(f"Could not determine local IPs: {e}")

    return local_ips


# =============================================================================
# Convenience Functions
# =============================================================================


def is_tls_enabled() -> bool:
    """Check if TLS is enabled in settings.

    Returns:
        True if TLS is enabled, False otherwise.
    """
    return get_settings().tls_enabled


def get_cert_info() -> dict[str, Any] | None:
    """Get information about the currently configured certificate.

    Returns:
        Certificate details dictionary or None if no certificate configured.
    """
    settings = get_settings()

    if not settings.tls_enabled:
        return None

    cert_path: Path | None = None

    if settings.tls_cert_file:
        cert_path = Path(settings.tls_cert_file)
    elif settings.tls_auto_generate:
        cert_path = Path(settings.tls_cert_dir) / "server.crt"

    if cert_path and cert_path.exists():
        try:
            return validate_certificate(cert_path)
        except Exception as e:
            logger.error(f"Failed to get certificate info: {e}")
            return None

    return None
