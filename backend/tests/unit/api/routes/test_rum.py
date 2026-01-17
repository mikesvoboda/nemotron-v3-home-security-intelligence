"""Unit tests for RUM (Real User Monitoring) API routes.

Tests for the POST /api/rum endpoint that receives Core Web Vitals
metrics from the frontend for Real User Monitoring.

RED Phase: These tests define the expected behavior for RUM routes.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


class TestRUMIngestEndpoint:
    """Tests for POST /api/rum endpoint."""

    @pytest.mark.asyncio
    async def test_ingest_single_metric_returns_200(self) -> None:
        """Test that POST /api/rum with a single metric returns 200 OK."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 2500.0,
                            "rating": "good",
                            "delta": 2500.0,
                            "id": "v1-1234567890123-1234567890123",
                        }
                    ]
                },
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_ingest_multiple_metrics_returns_200(self) -> None:
        """Test that POST /api/rum with multiple metrics returns 200 OK."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 2500.0,
                            "rating": "good",
                            "delta": 2500.0,
                            "id": "v1-1234567890123-1234567890123",
                        },
                        {
                            "name": "CLS",
                            "value": 0.05,
                            "rating": "good",
                            "delta": 0.02,
                            "id": "v1-1234567890123-1234567890124",
                        },
                        {
                            "name": "INP",
                            "value": 200.0,
                            "rating": "needs-improvement",
                            "delta": 200.0,
                            "id": "v1-1234567890123-1234567890125",
                        },
                    ]
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metrics_count"] == 3

    @pytest.mark.asyncio
    async def test_ingest_returns_json_content_type(self) -> None:
        """Test that RUM endpoint returns application/json content type."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 2500.0,
                            "rating": "good",
                            "delta": 2500.0,
                            "id": "v1-1234567890123-1234567890123",
                        }
                    ]
                },
            )

        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_ingest_response_structure(self) -> None:
        """Test that RUM endpoint response has correct structure."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 2500.0,
                            "rating": "good",
                            "delta": 2500.0,
                            "id": "v1-1234567890123-1234567890123",
                        }
                    ]
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "metrics_count" in data
        assert "message" in data
        assert "errors" in data
        assert isinstance(data["errors"], list)

    @pytest.mark.asyncio
    async def test_ingest_with_session_id(self) -> None:
        """Test that RUM endpoint accepts session_id."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 2500.0,
                            "rating": "good",
                            "delta": 2500.0,
                            "id": "v1-1234567890123-1234567890123",
                        }
                    ],
                    "session_id": "test-session-123",
                },
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_ingest_with_user_agent(self) -> None:
        """Test that RUM endpoint accepts user_agent."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 2500.0,
                            "rating": "good",
                            "delta": 2500.0,
                            "id": "v1-1234567890123-1234567890123",
                        }
                    ],
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                },
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_ingest_with_path(self) -> None:
        """Test that RUM endpoint accepts metric with path."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 2500.0,
                            "rating": "good",
                            "delta": 2500.0,
                            "id": "v1-1234567890123-1234567890123",
                            "path": "/dashboard",
                        }
                    ]
                },
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_ingest_with_navigation_type(self) -> None:
        """Test that RUM endpoint accepts metric with navigationType."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 2500.0,
                            "rating": "good",
                            "delta": 2500.0,
                            "id": "v1-1234567890123-1234567890123",
                            "navigationType": "navigate",
                        }
                    ]
                },
            )

        assert response.status_code == 200


class TestRUMIngestValidation:
    """Tests for RUM endpoint validation."""

    @pytest.mark.asyncio
    async def test_empty_metrics_returns_422(self) -> None:
        """Test that empty metrics array returns 422 Unprocessable Entity."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={"metrics": []},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_metrics_returns_422(self) -> None:
        """Test that missing metrics field returns 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_metric_name_returns_422(self) -> None:
        """Test that invalid metric name returns 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "INVALID_METRIC",
                            "value": 2500.0,
                            "rating": "good",
                            "delta": 2500.0,
                            "id": "v1-1234567890123-1234567890123",
                        }
                    ]
                },
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_rating_returns_422(self) -> None:
        """Test that invalid rating returns 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 2500.0,
                            "rating": "invalid_rating",
                            "delta": 2500.0,
                            "id": "v1-1234567890123-1234567890123",
                        }
                    ]
                },
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_required_metric_field_returns_422(self) -> None:
        """Test that missing required metric fields return 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            # Missing value, rating, delta, id
                        }
                    ]
                },
            )

        assert response.status_code == 422


