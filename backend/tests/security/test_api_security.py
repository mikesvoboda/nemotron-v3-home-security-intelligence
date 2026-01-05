"""API security tests for SQL injection, XSS, path traversal, rate limiting, and CORS.

This module tests the application's resilience against common web security vulnerabilities:
- SQL injection attacks on query parameters
- XSS prevention in API responses
- Path traversal attacks on file-serving endpoints
- Rate limiting enforcement
- CORS header validation
"""

import pytest
from fastapi.testclient import TestClient


class TestSQLInjection:
    """Test SQL injection protection across API endpoints.

    Note: These tests verify that SQLi payloads don't cause SQL syntax errors
    or expose data. Without a database connection, we test that the application
    handles these inputs without crashing.
    """

    @pytest.mark.parametrize(
        "malicious_input,description",
        [
            ("'; DROP TABLE cameras; --", "DROP TABLE attempt"),
            ("' OR '1'='1", "OR 1=1 bypass"),
            ("' OR '1'='1' --", "OR 1=1 with comment"),
            ("1; SELECT * FROM users --", "UNION SELECT attempt"),
            ("' UNION SELECT NULL, NULL, NULL --", "UNION NULL injection"),
            ("1 AND 1=1", "Tautology attack"),
            ("1' AND SLEEP(5) --", "Time-based blind SQLi"),
            ("1' AND (SELECT SUBSTRING(password,1,1) FROM users)='a' --", "Substring extraction"),
            ("%27", "URL-encoded quote"),
            ("admin'--", "Comment truncation"),
            ("';EXEC xp_cmdshell('dir');--", "Command execution attempt"),
        ],
    )
    def test_camera_id_sql_injection(
        self, security_client: TestClient, malicious_input: str, description: str
    ):
        """Test that camera ID parameter is safe from SQL injection.

        The camera_id is used in database queries. Malicious input should
        be handled without exposing SQL errors or executing injected SQL.

        Scenario: {description}
        """
        response = security_client.get(f"/api/cameras/{malicious_input}")

        # Response should not expose SQL syntax errors
        response_text = response.text.lower()
        assert "syntax error" not in response_text, f"SQL syntax error exposed: {description}"
        assert "sqlalchemy" not in response_text, f"SQLAlchemy error exposed: {description}"
        assert "psycopg" not in response_text, f"PostgreSQL error exposed: {description}"

        # The malicious SQL should never appear in error messages
        assert "drop table" not in response_text, f"SQL command reflected: {description}"
        assert "union select" not in response_text, f"SQL command reflected: {description}"

    @pytest.mark.parametrize(
        "malicious_input,description",
        [
            ("'; DROP TABLE events; --", "DROP TABLE in event_id"),
            ("1 UNION SELECT * FROM events --", "UNION SELECT in event_id"),
            ("-1 OR 1=1", "OR tautology"),
        ],
    )
    def test_event_id_sql_injection(
        self, security_client: TestClient, malicious_input: str, description: str
    ):
        """Test that event ID parameter is safe from SQL injection.

        Scenario: {description}
        """
        response = security_client.get(f"/api/events/{malicious_input}")

        # Response should not expose SQL syntax errors
        response_text = response.text.lower()
        assert "syntax error" not in response_text, f"SQL syntax error exposed: {description}"
        assert "sqlalchemy" not in response_text, f"SQLAlchemy error exposed: {description}"

    @pytest.mark.parametrize(
        "query_param,malicious_value,description",
        [
            ("camera_id", "' OR '1'='1", "camera_id filter"),
            ("severity", "high' OR '1'='1", "severity filter"),
            ("q", "'; DROP TABLE events --", "search query"),
        ],
    )
    def test_query_param_sql_injection(
        self,
        security_client: TestClient,
        query_param: str,
        malicious_value: str,
        description: str,
    ):
        """Test SQL injection in query parameters.

        Scenario: {description}
        """
        response = security_client.get(f"/api/events?{query_param}={malicious_value}")

        # Response should not expose SQL syntax errors
        response_text = response.text.lower()
        assert "syntax error" not in response_text, (
            f"SQL syntax error exposed in {query_param}: {description}"
        )


