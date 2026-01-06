"""Security headers middleware for HTTP responses.

This module implements security headers to protect against common web vulnerabilities:
- X-Content-Type-Options: Prevents MIME type sniffing
- X-Frame-Options: Prevents clickjacking attacks
- X-XSS-Protection: Enables browser XSS filtering (legacy, but still useful)
- Referrer-Policy: Controls referrer information sent with requests
- Content-Security-Policy: Restricts resource loading sources
- Permissions-Policy: Controls browser feature access
- Strict-Transport-Security (HSTS): Forces HTTPS connections
- Cache-Control: Controls caching behavior for sensitive responses
- X-Permitted-Cross-Domain-Policies: Controls cross-domain policy file access
"""

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# Default HSTS value: 1 year with includeSubDomains
# 31536000 seconds = 365 days
_DEFAULT_HSTS = "max-age=31536000; includeSubDomains"

# Default Cache-Control for security-sensitive API responses
# no-store prevents caching of potentially sensitive data
_DEFAULT_CACHE_CONTROL = "no-store, no-cache, must-revalidate, private"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to all HTTP responses.

    This middleware applies defense-in-depth security headers to protect
    against common web vulnerabilities. The headers are configurable via
    the constructor but have secure defaults.

    Attributes:
        content_type_options: X-Content-Type-Options header value
        frame_options: X-Frame-Options header value
        xss_protection: X-XSS-Protection header value
        referrer_policy: Referrer-Policy header value
        content_security_policy: Content-Security-Policy header value
        permissions_policy: Permissions-Policy header value
        strict_transport_security: Strict-Transport-Security (HSTS) header value
        cache_control: Cache-Control header value
        cross_domain_policies: X-Permitted-Cross-Domain-Policies header value
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        content_type_options: str = "nosniff",
        frame_options: str = "DENY",
        xss_protection: str = "1; mode=block",
        referrer_policy: str = "strict-origin-when-cross-origin",
        content_security_policy: str | None = None,
        permissions_policy: str | None = None,
        strict_transport_security: str | None = _DEFAULT_HSTS,
        cache_control: str | None = _DEFAULT_CACHE_CONTROL,
        cross_domain_policies: str = "none",
    ):
        """Initialize security headers middleware.

        Args:
            app: FastAPI/Starlette application
            content_type_options: X-Content-Type-Options value (default: "nosniff")
            frame_options: X-Frame-Options value (default: "DENY")
            xss_protection: X-XSS-Protection value (default: "1; mode=block")
            referrer_policy: Referrer-Policy value (default: "strict-origin-when-cross-origin")
            content_security_policy: Content-Security-Policy value (default: secure policy)
            permissions_policy: Permissions-Policy value (default: restrictive policy)
            strict_transport_security: HSTS header value (default: 1 year with includeSubDomains).
                Set to None to disable HSTS header.
            cache_control: Cache-Control header value (default: no-store for security).
                Set to None to skip adding Cache-Control header.
            cross_domain_policies: X-Permitted-Cross-Domain-Policies value (default: "none")
        """
        super().__init__(app)
        self.content_type_options = content_type_options
        self.frame_options = frame_options
        self.xss_protection = xss_protection
        self.referrer_policy = referrer_policy

        # Default CSP: Allow self, inline styles (for Tremor/Tailwind), and data URIs for images
        # WebSocket connections are allowed to same origin
        # Enhanced with object-src 'none' to block plugins and upgrade-insecure-requests
        self.content_security_policy = content_security_policy or (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "object-src 'none'; "
            "upgrade-insecure-requests"
        )

        # Default Permissions-Policy: Restrict access to sensitive browser features
        self.permissions_policy = permissions_policy or (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )

        # HSTS: Force HTTPS connections
        # Default: 1 year (31536000 seconds) with includeSubDomains
        # Set to None to disable (e.g., for local development over HTTP)
        self.strict_transport_security = strict_transport_security

        # Cache-Control: Prevent caching of security-sensitive responses
        # Set to None to skip (e.g., for static assets that should be cached)
        self.cache_control = cache_control

        # X-Permitted-Cross-Domain-Policies: Block cross-domain policy file access
        # Default: "none" to prevent Adobe Flash/Acrobat from loading cross-domain data
        self.cross_domain_policies = cross_domain_policies

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Add security headers to the response.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint handler

        Returns:
            HTTP response with security headers added
        """
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = self.content_type_options
        response.headers["X-Frame-Options"] = self.frame_options
        response.headers["X-XSS-Protection"] = self.xss_protection
        response.headers["Referrer-Policy"] = self.referrer_policy
        response.headers["Content-Security-Policy"] = self.content_security_policy
        response.headers["Permissions-Policy"] = self.permissions_policy

        # Add HSTS header if configured (default: enabled)
        # Note: HSTS should only be used when serving over HTTPS
        # Browsers will ignore HSTS headers over plain HTTP, but we include it
        # to ensure it's set when HTTPS is configured upstream (e.g., reverse proxy)
        if self.strict_transport_security is not None:
            response.headers["Strict-Transport-Security"] = self.strict_transport_security

        # Add Cache-Control header if configured (default: enabled)
        if self.cache_control is not None:
            response.headers["Cache-Control"] = self.cache_control

        # Add X-Permitted-Cross-Domain-Policies header
        response.headers["X-Permitted-Cross-Domain-Policies"] = self.cross_domain_policies

        return response
