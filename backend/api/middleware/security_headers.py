"""Security headers middleware for HTTP responses.

This module implements security headers to protect against common web vulnerabilities:
- X-Content-Type-Options: Prevents MIME type sniffing
- X-Frame-Options: Prevents clickjacking attacks
- X-XSS-Protection: Enables browser XSS filtering (legacy, but still useful)
- Referrer-Policy: Controls referrer information sent with requests
- Content-Security-Policy: Restricts resource loading sources
- Permissions-Policy: Controls browser feature access
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
        """
        super().__init__(app)
        self.content_type_options = content_type_options
        self.frame_options = frame_options
        self.xss_protection = xss_protection
        self.referrer_policy = referrer_policy

        # Default CSP: Allow self, inline styles (for Tremor/Tailwind), and data URIs for images
        # WebSocket connections are allowed to same origin
        self.content_security_policy = content_security_policy or (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
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
        response.headers["Content-Security-Policy"] = self.content_security_policy
        response.headers["Permissions-Policy"] = self.permissions_policy

        return response
