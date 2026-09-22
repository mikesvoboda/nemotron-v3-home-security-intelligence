"""Integration tests for Model Zoo Management API endpoints (NEM-4783).

Post-ai-gateway-consolidation contract (the previous revision of this file
tested the retired standalone-enrichment proxy: dispatch on ports 8094/8096,
GET {service}/models/status, load/unload returning 200 with freed_vram, and
load/unload returning 503 when the proxy target was absent — none of those
surfaces exist any more post-consolidation):

- Read endpoints (list / detail status / vram-summary) aggregate registry
  metadata with Triton readiness from the ai-gateway router health payloads
  (GET {router}/health, keyed by the triton_name values in the root
  models.yml catalogue) and, for backend-process models, from ModelManager.
  The shared integration fixtures stand in for a router outage — the whole
  app boots through the client fixture while no ai-gateway runs.
- Lifecycle endpoints (load / unload / reload / unload-all) return 501 with
  registry-validation precedence (404 unknown, then 400 disabled) and MUST
  NOT touch the network: Triton runs --model-control-mode=none and the
  gateway exposes no preload/unload surface. The http_client dependency
  factory is swapped for a tripwire that fails the test on ANY outbound
  call, so a "fixed" lifecycle route that starts POSTing to the gateway is
  caught here even though its 501 assertion would still pass (the route's
  validation only reads the registry, so no GET is expected either).
- vram-summary reports per-lane budgets with readiness-derived estimates
  and never fabricates live VRAM figures.

Registry state (models.yml at repo root is catalogue truth):
- fashion-clip: "both" service with triton_name fashion_clip — its
  registry vram_mb is overridden by a fixture to a value found nowhere else,
  so used_mb proves the lane sum reads the catalogue estimate, not a live
  figure.
- threat-detection-yolov8n: light-lane model (gpu_id 1).
- weather-classification: backend-only model, no Triton mapping.
- yolo26-general: disabled in the catalogue — the 400-on-disabled fixture.

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database
- client: httpx AsyncClient with test app
- mock_redis: Mock Redis client
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import yaml
from httpx import AsyncClient

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

# Router base URLs resolved from default settings (enrichment_url /
# enrichment_light_url already point at the ai-gateway routers
# post-consolidation) — the egress assertions key on these.
HEALTH_HEAVY = "http://ai-gateway:8090/enrichment/health"
HEALTH_LIGHT = "http://ai-gateway:8090/enrich-lt/health"

# models.yml stand-in: readiness keys are the catalogue's triton names.
CATALOGUE_ENTRIES = [
    {"name": "fashion-clip", "triton_name": "fashion_clip"},
    {"name": "threat-detection-yolov8n", "triton_name": "threat"},
    {"name": "osnet-ain-x1-0", "triton_name": "reid"},
    {"name": "weather-classification"},  # no triton_name — backend process
]

# fashion-clip registry estimate used by this file. The real models.yml value
# differs (500), so gpu0.used_mb pinning this number proves lane accounting
# reads the registry estimate (see the vram-summary docstring).
FASHION_CLIP_VRAM_ESTIMATE = 5123


def make_health(models: dict[str, bool]) -> dict[str, Any]:
    """Build a gateway router /health payload like the adapters serve."""
    return {
        "status": "healthy" if all(models.values()) else "degraded",
        "models": models,
    }


@contextmanager
def override_http_client(mock_http: Any):
    """Override the get_http_client dependency for the current request(s).

    FastAPI captures get_http_client at route-declaration time; unittest.mock
    .patch on the module attribute is a no-op (probe-verified, same DI trap as
    R-T7-SERVICES). dependency_overrides IS consulted at request time. Zero-arg
    override: an unannotated request param resolves as a query param and 422s.
    """
    from backend.api.routes.model_management import get_http_client
    from backend.main import app

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_http_client] = lambda: mock_http
    try:
        yield
    finally:
        app.dependency_overrides = original


@pytest.fixture
def fake_catalogue(tmp_path):
    """Point the route's models.yml lookup at a fake catalogue (lru_cache is
    keyed on nothing, so it must be cleared around the patch)."""
    catalogue = tmp_path / "models.yml"
    catalogue.write_text(yaml.safe_dump({"models": CATALOGUE_ENTRIES}))

    from backend.api.routes import model_management

    model_management._load_triton_name_map.cache_clear()
    with patch.object(model_management, "_MODELS_YML", catalogue):
        yield catalogue
    model_management._load_triton_name_map.cache_clear()


@pytest.fixture
def real_fashion_clip_config():
    """Real registry ModelConfig for fashion-clip with a stand-in estimate.

    The estimate is set to a value that cannot come from anywhere else so
    vram-summary assertions prove the registry-estimate basis; the real
    catalogue's vram_mb is deliberately not reused.
    """
    from backend.services.model_zoo import get_model_config

    config = get_model_config("fashion-clip")
    assert config is not None, "models.yml lost fashion-clip from the registry"
    original = config.vram_mb
    config.vram_mb = FASHION_CLIP_VRAM_ESTIMATE
    try:
        yield config
    finally:
        config.vram_mb = original


@pytest.fixture
def tripwire_http_client():
    """Async mock http client that fails the test on ANY outbound call.

    The lifecycle endpoints must answer purely from the registry — a GET here
    would mean someone re-introduced the router-proxy behavior the 501 exists
    to forbid. The current lifecycle signatures take no http_client
    dependency at all, so this tripwire fires against a "fixed" route that
    re-adds Depends(get_http_client) to POST to the gateway: its 501-for-a-
    valid-model assertion would still pass, and the recorded egress is what
    reddens it.
    """

    async def _no_egress(*args: Any, **kwargs: Any) -> httpx.Response:
        raise AssertionError(f"lifecycle endpoint must not touch the network: {args} {kwargs}")

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(side_effect=_no_egress)
    mock_http.post = AsyncMock(side_effect=_no_egress)
    return mock_http


# =============================================================================
# Read Endpoints — degraded path with no ai-gateway running
# =============================================================================


class TestListModelsIntegration:
    """Integration tests for GET /api/system/models endpoint."""

    @pytest.mark.asyncio
    async def test_list_models_degrades_gracefully_without_gateway(
        self,
        client: AsyncClient,
    ) -> None:
        """No ai-gateway in this environment → registry data survives, runtime
        reports unloaded, both routers report unhealthy.

        Verifies:
        - Response includes models from the registry
        - Triton-mapped and backend-process models alike report loaded=False
        - Service status shows both routers unhealthy (never a fabricated up)
        """
        response = await client.get("/api/system/models")

        assert response.status_code == 200
        data = response.json()

        assert "models" in data
        assert "service_status" in data

        models = data["models"]
        assert len(models) > 0

        # Heavy-lane Triton model: lane labels persist as router labels
        fashion_clip = next((m for m in models if m["name"] == "fashion-clip"), None)
        assert fashion_clip is not None
        assert fashion_clip["runtime"]["loaded"] is False
        assert fashion_clip["runtime"]["actual_vram_mb"] is None
        assert fashion_clip["gpu_id"] == 0
        assert fashion_clip["service"] == "ai-enrichment"

        # Light-lane Triton model
        threat_model = next((m for m in models if m["name"] == "threat-detection-yolov8n"), None)
        assert threat_model is not None
        assert threat_model["runtime"]["loaded"] is False
        assert threat_model["gpu_id"] == 1
        assert threat_model["service"] == "ai-enrichment-light"

        # Service status shows the routers unreachable
        service_status = data["service_status"]
        assert service_status["ai-enrichment"] == "unhealthy"
        assert service_status["ai-enrichment-light"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_list_models_readiness_from_gateway_health_payloads(
        self,
        client: AsyncClient,
        fake_catalogue,
    ) -> None:
        """With router health mocked, readiness comes from the health payloads
        keyed by the models.yml triton names, probed at {router}/health.

        Verifies:
        - GET goes to both routers' /health (not the retired /models/status)
        - triton=True models report loaded, triton=False models do not
        - backend-process models report from ModelManager, not the routers
        """
        heavy = make_health({"fashion_clip": True})
        light = make_health({"threat": True, "reid": False})

        async def mock_get(url: str, *args: Any, **kwargs: Any) -> httpx.Response:
            if url == HEALTH_HEAVY:
                return httpx.Response(200, json=heavy)
            if url == HEALTH_LIGHT:
                return httpx.Response(200, json=light)
            raise AssertionError(f"unexpected probe URL from list_models: {url}")

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=mock_get)

        with override_http_client(mock_http):
            response = await client.get("/api/system/models")

        assert response.status_code == 200
        data = response.json()
        models = data["models"]

        by_name = {m["name"]: m for m in models}

        # Triton-ready (heavy router said fashion_clip: true)
        fashion = by_name.get("fashion-clip")
        if fashion:  # present only while fashion-clip keeps a loader in _LOADER_MAP
            assert fashion["runtime"]["loaded"] is True
            # Triton exposes no per-model VRAM over HTTP
            assert fashion["runtime"]["actual_vram_mb"] is None

        threat = by_name.get("threat-detection-yolov8n")
        if threat:
            assert threat["runtime"]["loaded"] is True

        # Light router reported reid not-ready
        osnet = by_name.get("osnet-ain-x1-0")
        if osnet:
            assert osnet["runtime"]["loaded"] is False

        # Backend-process model: ModelManager state, routers not consulted for it
        weather = by_name.get("weather-classification")
        if weather:
            assert weather["runtime"]["loaded"] is False

        probed = [call.args[0] for call in mock_http.get.call_args_list]
        assert HEALTH_HEAVY in probed
        assert HEALTH_LIGHT in probed

        assert data["service_status"]["ai-enrichment"] == "healthy"
        assert data["service_status"]["ai-enrichment-light"] == "healthy"


class TestModelStatusEndpoint:
    """Integration tests for GET /api/system/models/{name}/status endpoint."""

    @pytest.mark.asyncio
    async def test_get_model_status_returns_detailed_info(
        self,
        client: AsyncClient,
    ) -> None:
        """Detail status answers with registry fields even with no gateway up;
        a Triton-mapped model reports unloaded rather than a fabricated up."""
        response = await client.get("/api/system/models/fashion-clip/status")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "fashion-clip"
        assert "category" in data
        assert data["estimated_vram_mb"] > 0
        assert "enabled" in data
        assert data["service"] == "ai-enrichment"
        assert data["gpu_id"] == 0
        runtime = data["runtime"]
        assert runtime["loaded"] is False
        assert "actual_vram_mb" in runtime
        assert "last_used" in runtime
        assert "load_count" in runtime

    @pytest.mark.asyncio
    async def test_get_model_status_backend_model_skips_router(
        self,
        client: AsyncClient,
        fake_catalogue,
    ) -> None:
        """A model with no Triton mapping is answered from ModelManager only —
        no router is probed for it."""
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=AssertionError("router probed for backend model"))

        with override_http_client(mock_http):
            response = await client.get("/api/system/models/weather-classification/status")

        assert response.status_code == 200
        data = response.json()
        assert data["runtime"]["loaded"] is False
        assert mock_http.get.await_count == 0


class TestVramSummaryIntegration:
    """Integration tests for GET /api/system/models/vram-summary endpoint."""

    @pytest.mark.asyncio
    async def test_vram_summary_reports_budgets_without_fabricated_usage(
        self,
        client: AsyncClient,
    ) -> None:
        """With no gateway up, both lanes report budgets and zero usage."""
        response = await client.get("/api/system/models/vram-summary")

        assert response.status_code == 200
        data = response.json()

        assert "gpus" in data
        assert "totals" in data

        gpus = data["gpus"]
        assert len(gpus) == 2  # heavy and light router lanes

        gpu0 = next(g for g in gpus if g["gpu_id"] == 0)
        assert gpu0["service"] == "ai-enrichment"
        assert gpu0["budget_mb"] == 6800
        assert gpu0["used_mb"] == 0
        assert gpu0["available_mb"] == 6800
        assert gpu0["loaded_models"] == []
        assert "utilization_percent" in gpu0

        gpu1 = next(g for g in gpus if g["gpu_id"] == 1)
        assert gpu1["service"] == "ai-enrichment-light"
        assert gpu1["budget_mb"] == 1200
        assert gpu1["used_mb"] == 0

        totals = data["totals"]
        assert totals["budget_mb"] == 8000  # 6800 + 1200
        assert totals["used_mb"] == 0
        assert totals["available_mb"] == 8000
        assert totals["model_count"] == 0

    @pytest.mark.asyncio
    async def test_vram_summary_sums_registry_estimates_of_ready_models(
        self,
        client: AsyncClient,
        fake_catalogue,
        real_fashion_clip_config,
    ) -> None:
        """Ready models on a lane sum the registry vram_mb estimates (the
        retired VRAM-manager accounting is gone and Triton exposes no live
        per-model figure)."""
        heavy = make_health({"fashion_clip": True})
        light = make_health({"threat": True})

        async def mock_get(url: str, *args: Any, **kwargs: Any) -> httpx.Response:
            if url == HEALTH_HEAVY:
                return httpx.Response(200, json=heavy)
            if url == HEALTH_LIGHT:
                return httpx.Response(200, json=light)
            raise AssertionError(f"unexpected probe URL from vram-summary: {url}")

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=mock_get)

        with override_http_client(mock_http):
            response = await client.get("/api/system/models/vram-summary")

        assert response.status_code == 200
        data = response.json()

        gpu0 = next(g for g in data["gpus"] if g["gpu_id"] == 0)
        assert gpu0["loaded_models"] == ["fashion-clip"]
        # proves the registry-estimate basis, not a live/other figure
        assert gpu0["used_mb"] == FASHION_CLIP_VRAM_ESTIMATE
        assert gpu0["available_mb"] == 6800 - FASHION_CLIP_VRAM_ESTIMATE

        gpu1 = next(g for g in data["gpus"] if g["gpu_id"] == 1)
        assert gpu1["loaded_models"] == ["threat-detection-yolov8n"]

        totals = data["totals"]
        assert totals["model_count"] == 2
        assert totals["used_mb"] == FASHION_CLIP_VRAM_ESTIMATE + gpu1["used_mb"]


# =============================================================================
# Lifecycle Endpoints — 501 with registry validation, zero egress
# =============================================================================


def no_egress_recorded(mock_http: AsyncMock) -> bool:
    """True iff the mocked client recorded no calls at all."""
    return (
        mock_http.get.await_count == 0
        and mock_http.post.await_count == 0
        and mock_http.mock_calls == []
    )


class TestLifecycleUnsupported:
    """load/unload/reload/unload-all: Triton runs --model-control-mode=none;
    every route answers 501 and must not issue any outbound HTTP call."""

    @pytest.mark.asyncio
    async def test_load_known_model_returns_501_without_egress(
        self,
        client: AsyncClient,
        tripwire_http_client: AsyncMock,
    ) -> None:
        with override_http_client(tripwire_http_client):
            response = await client.post("/api/system/models/fashion-clip/load")

        assert response.status_code == 501
        detail = response.json()["detail"].lower()
        assert "not supported" in detail
        assert no_egress_recorded(tripwire_http_client)

    @pytest.mark.asyncio
    async def test_unload_known_model_returns_501_without_egress(
        self,
        client: AsyncClient,
        tripwire_http_client: AsyncMock,
    ) -> None:
        with override_http_client(tripwire_http_client):
            response = await client.post("/api/system/models/fashion-clip/unload")

        assert response.status_code == 501
        assert no_egress_recorded(tripwire_http_client)

    @pytest.mark.asyncio
    async def test_reload_known_model_returns_501_without_egress(
        self,
        client: AsyncClient,
        tripwire_http_client: AsyncMock,
    ) -> None:
        with override_http_client(tripwire_http_client):
            response = await client.post("/api/system/models/fashion-clip/reload")

        assert response.status_code == 501
        assert no_egress_recorded(tripwire_http_client)

    @pytest.mark.asyncio
    async def test_unload_all_returns_501_without_egress(
        self,
        client: AsyncClient,
        tripwire_http_client: AsyncMock,
    ) -> None:
        with override_http_client(tripwire_http_client):
            response = await client.post("/api/system/models/unload-all")

        assert response.status_code == 501
        assert no_egress_recorded(tripwire_http_client)

    @pytest.mark.asyncio
    async def test_load_backend_process_model_still_501(
        self,
        client: AsyncClient,
        tripwire_http_client: AsyncMock,
    ) -> None:
        """Backend-process models load lazily via ModelManager on first use —
        the HTTP surface still refuses with 501 (no eager-load path)."""
        with override_http_client(tripwire_http_client):
            response = await client.post("/api/system/models/weather-classification/load")

        assert response.status_code == 501
        assert no_egress_recorded(tripwire_http_client)


class TestModelNotFoundErrors:
    """Registry validation precedes the 501 (404 unknown model)."""

    @pytest.mark.asyncio
    async def test_load_nonexistent_model_returns_error(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post("/api/system/models/nonexistent-model-xyz/load")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower() or "nonexistent" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_unload_nonexistent_model_returns_error(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post("/api/system/models/nonexistent-model-xyz/unload")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower() or "nonexistent" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_reload_nonexistent_model_returns_error(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post("/api/system/models/nonexistent-model-xyz/reload")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower() or "nonexistent" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_status_nonexistent_model_returns_error(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.get("/api/system/models/nonexistent-model-xyz/status")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestDisabledModelErrors:
    """Registry validation precedes the 501 (400 disabled model)."""

    @pytest.mark.asyncio
    async def test_load_disabled_model_returns_error(
        self,
        client: AsyncClient,
    ) -> None:
        """The model 'yolo26-general' is disabled in the registry."""
        response = await client.post("/api/system/models/yolo26-general/load")

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "disabled" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_reload_disabled_model_returns_error(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post("/api/system/models/yolo26-general/reload")

        assert response.status_code == 400
        data = response.json()
        assert "disabled" in data["detail"].lower()
