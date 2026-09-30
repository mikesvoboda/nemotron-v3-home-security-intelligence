"""Unit tests for Model Management API routes.

These tests pin the post-R8-S3 behavior of
backend/api/routes/model_management.py:

- Read/health endpoints aggregate registry metadata with Triton readiness
  unioned across TWO surfaces (there are no longer three): the gateway root
  health payload (GET {root}/health, which iterates the gateway's ACTIVE
  residency set — after the S3 prune that set is exactly the KEEP SET
  yolo26/reid/threat, the three Triton models that must stay served because
  S1's PASS depends on them) and the ONE mounted router's health payload
  (GET {router}/health of /enrich-lt, which reports threat/reid only). The
  heavy /enrichment router was unmounted by R8 S3 (owner rulings 1 + 5) and
  the clip/florence/action routers with it, so no payload any more reports
  clip/clip_text/stgcn_action — those Triton models were pruned from the
  repository. yolo26 is now the name the root answers and NO router reports
  (it is served through the gateway's own /yolo26 router), which is the
  shipped counterpart of the retired "root-only clip/stgcn" case this file
  used to pin. For backend-process models, state comes from the in-process
  ModelManager. A Triton name reported by NO payload logs a warning instead of
  silently reporting not-loaded.
- Service labelling has exactly two answers — "ai-enrichment-light" (models
  the /enrich-lt router serves) and "ai-gateway" (everything the root answers:
  yolo26 and the backend-process models). "ai-enrichment" is not an available
  answer: it named the router S3 unmounted.
- VRAM accounting is one lane: gpu 1, budget LIGHT_VRAM_BUDGET_MB (1200), the
  heavy lane's 6800 MB budget and its lane-0 device retired with the router.
- Load/unload/reload/unload-all return 501: Triton runs with
  --model-control-mode=none and the gateway exposes no preload/unload API,
  so the retired enrichment-service proxies cannot survive honestly.

Related Issues:
    - NEM-4780: Model Zoo Management Epic
    - NEM-4782: Backend API endpoints unit tests

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

import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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

# The one router URL, resolved from settings. The fake settings below keep the
# retired container-style host name purely so the root and router probe URLs
# stay textually distinct assertions — root is derived by stripping the
# "/enrich-lt" suffix, so it is this same base without the suffix.
LIGHT_ROUTER_URL = "http://ai-enrichment-light:8096/enrich-lt"
GATEWAY_ROOT_URL = "http://ai-enrichment-light:8096"

# The two service labels this endpoint can answer with, and the retired one
# that must never come back (R8 S3 owner ruling 1: the heavy router is gone, so
# a row labelled with it would render a card permanently stuck on unreachable).
LIGHT_SERVICE = "ai-enrichment-light"
GATEWAY_SERVICE = "ai-gateway"
RETIRED_HEAVY_SERVICE = "ai-enrichment"
SERVICE_LABELS = frozenset({LIGHT_SERVICE, GATEWAY_SERVICE})

# Shipped one-lane geometry (mirrors model_management._GPU_LANE_ID /
# LIGHT_VRAM_BUDGET_MB, which come from docker-compose's
# CUDA_VISIBLE_DEVICES=${GPU_AI_SERVICES:-1} for ai-gateway). Lane 0 was the
# heavy lane's device and no longer exists.
LANE_GPU_ID = 1
LANE_BUDGET_MB = 1200
RETIRED_LANE_GPU_ID = 0

# Shipped membership of the one lane (mirrors model_management.LIGHT_MODELS).
SHIPPED_LIGHT_MEMBERS = frozenset({"threat-detection-yolov8n", "osnet-ain-x1-0"})

# The Triton models the gateway still boots — the KEEP SET. The root /health
# iterates the ACTIVE residency set and the /enrich-lt adapter declares exactly
# threat/reid, so these two fake payloads below are shapes the shipped
# endpoints can actually produce (ai/gateway/main.py health_check,
# ai/gateway/adapters/enrichment_light.py health).
KEEP_SET = frozenset({"yolo26", "reid", "threat"})
LIGHT_ROUTER_REPORTS = frozenset({"threat", "reid"})

# Models outside the light lane whose readiness the gateway root answers: a
# Triton-backed one (yolo26), a 1:many Triton mapping (the stand-in below) and
# backend-process models with no Triton mapping at all. Used as the routing /
# labelling census — the retired exemplars (florence-2-base, face-recognizer on
# the heavy lane, fast-alpr "on the heavy router") named the unmounted router.
NON_LIGHT_EXEMPLARS = frozenset({"yolo26", "triton-pair-standin", "face-recognizer", "fast-alpr"})

# Routing/labelling census, and the non-vacuity claim it depends on: it holds
# at least one light member AND at least one non-light name, so a test looping
# it cannot pass on an empty or one-sided set.
ROUTING_CENSUS = SHIPPED_LIGHT_MEMBERS | NON_LIGHT_EXEMPLARS

# models.yml stand-in exercising the readiness name mapping on shipped Triton
# names: a root-only Triton name (yolo26 — reported by the gateway root, never
# by /enrich-lt), the two light-lane names (threat, reid), a 1:many
# triton_models mapping (a catalogue format models.yml still documents and
# _load_triton_name_map still parses, though no shipped row uses it — the row
# name is a stand-in that exists only in this file), a name with no triton_name
# (backend process), and a name NO payload reports (catalogue drift).
CATALOGUE_ENTRIES = [
    {"name": "yolo26", "triton_name": "yolo26"},
    {"name": "threat-detection-yolov8n", "triton_name": "threat"},
    {"name": "osnet-ain-x1-0", "triton_name": "reid"},
    {
        "name": "triton-pair-standin",
        "triton_models": [{"triton_name": "reid"}, {"triton_name": "threat"}],
    },
    {"name": "face-recognizer"},  # no triton_name — backend process
    {"name": "fast-alpr"},  # no triton_name — backend process
    {"name": "yolo26-general"},  # no triton_name — backend process, disabled
    {"name": "ghost-model", "triton_name": "phantom"},  # reported by no payload
]


def make_health(models: dict[str, bool]) -> dict:
    """Build a gateway /health payload like the root and the router serve."""
    return {
        "status": "healthy" if all(models.values()) else "degraded",
        "models": models,
    }


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def isolate_settings_and_catalogue(tmp_path):
    """Point module settings/lookup at the one fake router URL and a fake models.yml.

    enrichment_url is NOT in the fake settings: the field was deleted with the
    heavy router (backend/core/config.py), so get_router_urls has exactly one
    source left.
    """
    fake_settings = SimpleNamespace(
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
    """Create sample model configs from the registry (shipped catalogue names).

    Names mirror the post-S3 models.yml rows; the vram_mb values are chosen
    distinct from one another so lane sums prove they were actually added.
    yolo26 and yolo26-general carry their catalogue's enabled: false.
    """
    return {
        # Triton-backed, readiness answered ONLY by the gateway root /health.
        "yolo26": registry_entry("yolo26", "detection", 1400, enabled=False),
        "threat-detection-yolov8n": registry_entry("threat-detection-yolov8n", "detection", 300),
        "osnet-ain-x1-0": registry_entry("osnet-ain-x1-0", "embedding", 100),
        # 1:many Triton mapping (readiness needs BOTH of reid + threat).
        "triton-pair-standin": registry_entry("triton-pair-standin", "embedding", 400),
        # Backend-process models: no Triton mapping, answered by ModelManager.
        "face-recognizer": registry_entry("face-recognizer", "recognition", 200),
        "fast-alpr": registry_entry("fast-alpr", "ocr", 28),
        "yolo26-general": registry_entry("yolo26-general", "detection", 400, enabled=False),
    }


@pytest.fixture
def light_health() -> dict:
    """The /enrich-lt router health payload — exactly threat/reid, reid NOT ready.

    Mirrors ai/gateway/adapters/enrichment_light.py health(), which after the
    S3 prune declares exactly these two models: pose/pet/depth left with the
    pruned Triton repository, so a payload carrying them would describe a
    surface that cannot boot.
    """
    return make_health({"threat": True, "reid": False})


@pytest.fixture
def root_health() -> dict:
    """Gateway ROOT health payload — exactly the KEEP SET.

    Mirrors ai/gateway/main.py /health iterating the ACTIVE residency set.
    yolo26 is ready here and appears in NO router payload (it is served on the
    gateway's own /yolo26 router), reid is not ready (matching the light router
    fixture), and "phantom" is absent — ghost-model's Triton name is reported by
    no payload at all.
    """
    return make_health({"yolo26": True, "reid": False, "threat": True})


def make_url_router_client(
    client: AsyncMock,
    root: dict | None,
    light: dict | None,
) -> AsyncMock:
    """Route GET {url}/health on the mock client to the root and light payloads.

    A payload of None simulates that surface being unreachable (connection
    error), matching what _fetch_router_health tolerates. Any OTHER URL is a
    loud test failure: the heavy router's URL is no longer a probe target, and
    a probe to a base the fake settings do not produce means the derivation
    under test changed underneath this file.
    """

    async def mock_get(url: str, **kwargs):
        if url == f"{GATEWAY_ROOT_URL}/health":
            payload, reachable = root, root is not None
        elif url == f"{LIGHT_ROUTER_URL}/health":
            payload, reachable = light, light is not None
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
    light_health: dict,
):
    """Mock client routing GET /health to the gateway root and the one router."""
    return make_url_router_client(mock_enrichment_client, root_health, light_health)


def probed_urls(client: AsyncMock) -> set[str]:
    """The exact set of URLs the mock client was asked to probe."""
    return {call.args[0] for call in client.get.call_args_list}


# =============================================================================
# GET /api/system/models Tests
# =============================================================================


class TestListModels:
    """Tests for GET /api/system/models endpoint."""

    def test_payload_surfaces_are_the_two_shipped_health_shapes(
        self,
        root_health: dict,
        light_health: dict,
    ) -> None:
        """The fake payloads this file drives readiness with are the shipped shapes.

        Non-vacuity: both key sets are non-empty, and KEEP_SET is checked
        against the gateway's own residency tuple rather than against itself,
        so the equality claims below are about shipped code and not about two
        local constants agreeing.
        """
        from ai.gateway.residency import FULL_MODEL_SET

        root_models = root_health["models"]
        light_models = light_health["models"]
        assert root_models, "root health fixture must report at least one Triton model"
        assert light_models, "router health fixture must report at least one Triton model"
        assert frozenset(FULL_MODEL_SET) == KEEP_SET, (
            "the KEEP SET these fixtures mirror must stay the gateway's pruned "
            "universe — if residency moves, these payloads move with it"
        )
        assert set(root_models) == KEEP_SET, (
            "the gateway root /health iterates the ACTIVE residency set — the "
            "KEEP SET yolo26/reid/threat and nothing else after the S3 prune"
        )
        assert set(light_models) == LIGHT_ROUTER_REPORTS, (
            "the /enrich-lt adapter declares exactly threat/reid inline (pose/pet/"
            "depth were pruned, and a stale key would report degraded on every "
            "healthy boot)"
        )
        assert LIGHT_ROUTER_REPORTS <= KEEP_SET, (
            "the router reports only models the gateway still boots"
        )
        assert KEEP_SET.difference(LIGHT_ROUTER_REPORTS) == frozenset({"yolo26"}), (
            "yolo26 is the name only the root answers — the shipped case the "
            "retired root-only clip/clip_text/stgcn_action pins used to cover"
        )

    @patch("backend.api.routes.model_management.get_model_zoo", autospec=True)
    async def test_list_models_reports_triton_readiness_and_manager_state(
        self,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
        light_health: dict,
    ) -> None:
        """Registry models merge unioned Triton readiness and backend-manager state."""
        mock_get_model_zoo.return_value = sample_model_configs
        assert sample_model_configs, "the fake registry must not be empty"

        response = await model_management.list_models(http_client=healthy_client)

        assert isinstance(response, ModelListResponse)
        assert len(response.models) == len(sample_model_configs)

        # Root-only Triton name: yolo26 appears in the /enrich-lt payload not
        # at all, so it is ready only because the gateway root /health reports
        # it (non-vacuity: the absent key below is what makes the root probe
        # load-bearing). Its catalogue row is disabled, which readiness does not
        # consult — Triton's answer, not the enabled flag.
        assert "yolo26" not in light_health["models"]
        yolo26 = next(m for m in response.models if m.name == "yolo26")
        assert yolo26.runtime.loaded is True
        assert yolo26.enabled is False
        assert yolo26.service == GATEWAY_SERVICE
        assert yolo26.gpu_id == LANE_GPU_ID

        # Light-lane model reported ready by the router that serves it
        threat = next(m for m in response.models if m.name == "threat-detection-yolov8n")
        assert threat.runtime.loaded is True
        assert threat.service == LIGHT_SERVICE
        assert threat.gpu_id == LANE_GPU_ID

        # Triton-mapped light model reported not ready
        osnet = next(m for m in response.models if m.name == "osnet-ain-x1-0")
        assert osnet.runtime.loaded is False
        assert osnet.service == LIGHT_SERVICE

        # A 1:many triton_models mapping needs EVERY name: threat is ready,
        # reid is not, so the pair is not — the False must not be masked.
        pair = next(m for m in response.models if m.name == "triton-pair-standin")
        assert pair.runtime.loaded is False
        assert threat.runtime.loaded is True, (
            "threat alone being ready is what makes the pair's False a real "
            "'needs every name' answer rather than an all-not-ready answer"
        )

        # Triton exposes no per-model VRAM/usage over HTTP
        assert threat.runtime.actual_vram_mb is None
        assert threat.runtime.load_count == 0

        # Backend-process model, not loaded in the manager
        face = next(m for m in response.models if m.name == "face-recognizer")
        assert face.runtime.loaded is False

        # Every model sits on the one lane: the retired lane 0 never appears.
        lanes = {m.gpu_id for m in response.models}
        assert lanes == {LANE_GPU_ID}, "one serving lane — the heavy lane's device 0 is gone"

        # Service labels are exactly the two shipped answers, and the retired
        # heavy label is not among them.
        labels = {m.service for m in response.models}
        assert labels == set(SERVICE_LABELS)
        assert RETIRED_HEAVY_SERVICE not in labels

        # One row per label this endpoint can actually answer for.
        assert set(response.service_status) == set(SERVICE_LABELS)
        assert response.service_status[LIGHT_SERVICE] == "healthy"
        assert response.service_status[GATEWAY_SERVICE] == "healthy"

        # Health probes go to the gateway root and the ONE mounted router —
        # exact census, so a probe of the unmounted /enrichment router fails.
        assert probed_urls(healthy_client) == {
            f"{GATEWAY_ROOT_URL}/health",
            f"{LIGHT_ROUTER_URL}/health",
        }

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
        manager.is_loaded.side_effect = lambda name: name == "face-recognizer"
        mock_get_manager.return_value = manager

        response = await model_management.list_models(http_client=healthy_client)

        face = next(m for m in response.models if m.name == "face-recognizer")
        assert face.runtime.loaded is True
        # Estimate basis matches ModelManager.total_loaded_vram
        assert face.runtime.actual_vram_mb == 200

    @patch("backend.api.routes.model_management.get_model_zoo", autospec=True)
    async def test_list_models_handles_routers_down(
        self,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        mock_enrichment_client: AsyncMock,
    ) -> None:
        """Unreachable surfaces yield loaded=False and unhealthy service status."""
        mock_get_model_zoo.return_value = sample_model_configs
        mock_enrichment_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        response = await model_management.list_models(http_client=mock_enrichment_client)

        assert isinstance(response, ModelListResponse)
        assert len(response.models) == len(sample_model_configs)
        assert response.models, "the census below is vacuous on an empty list"
        for model in response.models:
            assert model.runtime.loaded is False
            assert model.runtime.actual_vram_mb is None

        assert set(response.service_status) == set(SERVICE_LABELS)
        assert set(response.service_status.values()) == {"unhealthy"}


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
        """Detail status reads readiness from the one router, unioned with the root."""
        model_name = "threat-detection-yolov8n"
        mock_get_model_config.return_value = sample_model_configs[model_name]

        result = await model_management.get_model_status(
            model_name=model_name,
            http_client=healthy_client,
        )

        assert isinstance(result, ModelDetailResponse)
        assert result.name == model_name
        assert result.category == "detection"
        assert result.path == "/models/model-zoo/threat-detection-yolov8n"
        assert result.estimated_vram_mb == 300
        assert result.enabled is True
        assert result.service == LIGHT_SERVICE
        assert result.gpu_id == LANE_GPU_ID
        assert result.runtime.loaded is True

        assert probed_urls(healthy_client) == {
            f"{LIGHT_ROUTER_URL}/health",
            f"{GATEWAY_ROOT_URL}/health",
        }

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    async def test_get_model_status_backend_model_skips_router(
        self,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        """Backend-process models (no Triton mapping) are not probed at all."""
        model_name = "face-recognizer"
        mock_get_model_config.return_value = sample_model_configs[model_name]

        result = await model_management.get_model_status(
            model_name=model_name,
            http_client=healthy_client,
        )

        assert result.runtime.loaded is False
        assert result.service == GATEWAY_SERVICE
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
# Gateway ROOT Health Readiness Tests (root + the one router, unioned)
# =============================================================================


class TestRootHealthReadiness:
    """Readiness for the Triton name NO router /health payload reports.

    After R8 S3 that name is yolo26: it is Triton-backed and resident (it is in
    the KEEP SET), but it is served through the gateway's own /yolo26 router, so
    the /enrich-lt payload never carries it — only the gateway root /health,
    which iterates the ACTIVE residency set, can make it report loaded=True.
    Probing only the router would have made it permanently false, which is the
    same bug the retired clip/clip_text/stgcn_action pins covered on the wider
    pre-S3 registry.
    """

    @patch("backend.api.routes.model_management.get_model_zoo", autospec=True)
    async def test_root_health_only_models_report_loaded_in_list(
        self,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        root_health: dict,
        light_health: dict,
    ) -> None:
        """The router-omitted name reports loaded=True when root health says ready.

        The router is unreachable here, so the root payload is the only
        readiness surface that answers at all — non-vacuity: "yolo26" is absent
        from the router payload that WOULD have been consulted.
        """
        mock_get_model_zoo.return_value = sample_model_configs
        assert "yolo26" not in light_health["models"]
        assert root_health["models"]["yolo26"] is True
        client = make_url_router_client(AsyncMock(), root_health, None)

        response = await model_management.list_models(http_client=client)

        yolo26 = next(m for m in response.models if m.name == "yolo26")
        assert yolo26.runtime.loaded is True
        # The unreachable router is still reported honestly.
        assert response.service_status[LIGHT_SERVICE] == "unhealthy"
        assert response.service_status[GATEWAY_SERVICE] == "healthy"

    @patch("backend.api.routes.model_management.get_model_zoo", autospec=True)
    async def test_root_health_not_ready_reports_loaded_false_in_list(
        self,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        light_health: dict,
    ) -> None:
        """Root health reporting yolo26 False flips loaded back to False.

        threat stays ready on both surfaces, so the yolo26 False is the only
        thing that can produce the expected loaded=False.
        """
        mock_get_model_zoo.return_value = sample_model_configs
        root = make_health({"yolo26": False, "reid": False, "threat": True})
        client = make_url_router_client(AsyncMock(), root, light_health)

        response = await model_management.list_models(http_client=client)

        yolo26 = next(m for m in response.models if m.name == "yolo26")
        assert yolo26.runtime.loaded is False
        threat = next(m for m in response.models if m.name == "threat-detection-yolov8n")
        assert threat.runtime.loaded is True

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    async def test_root_health_ready_in_detail_status(
        self,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        """Detail status unions root health with its one router probe."""
        mock_get_model_config.return_value = sample_model_configs["yolo26"]

        result = await model_management.get_model_status(
            model_name="yolo26",
            http_client=healthy_client,
        )

        assert result.runtime.loaded is True
        # yolo26 is not a light-lane model, but its probe target IS the one
        # mounted router — get_service_for_model returns a probe address, not an
        # ownership claim, and the root payload is what answers for it.
        assert result.service == GATEWAY_SERVICE
        assert probed_urls(healthy_client) == {
            f"{LIGHT_ROUTER_URL}/health",
            f"{GATEWAY_ROOT_URL}/health",
        }

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    async def test_root_health_not_ready_in_detail_status(
        self,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        light_health: dict,
    ) -> None:
        """Detail status reports loaded=False when root health says not ready."""
        mock_get_model_config.return_value = sample_model_configs["yolo26"]
        root = make_health({"yolo26": False, "reid": False, "threat": True})
        client = make_url_router_client(AsyncMock(), root, light_health)

        result = await model_management.get_model_status(
            model_name="yolo26",
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
        """A name missing from the root AND the router payload logs one warning."""
        mock_get_model_zoo.return_value = {
            **sample_model_configs,
            "ghost-model": registry_entry("ghost-model", "classification", 100),
        }

        with caplog.at_level("WARNING", logger="backend.api.routes.model_management"):
            response = await model_management.list_models(http_client=healthy_client)

        ghost = next(m for m in response.models if m.name == "ghost-model")
        assert ghost.runtime.loaded is False
        warned = [
            r.getMessage()
            for r in caplog.records
            if "reported by no gateway health payload" in r.getMessage()
        ]
        assert warned, (
            "a Triton name reported by no health payload must log a warning rather "
            "than silently report not-ready"
        )
        # Exact census: only the drifted name warns, so every shipped name in
        # the fake payloads is genuinely being recognised by the union.
        drift_names = {re.search(r"'([^']+)'", msg).group(1) for msg in warned}
        assert drift_names == {"phantom"}

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
        mock_get_model_zoo.return_value = {
            **sample_model_configs,
            "ghost-model": registry_entry("ghost-model", "classification", 100),
        }
        mock_enrichment_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with caplog.at_level("WARNING", logger="backend.api.routes.model_management"):
            response = await model_management.list_models(http_client=mock_enrichment_client)

        assert response.models, "the census below is vacuous on an empty list"
        assert all(m.runtime.loaded is False for m in response.models)
        assert not [r for r in caplog.records if "no gateway health payload" in r.getMessage()]


class TestGatewayRootUrlDerivation:
    """The root probe URL is derived from the router URLs, never guessed."""

    def test_root_url_stripped_from_router_settings(self) -> None:
        """The suffixed router settings field yields the gateway root base."""
        assert model_management.ROUTER_SUFFIXES == ("/enrich-lt",), (
            "the heavy router's suffix left with the settings field it was "
            "derived from, so exactly the surviving suffix is strippable"
        )
        root = model_management.get_gateway_root_url()
        assert root == GATEWAY_ROOT_URL
        # The two probes are distinct surfaces: the root base is the router
        # base with the suffix removed, not the router URL itself.
        assert root != LIGHT_ROUTER_URL

    def test_root_url_follows_gateway_mode(self, isolate_settings_and_catalogue: MagicMock) -> None:
        """Gateway mode derives the root from ai_gateway_url itself."""
        isolate_settings_and_catalogue.return_value = SimpleNamespace(
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
        mock_get_model_config.return_value = sample_model_configs["face-recognizer"]

        with pytest.raises(HTTPException) as exc_info:
            await model_management.load_model(model_name="face-recognizer")

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
        mock_get_model_config.return_value = sample_model_configs["yolo26-general"]

        with pytest.raises(HTTPException) as exc_info:
            await model_management.load_model(model_name="yolo26-general")

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
        mock_get_model_config.return_value = sample_model_configs["face-recognizer"]

        with pytest.raises(HTTPException) as exc_info:
            await model_management.reload_model(model_name="face-recognizer")

        assert exc_info.value.status_code == 501

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    async def test_reload_disabled_model_returns_400(
        self,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
    ) -> None:
        mock_get_model_config.return_value = sample_model_configs["yolo26-general"]

        with pytest.raises(HTTPException) as exc_info:
            await model_management.reload_model(model_name="yolo26-general")

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
        """used_mb sums registry estimates of the router-ready models of the lane."""
        mock_get_model_zoo.return_value = sample_model_configs
        assert SHIPPED_LIGHT_MEMBERS == model_management.LIGHT_MODELS, (
            "this file mirrors the shipped lane membership; the sums below "
            "are only meaningful while that mirror holds"
        )

        result = await model_management.get_vram_summary(http_client=healthy_client)

        assert isinstance(result, VramSummaryResponse)
        # One lane, exactly: the heavy row would report a 6800 MB budget
        # against a router that no longer mounts (R8 S3).
        assert len(result.gpus) == 1
        lane = result.gpus[0]
        assert (lane.gpu_id, lane.service) == (LANE_GPU_ID, LIGHT_SERVICE)
        assert lane.budget_mb == LANE_BUDGET_MB

        # threat is the lane's only ready member. The census is exact, so each
        # of the other three exclusions is pinned for its own reason: osnet is a
        # lane member whose Triton model (reid) is not ready, and yolo26 /
        # triton-pair-standin / the backend-process rows are not lane members at
        # all — yolo26 notwithstanding that the gateway root says it is ready,
        # because the lane row reads the ROUTER payload (see the probe pin).
        assert lane.loaded_models == ["threat-detection-yolov8n"]
        assert lane.used_mb == 300
        assert lane.available_mb == LANE_BUDGET_MB - 300
        assert lane.utilization_percent == 25.0

        # Totals are the sum of that one lane — no heavy budget is folded in.
        assert result.totals.budget_mb == LANE_BUDGET_MB
        assert result.totals.used_mb == 300
        assert result.totals.available_mb == 900
        assert result.totals.model_count == 1

        # The lane row is answered by router health alone (no root probe).
        assert probed_urls(healthy_client) == {f"{LIGHT_ROUTER_URL}/health"}

    @patch("backend.api.routes.model_management.get_model_zoo", autospec=True)
    async def test_vram_summary_with_routers_down(
        self,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        mock_enrichment_client: AsyncMock,
    ) -> None:
        """Unreachable routers report the one budget with zero usage."""
        mock_get_model_zoo.return_value = sample_model_configs
        mock_enrichment_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        result = await model_management.get_vram_summary(http_client=mock_enrichment_client)

        assert len(result.gpus) == 1
        assert result.totals.budget_mb == LANE_BUDGET_MB
        assert result.totals.used_mb == 0
        assert result.totals.available_mb == LANE_BUDGET_MB
        assert result.totals.model_count == 0


# =============================================================================
# Service Routing Tests
# =============================================================================


class TestServiceRouting:
    """Tests for model-to-router routing and labelling logic."""

    def test_routing_census_covers_both_sides_of_the_lane(self) -> None:
        """The census every routing pin loops is non-empty and two-sided."""
        assert ROUTING_CENSUS, "an empty census would make every loop below vacuous"
        assert ROUTING_CENSUS & SHIPPED_LIGHT_MEMBERS
        assert ROUTING_CENSUS - SHIPPED_LIGHT_MEMBERS
        assert SHIPPED_LIGHT_MEMBERS <= ROUTING_CENSUS

    def test_light_lane_membership_is_the_shipped_one_lane(self) -> None:
        """LIGHT_MODELS is the shipped membership; the retired lane members are gone."""
        assert model_management.LIGHT_MODELS == SHIPPED_LIGHT_MEMBERS
        # depth/pet/pose left with the enrichment tier in S2b and never came back
        assert (
            not {"yolov8n-pose", "pet-detector", "depth-estimator"} & model_management.LIGHT_MODELS
        )

    def test_every_model_routes_to_the_one_mounted_router(self) -> None:
        """get_service_for_model returns the only router for every name.

        Retargeted from the retired "heavy models route to the heavy router"
        pin. The shipped function is a probe-target lookup, not an ownership
        claim: with one mounted router it answers for light and non-light names
        alike, and a non-light name's readiness comes from the gateway root
        instead (see TestRootHealthReadiness).
        """
        assert ROUTING_CENSUS, "the loop below is vacuous on an empty census"
        for model_name in sorted(ROUTING_CENSUS):
            url = model_management.get_service_for_model(model_name)
            assert url == LIGHT_ROUTER_URL, f"{model_name} should route to the only mounted router"

    def test_get_router_urls_returns_the_single_router(self) -> None:
        """The probe fan-out is a one-entry tuple, not a heavy/light pair."""
        urls = model_management.get_router_urls()
        assert urls == (LIGHT_ROUTER_URL,)
        assert len(urls) == 1, "the heavy router's entry left with its settings field"

    def test_light_model_routes_to_enrichment_light_router(self) -> None:
        """Light-lane models are labelled with the router that serves them."""
        assert SHIPPED_LIGHT_MEMBERS, "the light set must not be empty"
        for model_name in sorted(SHIPPED_LIGHT_MEMBERS):
            label = model_management.get_service_name_for_model(model_name)
            assert label == LIGHT_SERVICE, f"{model_name} should be labelled {LIGHT_SERVICE}"

    def test_get_gpu_id_for_model(self) -> None:
        """Every model resolves to the one lane — the heavy lane's device is gone."""
        assert ROUTING_CENSUS, "the loop below is vacuous on an empty census"
        lanes = set()
        for model_name in sorted(ROUTING_CENSUS):
            gpu_id = model_management.get_gpu_id_for_model(model_name)
            assert gpu_id == LANE_GPU_ID, f"{model_name} should be on the only lane"
            lanes.add(gpu_id)
        assert lanes == {LANE_GPU_ID}, f"lane {RETIRED_LANE_GPU_ID} no longer exists"

    def test_service_labels_are_the_two_shipped_answers(self) -> None:
        """The label census is exactly the two surviving services."""
        assert ROUTING_CENSUS, "the loop below is vacuous on an empty census"
        # Both labels are reachable only if the census spans the lane boundary.
        assert ROUTING_CENSUS & model_management.LIGHT_MODELS
        assert ROUTING_CENSUS - model_management.LIGHT_MODELS
        labels = {model_management.get_service_name_for_model(name) for name in ROUTING_CENSUS}
        assert labels == set(SERVICE_LABELS), (
            "every name is labelled either by the router that serves it or by "
            "the gateway root that answers for it — nothing else"
        )
        assert RETIRED_HEAVY_SERVICE not in labels, RETIRED_HEAVY_SERVICE

    def test_router_urls_follow_gateway_mode(
        self, isolate_settings_and_catalogue: MagicMock
    ) -> None:
        """AI Gateway mode builds the one router URL from ai_gateway_url (client parity)."""
        isolate_settings_and_catalogue.return_value = SimpleNamespace(
            enrichment_light_url="http://stale:1/enrich-lt",
            ai_gateway_url="http://ai-gateway:8090/",
            use_ai_gateway=True,
        )
        assert model_management.get_router_urls() == ("http://ai-gateway:8090/enrich-lt",)


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
        # Serialized over HTTP: the two surviving service rows, both healthy.
        assert set(body["service_status"]) == set(SERVICE_LABELS)
        assert body["service_status"][LIGHT_SERVICE] == "healthy"
        assert body["service_status"][GATEWAY_SERVICE] == "healthy"

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
        config = sample_model_configs["yolo26"]
        with patch(
            "backend.api.routes.model_management.get_model_config",
            return_value=config,
            autospec=True,
        ):
            client = self._make_client(sample_model_configs, healthy_client)
            response = client.get("/api/system/models/yolo26/status")

        assert response.status_code == 200
        body = response.json()
        # Readiness the route read from the gateway ROOT payload (the router
        # payload never carries yolo26), serialized on the one lane.
        assert body["runtime"]["loaded"] is True
        assert body["service"] == GATEWAY_SERVICE
        assert body["gpu_id"] == LANE_GPU_ID

    def test_load_endpoint_returns_501(
        self,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        config = sample_model_configs["threat-detection-yolov8n"]
        with patch(
            "backend.api.routes.model_management.get_model_config",
            return_value=config,
            autospec=True,
        ):
            client = self._make_client(sample_model_configs, healthy_client)
            response = client.post("/api/system/models/threat-detection-yolov8n/load")

        assert response.status_code == 501
        assert "not supported" in response.json()["detail"].lower()

    def test_unload_endpoint_returns_501(
        self,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        config = sample_model_configs["threat-detection-yolov8n"]
        with patch(
            "backend.api.routes.model_management.get_model_config",
            return_value=config,
            autospec=True,
        ):
            client = self._make_client(sample_model_configs, healthy_client)
            response = client.post("/api/system/models/threat-detection-yolov8n/unload")

        assert response.status_code == 501

    def test_reload_endpoint_returns_501(
        self,
        sample_model_configs: dict[str, ModelConfig],
        healthy_client: AsyncMock,
    ) -> None:
        config = sample_model_configs["threat-detection-yolov8n"]
        with patch(
            "backend.api.routes.model_management.get_model_config",
            return_value=config,
            autospec=True,
        ):
            client = self._make_client(sample_model_configs, healthy_client)
            response = client.post("/api/system/models/threat-detection-yolov8n/reload")

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
        # The totals the endpoint serializes are the one surviving lane's.
        assert len(body["gpus"]) == 1
        assert body["gpus"][0]["service"] == LIGHT_SERVICE
        assert body["totals"]["budget_mb"] == LANE_BUDGET_MB
