"""Security headers middleware for HTTP responses.

This module implements security headers to protect against common web vulnerabilities:
- X-Content-Type-Options: Prevents MIME type sniffing
- X-Frame-Options: Prevents clickjacking attacks
- X-XSS-Protection: Enables browser XSS filtering (legacy, but still useful)
- Referrer-Policy: Controls referrer information sent with requests
- Content-Security-Policy: Restricts resource loading sources
- Permissions-Policy: Controls browser feature access
- Strict-Transport-Security: Enforces HTTPS connections (HSTS)
- Cross-Origin-Opener-Policy: Isolates browsing context
- Cross-Origin-Resource-Policy: Prevents cross-origin resource loading
"""

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


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
        hsts_enabled: Whether to add HSTS header (only on HTTPS)
        hsts_max_age: HSTS max-age in seconds (default: 1 year)
        hsts_include_subdomains: Whether HSTS includes subdomains
        hsts_preload: Whether to add HSTS preload directive (for hstspreload.org registration)
        csp_report_only: Use Content-Security-Policy-Report-Only instead
        cross_origin_opener_policy: Cross-Origin-Opener-Policy value
        cross_origin_resource_policy: Cross-Origin-Resource-Policy value
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
        hsts_enabled: bool = True,
        hsts_max_age: int = 31536000,
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = False,
        csp_report_only: bool = False,
        cross_origin_opener_policy: str = "same-origin",
        cross_origin_resource_policy: str = "same-origin",
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
            hsts_enabled: Add HSTS header when request is HTTPS (default: True)
            hsts_max_age: HSTS max-age in seconds (default: 31536000 = 1 year)
            hsts_include_subdomains: Include subdomains in HSTS (default: True)
            hsts_preload: Add preload directive for hstspreload.org (default: False)
            csp_report_only: Use report-only mode for CSP testing (default: False)
            cross_origin_opener_policy: COOP value (default: "same-origin")
            cross_origin_resource_policy: CORP value (default: "same-origin")
        """
        super().__init__(app)
        self.content_type_options = content_type_options
        self.frame_options = frame_options
        self.xss_protection = xss_protection
        self.referrer_policy = referrer_policy

        # HSTS settings
        self.hsts_enabled = hsts_enabled
        self.hsts_max_age = hsts_max_age
        self.hsts_include_subdomains = hsts_include_subdomains
        self.hsts_preload = hsts_preload

        # CSP settings
        self.csp_report_only = csp_report_only

        # Cross-Origin policies
        self.cross_origin_opener_policy = cross_origin_opener_policy
        self.cross_origin_resource_policy = cross_origin_resource_policy

        # Default CSP: Allow self, inline styles (for Tremor/Tailwind), and data URIs for images
        # WebSocket connections are allowed to same origin
        # Added: upgrade-insecure-requests to automatically upgrade HTTP to HTTPS
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
        response.headers["Permissions-Policy"] = self.permissions_policy

        # Add CSP header (report-only or enforcing mode)
        csp_header_name = (
            "Content-Security-Policy-Report-Only"
            if self.csp_report_only
            else "Content-Security-Policy"
        )
        response.headers[csp_header_name] = self.content_security_policy

        # Add Cross-Origin headers for additional isolation
        response.headers["Cross-Origin-Opener-Policy"] = self.cross_origin_opener_policy
        response.headers["Cross-Origin-Resource-Policy"] = self.cross_origin_resource_policy

        # Add HSTS header only when request came via HTTPS
        # Check both the scheme and X-Forwarded-Proto header (for reverse proxy setups)
        is_https = (
            request.url.scheme == "https"
            or request.headers.get("X-Forwarded-Proto", "").lower() == "https"
        )
        if self.hsts_enabled and is_https:
            hsts_value = f"max-age={self.hsts_max_age}"
            if self.hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            if self.hsts_preload:
                hsts_value += "; preload"
            response.headers["Strict-Transport-Security"] = hsts_value

        return response
