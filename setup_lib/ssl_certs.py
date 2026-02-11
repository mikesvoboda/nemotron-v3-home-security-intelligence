"""SSL certificate generation for setup.py.

Provides self-signed certificate generation for HTTPS setup without
requiring the full backend infrastructure.

Usage:
    from setup_lib.ssl_certs import prompt_and_generate_certificates
    prompt_and_generate_certificates(config)
"""

from __future__ import annotations

import ipaddress
import socket
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Python 3.10 compatibility: UTC was added in 3.11
if sys.version_info >= (3, 11):
    from datetime import UTC
else:
    UTC = timezone.utc

# Optional: cryptography library for certificate generation
try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False


def get_local_ip() -> str | None:
    """Get the primary local IP address.

    Returns:
        Local IP address string or None if detection fails.
    """
    try:
        # Connect to a public IP to determine local interface
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip_address: str = s.getsockname()[0]
            return ip_address
    except OSError:
        return None


def generate_self_signed_cert(
    cert_path: Path,
    key_path: Path,
    hostname: str = "localhost",
    san_ips: list[str] | None = None,
    san_dns: list[str] | None = None,
    days_valid: int = 365,
    key_size: int = 2048,
) -> bool:
    """Generate a self-signed certificate for HTTPS.

    Creates a certificate suitable for internal/LAN use. For production
    deployments exposed to the internet, use proper CA-signed certificates.

    Args:
        cert_path: Where to write the certificate (PEM format).
        key_path: Where to write the private key (PEM format).
        hostname: Common Name (CN) for the certificate.
        san_ips: List of IP addresses for Subject Alternative Names.
        san_dns: List of DNS names for Subject Alternative Names.
        days_valid: Number of days the certificate is valid.
        key_size: RSA key size in bits (default 2048).

    Returns:
        True if certificate was generated successfully, False otherwise.
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        print("! cryptography library not installed")
        print("  Install with: pip install cryptography")
        return False

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

    # Always include localhost and common names
    default_dns = ["localhost", "*.localhost", hostname]
    for dns_name in default_dns + san_dns:
        if dns_name not in [e.value for e in san_entries if isinstance(e, x509.DNSName)]:
            san_entries.append(x509.DNSName(dns_name))

    # Always include localhost IPs
    default_ips = ["127.0.0.1", "::1"]
    for ip_str in default_ips + san_ips:
        try:
            ip_addr = ipaddress.ip_address(ip_str)
            san_entries.append(x509.IPAddress(ip_addr))
        except ValueError:
            pass  # Skip invalid IPs silently

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
            x509.ExtendedKeyUsage(
                [
                    x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                    x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
                ]
            ),
            critical=False,
        )
    )

    # Sign the certificate
    certificate = cert_builder.sign(private_key, hashes.SHA256())

    # Write private key (with secure permissions)
    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    # Set key file permissions to 600 (owner read/write only)
    key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    # Write certificate
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))

    return True


def check_existing_certificates(cert_path: Path, key_path: Path) -> bool:
    """Check if valid certificates already exist.

    Args:
        cert_path: Path to certificate file.
        key_path: Path to private key file.

    Returns:
        True if both files exist and certificate is not expired.
    """
    if not cert_path.exists() or not key_path.exists():
        return False

    if not CRYPTOGRAPHY_AVAILABLE:
        # Can't validate, assume valid if files exist
        return True

    try:
        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        # Check if certificate is still valid
        now = datetime.now(UTC)
        not_after = cert.not_valid_after_utc

        # Consider valid if more than 7 days remaining
        days_remaining: int = (not_after - now).days
        return bool(days_remaining > 7)
    except Exception:
        return False


def prompt_and_generate_certificates(_config: dict) -> None:
    """Prompt user and generate SSL certificates if needed.

    Args:
        _config: Configuration dictionary (may contain auto_generate flag).
    """
    auto_generate = _config.get("auto_generate", False)
    
    print()
    print("=" * 60)
    print("SSL/TLS Certificate Generation")
    print("=" * 60)
    print()
    print("HTTPS is required for secure communication with the dashboard.")
    print("A self-signed certificate will be generated for local/LAN use.")
    print()
    print("For production internet-facing deployments, use Let's Encrypt")
    print("or a commercial CA certificate instead.")
    print()

    # Default certificate paths
    cert_dir = Path("./certs")
    cert_path = cert_dir / "cert.pem"
    key_path = cert_dir / "key.pem"

    # Check for existing certificates
    if check_existing_certificates(cert_path, key_path):
        print(f"+ Existing valid certificates found in {cert_dir}")
        if auto_generate:
            print("  Keeping existing certificates")
            return
        answer = input("  Regenerate certificates? [n]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("  Keeping existing certificates")
            return

    # Prompt for generation
    if auto_generate:
        print("Auto-generating self-signed SSL certificate...")
    else:
        answer = input("Generate self-signed SSL certificate? [y]: ").strip().lower()
        if answer and answer not in ("y", "yes"):
            print("  Skipping certificate generation")
            print("  ! HTTPS will not work without certificates")
            return

    # Get hostname
    hostname = socket.gethostname()
    if auto_generate:
        print(f"  Using hostname: {hostname}")
    else:
        print()
        hostname = input(f"  Hostname (CN) [{hostname}]: ").strip() or hostname

    # Get local IP for SAN
    local_ip = get_local_ip()
    san_ips: list[str] = []
    if local_ip:
        print(f"  Detected local IP: {local_ip}")
        if auto_generate:
            san_ips.append(local_ip)
            print(f"  Adding {local_ip} to certificate SANs")
        else:
            add_ip = input(f"  Add {local_ip} to certificate SANs? [y]: ").strip().lower()
            if not add_ip or add_ip in ("y", "yes"):
                san_ips.append(local_ip)

    # Allow additional IPs
    if not auto_generate:
        extra_ip = input("  Additional IP addresses (comma-separated, or Enter to skip): ").strip()
    else:
        extra_ip = ""
    if extra_ip:
        for ip_entry in extra_ip.split(","):
            ip_clean = ip_entry.strip()
            if ip_clean:
                try:
                    ipaddress.ip_address(ip_clean)
                    san_ips.append(ip_clean)
                except ValueError:
                    print(f"    ! Invalid IP address: {ip_clean}")

    # Generate certificate
    print()
    print("Generating certificate...")

    if not CRYPTOGRAPHY_AVAILABLE:
        print("! cryptography library not installed")
        print("  Install with: pip install cryptography")
        print("  Or run: ./scripts/generate-certs.sh")
        return

    try:
        success = generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname=hostname,
            san_ips=san_ips,
        )

        if success:
            print(f"+ Certificate generated: {cert_path}")
            print(f"+ Private key generated: {key_path}")
            print()
            print("Certificate details:")
            print(f"  - Hostname (CN): {hostname}")
            print("  - Valid for: 365 days")
            san_list = "localhost, 127.0.0.1, ::1" + (f", {', '.join(san_ips)}" if san_ips else "")
            print(f"  - SANs: {san_list}")
            print()
            print("! Note: Browsers will show a security warning for self-signed certificates.")
            print("  This is expected for local/LAN deployments.")
        else:
            print("! Failed to generate certificate")
    except Exception as e:
        print(f"! Error generating certificate: {e}")
