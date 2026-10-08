"""B1.4 (UR-18): the readiness payload must report the VERDICT ENGINE's own state.

Today an unreachable `ai-vlm` turns every event into `verification_failed` while the
platform looks healthy: `/api/system/health/ready` computes `ready`/HTTP status from
database, Redis and pipeline workers only (system.py's readiness body never reads
ai_status), so the engine's state is visible nowhere a caller can branch on. This
file pins the package's first two clauses:

1. engine unreachable -> `verdict_engine: {state: "unavailable", since, reason}` in
   the readiness payload; engine returns -> state `available`.
2. HTTP status STAYS 200 when only the engine is down: the backend container's
   healthcheck (docker-compose.prod.yml) and every `service_healthy` dependency read
   that status — a down engine must not take the platform with it.

The 200 assertion is a preservation pin, not new behavior: it already holds (the
readiness body ignores ai health), and must keep holding once verdict_engine lands.
The `verdict_engine` field itself does not exist yet — every access below is red by
KeyError until implemented. `since` is pinned as the TRANSITION time (unchanged
while the state is unchanged), not a per-request timestamp, because "since" only
answers an operator's question ("how long has this been down?") if it survives the
10 s readiness cache and the probe storm behind it.

Patched seam: `check_ai_services_health` returns the exact
HealthCheckServiceStatus shape `_check_shipped_ai_services_health` produces when the
vlm probe fails but yolo26 answers (status degraded, details carry the engine's own
error string) — the transport-level pin used by the sibling failure-scenario tests
in test_health_checks.py, including its clear_health_cache() autouse fixture.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest

from backend.api.schemas.system import HealthCheckServiceStatus

if TYPE_CHECKING:
    from httpx import AsyncClient

    from backend.core.redis import RedisClient

pytestmark = pytest.mark.integration

_VLM_DOWN = HealthCheckServiceStatus(
    status="degraded",
    message="ai-vlm service unavailable, YOLO26 operational",
    details={"yolo26": "healthy", "ai-vlm": "ConnectError: connection refused"},
)
_VLM_UP = HealthCheckServiceStatus(
    status="healthy",
    message="AI services operational",
    details={"yolo26": "healthy", "ai-vlm": "healthy"},
)


def _patch_ai_health(result: HealthCheckServiceStatus):
    """Patch the aggregated AI health at the seam the readiness route calls.

    new= (not autospec+new: mock refuses that combination — autospec builds its own
    mock) with an AsyncMock because the seam is awaited by asyncio.gather."""
    return patch(
        "backend.api.routes.system._check_ai_health_with_timeout",
        new=AsyncMock(return_value=result),
    )


class TestVerdictEngineReadiness:
    """`verdict_engine` in the readiness payload; HTTP 200 survives an engine outage."""

    @pytest.fixture(autouse=True)
    def _clear_health_caches(self) -> None:
        """Same cache hazard as test_health_checks.py's failure-scenario class
        (ledger R-T7-HEALTH): get_readiness caches for HEALTH_CACHE_TTL_SECONDS and
        these tests mutate engine health inside that window."""
        from backend.api.routes.system import clear_health_cache

        clear_health_cache()
        yield
        clear_health_cache()

    @pytest.fixture(autouse=True)
    def _healthy_pipeline_workers(self):
        """Readiness gates on critical pipeline workers when
        READINESS_REQUIRE_PIPELINE_WORKERS is true (its default). The integration
        client fixture mocks every background service OUT, so the workers are down
        by fixture environment — the 503 would be the WORKER gate, not the engine,
        and clause 2 is specifically about the engine not moving the status.
        Workers pinned healthy here so the only variable these tests move is the
        engine."""
        with patch(
            "backend.api.routes.system._are_critical_pipeline_workers_healthy",
            return_value=True,
        ):
            yield

    @pytest.mark.asyncio
    async def test_engine_unreachable_reports_verdict_engine_unavailable(
        self,
        client: AsyncClient,
        integration_db: str,
        mock_redis: AsyncMock,
    ) -> None:
        """Clause 1, down side: the payload names the engine's state, when it
        changed, and why. KeyError on verdict_engine is the red this package
        starts from."""
        with _patch_ai_health(_VLM_DOWN):
            response = await client.get("/api/system/health/ready")

        data = response.json()
        verdict = data["verdict_engine"]
        assert verdict is not None, "engine state must be present, not absent-until-down"
        assert verdict["state"] == "unavailable"
        assert verdict["reason"], "an operator reading this needs the engine's own error"
        assert "connection refused" in verdict["reason"], "reason carries the probe's error text"
        since = datetime.fromisoformat(verdict["since"])
        assert since.tzinfo is not None, "since must be an aware timestamp like every other field"

    @pytest.mark.asyncio
    async def test_engine_returns_reports_verdict_engine_available(
        self,
        client: AsyncClient,
        integration_db: str,
        mock_redis: AsyncMock,
    ) -> None:
        """Clause 1, up side."""
        with _patch_ai_health(_VLM_UP):
            response = await client.get("/api/system/health/ready")

        data = response.json()
        assert data["verdict_engine"]["state"] == "available"

    @pytest.mark.asyncio
    async def test_readiness_status_stays_200_when_only_the_engine_is_down(
        self,
        client: AsyncClient,
        integration_db: str,
        mock_redis: AsyncMock,
    ) -> None:
        """Clause 2, the production-safety pin: the container healthcheck and every
        service_healthy dependency read THIS status code. A down verdict engine must
        never flip it — the platform keeps serving while events honestly report the
        verification gap."""
        with _patch_ai_health(_VLM_DOWN):
            response = await client.get("/api/system/health/ready")

        assert response.status_code == 200, (
            "engine-down took the platform's readiness with it — compose healthcheck "
            "and service_healthy dependents would restart a healthy backend"
        )
        data = response.json()
        assert data["ready"] is True
        assert data["status"] == "ready"
        assert data["verdict_engine"]["state"] == "unavailable", (
            "200 stays, but the payload must not hide the outage"
        )

    @pytest.mark.asyncio
    async def test_since_is_the_transition_time_not_a_per_request_timestamp(
        self,
        client: AsyncClient,
        integration_db: str,
        mock_redis: AsyncMock,
    ) -> None:
        """Two probes while the engine stays down report the SAME `since`: it is the
        moment the state changed, not the moment you asked. (The readiness cache is
        cleared between probes here, so this pins the state tracker itself, not the
        cache.)"""
        with _patch_ai_health(_VLM_DOWN):
            first = (await client.get("/api/system/health/ready")).json()
            from backend.api.routes.system import clear_health_cache

            clear_health_cache()
            second = (await client.get("/api/system/health/ready")).json()

        assert first["verdict_engine"]["since"] == second["verdict_engine"]["since"]
