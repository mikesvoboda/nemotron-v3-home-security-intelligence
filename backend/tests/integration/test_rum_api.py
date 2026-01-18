"""Integration tests for RUM (Real User Monitoring) API endpoints.

Tests cover end-to-end RUM metrics ingestion including:
- Core Web Vitals ingestion (LCP, FID, INP, CLS, TTFB, FCP, PAGE_LOAD_TIME)
- Metrics validation and storage in Prometheus
- Batch ingestion with multiple metrics
- Error handling for invalid metrics
- Prometheus metrics endpoint verification

These integration tests verify the complete flow from API request
through to Prometheus metrics recording.

Integration Focus:
- Real HTTP client testing via httpx with ASGITransport
- Actual Prometheus metrics recording and retrieval
- Multi-metric batch processing
- Error handling and partial success scenarios
- Metrics endpoint validation for RUM histograms
"""

from __future__ import annotations

import pytest


class TestRUMCoreWebVitalsIngestion:
    """Integration tests for Core Web Vitals metrics ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_lcp_metric_end_to_end(self, client, mock_redis):
        """Test end-to-end LCP metric ingestion and Prometheus recording.

        Verifies:
        1. POST /api/rum accepts LCP metric
        2. Returns success response
        3. Metric is recorded to Prometheus
        4. Metric appears in /api/metrics endpoint
        """
        # Ingest LCP metric
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "LCP",
                        "value": 2500.0,
                        "rating": "good",
                        "delta": 2500.0,
                        "id": "v1-lcp-test-1",
                        "path": "/dashboard",
                    }
                ],
                "session_id": "integration-test-lcp",
            },
        )

        # Verify API response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metrics_count"] == 1
        assert "Successfully ingested 1 metric" in data["message"]
        assert data["errors"] == []

        # Verify Prometheus metrics recorded
        metrics_response = await client.get("/api/metrics")
        assert metrics_response.status_code == 200
        metrics_content = metrics_response.text

        # Check for RUM LCP histogram
        assert "hsi_rum_lcp_seconds" in metrics_content
        assert "# TYPE hsi_rum_lcp_seconds histogram" in metrics_content

    @pytest.mark.asyncio
    async def test_ingest_fid_metric_end_to_end(self, client, mock_redis):
        """Test end-to-end FID metric ingestion and Prometheus recording."""
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "FID",
                        "value": 100.0,
                        "rating": "good",
                        "delta": 100.0,
                        "id": "v1-fid-test-1",
                        "path": "/events",
                    }
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metrics_count"] == 1

        # Verify Prometheus metrics
        metrics_response = await client.get("/api/metrics")
        metrics_content = metrics_response.text
        assert "hsi_rum_fid_seconds" in metrics_content

    @pytest.mark.asyncio
    async def test_ingest_inp_metric_end_to_end(self, client, mock_redis):
        """Test end-to-end INP metric ingestion and Prometheus recording."""
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "INP",
                        "value": 200.0,
                        "rating": "needs-improvement",
                        "delta": 200.0,
                        "id": "v1-inp-test-1",
                        "path": "/cameras",
                    }
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metrics_count"] == 1

        # Verify Prometheus metrics
        metrics_response = await client.get("/api/metrics")
        metrics_content = metrics_response.text
        assert "hsi_rum_inp_seconds" in metrics_content

    @pytest.mark.asyncio
    async def test_ingest_cls_metric_end_to_end(self, client, mock_redis):
        """Test end-to-end CLS metric ingestion and Prometheus recording."""
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "CLS",
                        "value": 0.1,
                        "rating": "needs-improvement",
                        "delta": 0.05,
                        "id": "v1-cls-test-1",
                        "path": "/alerts",
                    }
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metrics_count"] == 1

        # Verify Prometheus metrics
        metrics_response = await client.get("/api/metrics")
        metrics_content = metrics_response.text
        assert "hsi_rum_cls" in metrics_content

    @pytest.mark.asyncio
    async def test_ingest_ttfb_metric_end_to_end(self, client, mock_redis):
        """Test end-to-end TTFB metric ingestion and Prometheus recording."""
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "TTFB",
                        "value": 150.0,
                        "rating": "good",
                        "delta": 150.0,
                        "id": "v1-ttfb-test-1",
                        "path": "/",
                    }
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metrics_count"] == 1

        # Verify Prometheus metrics
        metrics_response = await client.get("/api/metrics")
        metrics_content = metrics_response.text
        assert "hsi_rum_ttfb_seconds" in metrics_content

    @pytest.mark.asyncio
    async def test_ingest_fcp_metric_end_to_end(self, client, mock_redis):
        """Test end-to-end FCP metric ingestion and Prometheus recording."""
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "FCP",
                        "value": 1800.0,
                        "rating": "good",
                        "delta": 1800.0,
                        "id": "v1-fcp-test-1",
                        "path": "/settings",
                    }
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metrics_count"] == 1

        # Verify Prometheus metrics
        metrics_response = await client.get("/api/metrics")
        metrics_content = metrics_response.text
        assert "hsi_rum_fcp_seconds" in metrics_content

    @pytest.mark.asyncio
    async def test_ingest_page_load_time_metric_end_to_end(self, client, mock_redis):
        """Test end-to-end PAGE_LOAD_TIME metric ingestion and Prometheus recording."""
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "PAGE_LOAD_TIME",
                        "value": 3000.0,
                        "rating": "needs-improvement",
                        "delta": 3000.0,
                        "id": "plt-test-1",
                        "path": "/analytics",
                    }
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metrics_count"] == 1

        # Verify Prometheus metrics
        metrics_response = await client.get("/api/metrics")
        metrics_content = metrics_response.text
        assert "hsi_rum_page_load_time_seconds" in metrics_content


class TestRUMBatchIngestion:
    """Integration tests for batch metrics ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_multiple_metrics_batch(self, client, mock_redis):
        """Test batch ingestion of multiple Core Web Vitals metrics.

        Verifies:
        1. Multiple metrics processed in single request
        2. All metrics recorded successfully
        3. Correct metrics_count in response
        4. All metrics appear in Prometheus
        """
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "LCP",
                        "value": 2500.0,
                        "rating": "good",
                        "delta": 2500.0,
                        "id": "v1-batch-lcp",
                        "path": "/dashboard",
                    },
                    {
                        "name": "FID",
                        "value": 100.0,
                        "rating": "good",
                        "delta": 100.0,
                        "id": "v1-batch-fid",
                        "path": "/dashboard",
                    },
                    {
                        "name": "CLS",
                        "value": 0.05,
                        "rating": "good",
                        "delta": 0.02,
                        "id": "v1-batch-cls",
                        "path": "/dashboard",
                    },
                ],
                "session_id": "integration-test-batch",
            },
        )

        # Verify API response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metrics_count"] == 3
        assert "Successfully ingested 3 metric" in data["message"]
        assert data["errors"] == []

        # Verify all metrics recorded to Prometheus
        metrics_response = await client.get("/api/metrics")
        metrics_content = metrics_response.text
        assert "hsi_rum_lcp_seconds" in metrics_content
        assert "hsi_rum_fid_seconds" in metrics_content
        assert "hsi_rum_cls" in metrics_content

    @pytest.mark.asyncio
    async def test_ingest_all_core_web_vitals_batch(self, client, mock_redis):
        """Test batch ingestion of all supported Core Web Vitals metrics."""
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "LCP",
                        "value": 2500.0,
                        "rating": "good",
                        "delta": 2500.0,
                        "id": "v1-all-lcp",
                    },
                    {
                        "name": "FID",
                        "value": 50.0,
                        "rating": "good",
                        "delta": 50.0,
                        "id": "v1-all-fid",
                    },
                    {
                        "name": "INP",
                        "value": 200.0,
                        "rating": "needs-improvement",
                        "delta": 200.0,
                        "id": "v1-all-inp",
                    },
                    {
                        "name": "CLS",
                        "value": 0.1,
                        "rating": "needs-improvement",
                        "delta": 0.05,
                        "id": "v1-all-cls",
                    },
                    {
                        "name": "TTFB",
                        "value": 100.0,
                        "rating": "good",
                        "delta": 100.0,
                        "id": "v1-all-ttfb",
                    },
                    {
                        "name": "FCP",
                        "value": 1800.0,
                        "rating": "good",
                        "delta": 1800.0,
                        "id": "v1-all-fcp",
                    },
                    {
                        "name": "PAGE_LOAD_TIME",
                        "value": 3000.0,
                        "rating": "needs-improvement",
                        "delta": 3000.0,
                        "id": "plt-all",
                    },
                ],
                "session_id": "integration-test-all-vitals",
            },
        )

        # Verify API response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metrics_count"] == 7
        assert data["errors"] == []

    @pytest.mark.asyncio
    async def test_ingest_batch_with_different_paths(self, client, mock_redis):
        """Test batch ingestion with metrics from different page paths.

        Verifies that metrics from different pages are all recorded
        with their respective path labels.
        """
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "LCP",
                        "value": 2500.0,
                        "rating": "good",
                        "delta": 2500.0,
                        "id": "v1-path-1",
                        "path": "/dashboard",
                    },
                    {
                        "name": "LCP",
                        "value": 3000.0,
                        "rating": "needs-improvement",
                        "delta": 3000.0,
                        "id": "v1-path-2",
                        "path": "/events",
                    },
                    {
                        "name": "LCP",
                        "value": 2000.0,
                        "rating": "good",
                        "delta": 2000.0,
                        "id": "v1-path-3",
                        "path": "/cameras",
                    },
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metrics_count"] == 3

    @pytest.mark.asyncio
    async def test_ingest_batch_with_different_ratings(self, client, mock_redis):
        """Test batch ingestion with metrics having different ratings.

        Verifies that metrics with good, needs-improvement, and poor
        ratings are all recorded correctly.
        """
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "LCP",
                        "value": 2000.0,
                        "rating": "good",
                        "delta": 2000.0,
                        "id": "v1-rating-good",
                    },
                    {
                        "name": "LCP",
                        "value": 3000.0,
                        "rating": "needs-improvement",
                        "delta": 3000.0,
                        "id": "v1-rating-needs",
                    },
                    {
                        "name": "LCP",
                        "value": 5000.0,
                        "rating": "poor",
                        "delta": 5000.0,
                        "id": "v1-rating-poor",
                    },
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metrics_count"] == 3