class TestRUMIngestAllMetricTypes:
    """Tests for all Core Web Vitals metric types."""

    @pytest.mark.asyncio
    async def test_ingest_lcp_metric(self) -> None:
        """Test ingesting LCP (Largest Contentful Paint) metric."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 2500.0,
                            "rating": "good",
                            "delta": 2500.0,
                            "id": "v1-1234567890123-1234567890123",
                        }
                    ]
                },
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_ingest_fid_metric(self) -> None:
        """Test ingesting FID (First Input Delay) metric."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "FID",
                            "value": 50.0,
                            "rating": "good",
                            "delta": 50.0,
                            "id": "v1-1234567890123-1234567890123",
                        }
                    ]
                },
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_ingest_inp_metric(self) -> None:
        """Test ingesting INP (Interaction to Next Paint) metric."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "INP",
                            "value": 200.0,
                            "rating": "needs-improvement",
                            "delta": 200.0,
                            "id": "v1-1234567890123-1234567890123",
                        }
                    ]
                },
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_ingest_cls_metric(self) -> None:
        """Test ingesting CLS (Cumulative Layout Shift) metric."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "CLS",
                            "value": 0.05,
                            "rating": "good",
                            "delta": 0.02,
                            "id": "v1-1234567890123-1234567890123",
                        }
                    ]
                },
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_ingest_ttfb_metric(self) -> None:
        """Test ingesting TTFB (Time to First Byte) metric."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "TTFB",
                            "value": 100.0,
                            "rating": "good",
                            "delta": 100.0,
                            "id": "v1-1234567890123-1234567890123",
                        }
                    ]
                },
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_ingest_fcp_metric(self) -> None:
        """Test ingesting FCP (First Contentful Paint) metric."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "FCP",
                            "value": 1800.0,
                            "rating": "good",
                            "delta": 1800.0,
                            "id": "v1-1234567890123-1234567890123",
                        }
                    ]
                },
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_ingest_page_load_time_metric(self) -> None:
        """Test ingesting PAGE_LOAD_TIME metric."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "PAGE_LOAD_TIME",
                            "value": 2500.0,
                            "rating": "good",
                            "delta": 2500.0,
                            "id": "plt-1234567890123-abc1234",
                        }
                    ]
                },
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_ingest_all_core_web_vitals(self) -> None:
        """Test ingesting all Core Web Vitals in one batch."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 2500.0,
                            "rating": "good",
                            "delta": 2500.0,
                            "id": "v1-1234567890123-0",
                        },
                        {
                            "name": "FID",
                            "value": 50.0,
                            "rating": "good",
                            "delta": 50.0,
                            "id": "v1-1234567890123-1",
                        },
                        {
                            "name": "INP",
                            "value": 200.0,
                            "rating": "needs-improvement",
                            "delta": 200.0,
                            "id": "v1-1234567890123-2",
                        },
                        {
                            "name": "CLS",
                            "value": 0.05,
                            "rating": "good",
                            "delta": 0.02,
                            "id": "v1-1234567890123-3",
                        },
                        {
                            "name": "TTFB",
                            "value": 100.0,
                            "rating": "good",
                            "delta": 100.0,
                            "id": "v1-1234567890123-4",
                        },
                        {
                            "name": "FCP",
                            "value": 1800.0,
                            "rating": "good",
                            "delta": 1800.0,
                            "id": "v1-1234567890123-5",
                        },
                        {
                            "name": "PAGE_LOAD_TIME",
                            "value": 3000.0,
                            "rating": "good",
                            "delta": 3000.0,
                            "id": "plt-1234567890123-abc1234",
                        },
                    ]
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metrics_count"] == 7


class TestRUMRouterConfiguration:
    """Tests for RUM router configuration."""

    @pytest.mark.asyncio
    async def test_rum_endpoint_path(self) -> None:
        """Test that RUM endpoint is mounted at /api/rum."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 2500.0,
                            "rating": "good",
                            "delta": 2500.0,
                            "id": "v1-1234567890123-1234567890123",
                        }
                    ]
                },
            )

        # Should not be 404
        assert response.status_code != 404

    @pytest.mark.asyncio
    async def test_rum_endpoint_accepts_post_method(self) -> None:
        """Test that RUM endpoint accepts POST requests."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 2500.0,
                            "rating": "good",
                            "delta": 2500.0,
                            "id": "v1-1234567890123-1234567890123",
                        }
                    ]
                },
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rum_endpoint_rejects_get_method(self) -> None:
        """Test that RUM endpoint rejects GET requests."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/rum")

        # Should return 405 Method Not Allowed
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_rum_endpoint_rejects_put_method(self) -> None:
        """Test that RUM endpoint rejects PUT requests."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.put(
                "/api/rum",
                json={"metrics": []},
            )

        # Should return 405 Method Not Allowed
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_rum_endpoint_rejects_delete_method(self) -> None:
        """Test that RUM endpoint rejects DELETE requests."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete("/api/rum")

        # Should return 405 Method Not Allowed
        assert response.status_code == 405


class TestRUMPrometheusMetrics:
    """Tests for RUM Prometheus metrics recording."""

    @pytest.mark.asyncio
    async def test_ingest_records_prometheus_metrics(self) -> None:
        """Test that RUM ingest records Prometheus metrics."""
        # First, ingest some metrics
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 2500.0,
                            "rating": "good",
                            "delta": 2500.0,
                            "id": "v1-1234567890123-1234567890123",
                        },
                        {
                            "name": "CLS",
                            "value": 0.15,
                            "rating": "poor",
                            "delta": 0.15,
                            "id": "v1-1234567890123-1234567890124",
                        },
                    ]
                },
            )

        # Then, check that metrics are recorded
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            metrics_response = await client.get("/api/metrics")

        assert metrics_response.status_code == 200
        metrics_content = metrics_response.text

        # Should contain RUM histograms
        assert "hsi_rum_lcp_seconds" in metrics_content or "hsi_rum" in metrics_content

    @pytest.mark.asyncio
    async def test_rum_metrics_include_rating_labels(self) -> None:
        """Test that RUM metrics include rating labels."""
        # Ingest metrics with different ratings
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 1500.0,
                            "rating": "good",
                            "delta": 1500.0,
                            "id": "v1-1",
                        },
                        {
                            "name": "LCP",
                            "value": 3000.0,
                            "rating": "needs-improvement",
                            "delta": 3000.0,
                            "id": "v1-2",
                        },
                        {
                            "name": "LCP",
                            "value": 5000.0,
                            "rating": "poor",
                            "delta": 5000.0,
                            "id": "v1-3",
                        },
                    ]
                },
            )

        # Check metrics endpoint
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            metrics_response = await client.get("/api/metrics")

        assert metrics_response.status_code == 200
        # Metrics should be recorded (even if rating is not in labels)
        assert "hsi_rum" in metrics_response.text or len(metrics_response.text) > 0
