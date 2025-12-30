#!/usr/bin/env python3
"""Generate TLS certificates for Home Security Intelligence.

This script generates self-signed certificates for HTTPS deployment.
Supports both development (localhost) and LAN deployment scenarios.

Usage:
    # Generate development certificates (localhost only)
    python scripts/generate_certs.py

    # Generate LAN certificates with custom hostnames/IPs
    python scripts/generate_certs.py --hostname security.home --san 192.168.1.100

    # Generate with custom output directory
    python scripts/generate_certs.py --output-dir /etc/ssl/hsi

    # Generate with longer validity
    python scripts/generate_certs.py --validity-days 730

Examples:
    # Development setup
    python scripts/generate_certs.py
    # Creates: data/certs/cert.pem, data/certs/key.pem

    # Production LAN setup
    python scripts/generate_certs.py \\
        --hostname security.local \\
        --san 192.168.1.100 \\
        --san 192.168.1.101 \\
        --san localhost \\
        --validity-days 730 \\
        --output-dir /opt/hsi/certs

Environment Variables:
    TLS_CERT_PATH: Override default certificate output path
    TLS_KEY_PATH: Override default private key output path
"""

import argparse
import os
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.tls import generate_self_signed_certificate


def _get_output_dir(args_output_dir: str | None) -> Path:
    """Determine the output directory for certificates."""
    if args_output_dir:
        return Path(args_output_dir)
    env_cert_path = os.environ.get("TLS_CERT_PATH")
    return Path(env_cert_path).parent if env_cert_path else Path("data/certs")


def _build_san_list(san_hosts: list[str] | None, hostname: str) -> list[str]:
    """Build the Subject Alternative Names list."""
    result = list(san_hosts) if san_hosts else []
    # Always include localhost and 127.0.0.1 for development convenience
    if hostname == "localhost":
        for san in ["127.0.0.1", "::1"]:
            if san not in result:
                result.append(san)
    return result


def _print_info(
    args: argparse.Namespace, cert_path: Path, key_path: Path, san_hosts: list[str]
) -> None:
    """Print certificate generation info."""
    print("Generating TLS certificate...")
    print(f"  Hostname (CN): {args.hostname}")
    print(f"  Organization: {args.organization}")
    print(f"  Validity: {args.validity_days} days")
    if san_hosts:
        print(f"  SANs: {', '.join(san_hosts)}")
    print(f"  Certificate: {cert_path}")
    print(f"  Private Key: {key_path}")
    print()


def _print_success(cert_path: Path, key_path: Path) -> None:
    """Print success message with instructions."""
    print("Certificate generated successfully!")
    print()
    print("To enable HTTPS, add to your .env file:")
    print()
    print("  TLS_MODE=self_signed")
    print(f"  TLS_CERT_PATH={cert_path.absolute()}")
    print(f"  TLS_KEY_PATH={key_path.absolute()}")
    print()
    print("Or start the server with:")
    print()
    print(f"  uvicorn backend.main:app --ssl-certfile={cert_path} --ssl-keyfile={key_path}")


def main() -> int:
    """Generate TLS certificates based on command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate TLS certificates for Home Security Intelligence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Development (localhost only)
  %(prog)s

  # LAN deployment with specific IP
  %(prog)s --hostname security.home --san 192.168.1.100

  # Multiple SANs for load balancing
  %(prog)s --san 192.168.1.100 --san 192.168.1.101 --san lb.local
        """,
    )

    parser.add_argument("--hostname", default="localhost", help="Primary hostname (CN)")
    parser.add_argument(
        "--san", action="append", dest="san_hosts", metavar="HOST", help="Additional SAN"
    )
    parser.add_argument("--output-dir", default=None, help="Output directory")
    parser.add_argument("--cert-name", default="cert.pem", help="Certificate filename")
    parser.add_argument("--key-name", default="key.pem", help="Private key filename")
    parser.add_argument("--validity-days", type=int, default=365, help="Validity in days")
    parser.add_argument(
        "--organization", default="Home Security Intelligence", help="Organization name"
    )
    parser.add_argument("--force", action="store_true", help="Overwrite without prompting")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output")

    args = parser.parse_args()

    output_dir = _get_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cert_path = output_dir / args.cert_name
    key_path = output_dir / args.key_name

    # Check for existing certificates
    if not args.force and (cert_path.exists() or key_path.exists()) and not args.quiet:
        print(f"Certificate files already exist in {output_dir}")
        if input("Overwrite? [y/N]: ").strip().lower() != "y":
            print("Aborted.")
            return 1

    san_hosts = _build_san_list(args.san_hosts, args.hostname)

    if not args.quiet:
        _print_info(args, cert_path, key_path, san_hosts)

    try:
        success = generate_self_signed_certificate(
            cert_path=str(cert_path),
            key_path=str(key_path),
            hostname=args.hostname,
            san_hosts=san_hosts if san_hosts else None,
            _organization=args.organization,
            validity_days=args.validity_days,
        )

        if not success:
            if not args.quiet:
                print("Certificate generation failed.", file=sys.stderr)
            return 1

        if not args.quiet:
            _print_success(cert_path, key_path)
        return 0

    except Exception as e:
        if not args.quiet:
            print(f"Error generating certificate: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