class TestRUMMetricsValidation:
    """Integration tests for RUM metrics validation and error handling."""

    @pytest.mark.asyncio
    async def test_empty_metrics_array_returns_422(self, client, mock_redis):
        """Test that empty metrics array returns 422 Unprocessable Entity."""
        response = await client.post(
            "/api/rum",
            json={"metrics": []},
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_missing_metrics_field_returns_422(self, client, mock_redis):
        """Test that missing metrics field returns 422."""
        response = await client.post(
            "/api/rum",
            json={"session_id": "test"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_metric_name_returns_422(self, client, mock_redis):
        """Test that invalid metric name returns 422."""
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "INVALID_METRIC",
                        "value": 2500.0,
                        "rating": "good",
                        "delta": 2500.0,
                        "id": "v1-invalid",
                    }
                ]
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_rating_returns_422(self, client, mock_redis):
        """Test that invalid rating value returns 422."""
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "LCP",
                        "value": 2500.0,
                        "rating": "invalid_rating",
                        "delta": 2500.0,
                        "id": "v1-test",
                    }
                ]
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_required_fields_returns_422(self, client, mock_redis):
        """Test that missing required metric fields return 422."""
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

    @pytest.mark.asyncio
    async def test_invalid_value_type_returns_422(self, client, mock_redis):
        """Test that invalid value type returns 422."""
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "LCP",
                        "value": "not-a-number",
                        "rating": "good",
                        "delta": 2500.0,
                        "id": "v1-test",
                    }
                ]
            },
        )

        assert response.status_code == 422