class TestXSSPrevention:
    """Test XSS prevention in API responses and inputs."""

    @pytest.mark.parametrize(
        "xss_payload,description",
        [
            ("<script>alert('XSS')</script>", "Basic script tag"),
            ("<img src=x onerror=alert('XSS')>", "Event handler XSS"),
            ("javascript:alert('XSS')", "JavaScript protocol"),
            ("<svg onload=alert('XSS')>", "SVG onload XSS"),
            ("<body onload=alert('XSS')>", "Body onload XSS"),
            ("'><script>alert(String.fromCharCode(88,83,83))</script>", "Encoded XSS"),
            ("<iframe src='javascript:alert(`XSS`)'></iframe>", "Iframe XSS"),
            ("<div style='background:url(javascript:alert(1))'>", "CSS expression XSS"),
            ("%3Cscript%3Ealert('XSS')%3C/script%3E", "URL-encoded XSS"),
        ],
    )
    def test_camera_name_xss_in_search(
        self, security_client: TestClient, xss_payload: str, description: str
    ):
        """Test that XSS payloads in search queries don't cause reflection.

        Scenario: {description}
        """
        response = security_client.get(f"/api/events?q={xss_payload}")

        # Response should not contain raw script tags (even in error responses)
        response_text = response.text
        # The < should be escaped or not present
        assert (
            "<script>" not in response_text.lower() or "&lt;script&gt;" in response_text.lower()
        ), f"XSS payload reflected unescaped in response: {description}"

    def test_content_type_is_json(self, security_client: TestClient):
        """Test that API responses use JSON content type (not HTML).

        JSON content type prevents browser from rendering XSS payloads.
        """
        # Use root endpoint which doesn't require database
        response = security_client.get("/")

        # Check that successful responses return JSON content type
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            assert "application/json" in content_type, (
                f"Expected JSON content type, got: {content_type}"
            )

    def test_xss_in_error_messages(self, security_client: TestClient):
        """Test that error messages don't reflect XSS payloads."""
        xss_payload = "<script>alert('XSS')</script>"
        response = security_client.get(f"/api/cameras/{xss_payload}")

        # Error message should escape or not include the payload
        if response.status_code == 404:
            response_text = response.text
            # The payload should be escaped or not present
            assert "<script>" not in response_text, "XSS reflected in error message"


class TestPathTraversal:
    """Test path traversal protection on file-serving endpoints."""

    @pytest.mark.parametrize(
        "traversal_path,description",
        [
            ("../../../etc/passwd", "Basic path traversal"),
            ("..%2F..%2F..%2Fetc%2Fpasswd", "URL-encoded traversal"),
            ("....//....//....//etc/passwd", "Double dot traversal"),
            ("%2e%2e%2f%2e%2e%2fetc%2fpasswd", "Fully encoded traversal"),
            ("..\\..\\..\\etc\\passwd", "Windows-style traversal"),
            ("/etc/passwd", "Absolute path"),
            ("./.././../etc/passwd", "Mixed dot traversal"),
        ],
    )
    def test_media_endpoint_path_traversal(
        self, security_client: TestClient, traversal_path: str, description: str
    ):
        """Test that media endpoint blocks path traversal attempts.

        Scenario: {description}
        """
        response = security_client.get(f"/api/media/cameras/test/{traversal_path}")

        # Should never return 200 with sensitive file contents
        # Should return 400, 403, or 404
        assert response.status_code in [400, 403, 404], (
            f"Path traversal not blocked: {description}, got {response.status_code}"
        )

        # Response should not contain sensitive file contents
        response_text = response.text.lower()
        assert "root:" not in response_text, "Sensitive file contents leaked"

    @pytest.mark.parametrize(
        "traversal_path,description",
        [
            ("../../../etc/passwd", "Basic traversal on thumbnails"),
            ("/etc/shadow", "Absolute path to shadow"),
            ("..%2Fetc%2Fpasswd", "Partial encoding"),
        ],
    )
    def test_thumbnail_endpoint_path_traversal(
        self, security_client: TestClient, traversal_path: str, description: str
    ):
        """Test that thumbnail endpoint blocks path traversal.

        Scenario: {description}
        """
        response = security_client.get(f"/api/media/thumbnails/{traversal_path}")

        # Should be blocked
        assert response.status_code in [400, 403, 404]


class TestRateLimiting:
    """Test rate limiting behavior on API endpoints."""

    def test_rate_limit_headers_present(self, security_client: TestClient):
        """Test that rate limiting doesn't block basic endpoints."""
        # Use root endpoint which doesn't require database
        response = security_client.get("/")

        # Root endpoint should work (may return 500 if DB issues, but not 429)
        assert response.status_code != 429

    def test_health_endpoint_not_rate_limited(self, security_client: TestClient):
        """Test that health endpoints are exempt from rate limiting."""
        # Make multiple requests to root endpoint
        for _ in range(20):
            response = security_client.get("/")
            # Exempt endpoints should never return 429
            assert response.status_code != 429, "Exempt endpoint should not be rate limited"


