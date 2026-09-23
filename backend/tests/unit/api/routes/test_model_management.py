"""Unit tests for Model Management API routes.

These tests pin the post-consolidation behavior of
backend/api/routes/model_management.py:

- Read/health endpoints aggregate registry metadata with Triton readiness
  unioned across the gateway root health payload (GET {root}/health, keyed by
  the gateway's full Triton registry — the only surface that reports
  clip/clip_text/stgcn_action) and the ai-gateway router health payloads (GET
  {router}/health, keyed by the triton_name values from models.yml), and, for
  backend-process models, from the in-process ModelManager. A Triton name
  reported by NO payload logs a warning instead of silently reporting
  not-loaded.
- Load/unload/reload/unload-all return 501: Triton runs with
  --model-control-mode=none and the gateway exposes no preload/unload API,
  so the retired enrichment-service proxies cannot survive honestly.

Related Issues:
    - NEM-4780: Model Zoo Management Epic
    - NEM-4782: Backend API endpoint unit tests

Endpoints Tested:
    - GET  /api/system/models           - List all models with runtime state
    - GET  /api/system/models/{name}/status - Get detailed model status
    - POST /api/system/models/{name}/load   - 501 (Triton-resident models)
    - POST /api/system/models/{name}/unload - 501 (Triton-resident models)
    - POST /api/system/models/{name}/reload - 501 (Triton-resident models)
    - POST /api/system/models/unload-all    - 501 (Triton-resident models)
    - GET  /api/system/models/vram-summary  - Get VRAM usage summary
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.api.routes import model_management
from backend.api.schemas.model_management import (
    ModelDetailResponse,
    ModelListResponse,
    VramSummaryResponse,
)
from backend.services.model_zoo import ModelConfig

# =============================================================================
# Test Constants
# =============================================================================

# Gateway router URLs resolved from settings (mocked settings below use the
# retired container-style host names purely so URL assertions stay distinct).
# The router suffixes are load-bearing: the gateway ROOT /health — the only
# readiness surface reporting clip/clip_text/stgcn_action — is derived by
# stripping the suffix from these URLs, so GATEWAY_ROOT_URL is what the root
# probe must hit.
HEAVY_ROUTER_URL = "http://ai-enrichment:8094/enrichment"
LIGHT_ROUTER_URL = "http://ai-enrichment-light:8096/enrich-lt"
GATEWAY_ROOT_URL = "http://ai-enrichment:8094"

# Heavy lane models (gateway /enrichment router)
HEAVY_MODELS = frozenset(
    {
        "vehicle-segment-classification",
        "fashion-clip",
        "segformer-b2-clothes",
        "yolo-world-s",
        "vitpose-small",
        "vehicle-damage-detection",
        "violence-detection",
        "vit-age-classifier",
        "vit-gender-classifier",
    }
)

# Light lane models (gateway /enrich-lt router)
LIGHT_MODELS = frozenset(
    {
        "threat-detection-yolov8n",
        "osnet-ain-x1-0",
        "depth-anything-v2-tiny",
        "pet-classifier",
        "yolov8n-pose",
    }
)

# models.yml fragment exercising the readiness name mapping: triton-mapped
# entries (registry name != triton name), no Triton model (backend-process),
# a 1:many triton_models mapping, and the two catalogue entries whose Triton
# names (clip/clip_text, stgcn_action) NO router /health payload reports — they
# are only in the gateway root /health registry.
CATALOGUE_ENTRIES = [
    {"name": "vehicle-segment-classification", "triton_name": "vehicle"},
    {"name": "fashion-clip", "triton_name": "fashion_clip"},
    {"name": "threat-detection-yolov8n", "triton_name": "threat"},
    {"name": "osnet-ain-x1-0", "triton_name": "reid"},
    {"name": "yolov8n-pose", "triton_name": "pose"},
    {"name": "weather-classification"},  # no triton_name — backend process
    {"name": "florence-2-large"},  # no triton_name — backend process
    {
        "name": "siglip2-base-patch16-224",
        "triton_models": [{"triton_name": "clip"}, {"triton_name": "clip_text"}],
    },
    {"name": "stgcn-plus-plus", "triton_name": "stgcn_action"},
    {"name": "ghost-model", "triton_name": "phantom"},  # reported by no payload
]


def make_health(models: dict[str, bool]) -> dict:
    """Build a gateway router /health payload like the adapters serve."""
    return {
        "status": "healthy" if all(models.values()) else "degraded",
        "models": models,
    }


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def isolate_settings_and_catalogue(tmp_path):
    """Point module settings/lookup at fake enrichment URLs and a fake models.yml."""
    fake_settings = SimpleNamespace(
        enrichment_url=HEAVY_ROUTER_URL,
        enrichment_light_url=LIGHT_ROUTER_URL,
        ai_gateway_url=None,
        use_ai_gateway=False,
    )
    catalogue = tmp_path / "models.yml"
    catalogue.write_text(yaml.safe_dump({"models": CATALOGUE_ENTRIES}))

    with (
        patch("backend.api.routes.model_management.get_settings", autospec=True) as mock_gs,
        patch("backend.api.routes.model_management._MODELS_YML", catalogue),
    ):
        mock_gs.return_value = fake_settings
        model_management._load_triton_name_map.cache_clear()
        yield mock_gs
    model_management._load_triton_name_map.cache_clear()


@pytest.fixture
def mock_enrichment_client() -> AsyncMock:
    """Create a mock enrichment HTTP client."""
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    return client


def registry_entry(
    name: str,
    category: str,
    vram_mb: int,
    enabled: bool = True,
) -> ModelConfig:
    """Create a registry ModelConfig for tests."""
    return ModelConfig(
        name=name,
        path=f"/models/model-zoo/{name}",
        category=category,
        vram_mb=vram_mb,
        load_fn=AsyncMock(),
        enabled=enabled,
        available=False,
    )


@pytest.fixture
def sample_model_configs() -> dict[str, ModelConfig]:
    """Create sample model configs from the model zoo (realistic registry names)."""
    return {
        "vehicle-segment-classification": registry_entry(
            "vehicle-segment-classification", "classification", 1500
        ),
        "fashion-clip": registry_entry("fashion-clip", "classification", 500),
        "threat-detection-yolov8n": registry_entry("threat-detection-yolov8n", "detection", 300),
        "osnet-ain-x1-0": registry_entry("osnet-ain-x1-0", "embedding", 100),
        "yolov8n-pose": registry_entry("yolov8n-pose", "pose", 200),
        "weather-classification": registry_entry("weather-classification", "classification", 200),
        "florence-2-large": registry_entry(
            "florence-2-large", "vision-language", 1200, enabled=False
        ),
        # Gateway-served entries whose Triton names are reported ONLY by the
        # gateway root /health (no router health payload carries them).
        "siglip2-base-patch16-224": registry_entry("siglip2-base-patch16-224", "embedding", 200),
        "stgcn-plus-plus": registry_entry("stgcn-plus-plus", "action-recognition", 20),
    }


@pytest.fixture
def heavy_health() -> dict:
    """Heavy router health payload — vehicle/fashion/demographics/pet/depth ready.

    Mirrors the real /enrichment adapter: clip/clip_text/stgcn_action are
    deliberately absent — this router does not report them (ai/gateway/
    adapters/enrichment.py health()).
    """
    return make_health(
        {
            "vehicle": True,
            "fashion_clip": True,
            "demographics_age": True,
            "demographics_gender": True,
            "pet": True,
            "depth": True,
        }
    )


@pytest.fixture
def light_health() -> dict:
    """Light router health payload — reid (osnet) NOT ready.

    Mirrors the real /enrich-lt adapter (pose/threat/reid/pet/depth only).
    """
    return make_health(
        {
            "pose": True,
            "threat": True,
            "reid": False,
            "pet": True,
            "depth": True,
        }
    )


@pytest.fixture
def root_health() -> dict:
    """Gateway ROOT health payload — the full Triton registry.

    Mirrors ai/gateway/main.py /health iterating ALL_MODELS. clip/clip_text
    (siglip2-base-patch16-224) and stgcn_action (stgcn-plus-plus) are ready
    here but are reported by NO router payload; reid is not ready (matching
    the light router fixture) and yolo26 is not (its catalogue entry is
    disabled). "phantom" is absent — ghost-model's Triton name is reported by
    no payload at all.
    """
    return make_health(
        {
            "yolo26": False,
            "clip": True,
            "clip_text": True,
            "florence2": True,
            "vehicle": True,
            "fashion_clip": True,
            "demographics_age": True,
            "demographics_gender": True,
            "pet": True,
            "depth": True,
            "reid": False,
            "pose": True,
            "threat": True,
            "stgcn_action": True,
        }
    )


def make_url_router_client(
    client: AsyncMock,
    root: dict | None,
    heavy: dict | None,
    light: dict | None,
) -> AsyncMock:
    """Route GET {url}/health on the mock client to root/heavy/light payloads.

    A payload of None simulates that surface being unreachable (connection
    error), matching what _fetch_router_health tolerates.
    """
    import httpx

    async def mock_get(url: str, **kwargs):
        if url == f"{GATEWAY_ROOT_URL}/health":
            payload, reachable = root, root is not None
        elif url == f"{LIGHT_ROUTER_URL}/health":
            payload, reachable = light, light is not None
        elif url == f"{HEAVY_ROUTER_URL}/health":
            payload, reachable = heavy, heavy is not None
        else:
            raise AssertionError(f"unexpected health probe URL: {url}")
        if not reachable:
            raise httpx.ConnectError(f"Connection refused: {url}")
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = payload
        return response

    client.get = AsyncMock(side_effect=mock_get)
    return client


@pytest.fixture
def healthy_client(
    mock_enrichment_client: AsyncMock,
    root_health: dict,
    heavy_health: dict,
    light_health: dict,
):
    """Mock client routing GET /health to root-registry and per-lane payloads."""
    return make_url_router_client(mock_enrichment_client, root_health, heavy_health, light_health)


# =============================================================================
# GET /api/system/models Tests
# =============================================================================


class TestListModels:
    """Tests for GET /api/system/models endpoint."""

    @patch("backend.api.routes.model_management.get_model_zoo", autospec=True)
    async def test_list_models_reports_triton_readiness_and_manager_state(
        self,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        """Registry models merge Triton readiness and backend-manager load state."""
        mock_get_model_zoo.return_value = sample_model_configs

        response = await model_management.list_models(http_client=healthy_client)

        assert isinstance(response, ModelListResponse)
        assert len(response.models) == len(sample_model_configs)

        # Triton-mapped model reported ready by the heavy router
        vehicle = next(m for m in response.models if m.name == "vehicle-segment-classification")
        assert vehicle.runtime.loaded is True
        assert vehicle.service == "ai-enrichment"
        assert vehicle.gpu_id == 0

        # Triton-mapped light model reported ready
        threat = next(m for m in response.models if m.name == "threat-detection-yolov8n")
        assert threat.runtime.loaded is True
        assert threat.service == "ai-enrichment-light"
        assert threat.gpu_id == 1

        # Triton-mapped model whose readiness is False (reid)
        osnet = next(m for m in response.models if m.name == "osnet-ain-x1-0")
        assert osnet.runtime.loaded is False

        # Triton exposes no per-model VRAM/usage over HTTP
        assert threat.runtime.actual_vram_mb is None
        assert threat.runtime.load_count == 0

        # Backend-process model, not loaded in the manager
        weather = next(m for m in response.models if m.name == "weather-classification")
        assert weather.runtime.loaded is False

        # Root-only Triton names: clip/clip_text and stgcn_action appear in NO
        # router payload, so these two enabled models are ready only because
        # the gateway root /health registry reports them (the pre-fix bug made
        # them permanently loaded=False).
        siglip = next(m for m in response.models if m.name == "siglip2-base-patch16-224")
        assert siglip.runtime.loaded is True
        stgcn = next(m for m in response.models if m.name == "stgcn-plus-plus")
        assert stgcn.runtime.loaded is True

        assert response.service_status["ai-enrichment"] == "healthy"
        assert response.service_status["ai-enrichment-light"] == "healthy"

        # Health probes go to the gateway routers' and the gateway root's
        # /health endpoints
        probed = [call.args[0] for call in healthy_client.get.call_args_list]
        assert f"{HEAVY_ROUTER_URL}/health" in probed
        assert f"{LIGHT_ROUTER_URL}/health" in probed
        assert f"{GATEWAY_ROOT_URL}/health" in probed

    @patch("backend.api.routes.model_management.get_model_zoo", autospec=True)
    @patch("backend.api.routes.model_management.get_model_manager", autospec=True)
    async def test_list_models_reports_backend_manager_load_state(
        self,
        mock_get_manager: MagicMock,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        """Backend-process models loaded in ModelManager report loaded=True."""
        mock_get_model_zoo.return_value = sample_model_configs
        manager = MagicMock()
        manager.is_loaded.side_effect = lambda name: name == "weather-classification"
        mock_get_manager.return_value = manager

        response = await model_management.list_models(http_client=healthy_client)

        weather = next(m for m in response.models if m.name == "weather-classification")
        assert weather.runtime.loaded is True
        # Estimate basis matches ModelManager.total_loaded_vram
        assert weather.runtime.actual_vram_mb == 200

    @patch("backend.api.routes.model_management.get_model_zoo", autospec=True)
    async def test_list_models_handles_routers_down(
        self,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        mock_enrichment_client: AsyncMock,
    ) -> None:
        """Unreachable routers yield loaded=False and unhealthy service status."""
        import httpx

        mock_get_model_zoo.return_value = sample_model_configs
        mock_enrichment_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        response = await model_management.list_models(http_client=mock_enrichment_client)

        assert isinstance(response, ModelListResponse)
        assert len(response.models) == len(sample_model_configs)
        for model in response.models:
            assert model.runtime.loaded is False
            assert model.runtime.actual_vram_mb is None

        assert response.service_status["ai-enrichment"] == "unhealthy"
        assert response.service_status["ai-enrichment-light"] == "unhealthy"


# =============================================================================
# GET /api/system/models/{name}/status Tests
# =============================================================================


class TestGetModelStatus:
    """Tests for GET /api/system/models/{name}/status endpoint."""

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    async def test_get_model_status_reports_triton_readiness(
        self,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        """Detail status reads readiness from the serving router's health payload."""
        model_name = "vehicle-segment-classification"
        mock_get_model_config.return_value = sample_model_configs[model_name]

        result = await model_management.get_model_status(
            model_name=model_name,
            http_client=healthy_client,
        )

        assert isinstance(result, ModelDetailResponse)
        assert result.name == model_name
        assert result.category == "classification"
        assert result.path == "/models/model-zoo/vehicle-segment-classification"
        assert result.estimated_vram_mb == 1500
        assert result.enabled is True
        assert result.service == "ai-enrichment"
        assert result.gpu_id == 0
        assert result.runtime.loaded is True

        probed = [call.args[0] for call in healthy_client.get.call_args_list]
        assert f"{HEAVY_ROUTER_URL}/health" in probed
        assert f"{GATEWAY_ROOT_URL}/health" in probed

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    async def test_get_model_status_backend_model_skips_router(
        self,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        """Backend-process models (no Triton mapping) are not probed on routers."""
        model_name = "weather-classification"
        mock_get_model_config.return_value = sample_model_configs[model_name]

        result = await model_management.get_model_status(
            model_name=model_name,
            http_client=healthy_client,
        )

        assert result.runtime.loaded is False
        assert healthy_client.get.await_count == 0

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    async def test_get_model_status_unknown_model_returns_404(
        self,
        mock_get_model_config: MagicMock,
    ) -> None:
        """Get model status should return 404 for unknown models."""
        mock_get_model_config.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await model_management.get_model_status(
                model_name="nonexistent-model",
                http_client=AsyncMock(),
            )

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


# =============================================================================
# Gateway ROOT Health Readiness Tests (root + router union)
# =============================================================================


class TestRootHealthReadiness:
    """Readiness for Triton names that NO router /health payload reports.

    siglip2-base-patch16-224 maps to Triton names clip/clip_text and
    stgcn-plus-plus maps to stgcn_action; the /enrichment and /enrich-lt
    health payloads never carry those keys (they live behind the /clip and
    action routers), so only the gateway root /health — which iterates the
    gateway's full Triton registry — can make these enabled models report
    loaded=True. Probing only the routers made them permanently false.
    """

    @patch("backend.api.routes.model_management.get_model_zoo", autospec=True)
    async def test_root_health_only_models_report_loaded_in_list(
        self,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        root_health: dict,
    ) -> None:
        """Router-omitted names report loaded=True when root health says ready.

        Both routers are unreachable here so the root payload is the only
        readiness surface that answers at all.
        """
        mock_get_model_zoo.return_value = sample_model_configs
        client = make_url_router_client(AsyncMock(), root_health, None, None)

        response = await model_management.list_models(http_client=client)

        siglip = next(m for m in response.models if m.name == "siglip2-base-patch16-224")
        assert siglip.runtime.loaded is True
        stgcn = next(m for m in response.models if m.name == "stgcn-plus-plus")
        assert stgcn.runtime.loaded is True

    @patch("backend.api.routes.model_management.get_model_zoo", autospec=True)
    async def test_root_health_not_ready_reports_loaded_false_in_list(
        self,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        heavy_health: dict,
        light_health: dict,
    ) -> None:
        """Root health reporting those names False flips loaded back to False."""
        mock_get_model_zoo.return_value = sample_model_configs
        root = make_health(
            {
                "clip": False,
                "clip_text": True,
                "stgcn_action": False,
                "threat": True,
                "pose": True,
                "vehicle": True,
            }
        )
        client = make_url_router_client(AsyncMock(), root, heavy_health, light_health)

        response = await model_management.list_models(http_client=client)

        siglip = next(m for m in response.models if m.name == "siglip2-base-patch16-224")
        assert siglip.runtime.loaded is False
        stgcn = next(m for m in response.models if m.name == "stgcn-plus-plus")
        assert stgcn.runtime.loaded is False

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    async def test_root_health_ready_in_detail_status(
        self,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        """Detail status unions root health with its one router probe."""
        mock_get_model_config.return_value = sample_model_configs["stgcn-plus-plus"]

        result = await model_management.get_model_status(
            model_name="stgcn-plus-plus",
            http_client=healthy_client,
        )

        assert result.runtime.loaded is True
        # stgcn-plus-plus is a heavy-lane model, so its router probe and the
        # root probe are the same container's two endpoints.
        probed = [call.args[0] for call in healthy_client.get.call_args_list]
        assert f"{GATEWAY_ROOT_URL}/health" in probed

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    async def test_root_health_not_ready_in_detail_status(
        self,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        heavy_health: dict,
    ) -> None:
        """Detail status reports loaded=False when root health says not ready."""
        mock_get_model_config.return_value = sample_model_configs["siglip2-base-patch16-224"]
        root = make_health({"clip": True, "clip_text": False, "vehicle": True})
        # siglip2 is a heavy-lane model: the detail probe hits that router and
        # the derived root, and the router payload never carries clip names.
        client = make_url_router_client(AsyncMock(), root, heavy_health, None)

        result = await model_management.get_model_status(
            model_name="siglip2-base-patch16-224",
            http_client=client,
        )

        assert result.runtime.loaded is False


class TestReadinessVisibility:
    """Catalogue drift is logged, not hidden behind a silent permanent false."""

    @patch("backend.api.routes.model_management.get_model_zoo", autospec=True)
    async def test_triton_name_reported_by_no_payload_warns(
        self,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A name missing from root AND both router payloads logs a warning."""
        mock_get_model_zoo.return_value = {
            **sample_model_configs,
            "ghost-model": registry_entry("ghost-model", "classification", 100),
        }

        with caplog.at_level("WARNING", logger="backend.api.routes.model_management"):
            response = await model_management.list_models(http_client=healthy_client)

        ghost = next(m for m in response.models if m.name == "ghost-model")
        assert ghost.runtime.loaded is False
        warnings = [r.message for r in caplog.records if "phantom" in r.getMessage()]
        assert warnings, (
            "a Triton name reported by no health payload must log a warning rather "
            "than silently report not-ready"
        )

    @patch("backend.api.routes.model_management.get_model_zoo", autospec=True)
    async def test_all_surfaces_down_does_not_spam_drift_warnings(
        self,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        mock_enrichment_client: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """With every surface unreachable the connectivity warning stands alone.

        Every Triton name is trivially "reported by no payload" when nothing
        answered — that is an outage, not catalogue drift, and must not bury
        the connection warnings _fetch_router_health already logs.
        """
        import httpx

        mock_get_model_zoo.return_value = {
            **sample_model_configs,
            "ghost-model": registry_entry("ghost-model", "classification", 100),
        }
        mock_enrichment_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with caplog.at_level("WARNING", logger="backend.api.routes.model_management"):
            response = await model_management.list_models(http_client=mock_enrichment_client)

        assert all(m.runtime.loaded is False for m in response.models)
        assert not [r for r in caplog.records if "no gateway health payload" in r.getMessage()]


class TestGatewayRootUrlDerivation:
    """The root probe URL is derived from the router URLs, never guessed."""

    def test_root_url_stripped_from_router_settings(self) -> None:
        """Suffixed router settings fields yield the gateway root base."""
        root = model_management.get_gateway_root_url()
        assert root == GATEWAY_ROOT_URL

    def test_root_url_follows_gateway_mode_base(
        self, isolate_settings_and_catalogue: MagicMock
    ) -> None:
        """Gateway mode derives the root from ai_gateway_url itself."""
        isolate_settings_and_catalogue.return_value = SimpleNamespace(
            enrichment_url="http://stale:1/enrichment",
            enrichment_light_url="http://stale:1/enrich-lt",
            ai_gateway_url="http://ai-gateway:8090/",
            use_ai_gateway=True,
        )
        assert model_management.get_gateway_root_url() == "http://ai-gateway:8090"

    def test_root_url_undervivable_yields_none_and_warns(
        self,
        isolate_settings_and_catalogue: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A suffixless router URL skips the root probe instead of guessing."""
        isolate_settings_and_catalogue.return_value = SimpleNamespace(
            enrichment_url="http://gateway-host:8090",
            enrichment_light_url="http://gateway-host:8090",
            ai_gateway_url=None,
            use_ai_gateway=False,
        )
        with caplog.at_level("WARNING", logger="backend.api.routes.model_management"):
            assert model_management.get_gateway_root_url() is None
        assert "root URL" in caplog.text


# =============================================================================
# Load/Unload Lifecycle Tests (501 after ai-gateway consolidation)
# =============================================================================


class TestLifecycleUnsupported:
    """Triton runs with --model-control-mode=none; lifecycle calls report 501."""

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    async def test_load_enabled_model_returns_501_without_proxying(
        self,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        """Load must not fabricate success against the gateway — it has no load API."""
        mock_get_model_config.return_value = sample_model_configs["vehicle-segment-classification"]

        with pytest.raises(HTTPException) as exc_info:
            await model_management.load_model(model_name="vehicle-segment-classification")

        assert exc_info.value.status_code == 501
        assert "not supported" in exc_info.value.detail.lower()
        assert healthy_client.post.await_count == 0

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    async def test_load_unknown_model_returns_404(self, mock_get_model_config: MagicMock) -> None:
        mock_get_model_config.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await model_management.load_model(model_name="nonexistent-model")

        assert exc_info.value.status_code == 404

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    async def test_load_disabled_model_returns_400(
        self,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
    ) -> None:
        """Loading a disabled model should return 400 error."""
        mock_get_model_config.return_value = sample_model_configs["florence-2-large"]

        with pytest.raises(HTTPException) as exc_info:
            await model_management.load_model(model_name="florence-2-large")

        assert exc_info.value.status_code == 400
        assert "disabled" in exc_info.value.detail.lower()

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    async def test_unload_known_model_returns_501(
        self,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        mock_get_model_config.return_value = sample_model_configs["threat-detection-yolov8n"]

        with pytest.raises(HTTPException) as exc_info:
            await model_management.unload_model(model_name="threat-detection-yolov8n")

        assert exc_info.value.status_code == 501
        assert healthy_client.post.await_count == 0

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    async def test_unload_unknown_model_returns_404(
        self,
        mock_get_model_config: MagicMock,
    ) -> None:
        """Unloading an unknown model should return 404."""
        mock_get_model_config.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await model_management.unload_model(model_name="nonexistent-model")

        assert exc_info.value.status_code == 404

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    async def test_reload_enabled_model_returns_501(
        self,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
    ) -> None:
        mock_get_model_config.return_value = sample_model_configs["vehicle-segment-classification"]

        with pytest.raises(HTTPException) as exc_info:
            await model_management.reload_model(model_name="vehicle-segment-classification")

        assert exc_info.value.status_code == 501

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    async def test_reload_disabled_model_returns_400(
        self,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
    ) -> None:
        mock_get_model_config.return_value = sample_model_configs["florence-2-large"]

        with pytest.raises(HTTPException) as exc_info:
            await model_management.reload_model(model_name="florence-2-large")

        assert exc_info.value.status_code == 400

    async def test_unload_all_returns_501(self, healthy_client: AsyncMock) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await model_management.unload_all_models()

        assert exc_info.value.status_code == 501
        assert healthy_client.post.await_count == 0


# =============================================================================
# GET /api/system/models/vram-summary Tests
# =============================================================================


class TestVramSummary:
    """Tests for GET /api/system/models/vram-summary endpoint."""

    @patch("backend.api.routes.model_management.get_model_zoo", autospec=True)
    async def test_vram_summary_aggregates_readiness_estimates(
        self,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        """used_mb sums registry estimates of Triton-ready models per lane."""
        mock_get_model_zoo.return_value = sample_model_configs

        result = await model_management.get_vram_summary(http_client=healthy_client)

        assert isinstance(result, VramSummaryResponse)
        assert len(result.gpus) == 2

        gpu0 = next(g for g in result.gpus if g.gpu_id == 0)
        assert gpu0.service == "ai-enrichment"
        assert gpu0.budget_mb == 6800
        assert gpu0.loaded_models == ["vehicle-segment-classification", "fashion-clip"]
        assert gpu0.used_mb == 2000
        assert gpu0.available_mb == 4800

        # osnet's Triton model (reid) is not ready; weather has no Triton model
        gpu1 = next(g for g in result.gpus if g.gpu_id == 1)
        assert gpu1.service == "ai-enrichment-light"
        assert gpu1.budget_mb == 1200
        assert gpu1.loaded_models == ["threat-detection-yolov8n", "yolov8n-pose"]
        assert gpu1.used_mb == 500
        assert gpu1.available_mb == 700

        assert result.totals.budget_mb == 8000
        assert result.totals.used_mb == 2500
        assert result.totals.available_mb == 5500
        assert result.totals.model_count == 4

    @patch("backend.api.routes.model_management.get_model_zoo", autospec=True)
    async def test_vram_summary_with_routers_down(
        self,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        mock_enrichment_client: AsyncMock,
    ) -> None:
        """Unreachable routers report budgets with zero usage."""
        import httpx

        mock_get_model_zoo.return_value = sample_model_configs
        mock_enrichment_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        result = await model_management.get_vram_summary(http_client=mock_enrichment_client)

        assert result.totals.used_mb == 0
        assert result.totals.available_mb == 8000
        assert result.totals.model_count == 0


# =============================================================================
# Service Routing Tests
# =============================================================================


class TestServiceRouting:
    """Tests for model-to-router routing logic."""

    def test_heavy_model_routes_to_enrichment_router(self) -> None:
        """Heavy-lane models should resolve to the gateway heavy router."""
        for model_name in HEAVY_MODELS:
            url = model_management.get_service_for_model(model_name)
            assert url == HEAVY_ROUTER_URL, f"{model_name} should route to the heavy router"

    def test_light_model_routes_to_enrichment_light_router(self) -> None:
        """Light-lane models should resolve to the gateway light router."""
        for model_name in LIGHT_MODELS:
            url = model_management.get_service_for_model(model_name)
            assert url == LIGHT_ROUTER_URL, f"{model_name} should route to the light router"

    def test_get_gpu_id_for_model(self) -> None:
        """Lane ids follow the heavy/light split."""
        for model_name in HEAVY_MODELS:
            assert model_management.get_gpu_id_for_model(model_name) == 0, (
                f"{model_name} should be on lane 0"
            )
        for model_name in LIGHT_MODELS:
            assert model_management.get_gpu_id_for_model(model_name) == 1, (
                f"{model_name} should be on lane 1"
            )

    def test_router_urls_follow_gateway_mode(
        self, isolate_settings_and_catalogue: MagicMock
    ) -> None:
        """AI Gateway mode builds router URLs from ai_gateway_url (client parity)."""
        isolate_settings_and_catalogue.return_value = SimpleNamespace(
            enrichment_url="http://stale:1/enrichment",
            enrichment_light_url="http://stale:1/enrich-lt",
            ai_gateway_url="http://ai-gateway:8090/",
            use_ai_gateway=True,
        )
        heavy, light = model_management.get_router_urls()
        assert heavy == "http://ai-gateway:8090/enrichment"
        assert light == "http://ai-gateway:8090/enrich-lt"


# =============================================================================
# FastAPI TestClient Integration Tests
# =============================================================================


class TestModelManagementRouterIntegration:
    """Integration tests using FastAPI TestClient.

    These tests verify the router is correctly wired and endpoints
    respond with expected HTTP status codes and response formats.
    """

    def _make_client(
        self,
        configs: dict[str, ModelConfig],
        http_client: AsyncMock,
    ) -> TestClient:
        """Build a TestClient with the registry and HTTP client mocked."""
        app = FastAPI()
        app.include_router(model_management.router)

        async def mock_get_http_client():
            return http_client

        app.dependency_overrides[model_management.get_http_client] = mock_get_http_client
        return TestClient(app, raise_server_exceptions=False)

    def test_list_models_endpoint_returns_registry(
        self,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        with patch(
            "backend.api.routes.model_management.get_model_zoo",
            return_value=sample_model_configs,
            autospec=True,
        ):
            client = self._make_client(sample_model_configs, healthy_client)
            response = client.get("/api/system/models")

        assert response.status_code == 200
        body = response.json()
        assert len(body["models"]) == len(sample_model_configs)
        assert body["service_status"]["ai-enrichment"] == "healthy"

    def test_get_model_status_unknown_model_returns_404(
        self,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        with patch(
            "backend.api.routes.model_management.get_model_config",
            return_value=None,
            autospec=True,
        ):
            client = self._make_client(sample_model_configs, healthy_client)
            response = client.get("/api/system/models/test-model/status")

        assert response.status_code == 404

    def test_get_model_status_known_model_returns_detail(
        self,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        config = sample_model_configs["vehicle-segment-classification"]
        with patch(
            "backend.api.routes.model_management.get_model_config",
            return_value=config,
            autospec=True,
        ):
            client = self._make_client(sample_model_configs, healthy_client)
            response = client.get("/api/system/models/vehicle-segment-classification/status")

        assert response.status_code == 200
        assert response.json()["runtime"]["loaded"] is True

    def test_load_endpoint_returns_501(
        self,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        config = sample_model_configs["vehicle-segment-classification"]
        with patch(
            "backend.api.routes.model_management.get_model_config",
            return_value=config,
            autospec=True,
        ):
            client = self._make_client(sample_model_configs, healthy_client)
            response = client.post("/api/system/models/vehicle-segment-classification/load")

        assert response.status_code == 501
        assert "not supported" in response.json()["detail"].lower()

    def test_unload_endpoint_returns_501(
        self,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        config = sample_model_configs["vehicle-segment-classification"]
        with patch(
            "backend.api.routes.model_management.get_model_config",
            return_value=config,
            autospec=True,
        ):
            client = self._make_client(sample_model_configs, healthy_client)
            response = client.post("/api/system/models/vehicle-segment-classification/unload")

        assert response.status_code == 501

    def test_reload_endpoint_returns_501(
        self,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        config = sample_model_configs["vehicle-segment-classification"]
        with patch(
            "backend.api.routes.model_management.get_model_config",
            return_value=config,
            autospec=True,
        ):
            client = self._make_client(sample_model_configs, healthy_client)
            response = client.post("/api/system/models/vehicle-segment-classification/reload")

        assert response.status_code == 501

    def test_unload_all_endpoint_returns_501(
        self,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        client = self._make_client(sample_model_configs, healthy_client)
        response = client.post("/api/system/models/unload-all")

        assert response.status_code == 501

    def test_vram_summary_endpoint_returns_budgets(
        self,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        with patch(
            "backend.api.routes.model_management.get_model_zoo",
            return_value=sample_model_configs,
            autospec=True,
        ):
            client = self._make_client(sample_model_configs, healthy_client)
            response = client.get("/api/system/models/vram-summary")

        assert response.status_code == 200
        body = response.json()
        assert body["totals"]["budget_mb"] == 8000