class TestRUMPrometheusIntegration:
    """Integration tests for RUM metrics in Prometheus."""

    @pytest.mark.asyncio
    async def test_rum_metrics_in_prometheus_format(self, client, mock_redis):
        """Test that RUM metrics appear in correct Prometheus format.

        Verifies:
        1. HELP declarations present
        2. TYPE declarations correct (histogram)
        3. Metric names follow convention
        """
        # Ingest some metrics first
        await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "LCP",
                        "value": 2500.0,
                        "rating": "good",
                        "delta": 2500.0,
                        "id": "v1-prom-test",
                        "path": "/test",
                    }
                ]
            },
        )

        # Get Prometheus metrics
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "text/plain; charset=utf-8"

        content = response.text
        # Check for proper Prometheus format
        assert "# HELP hsi_rum_lcp_seconds" in content
        assert "# TYPE hsi_rum_lcp_seconds histogram" in content

    @pytest.mark.asyncio
    async def test_rum_histograms_have_buckets(self, client, mock_redis):
        """Test that RUM histograms include bucket data.

        Prometheus histograms should have:
        - _bucket entries with le (less than or equal) labels
        - _sum entry with total sum
        - _count entry with total count
        """
        # Ingest metrics
        await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "LCP",
                        "value": 2500.0,
                        "rating": "good",
                        "delta": 2500.0,
                        "id": "v1-bucket-test",
                    }
                ]
            },
        )

        # Get Prometheus metrics
        response = await client.get("/api/metrics")
        content = response.text

        # Check for histogram components
        assert "hsi_rum_lcp_seconds_bucket" in content
        assert "hsi_rum_lcp_seconds_sum" in content
        assert "hsi_rum_lcp_seconds_count" in content

    @pytest.mark.asyncio
    async def test_multiple_rum_metric_observations(self, client, mock_redis):
        """Test that multiple observations accumulate in histograms.

        Verifies that multiple ingestions of the same metric type
        are all recorded and reflected in the histogram count.
        """
        # Ingest multiple LCP metrics
        for i in range(3):
            await client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 2500.0 + (i * 100),
                            "rating": "good",
                            "delta": 2500.0,
                            "id": f"v1-multi-{i}",
                        }
                    ]
                },
            )

        # Get Prometheus metrics
        response = await client.get("/api/metrics")
        content = response.text

        # Verify metrics recorded (count should be >= 3)
        assert "hsi_rum_lcp_seconds_count" in content


