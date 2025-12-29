#!/usr/bin/env python3
"""Generate self-signed TLS certificates for LAN deployment.

This script generates self-signed certificates suitable for securing the
Home Security Intelligence API on a local network. These certificates
should NOT be used for production deployments exposed to the internet.

Usage:
    python scripts/generate_certs.py                    # Use defaults
    python scripts/generate_certs.py --hostname myserver
    python scripts/generate_certs.py --output /path/to/certs
    python scripts/generate_certs.py --san-ip 192.168.1.100 --san-ip 10.0.0.5
    python scripts/generate_certs.py --days 730        # 2-year validity

Examples:
    # Generate certs for local development
    python scripts/generate_certs.py --hostname localhost

    # Generate certs for LAN server with multiple IPs
    python scripts/generate_certs.py \\
        --hostname security-server \\
        --san-ip 192.168.1.100 \\
        --san-ip 10.0.0.1 \\
        --san-dns security.local \\
        --output data/certs

    # Generate certs with custom validity period
    python scripts/generate_certs.py --days 365 --hostname myserver

Note:
    For production deployments accessible from the internet, use proper
    CA-signed certificates from Let's Encrypt or another trusted CA.
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.tls import generate_self_signed_cert, validate_certificate


def get_local_ips() -> list[str]:
    """Discover local IP addresses.

    Returns:
        List of local IPv4 addresses.
    """
    local_ips: list[str] = ["127.0.0.1"]

    try:
        hostname = socket.gethostname()
        host_ip = socket.gethostbyname(hostname)
        if host_ip not in local_ips:
            local_ips.append(host_ip)

        # Try to get additional addresses
        try:
            addrs = socket.getaddrinfo(hostname, None, socket.AF_INET)
            for addr in addrs:
                ip = addr[4][0]
                if ip not in local_ips and not ip.startswith("127."):
                    local_ips.append(ip)
        except Exception:  # noqa: S110
            pass

    except Exception as e:
        print(f"Warning: Could not discover local IPs: {e}")

    return local_ips


def main() -> int:
    """Main entry point for certificate generation.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = argparse.ArgumentParser(
        description="Generate self-signed TLS certificates for LAN deployment.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --hostname localhost
  %(prog)s --hostname myserver --san-ip 192.168.1.100
  %(prog)s --output /etc/ssl/certs --days 730
        """,
    )

    parser.add_argument(
        "--hostname",
        default=None,
        help="Hostname for the certificate (default: system hostname)",
    )

    parser.add_argument(
        "--output",
        "-o",
        default="data/certs",
        help="Output directory for certificates (default: data/certs)",
    )

    parser.add_argument(
        "--cert-name",
        default="server.crt",
        help="Certificate filename (default: server.crt)",
    )

    parser.add_argument(
        "--key-name",
        default="server.key",
        help="Private key filename (default: server.key)",
    )

    parser.add_argument(
        "--san-ip",
        action="append",
        default=[],
        help="IP address for Subject Alternative Name (can be repeated)",
    )

    parser.add_argument(
        "--san-dns",
        action="append",
        default=[],
        help="DNS name for Subject Alternative Name (can be repeated)",
    )

    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Certificate validity in days (default: 365)",
    )

    parser.add_argument(
        "--key-size",
        type=int,
        default=2048,
        choices=[2048, 4096],
        help="RSA key size in bits (default: 2048)",
    )

    parser.add_argument(
        "--auto-discover-ips",
        action="store_true",
        help="Automatically add discovered local IPs to SANs",
    )

    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing certificates",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress non-error output",
    )

    args = parser.parse_args()

    # Determine hostname
    hostname = args.hostname or socket.gethostname()

    # Build output paths
    output_dir = Path(args.output)
    cert_path = output_dir / args.cert_name
    key_path = output_dir / args.key_name

    # Check for existing certificates
    if not args.force:
        if cert_path.exists():
            print(f"Error: Certificate already exists: {cert_path}")
            print("Use --force to overwrite.")
            return 1
        if key_path.exists():
            print(f"Error: Key already exists: {key_path}")
            print("Use --force to overwrite.")
            return 1

    # Build SAN lists
    san_ips = list(args.san_ip)
    san_dns = list(args.san_dns)

    # Auto-discover local IPs if requested
    if args.auto_discover_ips:
        discovered = get_local_ips()
        for ip in discovered:
            if ip not in san_ips:
                san_ips.append(ip)
        if not args.quiet:
            print(f"Discovered local IPs: {discovered}")

    # Always include localhost
    if "localhost" not in san_dns:
        san_dns.append("localhost")
    if "127.0.0.1" not in san_ips:
        san_ips.append("127.0.0.1")

    if not args.quiet:
        print(f"Generating certificate for: {hostname}")
        print(f"Output directory: {output_dir}")
        print(f"Certificate file: {cert_path}")
        print(f"Key file: {key_path}")
        print(f"Validity: {args.days} days")
        print(f"Key size: {args.key_size} bits")
        print(f"SAN IPs: {san_ips}")
        print(f"SAN DNS: {san_dns}")
        print()

    try:
        # Generate certificates
        generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname=hostname,
            san_ips=san_ips,
            san_dns=san_dns,
            days_valid=args.days,
            key_size=args.key_size,
        )

        if not args.quiet:
            print("Certificate generated successfully!")
            print()

            # Validate and show certificate info
            cert_info = validate_certificate(cert_path)
            print("Certificate Details:")
            print(f"  Subject: {cert_info['subject']}")
            print(f"  Issuer: {cert_info['issuer']}")
            print(f"  Valid from: {cert_info['not_before']}")
            print(f"  Valid until: {cert_info['not_after']}")
            print(f"  Days remaining: {cert_info['days_remaining']}")
            print()

            # Show usage instructions
            print("To use with the API server:")
            print("  export TLS_ENABLED=true")
            print(f"  export TLS_CERT_FILE={cert_path.absolute()}")
            print(f"  export TLS_KEY_FILE={key_path.absolute()}")
            print()
            print("Or add to .env file:")
            print("  TLS_ENABLED=true")
            print(f"  TLS_CERT_FILE={cert_path.absolute()}")
            print(f"  TLS_KEY_FILE={key_path.absolute()}")

        return 0

    except Exception as e:
        print(f"Error generating certificates: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
