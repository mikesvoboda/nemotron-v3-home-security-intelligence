"""TLS configuration and certificate utilities for HTTPS support.

This module provides:
- TLS configuration management via TLSConfig dataclass
- Self-signed certificate generation for development/LAN deployments
- SSL context creation for FastAPI/Uvicorn
- Certificate file validation utilities

Usage:
    from backend.core.tls import get_tls_config, create_ssl_context

    config = get_tls_config()
    ssl_context = create_ssl_context(config)
"""

import ipaddress
import os
import ssl
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from backend.core.logging import get_logger

logger = get_logger(__name__)


class TLSMode(str, Enum):
    """TLS operation mode.

    Attributes:
        DISABLED: No TLS, HTTP only (default for development)
        SELF_SIGNED: Auto-generate self-signed certificates
        PROVIDED: Use externally provided certificate files
    """

    DISABLED = "disabled"
    SELF_SIGNED = "self_signed"
    PROVIDED = "provided"


@dataclass
class TLSConfig:
    """TLS configuration settings.

    Attributes:
        mode: TLS operation mode (disabled, self_signed, provided)
        cert_path: Path to the certificate file (PEM format)
        key_path: Path to the private key file (PEM format)
        ca_path: Optional path to CA certificate for client verification
        verify_client: Whether to require and verify client certificates
        min_version: Minimum TLS version to accept (default TLS 1.2)
    """

    mode: TLSMode = TLSMode.DISABLED
    cert_path: str | None = None
    key_path: str | None = None
    ca_path: str | None = None
    verify_client: bool = False
    min_version: ssl.TLSVersion = field(default=ssl.TLSVersion.TLSv1_2)

    @property
    def is_enabled(self) -> bool:
        """Check if TLS is enabled."""
        return self.mode != TLSMode.DISABLED


def validate_certificate_files(
    cert_path: str,
    key_path: str,
    ca_path: str | None = None,
) -> None:
    """Validate that certificate files exist.

    Args:
        cert_path: Path to the certificate file
        key_path: Path to the private key file
        ca_path: Optional path to CA certificate file

    Raises:
        FileNotFoundError: If any required file does not exist
    """
    if not Path(cert_path).exists():
        raise FileNotFoundError(f"Certificate file not found: {cert_path}")

    if not Path(key_path).exists():
        raise FileNotFoundError(f"Private key file not found: {key_path}")

    if ca_path and not Path(ca_path).exists():
        raise FileNotFoundError(f"CA certificate file not found: {ca_path}")