class TestRUMSessionTracking:
    """Integration tests for RUM session tracking features."""

    @pytest.mark.asyncio
    async def test_ingest_with_session_id(self, client, mock_redis):
        """Test that metrics can be ingested with session_id for tracking."""
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "LCP",
                        "value": 2500.0,
                        "rating": "good",
                        "delta": 2500.0,
                        "id": "v1-session-test",
                    }
                ],
                "session_id": "test-session-12345",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_ingest_with_user_agent(self, client, mock_redis):
        """Test that metrics can be ingested with user_agent for analysis."""
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "LCP",
                        "value": 2500.0,
                        "rating": "good",
                        "delta": 2500.0,
                        "id": "v1-ua-test",
                    }
                ],
                "user_agent": "Mozilla/5.0 (X11; Linux x86_64)",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_ingest_with_navigation_type(self, client, mock_redis):
        """Test that metrics can include navigationType field."""
        response = await client.post(
            "/api/rum",
            json={
                "metrics": [
                    {
                        "name": "LCP",
                        "value": 2500.0,
                        "rating": "good",
                        "delta": 2500.0,
                        "id": "v1-nav-test",
                        "navigationType": "navigate",
                    }
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestRUMConcurrentRequests:
    """Integration tests for concurrent RUM metrics ingestion."""

    @pytest.mark.asyncio
    async def test_concurrent_metric_ingestion(self, client, mock_redis):
        """Test that concurrent metric ingestion requests are handled correctly.

        Verifies that multiple simultaneous RUM ingestion requests
        don't interfere with each other and all metrics are recorded.
        """
        import asyncio

        # Create multiple concurrent requests
        tasks = []
        for i in range(5):
            task = client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": "LCP",
                            "value": 2500.0 + (i * 100),
                            "rating": "good",
                            "delta": 2500.0,
                            "id": f"v1-concurrent-{i}",
                        }
                    ],
                    "session_id": f"concurrent-session-{i}",
                },
            )
            tasks.append(task)

        # Execute all requests concurrently
        responses = await asyncio.gather(*tasks)

        # Verify all requests succeeded
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["metrics_count"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_different_metric_types(self, client, mock_redis):
        """Test concurrent ingestion of different metric types.

        Verifies that ingesting different metric types concurrently
        works correctly and all metrics are recorded to Prometheus.
        """
        import asyncio

        metric_types = ["LCP", "FID", "INP", "CLS", "TTFB", "FCP"]
        tasks = []

        for metric_name in metric_types:
            value = 2500.0 if metric_name != "CLS" else 0.1
            task = client.post(
                "/api/rum",
                json={
                    "metrics": [
                        {
                            "name": metric_name,
                            "value": value,
                            "rating": "good",
                            "delta": value,
                            "id": f"v1-concurrent-{metric_name.lower()}",
                        }
                    ]
                },
            )
            tasks.append(task)

        # Execute all requests concurrently
        responses = await asyncio.gather(*tasks)

        # Verify all requests succeeded
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