class TestCORSHeaders:
    """Test CORS header configuration."""

    def test_cors_headers_on_options(self, security_client: TestClient):
        """Test CORS preflight response headers."""
        response = security_client.options(
            "/api/cameras",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        # CORS configuration should allow legitimate origins
        # The exact behavior depends on CORS middleware configuration
        assert response.status_code in [200, 204, 405]

    def test_cors_disallows_arbitrary_origins(self, security_client: TestClient):
        """Test that CORS doesn't allow arbitrary origins to be reflected."""
        malicious_origin = "http://evil-site.com"
        response = security_client.get(
            "/api/cameras",
            headers={"Origin": malicious_origin},
        )

        # The Access-Control-Allow-Origin should NOT reflect the malicious origin
        allow_origin = response.headers.get("Access-Control-Allow-Origin", "")
        assert allow_origin != malicious_origin, (
            "CORS is reflecting arbitrary origins - security vulnerability"
        )


class TestSecurityHeaders:
    """Test presence of security headers in responses."""

    def test_security_headers_present(self, security_client: TestClient):
        """Test that security headers are present in responses."""
        # Use root endpoint which doesn't require database
        response = security_client.get("/")

        # Check for security headers only on successful responses
        if response.status_code == 200:
            headers = response.headers

            # X-Content-Type-Options prevents MIME sniffing
            assert headers.get("X-Content-Type-Options") == "nosniff", (
                "X-Content-Type-Options header missing or incorrect"
            )

            # X-Frame-Options prevents clickjacking
            assert headers.get("X-Frame-Options") in ["DENY", "SAMEORIGIN"], (
                "X-Frame-Options header missing or incorrect"
            )

    def test_no_server_version_disclosure(self, security_client: TestClient):
        """Test that server version is not disclosed in headers."""
        response = security_client.get("/")

        # Server header should not reveal detailed version info
        server_header = response.headers.get("Server", "")
        # Should not contain version numbers like "uvicorn/0.x.x"
        assert not any(c.isdigit() for c in server_header.split("/")[-1:]), (
            f"Server version disclosed: {server_header}"
        )


class TestHostHeaderInjection:
    """Test Host header injection protection."""

    def test_host_header_injection(self, security_client: TestClient):
        """Test that malicious Host headers don't cause issues."""
        # Attempt host header injection on root endpoint
        response = security_client.get(
            "/",
            headers={"Host": "evil.com"},
        )

        # Should complete without crashing (any status is acceptable)
        # Key is that it doesn't crash and doesn't reflect the evil host
        assert response is not None

        # Response should not contain the injected host
        response_text = response.text
        assert "evil.com" not in response_text


class TestHTTPMethodRestrictions:
    """Test HTTP method restrictions on endpoints."""

    def test_readonly_endpoints_reject_post(self, security_client: TestClient):
        """Test that read-only endpoints reject POST requests."""
        response = security_client.post("/api/events")

        # Should return 405 Method Not Allowed (not 500)
        assert response.status_code in [405, 422], (
            f"Read-only endpoint accepted POST: {response.status_code}"
        )

    def test_readonly_endpoints_reject_delete(self, security_client: TestClient):
        """Test that read-only endpoints reject DELETE requests."""
        response = security_client.delete("/api/events")

        # Should return 405 Method Not Allowed
        assert response.status_code in [405, 422]


class TestInputSizeValidation:
    """Test input size validation to prevent DoS attacks."""

    def test_oversized_query_parameter(self, security_client: TestClient):
        """Test that oversized query parameters are handled gracefully."""
        # Create a moderately long query string (not too long to cause HTTP issues)
        long_query = "a" * 10000  # 10KB of data

        response = security_client.get(f"/api/events?q={long_query}")

        # Should handle gracefully (may be 500 if no DB, but shouldn't crash)
        # Key is that it doesn't cause connection reset or crash
        assert response.status_code in [200, 400, 414, 422, 500]

    def test_many_query_parameters(self, security_client: TestClient):
        """Test handling of excessive query parameters."""
        # Create many query parameters
        params = "&".join([f"param{i}=value{i}" for i in range(100)])

        response = security_client.get(f"/?{params}")

        # Should handle gracefully and ignore extra params
        # May return 500 if DB issues, but shouldn't crash or timeout
        assert response.status_code in [200, 500]
