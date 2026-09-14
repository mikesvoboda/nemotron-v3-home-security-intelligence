"""URL validation utilities with SSRF protection.

This module provides secure URL validation to prevent Server-Side Request Forgery (SSRF)
attacks. It validates URLs against private IP ranges, cloud metadata endpoints, and
ensures only allowed schemes are used.

Usage:
    from backend.core.url_validation import validate_webhook_url, SSRFValidationError

    try:
        validated_url = validate_webhook_url("https://example.com/webhook")
    except SSRFValidationError as e:
        logger.error(f"Invalid webhook URL: {e}")

Security considerations:
- Only HTTPS is allowed in production (HTTP allowed for localhost in dev mode)
- Private IP ranges are blocked (10.x, 172.16-31.x, 192.168.x, 127.x)
- Cloud metadata endpoints are blocked (169.254.169.254)
- Link-local addresses are blocked (169.254.x.x)
- IPv6 localhost and link-local addresses are blocked
- .local and other internal domain suffixes are blocked
- All blocked SSRF attempts are logged for security monitoring
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from urllib.parse import ParseResult, urlparse

# Use standard logging to avoid circular imports with backend.core.logging
logger = logging.getLogger(__name__)


class SSRFValidationError(Exception):
    """Exception raised when URL fails SSRF validation.

    Note: This intentionally does NOT inherit from ValueError to avoid
    being caught by except ValueError clauses in IP address parsing.
    """

    pass


# Private and reserved IP ranges that should be blocked
# These are networks that should never be accessed from webhook notifications
BLOCKED_IP_NETWORKS = [
    # IPv4 Private Networks (RFC 1918)
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    # Loopback (RFC 990)
    ipaddress.ip_network("127.0.0.0/8"),
    # Link-Local (RFC 3927)
    ipaddress.ip_network("169.254.0.0/16"),
    # Carrier-Grade NAT (RFC 6598)
    ipaddress.ip_network("100.64.0.0/10"),
    # Documentation (RFC 5737)
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    # Benchmarking (RFC 2544)
    ipaddress.ip_network("198.18.0.0/15"),
    # IPv6 Loopback
    ipaddress.ip_network("::1/128"),
    # IPv6 Link-Local
    ipaddress.ip_network("fe80::/10"),
    # IPv6 Unique Local
    ipaddress.ip_network("fc00::/7"),
]

# Specific IPs to always block (cloud metadata endpoints)
BLOCKED_IPS = {
    # AWS/GCP/Azure metadata service
    "169.254.169.254",
    # AWS ECS metadata
    "169.254.170.2",
    # Azure Instance Metadata Service
    "169.254.169.253",
    # GCP metadata (alias)
    "metadata.google.internal",
}

# Blocked hostnames (case-insensitive)
BLOCKED_HOSTNAMES = {
    "metadata.google.internal",
    "metadata",
    "instance-data",
}

# Blocked domain suffixes (case-insensitive)
# These are internal/local domain extensions that should not be accessible externally
BLOCKED_DOMAIN_SUFFIXES = {
    ".local",  # mDNS/Bonjour local network domains
    ".localhost",  # RFC 6761 localhost TLD
    ".internal",  # Common internal domain suffix
    ".lan",  # Common LAN suffix
    ".home",  # Home network suffix
    ".localdomain",  # Standard local domain
    ".intranet",  # Intranet suffix
    ".corp",  # Corporate internal domain
    ".home.arpa",  # RFC 8375 home network domain
}

# Allowed schemes
ALLOWED_SCHEMES = {"https"}
DEV_ALLOWED_SCHEMES = {"http", "https"}

# Localhost patterns for dev mode
LOCALHOST_PATTERNS = {
    "localhost",
    "127.0.0.1",
    "::1",
}


def is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is in a private or reserved range.

    Args:
        ip_str: IP address string to check

    Returns:
        True if the IP is in a blocked private/reserved range
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in network for network in BLOCKED_IP_NETWORKS)
    except ValueError:
        # Not a valid IP address, will be checked as hostname
        return False


def is_blocked_ip(ip_str: str) -> bool:
    """Check if an IP address is specifically blocked (e.g., metadata endpoints).

    Args:
        ip_str: IP address string to check

    Returns:
        True if the IP is in the blocked list
    """
    return ip_str in BLOCKED_IPS


def is_blocked_hostname(hostname: str) -> bool:
    """Check if a hostname is in the blocked list.

    Args:
        hostname: Hostname to check (case-insensitive)

    Returns:
        True if the hostname is blocked
    """
    return hostname.lower() in BLOCKED_HOSTNAMES


def is_blocked_domain_suffix(hostname: str) -> bool:
    """Check if a hostname has a blocked domain suffix.

    This blocks internal/local domain extensions like .local, .localhost,
    .internal, .lan, etc. that should not be accessible externally.

    Args:
        hostname: Hostname to check (case-insensitive)

    Returns:
        True if the hostname has a blocked suffix
    """
    hostname_lower = hostname.lower()
    return any(hostname_lower.endswith(suffix) for suffix in BLOCKED_DOMAIN_SUFFIXES)


def _log_blocked_ssrf_attempt(url: str, reason: str, hostname: str | None = None) -> None:
    """Log a blocked SSRF attempt for security monitoring.

    Args:
        url: The URL that was blocked (will be truncated for safety)
        reason: The reason the URL was blocked
        hostname: The extracted hostname if available
    """
    # Truncate URL to avoid log injection with very long URLs
    safe_url = url[:200] if len(url) > 200 else url
    # Sanitize the URL to remove potential control characters
    safe_url = "".join(c if c.isprintable() else "?" for c in safe_url)

    logger.warning(
        "SSRF attempt blocked: reason=%s, hostname=%s, url=%s",
        reason,
        hostname[:100] if hostname and len(hostname) > 100 else hostname,
        safe_url,
    )


def resolve_hostname(hostname: str) -> list[str]:
    """Resolve a hostname to its IP addresses.

    Args:
        hostname: Hostname to resolve

    Returns:
        List of resolved IP addresses

    Raises:
        SSRFValidationError: If hostname cannot be resolved
    """
    try:
        # getaddrinfo returns list of (family, type, proto, canonname, sockaddr)
        # sockaddr is (ip, port) for IPv4 or (ip, port, flow, scope) for IPv6
        results = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        # result[4][0] is always a string (IP address) per socket.getaddrinfo spec
        return list({str(result[4][0]) for result in results})
    except socket.gaierror as e:
        raise SSRFValidationError(f"Cannot resolve hostname '{hostname}': {e}") from e


def _validate_ip_address(hostname: str, allow_dev_http: bool) -> bool:
    """Check if hostname is an IP address and validate it.

    Args:
        hostname: The hostname to check (might be an IP address)
        allow_dev_http: If True, allow localhost IPs

    Returns:
        True if hostname is an IP address (whether allowed or not)
        False if hostname is not an IP address

    Raises:
        SSRFValidationError: If hostname is a blocked IP address
    """
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        # Not an IP address, it's a hostname
        return False

    # It's an IP address - validate it

    # Check if it's a blocked IP (metadata endpoints)
    if is_blocked_ip(hostname):
        raise SSRFValidationError(f"IP address '{hostname}' is blocked (cloud metadata endpoint)")

    # Check if it's a private/reserved IP
    if is_private_ip(hostname):
        # Allow localhost in dev mode
        if allow_dev_http and str(ip) in LOCALHOST_PATTERNS:
            pass  # Allowed
        else:
            raise SSRFValidationError(f"Private/reserved IP addresses are not allowed: {hostname}")

    return True


def _validate_scheme(scheme: str, hostname: str, allow_dev_http: bool) -> None:
    """Validate URL scheme.

    Args:
        scheme: URL scheme (http or https)
        hostname: Hostname for localhost check
        allow_dev_http: If True, allow HTTP for localhost

    Raises:
        SSRFValidationError: If scheme is not allowed
    """
    allowed = DEV_ALLOWED_SCHEMES if allow_dev_http else ALLOWED_SCHEMES

    if allow_dev_http and scheme == "http":
        if hostname.lower() not in LOCALHOST_PATTERNS:
            raise SSRFValidationError(
                f"HTTP scheme is only allowed for localhost in development mode. "
                f"Got: {hostname}. Use HTTPS for external URLs."
            )
    elif scheme not in allowed:
        raise SSRFValidationError(f"URL scheme '{scheme}' is not allowed. Only HTTPS is permitted.")


def _validate_resolved_ips(hostname: str, resolved_ips: list[str], allow_dev_http: bool) -> None:
    """Validate resolved IP addresses.

    Args:
        hostname: Original hostname for error messages
        resolved_ips: List of resolved IP addresses
        allow_dev_http: If True, allow localhost IPs

    Raises:
        SSRFValidationError: If any resolved IP is blocked
    """
    for resolved_ip in resolved_ips:
        if is_blocked_ip(resolved_ip):
            raise SSRFValidationError(
                f"Hostname '{hostname}' resolves to blocked IP: {resolved_ip}"
            )

        if is_private_ip(resolved_ip):
            if allow_dev_http and resolved_ip in LOCALHOST_PATTERNS:
                continue
            raise SSRFValidationError(
                f"Hostname '{hostname}' resolves to private IP: {resolved_ip}"
            )


def validate_webhook_url(
    url: str,
    *,
    allow_dev_http: bool = False,
    resolve_dns: bool = True,
) -> str:
    """Validate a webhook URL for SSRF protection.

    This function performs comprehensive validation to prevent SSRF attacks:
    1. Validates URL structure and scheme
    2. Blocks private/reserved IP ranges
    3. Blocks cloud metadata endpoints
    4. Blocks .local and other internal domain suffixes
    5. Optionally resolves DNS and checks resolved IPs
    6. Logs all blocked SSRF attempts for security monitoring

    Args:
        url: The webhook URL to validate
        allow_dev_http: If True, allow HTTP for localhost (dev mode only)
        resolve_dns: If True, resolve hostname and validate resolved IPs

    Returns:
        The validated URL (unchanged if valid)

    Raises:
        SSRFValidationError: If the URL fails validation
    """
    if not url:
        _log_blocked_ssrf_attempt(url or "", "empty_url")
        raise SSRFValidationError("URL cannot be empty")

    # Parse the URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        _log_blocked_ssrf_attempt(url, "invalid_format")
        raise SSRFValidationError(f"Invalid URL format: {e}") from e

    # Validate hostname exists first
    hostname: str | None = parsed.hostname
    if not hostname:
        _log_blocked_ssrf_attempt(url, "missing_hostname")
        raise SSRFValidationError("URL must have a hostname")

    # Check scheme using helper function
    scheme = parsed.scheme.lower()
    try:
        _validate_scheme(scheme, hostname, allow_dev_http)
    except SSRFValidationError:
        _log_blocked_ssrf_attempt(url, f"invalid_scheme:{scheme}", hostname)
        raise

    # Check for blocked hostnames
    if is_blocked_hostname(hostname):
        _log_blocked_ssrf_attempt(url, "blocked_hostname", hostname)
        raise SSRFValidationError(f"Hostname '{hostname}' is blocked for security reasons")

    # Check for blocked domain suffixes (.local, .localhost, .internal, etc.)
    if is_blocked_domain_suffix(hostname):
        _log_blocked_ssrf_attempt(url, "blocked_domain_suffix", hostname)
        raise SSRFValidationError(f"Hostname '{hostname}' uses a blocked internal domain suffix")

    # Check if hostname is an IP address and validate it
    try:
        is_ip = _validate_ip_address(hostname, allow_dev_http)
    except SSRFValidationError:
        _log_blocked_ssrf_attempt(url, "blocked_ip", hostname)
        raise

    # If it's a hostname (not IP) and we need to resolve DNS
    if not is_ip and resolve_dns:
        try:
            _resolve_and_validate_dns(hostname, allow_dev_http)
        except SSRFValidationError:
            _log_blocked_ssrf_attempt(url, "dns_resolves_to_blocked_ip", hostname)
            raise

    # Check for suspicious URL patterns
    try:
        _validate_url_patterns(parsed, scheme)
    except SSRFValidationError:
        _log_blocked_ssrf_attempt(url, "suspicious_pattern", hostname)
        raise

    return url


def _resolve_and_validate_dns(hostname: str, allow_dev_http: bool) -> None:
    """Resolve DNS and validate resolved IPs.

    Args:
        hostname: Hostname to resolve
        allow_dev_http: If True, allow localhost IPs
    """
    try:
        resolved_ips = resolve_hostname(hostname)
        _validate_resolved_ips(hostname, resolved_ips, allow_dev_http)
    except SSRFValidationError:
        raise
    except Exception as e:
        logger.warning("DNS resolution failed for '%s': %s", hostname, e)


def _validate_url_patterns(parsed: ParseResult, scheme: str) -> None:
    """Validate URL patterns for suspicious content.

    Args:
        parsed: Parsed URL result
        scheme: URL scheme

    Raises:
        SSRFValidationError: If URL has suspicious patterns
    """
    # Prevent URL tricks like http://evil.com@169.254.169.254/
    if parsed.username or parsed.password:
        raise SSRFValidationError("URLs with embedded credentials are not allowed")

    # Prevent file:// or other exotic schemes that might slip through
    if not re.match(r"^https?$", scheme):
        raise SSRFValidationError(f"Invalid URL scheme: {scheme}")


def validate_webhook_url_for_request(
    url: str,
    *,
    is_development: bool = False,
) -> str:
    """Validate a webhook URL immediately before making an HTTP request.

    This is a stricter validation that always resolves DNS and checks the
    resolved IPs. Use this at request time to ensure no DNS rebinding attacks.

    Args:
        url: The webhook URL to validate
        is_development: If True, allow HTTP for localhost

    Returns:
        The validated URL

    Raises:
        SSRFValidationError: If the URL fails validation
    """
    return validate_webhook_url(
        url,
        allow_dev_http=is_development,
        resolve_dns=True,
    )
