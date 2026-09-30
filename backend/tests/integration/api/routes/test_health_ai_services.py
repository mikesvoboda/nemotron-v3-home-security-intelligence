"""Integration tests for AI services health endpoint (NEM-3143).

These tests verify the /api/health/ai-services endpoint works correctly
with the real application context, including Redis integration.

R8 S3 (2026-09-29, owner rulings 1 + 5) note: this file used to drive a 5-row
health table {yolo26, ai-vlm, florence, clip, enrichment}. The rollup
MACHINERY is live — ``AI_SERVICES_CONFIG`` still exists, the route still probes
each row in parallel and still folds the results into a per-service map — but
three of those five rows were deleted IN THE DATA with their providers, so the
shipped table is {yolo26, ai-vlm}. ``test_ai_services_health_includes_all_services``
was RETARGETED onto that surviving surface rather than weakened: it still pins
the table exactly, and it now additionally pins that the rollup actually DROVE
one probe per surviving row (so a retired name cannot be "absent" merely
because the endpoint stopped reporting anything).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from backend.api.schemas.ai_services_health import (
    AIServiceCircuitState,
    AIServiceHealthDetail,
    AIServiceStatus,
)

if TYPE_CHECKING:
    from httpx import AsyncClient


def _detail(status: str = "healthy", error: str | None = None) -> AIServiceHealthDetail:
    """Real schema instance — the route serializes the gathered results
    into AIServicesHealthResponse, so an AsyncMock return_value fails
    response validation → 500 INTERNAL_ERROR (ledger R-T9-AIHEALTH2)."""
    return AIServiceHealthDetail(
        status=AIServiceStatus(status),
        circuit_state=AIServiceCircuitState.CLOSED,
        last_health_check=datetime.now(UTC),
        error_rate_1h=None,
        latency_p99_ms=None,
        url="http://localhost:8090",
        error=error,
    )


@pytest.fixture
async def async_client(client):
    """Alias for the shared client fixture (ledger R-T9-AIHEALTH).

    The tests request `async_client`, which no fixture provides — every test
    in this class ERRORed at setup with "fixture 'async_client' not found".
    Same ghost-name class as test_tracks.py; the shared fixture is `client`.
    """
    yield client


@pytest.mark.integration
class TestAIServicesHealthIntegration:
    """Integration tests for AI services health endpoint."""

    @pytest.mark.asyncio
    async def test_ai_services_health_endpoint_returns_valid_response(
        self, async_client: AsyncClient
    ) -> None:
        """Verify the endpoint returns a valid response structure."""
        # Mock the AI service health checks since actual AI services aren't running
        with patch(
            "backend.api.routes.health_ai_services._check_ai_service_health",
            return_value=_detail("healthy"),
            autospec=True,
        ):
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
        with patch(
            "backend.api.routes.health_ai_services._check_ai_service_health",
            return_value=_detail("unknown", error="Service URL not configured"),
            autospec=True,
        ):
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
        """Verify the rollup reports exactly the services that still ship.

        What used to be true: this test asserted a 5-row table
        ``{yolo26, ai-vlm, florence, clip, enrichment}`` and the shipped
        ``PIPELINE_MODE=vlm`` deployment really did probe all five, because the
        Triton tier still served the ``/florence``, ``/clip`` and
        ``/enrichment`` routers.

        Why it died: R8 S3 (2026-09-29, owner rulings 1 + 5) deleted the
        Florence provider and swept the CLIP / enrichment / enrichment-light
        serving tier, and the prune to yolo26/reid/threat made those routers
        unbootable. Their Settings fields went with them —
        ``backend/core/config.py``:1489-1493 records ``florence_url``,
        ``clip_url`` and ``enrichment_url`` as DELETED — so a probe row for a
        router that cannot boot could only ever report UNKNOWN forever.

        What is LIVE, and therefore what this pin now asserts: the rollup
        itself survives in ``backend/api/routes/health_ai_services.py``.
        ``AI_SERVICES_CONFIG`` is still the table the route reads (lines
        50-78, now yolo26 + ai-vlm only), ``get_ai_services_health`` still
        fans out one ``_check_ai_service_health`` per row (lines 397-405) and
        still keys the response ``services`` map off the row names, and
        ``_calculate_overall_status`` still rolls the per-row states into
        healthy/degraded/critical (lines 327-361). So the assertion keeps its
        teeth: it still pins the reported set EXACTLY, onto the surviving two.

        Non-vacuity: an "absent" retired name is only evidence if the endpoint
        reported *something*, so the pin also requires that the rollup actually
        drove one probe per surviving row (the call-count assert below) and
        that each reported row carries a real detail payload. An endpoint that
        reported nothing would otherwise satisfy every absence assert here.
        """
        from backend.api.routes.health_ai_services import AI_SERVICES_CONFIG
        from backend.core.config import Settings

        retired_services = {"florence", "clip", "enrichment"}
        with patch(
            "backend.api.routes.health_ai_services._check_ai_service_health",
            return_value=_detail("unknown", error="Service URL not configured"),
            autospec=True,
        ) as mocked_probe:
            response = await async_client.get("/api/health/ai-services")
            data = response.json()

            actual_services = set(data["services"])

            # The shipped table, exactly. R8 S3 deleted the florence, clip and
            # enrichment rows IN THE DATA; yolo26 + ai-vlm cover the whole
            # surviving set, and the kept light specialists ride inside
            # ai-gateway, which the monitor set already tracks as one container.
            expected_services = {"yolo26", "ai-vlm"}
            assert expected_services == actual_services, (
                f"reported {sorted(actual_services)}, expected {sorted(expected_services)}"
            )
            assert len(expected_services) >= 2, (
                "the table's two live rows (yolo26 + ai-vlm) are the floor; a "
                "smaller expected set means a row was dropped, not retired"
            )

            # The expected set is derived, not hand-waved: it is exactly the
            # shipped config's names, so this pin tracks the table instead of
            # freezing a snapshot of it.
            assert expected_services == {cfg["name"] for cfg in AI_SERVICES_CONFIG}

            # The retired trio stays retired, asserted by name against the LIVE
            # response shape (a bare equality above would pass for the wrong
            # reason if a survivor were renamed).
            assert not (retired_services & actual_services), (
                f"retired services back in the health rollup: {sorted(retired_services & actual_services)}"
            )
            # And the reason they cannot come back as rows: their probe targets
            # were deleted with their providers, so a re-added row would be a
            # permanently-UNKNOWN probe of nothing.
            settings_fields = set(Settings.model_fields)
            orphaned = {f"{n}_url" for n in retired_services} - settings_fields
            assert orphaned == {"florence_url", "clip_url", "enrichment_url"}, (
                f"a retired service's Settings field is back: {sorted(orphaned)}"
            )

            # NON-VACUITY: the absence above is only meaningful because the
            # rollup really drove one probe per surviving row. Without this, an
            # endpoint that reported nothing at all would satisfy every assert.
            assert len(AI_SERVICES_CONFIG) >= 2, "the rollup has no rows to roll up"
            assert mocked_probe.call_count == len(AI_SERVICES_CONFIG)
            probed_names = {c.args[0]["name"] for c in mocked_probe.call_args_list}
            assert probed_names == expected_services, sorted(probed_names)
            # Each reported row is a real detail payload, not a placeholder.
            for name in expected_services:
                row = data["services"][name]
                assert row["status"] in {"healthy", "unhealthy", "degraded", "unknown"}
                assert "circuit_state" in row
                assert "last_health_check" in row

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
            autospec=True,
        ):
            response = await async_client.get("/api/health/ai-services")

            # Should return 503 since yolo26 is critical
            assert response.status_code == 503
            data = response.json()
            assert data["overall_status"] == "critical"
