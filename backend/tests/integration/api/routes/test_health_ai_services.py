"""Integration tests for AI services health endpoint (NEM-3143).

These tests verify the /api/health/ai-services endpoint works correctly
with the real application context, including Redis integration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.mark.integration
class TestAIServicesHealthIntegration:
    """Integration tests for AI services health endpoint."""

    @pytest.mark.asyncio
    async def test_ai_services_health_endpoint_returns_valid_response(
        self, async_client: AsyncClient
    ) -> None:
        """Verify the endpoint returns a valid response structure."""
        # Mock the AI service health checks since actual AI services aren't running
        with patch("backend.api.routes.health_ai_services._check_ai_service_health") as mock_check:
            mock_check.return_value = AsyncMock(
                status="healthy",
                circuit_state="closed",
                last_health_check="2026-01-20T00:00:00Z",
                error_rate_1h=None,
                latency_p99_ms=None,
                url="http://localhost:8090",
                error=None,
            )

            response = await async_client.get("/api/health/ai-services")

            # Should return 200 or 503 depending on service health
            assert response.status_code in (200, 503)
            data = response.json()

            # Verify response structure
            assert "overall_status" in data
            assert "services" in data
            assert "queues" in data
            assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_ai_services_health_returns_queue_depths(self, async_client: AsyncClient) -> None:
        """Verify queue depth information is included in response."""
        with patch("backend.api.routes.health_ai_services._check_ai_service_health") as mock_check:
            mock_check.return_value = AsyncMock(
                status="unknown",
                circuit_state="closed",
                last_health_check="2026-01-20T00:00:00Z",
                error_rate_1h=None,
                latency_p99_ms=None,
                url=None,
                error="Service URL not configured",
            )

            response = await async_client.get("/api/health/ai-services")
            data = response.json()

            # Verify queue structure
            assert "queues" in data
            queues = data["queues"]
            assert "detection_queue" in queues
            assert "analysis_queue" in queues

            # Each queue should have depth info
            for queue_info in queues.values():
                assert "depth" in queue_info
                assert "dlq_depth" in queue_info

    @pytest.mark.asyncio
    async def test_ai_services_health_includes_all_services(
        self, async_client: AsyncClient
    ) -> None:
        """Verify all expected AI services are included in response."""
        with patch("backend.api.routes.health_ai_services._check_ai_service_health") as mock_check:
            mock_check.return_value = AsyncMock(
                status="unknown",
                circuit_state="closed",
                last_health_check="2026-01-20T00:00:00Z",
                error_rate_1h=None,
                latency_p99_ms=None,
                url=None,
                error="Service URL not configured",
            )

            response = await async_client.get("/api/health/ai-services")
            data = response.json()

            # Should include all 5 AI services
            expected_services = {"rtdetr", "nemotron", "florence", "clip", "enrichment"}
            actual_services = set(data["services"].keys())
            assert expected_services == actual_services

    @pytest.mark.asyncio
    async def test_ai_services_health_returns_503_when_critical_service_down(
        self, async_client: AsyncClient
    ) -> None:
        """Verify endpoint returns 503 when critical services are unhealthy."""
        from datetime import UTC, datetime

        from backend.api.schemas.ai_services_health import (
            AIServiceCircuitState,
            AIServiceHealthDetail,
            AIServiceStatus,
        )

        # Create unhealthy response for critical service
        unhealthy_detail = AIServiceHealthDetail(
            status=AIServiceStatus.UNHEALTHY,
            circuit_state=AIServiceCircuitState.OPEN,
            last_health_check=datetime.now(UTC),
            error_rate_1h=0.5,
            latency_p99_ms=None,
            url="http://localhost:8090",
            error="Connection refused",
        )

        with patch(
            "backend.api.routes.health_ai_services._check_ai_service_health",
            return_value=unhealthy_detail,
        ):
            response = await async_client.get("/api/health/ai-services")

            # Should return 503 since rtdetr and nemotron are critical
            assert response.status_code == 503
            data = response.json()
            assert data["overall_status"] == "critical"
