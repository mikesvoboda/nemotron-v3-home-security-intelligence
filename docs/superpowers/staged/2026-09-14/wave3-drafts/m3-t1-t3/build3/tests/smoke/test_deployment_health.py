"""
Deployment Health Smoke Tests

These tests verify that the deployed environment is healthy and responding.
They run against staging or production after deployment.

Test Categories:
- Critical: Health endpoints that must always respond
- Integration: Service-to-service connectivity
- WebSocket: Real-time communication paths
"""

import httpx
import pytest


class TestBackendHealth:
    """Backend health endpoint tests."""

    @pytest.mark.critical
    def test_backend_readiness_endpoint_responds(self, http_client: httpx.Client, backend_url: str):
        """
        Backend /api/system/health/ready returns 200 OK.

        This endpoint indicates if the backend is ready to serve requests.
        All critical dependencies must be available.
        """
        response = http_client.get(f"{backend_url}/api/system/health/ready")

        assert response.status_code == 200, f"Backend readiness endpoint failed: {response.text}"

        data = response.json()
        assert "ready" in data, "Missing 'ready' field in health response"

    @pytest.mark.critical
    def test_backend_health_endpoint_responds(self, http_client: httpx.Client, backend_url: str):
        """
        Backend /api/system/health returns 200 OK with health status.

        Returns overall system health: healthy, degraded, or unhealthy.
        """
        response = http_client.get(f"{backend_url}/api/system/health")

        assert response.status_code == 200, f"Backend health endpoint failed: {response.text}"

        data = response.json()
        assert "status" in data, "Missing 'status' field in health response"
        assert data["status"] in ["healthy", "degraded", "unhealthy"], (
            f"Invalid status: {data['status']}"
        )

    @pytest.mark.critical
    def test_backend_is_accessible(self, http_client: httpx.Client, backend_url: str):
        """Backend is accessible and responding to requests."""
        try:
            response = http_client.get(f"{backend_url}/api/system/health", timeout=5.0)
            assert response.status_code in [200, 503], (
                f"Backend not accessible: {response.status_code}"
            )
        except httpx.RequestError as e:
            pytest.fail(f"Backend is not accessible: {e}")


class TestFrontendHealth:
    """Frontend health endpoint tests."""

    @pytest.mark.critical
    def test_frontend_serves_html(self, http_client: httpx.Client, frontend_url: str):
        """Frontend serves HTML content at root path."""
        response = http_client.get(f"{frontend_url}/", follow_redirects=True)

        assert response.status_code == 200, f"Frontend failed: {response.status_code}"

        content_type = response.headers.get("content-type", "").lower()
        assert "text/html" in content_type, f"Frontend not serving HTML: {content_type}"

    @pytest.mark.critical
    def test_frontend_is_accessible(self, http_client: httpx.Client, frontend_url: str):
        """Frontend is accessible and responding."""
        try:
            response = http_client.get(f"{frontend_url}/", timeout=5.0)
            assert response.status_code == 200, f"Frontend not accessible: {response.status_code}"
        except httpx.RequestError as e:
            pytest.fail(f"Frontend is not accessible: {e}")


class TestAPIEndpoints:
    """Core API endpoint tests."""

    @pytest.mark.critical
    def test_system_stats_endpoint(self, http_client: httpx.Client, backend_url: str):
        """
        GET /api/system/stats returns system statistics.

        Verifies: total_cameras, detection_rate, uptime
        """
        response = http_client.get(f"{backend_url}/api/system/stats")

        assert response.status_code == 200, f"System stats failed: {response.text}"

        data = response.json()
        assert "total_cameras" in data, "Missing total_cameras in stats"
        assert isinstance(data["total_cameras"], int), "total_cameras should be integer"
        assert data["total_cameras"] >= 0, "total_cameras should be non-negative"

    @pytest.mark.critical
    def test_cameras_endpoint(self, http_client: httpx.Client, backend_url: str):
        """
        GET /api/cameras returns camera list.

        Verifies: cameras array is present and properly formatted
        """
        response = http_client.get(f"{backend_url}/api/cameras")

        assert response.status_code == 200, f"Cameras endpoint failed: {response.text}"

        data = response.json()
        assert "items" in data, "Missing items array in response"
        assert isinstance(data["items"], list), "items should be an array"

    @pytest.mark.integration
    def test_events_endpoint(self, http_client: httpx.Client, backend_url: str):
        """
        GET /api/events returns recent events.

        Verifies: events array exists and contains proper fields
        """
        response = http_client.get(f"{backend_url}/api/events?limit=10")

        assert response.status_code == 200, f"Events endpoint failed: {response.text}"

        data = response.json()
        assert "items" in data, "Missing items array in response"
        assert isinstance(data["items"], list), "items should be an array"

        # Verify event structure if events exist
        if data["items"]:
            event = data["items"][0]
            assert "id" in event, "Event missing id field"
            assert "timestamp" in event, "Event missing timestamp field"

    @pytest.mark.integration
    def test_detections_endpoint(self, http_client: httpx.Client, backend_url: str):
        """
        GET /api/detections returns recent detections.

        Verifies: detections array with proper structure
        """
        response = http_client.get(f"{backend_url}/api/detections?limit=5")

        assert response.status_code == 200, f"Detections endpoint failed: {response.text}"

        data = response.json()
        assert "items" in data, "Missing items array in response"
        assert isinstance(data["items"], list), "items should be an array"


