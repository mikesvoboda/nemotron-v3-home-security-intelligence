"""Unit tests for security headers middleware.

Tests the SecurityHeadersMiddleware to ensure proper security headers are
added to all HTTP responses.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware.security_headers import SecurityHeadersMiddleware


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware class."""

    @pytest.fixture
    def app_with_security_headers(self):
        """Create a test FastAPI app with SecurityHeadersMiddleware."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        return app

    def test_x_content_type_options_header(self, app_with_security_headers):
        """Test that X-Content-Type-Options header is set to nosniff."""
        client = TestClient(app_with_security_headers)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options_header(self, app_with_security_headers):
        """Test that X-Frame-Options header is set to DENY."""
        client = TestClient(app_with_security_headers)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_x_xss_protection_header(self, app_with_security_headers):
        """Test that X-XSS-Protection header is set correctly."""
        client = TestClient(app_with_security_headers)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

    def test_referrer_policy_header(self, app_with_security_headers):
        """Test that Referrer-Policy header is set correctly."""
        client = TestClient(app_with_security_headers)
        response = client.get("/test")

        assert response.status_code == 200
        assert "Referrer-Policy" in response.headers
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_content_security_policy_header(self, app_with_security_headers):
        """Test that Content-Security-Policy header is set with secure defaults."""
        client = TestClient(app_with_security_headers)
        response = client.get("/test")

        assert response.status_code == 200
        assert "Content-Security-Policy" in response.headers
        csp = response.headers["Content-Security-Policy"]
        # Verify key CSP directives are present
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_permissions_policy_header(self, app_with_security_headers):
        """Test that Permissions-Policy header restricts browser features."""
        client = TestClient(app_with_security_headers)
        response = client.get("/test")

        assert response.status_code == 200
        assert "Permissions-Policy" in response.headers
        policy = response.headers["Permissions-Policy"]
        # Verify key restrictions are present
        assert "camera=()" in policy
        assert "microphone=()" in policy
        assert "geolocation=()" in policy

    def test_all_security_headers_present(self, app_with_security_headers):
        """Test that all required security headers are present in response."""
        client = TestClient(app_with_security_headers)
        response = client.get("/test")

        assert response.status_code == 200

        required_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Content-Security-Policy",
            "Permissions-Policy",
        ]

        for header in required_headers:
            assert header in response.headers, f"Missing security header: {header}"

    def test_headers_on_different_endpoints(self, app_with_security_headers):
        """Test that security headers are applied to all endpoints."""
        client = TestClient(app_with_security_headers)

        # Test different endpoints
        for path in ["/test", "/health"]:
            response = client.get(path)
            assert "X-Content-Type-Options" in response.headers
            assert "X-Frame-Options" in response.headers
            assert "Content-Security-Policy" in response.headers

    def test_custom_content_type_options(self):
        """Test that custom X-Content-Type-Options value can be set."""
        app = FastAPI()
        # While "nosniff" is the only valid value, test that the parameter works
        app.add_middleware(SecurityHeadersMiddleware, content_type_options="nosniff")

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_custom_frame_options(self):
        """Test that custom X-Frame-Options value can be set."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, frame_options="SAMEORIGIN")

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"

    def test_custom_xss_protection(self):
        """Test that custom X-XSS-Protection value can be set."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, xss_protection="0")

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.headers["X-XSS-Protection"] == "0"

    def test_custom_referrer_policy(self):
        """Test that custom Referrer-Policy value can be set."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, referrer_policy="no-referrer")

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.headers["Referrer-Policy"] == "no-referrer"

    def test_custom_content_security_policy(self):
        """Test that custom Content-Security-Policy value can be set."""
        app = FastAPI()
        custom_csp = "default-src 'none'; script-src 'self'"
        app.add_middleware(SecurityHeadersMiddleware, content_security_policy=custom_csp)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.headers["Content-Security-Policy"] == custom_csp

    def test_custom_permissions_policy(self):
        """Test that custom Permissions-Policy value can be set."""
        app = FastAPI()
        custom_policy = "camera=(), microphone=()"
        app.add_middleware(SecurityHeadersMiddleware, permissions_policy=custom_policy)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.headers["Permissions-Policy"] == custom_policy

    def test_headers_on_http_error_responses(self):
        """Test that security headers are added on HTTP error responses."""
        from fastapi import HTTPException

        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/error")
        async def error_endpoint():
            raise HTTPException(status_code=400, detail="Bad request")

        client = TestClient(app)
        response = client.get("/error")

        # On HTTP errors (like 400), security headers should be present
        assert response.status_code == 400
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers

    def test_headers_on_not_found(self):
        """Test that security headers are added on 404 responses."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/nonexistent")

        assert response.status_code == 404
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers


class TestSecurityHeadersDefaults:
    """Test default values of security headers."""

    def test_default_csp_allows_self(self):
        """Test that default CSP allows 'self' for most directives."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp

    def test_default_csp_allows_inline_styles(self):
        """Test that default CSP allows inline styles for Tailwind/Tremor compatibility."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        csp = response.headers["Content-Security-Policy"]
        assert "style-src 'self' 'unsafe-inline'" in csp

    def test_default_csp_allows_websockets(self):
        """Test that default CSP allows WebSocket connections."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        csp = response.headers["Content-Security-Policy"]
        assert "connect-src 'self' ws: wss:" in csp

    def test_default_csp_prevents_framing(self):
        """Test that default CSP prevents page from being framed."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        csp = response.headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in csp

    def test_default_permissions_policy_restricts_camera(self):
        """Test that default Permissions-Policy restricts camera access."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        policy = response.headers["Permissions-Policy"]
        assert "camera=()" in policy

    def test_default_permissions_policy_restricts_payment(self):
        """Test that default Permissions-Policy restricts payment API access."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        policy = response.headers["Permissions-Policy"]
        assert "payment=()" in policy


class TestSecurityHeadersMiddlewareInit:
    """Test SecurityHeadersMiddleware initialization."""

    def test_middleware_stores_custom_values(self):
        """Test that middleware stores custom values correctly."""
        app = FastAPI()
        middleware = SecurityHeadersMiddleware(
            app,
            content_type_options="custom-cto",
            frame_options="custom-fo",
            xss_protection="custom-xss",
            referrer_policy="custom-rp",
            content_security_policy="custom-csp",
            permissions_policy="custom-pp",
        )

        assert middleware.content_type_options == "custom-cto"
        assert middleware.frame_options == "custom-fo"
        assert middleware.xss_protection == "custom-xss"
        assert middleware.referrer_policy == "custom-rp"
        assert middleware.content_security_policy == "custom-csp"
        assert middleware.permissions_policy == "custom-pp"

    def test_middleware_uses_defaults_when_not_specified(self):
        """Test that middleware uses default values when not specified."""
        app = FastAPI()
        middleware = SecurityHeadersMiddleware(app)

        assert middleware.content_type_options == "nosniff"
        assert middleware.frame_options == "DENY"
        assert middleware.xss_protection == "1; mode=block"
        assert middleware.referrer_policy == "strict-origin-when-cross-origin"
        assert "default-src 'self'" in middleware.content_security_policy
        assert "camera=()" in middleware.permissions_policy
