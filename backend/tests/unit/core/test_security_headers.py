"""Unit tests for security headers middleware.

Tests the SecurityHeadersMiddleware to ensure proper security headers are
added to all HTTP responses.
"""

import pytest
from fastapi import FastAPI, HTTPException
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
        assert "camera=()" in policy
        assert "microphone=()" in policy
        assert "geolocation=()" in policy

    def test_all_security_headers_present(self, app_with_security_headers):
        """Test that all required security headers are present in response."""
        client = TestClient(app_with_security_headers)
        response = client.get("/test")
        assert response.status_code == 200
        for header in [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Content-Security-Policy",
            "Permissions-Policy",
        ]:
            assert header in response.headers, f"Missing security header: {header}"

    def test_headers_on_different_endpoints(self, app_with_security_headers):
        """Test that security headers are applied to all endpoints."""
        client = TestClient(app_with_security_headers)
        for path in ["/test", "/health"]:
            response = client.get(path)
            assert "X-Content-Type-Options" in response.headers
            assert "X-Frame-Options" in response.headers
            assert "Content-Security-Policy" in response.headers

    def test_custom_content_type_options(self):
        """Test that custom X-Content-Type-Options value can be set."""
        app = FastAPI()
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
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/error")
        async def error_endpoint():
            raise HTTPException(status_code=400, detail="Bad request")

        client = TestClient(app)
        response = client.get("/error")
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
        """Test that default CSP allows inline styles for Tailwind/Tremor."""
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


class TestHSTSHeader:
    """Test HSTS (HTTP Strict Transport Security) header functionality."""

    def test_hsts_header_present_by_default(self):
        """Test that Strict-Transport-Security header is present in responses."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert "Strict-Transport-Security" in response.headers

    def test_hsts_header_value_contains_max_age(self):
        """Test that HSTS header contains max-age directive."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        hsts = response.headers["Strict-Transport-Security"]
        assert "max-age=" in hsts

    def test_hsts_default_max_age_is_one_year(self):
        """Test that default HSTS max-age is 1 year (31536000 seconds)."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        hsts = response.headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts

    def test_hsts_includes_subdomains(self):
        """Test that HSTS header includes includeSubDomains directive."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        hsts = response.headers["Strict-Transport-Security"]
        assert "includeSubDomains" in hsts

    def test_custom_hsts_value(self):
        """Test that custom HSTS value can be set."""
        app = FastAPI()
        custom_hsts = "max-age=86400"
        app.add_middleware(SecurityHeadersMiddleware, strict_transport_security=custom_hsts)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        assert response.headers["Strict-Transport-Security"] == custom_hsts

    def test_hsts_disabled_when_set_to_none(self):
        """Test that HSTS header is not included when explicitly disabled."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, strict_transport_security=None)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        assert "Strict-Transport-Security" not in response.headers

    def test_hsts_header_on_error_responses(self):
        """Test that HSTS header is present on error responses."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/error")
        async def error_endpoint():
            raise HTTPException(status_code=500, detail="Server error")

        client = TestClient(app)
        response = client.get("/error")
        assert response.status_code == 500
        assert "Strict-Transport-Security" in response.headers


class TestEnhancedCSP:
    """Test enhanced Content Security Policy directives."""

    def test_csp_includes_object_src_none(self):
        """Test that CSP includes object-src 'none' to block plugins."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        csp = response.headers["Content-Security-Policy"]
        assert "object-src 'none'" in csp

    def test_csp_includes_upgrade_insecure_requests(self):
        """Test that CSP includes upgrade-insecure-requests directive."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        csp = response.headers["Content-Security-Policy"]
        assert "upgrade-insecure-requests" in csp


class TestCacheControlHeader:
    """Test Cache-Control security header for sensitive responses."""

    def test_cache_control_header_present(self):
        """Test that Cache-Control header is present in responses."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert "Cache-Control" in response.headers

    def test_cache_control_includes_no_store(self):
        """Test that Cache-Control includes no-store for security."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        cache_control = response.headers["Cache-Control"]
        assert "no-store" in cache_control

    def test_custom_cache_control(self):
        """Test that custom Cache-Control value can be set."""
        app = FastAPI()
        custom_cache = "public, max-age=3600"
        app.add_middleware(SecurityHeadersMiddleware, cache_control=custom_cache)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        assert response.headers["Cache-Control"] == custom_cache

    def test_cache_control_disabled_when_none(self):
        """Test that Cache-Control header is not added when disabled."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, cache_control=None)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        cache_control = response.headers.get("Cache-Control", "")
        assert "no-store" not in cache_control


class TestXPermittedCrossDomainPolicies:
    """Test X-Permitted-Cross-Domain-Policies header."""

    def test_cross_domain_policies_header_present(self):
        """Test that X-Permitted-Cross-Domain-Policies header is present."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-Permitted-Cross-Domain-Policies" in response.headers

    def test_cross_domain_policies_default_none(self):
        """Test that X-Permitted-Cross-Domain-Policies defaults to 'none'."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        assert response.headers["X-Permitted-Cross-Domain-Policies"] == "none"

    def test_custom_cross_domain_policies(self):
        """Test that custom X-Permitted-Cross-Domain-Policies value can be set."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, cross_domain_policies="master-only")

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        assert response.headers["X-Permitted-Cross-Domain-Policies"] == "master-only"


class TestAllSecurityHeadersIncludingNew:
    """Test that all security headers including new ones are present."""

    def test_all_security_headers_present(self):
        """Test that all required security headers are present in response."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        required_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Content-Security-Policy",
            "Permissions-Policy",
            "Strict-Transport-Security",
            "Cache-Control",
            "X-Permitted-Cross-Domain-Policies",
        ]
        for header in required_headers:
            assert header in response.headers, f"Missing security header: {header}"


class TestMiddlewareInitWithNewHeaders:
    """Test SecurityHeadersMiddleware initialization with new header parameters."""

    def test_middleware_stores_hsts_value(self):
        """Test that middleware stores HSTS value correctly."""
        app = FastAPI()
        custom_hsts = "max-age=86400"
        middleware = SecurityHeadersMiddleware(app, strict_transport_security=custom_hsts)
        assert middleware.strict_transport_security == custom_hsts

    def test_middleware_stores_cache_control_value(self):
        """Test that middleware stores Cache-Control value correctly."""
        app = FastAPI()
        custom_cache = "public, max-age=3600"
        middleware = SecurityHeadersMiddleware(app, cache_control=custom_cache)
        assert middleware.cache_control == custom_cache

    def test_middleware_stores_cross_domain_policies_value(self):
        """Test that middleware stores cross-domain policies value correctly."""
        app = FastAPI()
        middleware = SecurityHeadersMiddleware(app, cross_domain_policies="master-only")
        assert middleware.cross_domain_policies == "master-only"

    def test_middleware_uses_default_hsts(self):
        """Test that middleware uses default HSTS value when not specified."""
        app = FastAPI()
        middleware = SecurityHeadersMiddleware(app)
        assert middleware.strict_transport_security is not None
        assert "max-age=31536000" in middleware.strict_transport_security

    def test_middleware_uses_default_cache_control(self):
        """Test that middleware uses default Cache-Control value."""
        app = FastAPI()
        middleware = SecurityHeadersMiddleware(app)
        assert middleware.cache_control is not None
        assert "no-store" in middleware.cache_control

    def test_middleware_uses_default_cross_domain_policies(self):
        """Test that middleware uses default cross-domain policies."""
        app = FastAPI()
        middleware = SecurityHeadersMiddleware(app)
        assert middleware.cross_domain_policies == "none"