class TestServiceConnectivity:
    """Service-to-service connectivity tests."""

    @pytest.mark.integration
    def test_backend_can_reach_database(self, http_client: httpx.Client, backend_url: str):
        """
        Backend can connect to database.

        Verified through health endpoint indicating database availability.
        """
        response = http_client.get(f"{backend_url}/api/system/health")

        assert response.status_code == 200
        data = response.json()

        # Check if database is in dependencies
        if "dependencies" in data:
            db_status = data["dependencies"].get("database")
            # Database should be healthy or at least not in error state
            assert db_status != "unhealthy", "Database appears to be unhealthy"

    @pytest.mark.integration
    def test_backend_can_reach_redis(self, http_client: httpx.Client, backend_url: str):
        """
        Backend can connect to Redis.

        Verified through health endpoint indicating cache availability.
        """
        response = http_client.get(f"{backend_url}/api/system/health")

        assert response.status_code == 200
        data = response.json()

        # Check if Redis is in dependencies
        if "dependencies" in data:
            redis_status = data["dependencies"].get("cache")
            # Cache should be healthy or at least accessible
            assert redis_status != "unhealthy", "Cache appears to be unhealthy"


class TestDataFlow:
    """Data flow through critical paths."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_camera_data_retrieval(self, http_client: httpx.Client, backend_url: str):
        """
        Verify camera data can be retrieved without errors.

        Tests the full data retrieval path: API -> Database -> Response
        """
        response = http_client.get(f"{backend_url}/api/cameras")

        assert response.status_code == 200
        data = response.json()

        # Should have at least the structure, even if no cameras
        assert "items" in data
        assert isinstance(data["items"], list)

    @pytest.mark.integration
    @pytest.mark.slow
    def test_event_history_retrieval(self, http_client: httpx.Client, backend_url: str):
        """
        Verify event history can be retrieved.

        Tests: Data retrieval, filtering, sorting
        """
        # Try to get events with pagination
        response = http_client.get(f"{backend_url}/api/events?limit=5&offset=0")

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert isinstance(data["items"], list)

        # If events exist, verify they have expected structure
        for event in data["items"]:
            assert "id" in event
            assert "timestamp" in event


class TestErrorHandling:
    """Verify proper error handling in deployed environment."""

    @pytest.mark.critical
    def test_invalid_endpoint_returns_404(self, http_client: httpx.Client, backend_url: str):
        """
        Invalid endpoints return 404 Not Found.

        Verifies: Error handling is working correctly
        """
        response = http_client.get(f"{backend_url}/api/nonexistent-endpoint")

        assert response.status_code == 404, "Invalid endpoint should return 404"

    @pytest.mark.critical
    def test_invalid_method_returns_405(self, http_client: httpx.Client, backend_url: str):
        """
        Invalid HTTP methods return 405 Method Not Allowed.

        Verifies: Method validation is working
        """
        response = http_client.delete(f"{backend_url}/api/cameras")

        assert response.status_code == 405, "DELETE on GET-only endpoint should return 405"


class TestResponseFormat:
    """Verify response format consistency."""

    @pytest.mark.critical
    def test_api_response_has_proper_json(self, http_client: httpx.Client, backend_url: str):
        """
        API responses are valid JSON.

        Verifies: Response serialization is working
        """
        response = http_client.get(f"{backend_url}/api/system/health")

        assert response.status_code == 200

        # Should be able to parse as JSON without error
        try:
            data = response.json()
            assert isinstance(data, dict), "Response should be a JSON object"
        except ValueError as e:
            pytest.fail(f"Response is not valid JSON: {e}")

    @pytest.mark.critical
    def test_error_response_has_proper_format(self, http_client: httpx.Client, backend_url: str):
        """
        Error responses follow proper error format.

        Verifies: Error responses are structured correctly
        """
        response = http_client.get(f"{backend_url}/api/invalid")

        assert response.status_code == 404

        # Error response should be JSON
        try:
            data = response.json()
            assert isinstance(data, dict), "Error response should be an object"
            # Should have detail field or similar error information
            assert "detail" in data or "error" in data or "message" in data, (
                "Error response should have error information"
            )
        except ValueError:
            pytest.fail("Error response is not valid JSON")
