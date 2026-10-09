"""Core utility functions for setup script.

This module contains reusable utilities for port checking, password generation,
and other setup-related operations. These functions are extracted from the
main setup.py to enable better testing and reusability.
"""

import secrets
import socket

# Known weak/default passwords to warn about
WEAK_PASSWORDS = {
    "security_dev_password",
    "password",
    "postgres",
    "admin",
    "root",
    "123456",
    "changeme",
    "secret",
}


def check_port_available(port: int) -> bool:
    """Check if a port is available for binding.

    Checks both IPv4 and IPv6 localhost to detect processes bound to either.

    Args:
        port: Port number to check

    Returns:
        True if port is available on both IPv4 and IPv6, False if in use
    """
    # Check IPv4
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", port)) == 0:
            return False
    # Check IPv6
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            if s.connect_ex(("::1", port)) == 0:
                return False
    except OSError:
        pass  # IPv6 not available
    return True


def find_available_port(start: int, exclude: set[int] | None = None) -> int:
    """Find the next available port starting from a given port.

    Args:
        start: Starting port number
        exclude: Set of ports to skip (already assigned to other services)

    Returns:
        First available port >= start that is not in exclude set

    Raises:
        RuntimeError: If no available ports found up to 65535
    """
    if exclude is None:
        exclude = set()
    port = start
    while not check_port_available(port) or port in exclude:
        port += 1
        if port > 65535:
            raise RuntimeError(f"No available ports found starting from {start}")
    return port


def generate_password(length: int = 32) -> str:
    """Generate a secure random password.

    Args:
        length: Desired password length (default: 32 for security)

    Returns:
        URL-safe random string of specified length
    """
    return secrets.token_urlsafe(length)[:length]


def derive_frontend_bind_address(expose_lan: str) -> str:
    """Map an EXPOSE_LAN value to the frontend's published-port bind address.

    O1.6 (D10; OD-12): compose has no conditionals, so the switch lives here —
    setup.py derives FRONTEND_BIND_ADDRESS from EXPOSE_LAN and writes both into
    the .env it generates, and docker-compose.prod.yml references the bind var.

    One flag, one vocabulary (O1.6 review follow-up): the truthy set matches
    what pydantic parses for Settings.expose_lan from a string — case-
    insensitive {"true", "t", "yes", "y", "on", "1"} (probed against
    TypeAdapter(bool) on pydantic 2.13), so a value like EXPOSE_LAN=yes can
    never arm the auth gate here while the bind stayed loopback there.
    Everything else — unset, "false"/"no"/"off", a typo — yields loopback
    "127.0.0.1" (fail-safe). The words pydantic REJECTS outright (e.g. "banana")
    can't split the readers either: Settings construction raises before any
    render happens. One edge, stated exactly: this derive .strip()s, pydantic
    does not — a whitespace-padded truthy word (" true") wilds the bind here
    while Settings raises there, so the backend never boots behind it (the
    split is loud, never silent). The second fail-safe layer is compose's own
    ${FRONTEND_BIND_ADDRESS:-127.0.0.1} default, which covers a hand-edited
    .env that sets EXPOSE_LAN=true without re-running setup.py.

    Args:
        expose_lan: raw EXPOSE_LAN value (from a prompt answer or an env read)

    Returns:
        "0.0.0.0" when the UI is deliberately LAN-exposed, else "127.0.0.1"
    """
    return (
        "0.0.0.0"  # noqa: S104
        if expose_lan.strip().lower() in ("true", "t", "yes", "y", "on", "1")
        else "127.0.0.1"
    )


def _expose_lan_is_truthy(expose_lan: str) -> bool:
    """The one truthy vocabulary, shared by every EXPOSE_LAN reader (O1.6).

    Case-insensitive {"true", "t", "yes", "y", "on", "1"} — the exact set
    pydantic parses for Settings.expose_lan and the exact set
    derive_frontend_bind_address uses, so the auth gate, the bind address and
    the O1.11 monitoring renders can never disagree about what "exposed"
    means. Everything else (unset, "false"/"no"/"off", a typo) is the
    DEFAULT un-exposed mode — fail-safe in the direction that keeps the
    attack surface small.
    """
    return expose_lan.strip().lower() in ("true", "t", "yes", "y", "on", "1")


def derive_grafana_anonymous_enabled(expose_lan: str) -> str:
    """Whether Grafana's anonymous Admin access stays on, from EXPOSE_LAN.

    O1.11 (UR-33): the shipped ``GF_AUTH_ANONYMOUS_ENABLED=true`` +
    ``ORG_ROLE=Admin`` pairing is the one door into /grafana/ today (the
    login form is already disabled), and it is exactly what exposure must
    close — a LAN-reachable dashboard with anonymous Admin reads every
    panel and mints API tokens. Unexposed, this returns "true": today's
    behavior, byte for byte (spec checklist 4).

    Same one flag, one vocabulary as derive_frontend_bind_address; compose
    carries the value through a nested default so a .env that already
    hand-set GF_AUTH_ANONYMOUS_ENABLED=false keeps its own "false" (see the
    render tests — the security direction only ever goes one way).

    Args:
        expose_lan: raw EXPOSE_LAN value (prompt answer or env read)

    Returns:
        "false" when deliberately LAN-exposed, else "true" (fail-safe)
    """
    return "false" if _expose_lan_is_truthy(expose_lan) else "true"


def derive_grafana_auth_proxy_enabled(expose_lan: str) -> str:
    """Whether Grafana trusts the frontend's auth-proxy header, from EXPOSE_LAN.

    O1.11's recorded DECIDE: nginx ``auth_request`` against the backend
    session + Grafana auth proxy — one login serves /grafana/ and the three
    embedded dashboards. Unexposed this must be "false" or the frontend's
    (never-rendered) X-Auth-User header would be the only credential Grafana
    accepts while nothing validates it: the render and the trust arm
    together, off together.

    Args:
        expose_lan: raw EXPOSE_LAN value (prompt answer or env read)

    Returns:
        "true" when deliberately LAN-exposed, else "false" (fail-safe)
    """
    return "true" if _expose_lan_is_truthy(expose_lan) else "false"


def derive_alert_sink_url(expose_lan: str) -> str:
    """Where Alertmanager delivers webhooks, from EXPOSE_LAN.

    Alertmanager cannot attach an X-API-Key in ANY version (probe:
    http_headers rejected by amtool v0.27.0 through v0.34.1; only
    basic_auth/bearer exist, and the B1.5 gate reads neither). The
    credential therefore joins at the frontend's unpublished machine
    listener (compose-network ``listen 8081``, path-exact route) which
    renders the header in. Unexposed, the sink stays today's direct
    backend URL — the listener isn't rendered there, and the gate lets
    the compose network through without a credential anyway.

    Args:
        expose_lan: raw EXPOSE_LAN value (prompt answer or env read)

    Returns:
        The frontend machine-listener URL when exposed, else the direct
        backend URL (fail-safe, today's behavior).
    """
    if _expose_lan_is_truthy(expose_lan):
        return "http://frontend:8081/api/webhooks/alerts"
    return "http://backend:8000/api/webhooks/alerts"


def is_weak_password(password: str) -> bool:
    """Check if a password is considered weak.

    Args:
        password: Password to check

    Returns:
        True if password is weak, False otherwise
    """
    if len(password) < 16:
        return True
    return password.lower() in WEAK_PASSWORDS
