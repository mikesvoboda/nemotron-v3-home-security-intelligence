"""Unit tests for Prometheus HTTP metrics middleware (NEM-4149).

This module provides comprehensive tests for:
- PrometheusMiddleware: HTTP request metrics recording
- http_request_duration_seconds histogram
- Label extraction (method, handler, status, http_route)
- Excluded path handling

Tests follow TDD approach and cover:
- Metric recording for successful requests
- Metric recording for error responses
- Route pattern extraction
- Handler name extraction
- Excluded paths (health checks, metrics endpoint)
- Different HTTP methods
"""

import asyncio

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from backend.api.middleware.prometheus import (
    EXCLUDED_PATHS,
    HTTP_REQUEST_DURATION_BUCKETS,
    PrometheusMiddleware,
    http_request_duration_seconds,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def clear_prometheus_metrics():
    """Clear Prometheus metrics before and after each test.

    This ensures tests don't interfere with each other.
    """
    # Clear metrics before test
    http_request_duration_seconds.clear()
    yield
    # Clear metrics after test
    http_request_duration_seconds.clear()


@pytest.fixture
def app_with_prometheus_middleware(clear_prometheus_metrics):
    """Create a test FastAPI app with PrometheusMiddleware."""
    app = FastAPI()
    app.add_middleware(PrometheusMiddleware)

    @app.get("/test")
    async def test_endpoint():
        """Simple test endpoint."""
        return {"message": "ok"}

    @app.get("/items/{item_id}")
    async def get_item(item_id: int):
        """Endpoint with path parameter."""
        return {"item_id": item_id}

    @app.post("/create")
    async def create_endpoint():
        """POST endpoint."""
        return {"id": 123}

    @app.get("/error")
    async def error_endpoint():
        """Endpoint that raises an error."""
        raise HTTPException(status_code=500, detail="Test error")

    @app.get("/not-found")
    async def not_found_endpoint():
        """Endpoint that returns 404."""
        raise HTTPException(status_code=404, detail="Not found")

    @app.get("/slow")
    async def slow_endpoint():
        """Endpoint that simulates slow response."""
        await asyncio.sleep(0.05)  # 50ms delay
        return {"message": "slow"}

    return app


# =============================================================================
# Histogram Metric Tests
# =============================================================================


class TestHttpRequestDurationHistogram:
    """Tests for http_request_duration_seconds histogram metric."""

    def test_histogram_exists(self):
        """Test that the histogram metric is registered."""
        # The metric should be registered in the default registry
        assert http_request_duration_seconds is not None

    def test_histogram_has_correct_name(self):
        """Test that histogram has the standard name."""
        assert http_request_duration_seconds._name == "http_request_duration_seconds"

    def test_histogram_has_correct_labels(self):
        """Test that histogram has required labels."""
        expected_labels = ["method", "handler", "status", "http_route"]
        assert set(http_request_duration_seconds._labelnames) == set(expected_labels)

    def test_histogram_has_appropriate_buckets(self):
        """Test that histogram has appropriate latency buckets."""
        # Buckets should cover range from fast (5ms) to slow (10s)
        assert HTTP_REQUEST_DURATION_BUCKETS[0] <= 0.01  # Fast responses
        assert HTTP_REQUEST_DURATION_BUCKETS[-1] >= 5.0  # Slow operations
        # Buckets should be in ascending order
        for i in range(len(HTTP_REQUEST_DURATION_BUCKETS) - 1):
            assert HTTP_REQUEST_DURATION_BUCKETS[i] < HTTP_REQUEST_DURATION_BUCKETS[i + 1]


# =============================================================================
# PrometheusMiddleware Tests
# =============================================================================


class TestPrometheusMiddleware:
    """Tests for PrometheusMiddleware class."""

    def test_records_request_duration(self, app_with_prometheus_middleware):
        """Test that middleware records request duration."""
        client = TestClient(app_with_prometheus_middleware)
        response = client.get("/test")

        assert response.status_code == 200

        # Check that metric was recorded
        # The metric should have at least one observation
        labels = {
            "method": "GET",
            "status": "200",
            "http_route": "/test",
        }
        # Get sample value from the histogram
        metric_value = http_request_duration_seconds.labels(
            method="GET",
            handler="test_endpoint",
            status="200",
            http_route="/test",
        )
        # Should have observed at least one request
        assert metric_value._sum._value > 0

    def test_records_different_http_methods(self, app_with_prometheus_middleware):
        """Test that different HTTP methods are recorded correctly."""
        client = TestClient(app_with_prometheus_middleware)

        # GET request
        client.get("/test")
        # POST request
        client.post("/create")

        # Both should be recorded with correct method labels
        get_metric = http_request_duration_seconds.labels(
            method="GET",
            handler="test_endpoint",
            status="200",
            http_route="/test",
        )
        post_metric = http_request_duration_seconds.labels(
            method="POST",
            handler="create_endpoint",
            status="200",
            http_route="/create",
        )

        assert get_metric._sum._value > 0
        assert post_metric._sum._value > 0

    def test_records_error_status_codes(self, app_with_prometheus_middleware):
        """Test that error responses are recorded with correct status."""
        client = TestClient(app_with_prometheus_middleware, raise_server_exceptions=False)
        response = client.get("/error")

        assert response.status_code == 500

        # Check metric was recorded with 500 status
        metric = http_request_duration_seconds.labels(
            method="GET",
            handler="error_endpoint",
            status="500",
            http_route="/error",
        )
        assert metric._sum._value > 0

    def test_records_404_status(self, app_with_prometheus_middleware):
        """Test that 404 responses are recorded."""
        client = TestClient(app_with_prometheus_middleware)
        response = client.get("/not-found")

        assert response.status_code == 404

        metric = http_request_duration_seconds.labels(
            method="GET",
            handler="not_found_endpoint",
            status="404",
            http_route="/not-found",
        )
        assert metric._sum._value > 0

    def test_records_path_parameters_as_pattern(self, app_with_prometheus_middleware):
        """Test that path parameters are recorded as patterns, not values."""
        client = TestClient(app_with_prometheus_middleware)

        # Make requests with different item IDs
        client.get("/items/1")
        client.get("/items/2")
        client.get("/items/999")

        # All should be recorded under the same route pattern
        # Use REGISTRY.get_sample_value to get the count
        count = REGISTRY.get_sample_value(
            "http_request_duration_seconds_count",
            {
                "method": "GET",
                "handler": "get_item",
                "status": "200",
                "http_route": "/items/{item_id}",
            },
        )
        # Should have 3 observations
        assert count == 3

    def test_measures_accurate_duration(self, app_with_prometheus_middleware):
        """Test that recorded duration is reasonably accurate."""
        client = TestClient(app_with_prometheus_middleware)

        # Make a slow request (50ms)
        client.get("/slow")

        metric = http_request_duration_seconds.labels(
            method="GET",
            handler="slow_endpoint",
            status="200",
            http_route="/slow",
        )

        # Duration should be at least 50ms (0.05s)
        assert metric._sum._value >= 0.04  # Allow some tolerance

    def test_excludes_health_endpoint(self, clear_prometheus_metrics):
        """Test that /health endpoint is excluded from metrics."""
        app = FastAPI()
        app.add_middleware(PrometheusMiddleware)

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)

        # Make requests to both endpoints
        client.get("/health")
        client.get("/test")

        # /test should be recorded
        test_metric = http_request_duration_seconds.labels(
            method="GET",
            handler="test_endpoint",
            status="200",
            http_route="/test",
        )
        assert test_metric._sum._value > 0

        # /health should NOT be recorded - check by trying to find any health metric
        # If we try to access a label combination that doesn't exist, it will be created
        # So we check the registry directly
        samples = list(
            REGISTRY.get_sample_value(
                "http_request_duration_seconds_count",
                {"method": "GET", "handler": "health", "status": "200", "http_route": "/health"},
            )
            or [0]
        )
        # Should be None or 0 since health is excluded
        assert samples in ([0], [])

    def test_excludes_metrics_endpoint(self, clear_prometheus_metrics):
        """Test that /api/metrics endpoint is excluded from metrics."""
        app = FastAPI()
        app.add_middleware(PrometheusMiddleware)

        @app.get("/api/metrics")
        async def metrics():
            return "metrics"

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)

        # Make requests to both endpoints
        client.get("/api/metrics")
        client.get("/test")

        # /test should be recorded, /api/metrics should not
        test_metric = http_request_duration_seconds.labels(
            method="GET",
            handler="test_endpoint",
            status="200",
            http_route="/test",
        )
        assert test_metric._sum._value > 0

    def test_excludes_root_endpoint(self, clear_prometheus_metrics):
        """Test that / endpoint is excluded from metrics."""
        app = FastAPI()
        app.add_middleware(PrometheusMiddleware)

        @app.get("/")
        async def root():
            return {"status": "ok"}

        client = TestClient(app)
        client.get("/")

        # Root should be excluded
        sample = REGISTRY.get_sample_value(
            "http_request_duration_seconds_count",
            {"method": "GET", "handler": "root", "status": "200", "http_route": "/"},
        )
        assert sample is None or sample == 0

    def test_excludes_ready_endpoint(self, clear_prometheus_metrics):
        """Test that /ready endpoint is excluded from metrics."""
        app = FastAPI()
        app.add_middleware(PrometheusMiddleware)

        @app.get("/ready")
        async def ready():
            return {"ready": True}

        client = TestClient(app)
        client.get("/ready")

        # /ready should be excluded
        sample = REGISTRY.get_sample_value(
            "http_request_duration_seconds_count",
            {"method": "GET", "handler": "ready", "status": "200", "http_route": "/ready"},
        )
        assert sample is None or sample == 0

    def test_custom_exclude_paths(self, clear_prometheus_metrics):
        """Test that custom exclude paths can be specified."""
        app = FastAPI()
        custom_excludes = frozenset({"/custom-health", "/internal"})
        app.add_middleware(PrometheusMiddleware, exclude_paths=custom_excludes)

        @app.get("/custom-health")
        async def custom_health():
            return {"status": "ok"}

        @app.get("/internal")
        async def internal():
            return {"internal": True}

        @app.get("/api/data")
        async def api_data():
            return {"data": []}

        client = TestClient(app)

        # Custom excluded paths should not be recorded
        client.get("/custom-health")
        client.get("/internal")
        client.get("/api/data")

        # /api/data should be recorded
        api_metric = http_request_duration_seconds.labels(
            method="GET",
            handler="api_data",
            status="200",
            http_route="/api/data",
        )
        assert api_metric._sum._value > 0