def generate_self_signed_certificate(
    cert_path: str,
    key_path: str,
    hostname: str = "localhost",
    san_hosts: list[str] | None = None,
    organization: str = "Home Security Intelligence",
    validity_days: int = 365,
) -> bool:
    """Generate a self-signed certificate and private key.

    Creates a self-signed X.509 certificate suitable for HTTPS on a local
    network. The certificate includes Subject Alternative Names (SANs) for
    the specified hosts and IP addresses.

    Args:
        cert_path: Path to write the certificate file (PEM format)
        key_path: Path to write the private key file (PEM format)
        hostname: Primary hostname/CN for the certificate
        san_hosts: Additional hostnames and IPs for SAN extension
        organization: Organization name for the certificate subject
        validity_days: Certificate validity period in days

    Returns:
        True if certificate was successfully generated

    Example:
        >>> generate_self_signed_certificate(
        ...     cert_path="/data/certs/server.crt",
        ...     key_path="/data/certs/server.key",
        ...     hostname="security.home",
        ...     san_hosts=["192.168.1.100", "localhost"],
        ...     validity_days=730,
        ... )
        True
    """
    # Ensure parent directories exist
    Path(cert_path).parent.mkdir(parents=True, exist_ok=True)
    Path(key_path).parent.mkdir(parents=True, exist_ok=True)

    # Generate RSA private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Build subject name
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        ]
    )

    # Build Subject Alternative Names
    san_entries: list[x509.GeneralName] = [x509.DNSName(hostname)]

    if san_hosts:
        for host in san_hosts:
            # Check if it's an IP address
            try:
                ip = ipaddress.ip_address(host)
                san_entries.append(x509.IPAddress(ip))
            except ValueError:
                # It's a hostname
                san_entries.append(x509.DNSName(host))

    # Build certificate
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=validity_days))
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
            x509.ExtendedKeyUsage(
                [
                    x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                ]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    # Write private key with restricted permissions
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Write key file with secure permissions (0600)
    key_path_obj = Path(key_path)
    key_path_obj.write_bytes(key_pem)
    if os.name != "nt":  # Unix-like systems
        key_path_obj.chmod(0o600)

    # Write certificate
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    Path(cert_path).write_bytes(cert_pem)

    logger.info(
        "Generated self-signed certificate",
        extra={
            "hostname": hostname,
            "validity_days": validity_days,
            "cert_path": cert_path,
        },
    )

    return True


def create_ssl_context(config: TLSConfig) -> ssl.SSLContext | None:
    """Create an SSL context from TLS configuration.

    Creates an ssl.SSLContext configured for server-side TLS with the
    specified certificate and key files. The context is configured with
    secure defaults following modern best practices.

    Args:
        config: TLS configuration settings

    Returns:
        Configured SSLContext if TLS is enabled, None if disabled

    Raises:
        FileNotFoundError: If certificate files are missing
        ssl.SSLError: If certificate files are invalid

    Example:
        >>> config = TLSConfig(
        ...     mode=TLSMode.PROVIDED,
        ...     cert_path="/path/to/cert.pem",
        ...     key_path="/path/to/key.pem",
        ... )
        >>> context = create_ssl_context(config)
    """
    if config.mode == TLSMode.DISABLED:
        return None

    # Validate certificate files exist
    if config.cert_path and config.key_path:
        validate_certificate_files(config.cert_path, config.key_path, config.ca_path)

    # Create server-side SSL context
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # Set minimum TLS version
    context.minimum_version = config.min_version

    # Disable old protocols (SSLv2, SSLv3, TLS 1.0, TLS 1.1 are already disabled
    # when using minimum_version >= TLSv1_2)
    context.options |= ssl.OP_NO_SSLv2
    context.options |= ssl.OP_NO_SSLv3

    # Load certificate and key
    if config.cert_path and config.key_path:
        context.load_cert_chain(
            certfile=config.cert_path,
            keyfile=config.key_path,
        )

    # Configure client certificate verification if requested
    if config.verify_client:
        context.verify_mode = ssl.CERT_REQUIRED
        if config.ca_path:
            context.load_verify_locations(cafile=config.ca_path)
    else:
        context.verify_mode = ssl.CERT_NONE

    logger.info(
        "Created SSL context",
        extra={
            "mode": config.mode.value,
            "min_version": config.min_version.name,
            "verify_client": config.verify_client,
        },
    )

    return context


def _parse_tls_version(version_str: str) -> ssl.TLSVersion:
    """Parse TLS version string to ssl.TLSVersion enum.

    Args:
        version_str: Version string like "TLSv1.2" or "TLSv1.3"

    Returns:
        Corresponding ssl.TLSVersion value
    """
    version_map = {
        "TLSv1.2": ssl.TLSVersion.TLSv1_2,
        "TLSv1.3": ssl.TLSVersion.TLSv1_3,
        "1.2": ssl.TLSVersion.TLSv1_2,
        "1.3": ssl.TLSVersion.TLSv1_3,
    }
    return version_map.get(version_str, ssl.TLSVersion.TLSv1_2)


def get_tls_config() -> TLSConfig:
    """Get TLS configuration from application settings.

    Reads TLS settings from the application configuration and returns
    a TLSConfig object. This is the primary way to obtain TLS configuration
    in the application.

    Returns:
        TLSConfig populated from application settings
    """
    from backend.core.config import get_settings

    settings = get_settings()

    return TLSConfig(
        mode=TLSMode(settings.tls_mode),
        cert_path=settings.tls_cert_path,
        key_path=settings.tls_key_path,
        ca_path=settings.tls_ca_path,
        verify_client=settings.tls_verify_client,
        min_version=_parse_tls_version(settings.tls_min_version),
    )