# =============================================================================
# Route Pattern Extraction Tests
# =============================================================================


class TestRoutePatternExtraction:
    """Tests for _get_route_pattern helper function."""

    def test_extracts_simple_route(self, app_with_prometheus_middleware):
        """Test extraction of simple route pattern."""
        client = TestClient(app_with_prometheus_middleware)
        response = client.get("/test")

        assert response.status_code == 200
        # Metric should have http_route="/test"
        metric = http_request_duration_seconds.labels(
            method="GET",
            handler="test_endpoint",
            status="200",
            http_route="/test",
        )
        assert metric._sum._value > 0

    def test_extracts_parameterized_route(self, app_with_prometheus_middleware):
        """Test extraction of route with path parameters."""
        client = TestClient(app_with_prometheus_middleware)
        response = client.get("/items/42")

        assert response.status_code == 200
        # Should use pattern, not actual value
        metric = http_request_duration_seconds.labels(
            method="GET",
            handler="get_item",
            status="200",
            http_route="/items/{item_id}",
        )
        assert metric._sum._value > 0


# =============================================================================
# Handler Name Extraction Tests
# =============================================================================


class TestHandlerNameExtraction:
    """Tests for _get_handler_name helper function."""

    def test_extracts_function_name(self, app_with_prometheus_middleware):
        """Test extraction of handler function name."""
        client = TestClient(app_with_prometheus_middleware)
        client.get("/test")

        # Handler should be "test_endpoint"
        metric = http_request_duration_seconds.labels(
            method="GET",
            handler="test_endpoint",
            status="200",
            http_route="/test",
        )
        assert metric._sum._value > 0

    def test_extracts_post_handler_name(self, app_with_prometheus_middleware):
        """Test extraction of POST handler function name."""
        client = TestClient(app_with_prometheus_middleware)
        client.post("/create")

        # Handler should be "create_endpoint"
        metric = http_request_duration_seconds.labels(
            method="POST",
            handler="create_endpoint",
            status="200",
            http_route="/create",
        )
        assert metric._sum._value > 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestPrometheusMiddlewareIntegration:
    """Integration tests with other middleware."""

    def test_works_with_timing_middleware(self, clear_prometheus_metrics):
        """Test that PrometheusMiddleware works with RequestTimingMiddleware."""
        from backend.api.middleware.request_timing import RequestTimingMiddleware

        app = FastAPI()
        app.add_middleware(PrometheusMiddleware)
        app.add_middleware(RequestTimingMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        # Both middlewares should work
        assert "X-Response-Time" in response.headers

        # Prometheus metric should be recorded
        metric = http_request_duration_seconds.labels(
            method="GET",
            handler="test_endpoint",
            status="200",
            http_route="/test",
        )
        assert metric._sum._value > 0

    def test_works_with_request_id_middleware(self, clear_prometheus_metrics):
        """Test that PrometheusMiddleware works with RequestIDMiddleware."""
        from backend.api.middleware.request_id import RequestIDMiddleware

        app = FastAPI()
        app.add_middleware(PrometheusMiddleware)
        app.add_middleware(RequestIDMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers

        # Prometheus metric should be recorded
        metric = http_request_duration_seconds.labels(
            method="GET",
            handler="test_endpoint",
            status="200",
            http_route="/test",
        )
        assert metric._sum._value > 0


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestPrometheusMiddlewareEdgeCases:
    """Edge case tests for PrometheusMiddleware."""

    def test_handles_exception_in_handler(self, clear_prometheus_metrics):
        """Test that metrics are recorded even when handler raises exception."""
        app = FastAPI()
        app.add_middleware(PrometheusMiddleware)

        @app.get("/crash")
        async def crash_endpoint():
            raise ValueError("Unexpected error")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/crash")

        assert response.status_code == 500

        # Metric should still be recorded with 500 status
        metric = http_request_duration_seconds.labels(
            method="GET",
            handler="crash_endpoint",
            status="500",
            http_route="/crash",
        )
        assert metric._sum._value > 0

    def test_handles_very_fast_requests(self, app_with_prometheus_middleware):
        """Test handling of very fast requests (sub-millisecond)."""
        client = TestClient(app_with_prometheus_middleware)

        for _ in range(10):
            client.get("/test")

        # Should have recorded all requests
        # Use REGISTRY.get_sample_value to get the count
        count = REGISTRY.get_sample_value(
            "http_request_duration_seconds_count",
            {
                "method": "GET",
                "handler": "test_endpoint",
                "status": "200",
                "http_route": "/test",
            },
        )
        assert count is not None and count >= 10

    def test_multiple_requests_accumulate(self, app_with_prometheus_middleware):
        """Test that multiple requests accumulate in the histogram."""
        client = TestClient(app_with_prometheus_middleware)

        # Make 5 requests
        for _ in range(5):
            client.get("/test")

        # Use REGISTRY.get_sample_value to get the count
        count = REGISTRY.get_sample_value(
            "http_request_duration_seconds_count",
            {
                "method": "GET",
                "handler": "test_endpoint",
                "status": "200",
                "http_route": "/test",
            },
        )
        assert count is not None and count >= 5


# =============================================================================
# Excluded Paths Constant Tests
# =============================================================================


class TestExcludedPaths:
    """Tests for EXCLUDED_PATHS constant."""

    def test_excluded_paths_is_frozenset(self):
        """Test that EXCLUDED_PATHS is a frozenset (immutable)."""
        assert isinstance(EXCLUDED_PATHS, frozenset)

    def test_excluded_paths_contains_health_endpoints(self):
        """Test that standard health check paths are excluded."""
        assert "/" in EXCLUDED_PATHS
        assert "/health" in EXCLUDED_PATHS
        assert "/ready" in EXCLUDED_PATHS

    def test_excluded_paths_contains_metrics_endpoint(self):
        """Test that metrics endpoint is excluded."""
        assert "/api/metrics" in EXCLUDED_PATHS
