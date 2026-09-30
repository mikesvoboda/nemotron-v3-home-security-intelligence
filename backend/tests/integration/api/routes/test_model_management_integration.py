"""Integration tests for Model Zoo Management API endpoints (NEM-4783).

Post-R8-S3 contract (2026-09-29). Two revisions of this file's premises are
gone: the standalone-enrichment proxy revision (dispatch on 8094/8096, GET
{service}/models/status, load/unload 200-with-freed_vram) and the TWO-LANE
revision that replaced it (heavy /enrichment + light /enrich-lt routers, a
gpu0 row budgeted at 6800 MB, a "ai-enrichment" service label, and
fashion-clip as the heavy-lane fixture).

Which slice killed what, measured rather than assumed -- this file entered S3
with ten reds and NOT all of them were S3's:

  * S2b (602379e2, "delete the legacy LLM + enrichment tier") removed the
    fashion-clip and weather-classification rows from models.yml. Verified:
    ``git show HEAD:models.yml`` holds zero matches for either name, and the
    backend registry is built solely from that file, so
    ``get_model_config("fashion-clip")`` could not have resolved at HEAD
    either. 8 of the 10 reds are those two names 404-ing (or the registry
    fixture returning None) -- i.e. they were already red before S3 started.
  * S3 then deleted what HEAD's model_management.py still had live:
    ``HEAVY_VRAM_BUDGET_MB = 6800``, the second lane in vram-summary, and
    ``return "ai-enrichment"`` as a service label (HEAD line 227). S3 also
    unmounted the heavy router, dropping /enrichment/health from the readiness
    fan-out, and swept ai/clip + ai/enrichment + ai/enrichment-light +
    ai/florence plus the nemotron-3-nano / florence-2-base / yolov8n-pose rows
    (owner rulings 1, 2, 4, 5 -- docs/plans/2026-09-28-r8-legacy-retirement-
    scope.md plus the docs/vss-integration ledger).

So exactly TWO of the ten reds are S3's -- ``len(gpus) == 2`` in vram-summary
and ``HEALTH_HEAVY in probed`` in the readiness fan-out. (The "ai-enrichment"
label assert is S3's too but was masked: it sat after the fashion-clip name
lookup in the same test, so the S2b death of that name failed first.) The
other eight were already red when this slice started. All ten are FIXTURE
deaths, not behavior deaths: the readiness rollup, the detail-status answer,
the VRAM-honesty claim and the 501 lifecycle contract are all LIVE machinery
that was being driven through enrichment-tier names. They are retargeted below
onto the surviving surface. The genuinely dead thing -- the heavy lane and its
service label -- is tombstoned in TestRetiredHeavyLane, which asserts absence
against LIVE forms (mounted routers, module attributes, the live catalogue, the
label function's answers over the live registry) and pins its own non-vacuity.

What ships (backend/api/routes/model_management.py, read at S3):
- Read endpoints (list / detail status / vram-summary) aggregate registry
  metadata with Triton readiness unioned across TWO live surfaces keyed by the
  triton_name values in the root models.yml catalogue:
    * the one mounted router: GET {router}/health -> /enrich-lt/health, which
      reports the KEPT threat/reid pair, and
    * the gateway root: GET {root}/health -> http://ai-gateway:8090/health,
      which iterates the ACTIVE residency set and answers any Triton name no
      router reports (that is how yolo26 is answered -- it is served through
      the gateway's own /detections router, so it is in no router payload).
  Backend-process models (no triton_name) are answered from ModelManager and
  probe nothing at all.
- Lifecycle endpoints (load / unload / reload / unload-all) return 501 with
  registry-validation precedence (404 unknown, then 400 disabled) and MUST NOT
  touch the network: Triton runs --model-control-mode=none and the gateway
  exposes no preload/unload surface. The http_client dependency factory is
  swapped for a tripwire that fails on ANY outbound call, so a "fixed"
  lifecycle route that starts POSTing to the gateway is caught here even
  though its 501 assertion would still pass.
- vram-summary reports the ONE lane's budget with readiness-derived registry
  estimates and never fabricates live VRAM figures.

Registry state (models.yml at repo root is catalogue truth; the backend
registry is that catalogue filtered to service backend|both AND a name in
model_zoo._LOADER_MAP -- measured, not assumed):
- osnet-ain-x1-0: the ONLY triton-mapped row in the live registry
  (triton_name "reid", lane member of model_management.LIGHT_MODELS, gpu_id 1).
  Its registry vram_mb is overridden by a fixture to a value found nowhere
  else, so the lane's used_mb proves the sum reads the catalogue estimate.
- paddleocr: backend-process row (no triton_name, preload false) -- the
  "answers from ModelManager, probes nothing" drive and the 501-for-a-backend-
  model drive.
- yolo26-general: disabled in the catalogue -- the 400-on-disabled fixture.
- fashion-clip / weather-classification: NOT here any more -- both left
  models.yml with S2b's enrichment-tier deletion, so the names 404 on every
  endpoint that validates against the registry. That absence is pinned in
  TestRetiredHeavyLane rather than relied on silently. (threat-detection-
  yolov8n keeps its catalogue row and stays a LIGHT_MODELS lane member, but it
  has no entry in model_zoo._LOADER_MAP, so it never reaches the BACKEND
  registry -- it is readiness-answered only through the router payload.)

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database
- client: httpx AsyncClient with test app
- mock_redis: Mock Redis client
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import yaml
from httpx import AsyncClient

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

# Router base URLs resolved from default settings. Post-S3 there is exactly
# one router (settings.enrichment_light_url already points at it) and the root
# is recovered by stripping ROUTER_SUFFIXES from it -- the egress assertions
# key on these two, and each test also asserts the live resolvers still
# produce them so a settings edit is caught instead of silently retargeting
# the probe.
HEALTH_LIGHT = "http://ai-gateway:8090/enrich-lt/health"
HEALTH_ROOT = "http://ai-gateway:8090/health"

# The heavy router's health URL, dead since S3. Named here ONLY as the string
# the probe fan-out must never produce again; a live probe of it would mean
# someone re-mounted the router this slice unmounted.
RETIRED_HEALTH_HEAVY = "http://ai-gateway:8090/enrichment/health"

# .../backend/tests/integration/api/routes/<this file> -> repo root is 5 up.
REPO_ROOT = Path(__file__).resolve().parents[5]

# osnet-ain-x1-0 registry estimate used by this file. The real models.yml value
# is 100, so lane used_mb pinning THIS number proves lane accounting reads the
# registry estimate rather than a live or hard-coded figure (see the
# vram-summary docstrings).
LANE_MODEL_VRAM_SENTINEL = 137

# Names that used to drive this file and no longer resolve in the live
# registry (both left models.yml in S2b, one commit before S3 -- see the module
# docstring). Every endpoint that validates against the registry answers 404
# for them; TestRetiredHeavyLane pins that rather than leaving it as a comment.
RETIRED_REGISTRY_NAMES = ("fashion-clip", "weather-classification")


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


def probed_urls(mock_http: AsyncMock) -> list[str]:
    """The URLs a mocked client was asked to GET, in call order."""
    return [call.args[0] for call in mock_http.get.call_args_list]


@pytest.fixture
def unreachble_gateway_client():
    """An http client whose every GET raises ConnectError.

    The degradation tests want "no ai-gateway is running" to be the INPUT, not
    an environmental accident. Left to itself this endpoint resolves
    http://ai-gateway:8090 for real, and what that yields depends on where the
    suite runs -- this sandbox's proxy answers HTTP 500, CI fails DNS. Both
    happen to land on the same degradation branch today, and neither is the
    contract. ConnectError is the branch, named.
    """

    async def _refused(*args: Any, **kwargs: Any) -> httpx.Response:
        raise httpx.ConnectError("no ai-gateway in this environment")

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(side_effect=_refused)
    return mock_http


@pytest.fixture
def fake_catalogue(tmp_path):
    """Point the route's models.yml lookup at a fake catalogue (lru_cache is
    keyed on nothing, so it must be cleared around the patch).

    Retargeted in S3: the rows here are SYNTHETIC names, deliberately absent
    from the real catalogue. That is what makes this fixture worth having --
    it can hold a triton name no live payload reports, which is how the
    "catalogue drift is logged, never hidden behind a silent not-ready" branch
    is driven. The real catalogue is single-source-of-truth and the HTTP
    drives below read it, not this file.
    """
    catalogue = tmp_path / "models.yml"
    catalogue.write_text(
        yaml.safe_dump(
            {
                "models": [
                    {"name": "lane-member", "triton_name": "reid"},
                    {"name": "drifted", "triton_name": "no_such_triton_model"},
                    {"name": "backend-process"},  # no triton_name
                ]
            }
        )
    )

    from backend.api.routes import model_management

    model_management._load_triton_name_map.cache_clear()
    with patch.object(model_management, "_MODELS_YML", catalogue):
        yield catalogue
    model_management._load_triton_name_map.cache_clear()


@pytest.fixture
def real_lane_model_config():
    """Real registry ModelConfig for the live lane member, estimate overridden.

    osnet-ain-x1-0 is the one registry row that is both triton-mapped and a
    member of model_management.LIGHT_MODELS, so it is the only row the
    vram-summary lane builder can ever list. The estimate is set to a value
    that cannot come from anywhere else so vram-summary assertions prove the
    registry-estimate basis; the real catalogue's vram_mb is deliberately not
    reused.
    """
    from backend.api.routes.model_management import LIGHT_MODELS
    from backend.services.model_zoo import get_model_config, get_model_zoo

    lane_rows = sorted(set(get_model_zoo()) & set(LIGHT_MODELS))
    assert lane_rows, (
        "no registry row is a member of LIGHT_MODELS; the lane builder iterates "
        "nothing and every vram-summary assertion below is vacuous"
    )
    assert "osnet-ain-x1-0" in lane_rows, f"lane membership moved: {lane_rows}"

    config = get_model_config("osnet-ain-x1-0")
    assert config is not None, "models.yml lost osnet-ain-x1-0 from the registry"
    original = config.vram_mb
    assert original != LANE_MODEL_VRAM_SENTINEL, (
        "the sentinel must be a value no real source holds, or used_mb proves nothing"
    )
    config.vram_mb = LANE_MODEL_VRAM_SENTINEL
    try:
        yield config
    finally:
        config.vram_mb = original


@pytest.fixture
def tripwire_http_client():
    """Async mock http client that fails the test on ANY outbound call.

    The lifecycle endpoints must answer purely from the registry -- a GET here
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
# Read Endpoints — degraded path with no ai-gateway reachable
# =============================================================================


class TestListModelsIntegration:
    """Integration tests for GET /api/system/models endpoint."""

    @pytest.mark.asyncio
    async def test_list_models_degrades_gracefully_without_gateway(
        self,
        client: AsyncClient,
        unreachble_gateway_client: AsyncMock,
    ) -> None:
        """No reachable ai-gateway -> registry data survives, every model
        reports unloaded, no surface is reported as up.

        Verifies:
        - Response includes EVERY registry row (the non-vacuity anchor: "all
          models report loaded=False" is trivially true over an empty list,
          which is the S2b compose-vacuity lesson this file keeps naming)
        - The Triton-mapped row and the backend-process rows alike report
          loaded=False -- a dead gateway is never answered with a fabricated up
        - Both service labels this endpoint can answer for report unhealthy,
          and the label set is exactly the two live ones
        """
        with override_http_client(unreachble_gateway_client):
            response = await client.get("/api/system/models")

        assert response.status_code == 200
        data = response.json()

        assert "models" in data
        assert "service_status" in data

        from backend.services.model_zoo import get_model_zoo

        registry = get_model_zoo()
        models = data["models"]
        assert len(models) == len(registry) == len({m["name"] for m in models}) > 0
        assert {m["name"] for m in models} == set(registry)

        by_name = {m["name"]: m for m in models}

        # The live Triton-mapped row: lane labels persist as router labels, and
        # an unreachable gateway answers "not loaded", never a guessed up.
        reid = by_name["osnet-ain-x1-0"]
        assert reid["runtime"]["loaded"] is False
        assert reid["runtime"]["actual_vram_mb"] is None
        assert reid["gpu_id"] == 1
        assert reid["service"] == "ai-enrichment-light"

        # A backend-process row (no triton_name): answered from ModelManager,
        # which has loaded nothing in this environment.
        ocr = by_name["paddleocr"]
        assert ocr["runtime"]["loaded"] is False
        assert ocr["service"] == "ai-gateway"

        # Both rows the aggregation actually measured report unreachable. Exact
        # equality, so a third fabricated row cannot slip through.
        assert data["service_status"] == {
            "ai-enrichment-light": "unhealthy",
            "ai-gateway": "unhealthy",
        }

    @pytest.mark.asyncio
    async def test_list_models_readiness_from_gateway_health_payloads(
        self,
        client: AsyncClient,
    ) -> None:
        """With gateway health mocked, readiness comes from the health payloads
        keyed by the models.yml triton names, probed at {root}/health and
        {router}/health -- and nothing else.

        Retargeted off fashion-clip / the heavy router in S3. Same claim, new
        fixture: osnet-ain-x1-0 -> triton "reid", which the /enrich-lt payload
        reports.

        Verifies:
        - GET goes to exactly the root and the one router's /health (never the
          retired /models/status, never the heavy router this slice unmounted)
        - A Triton name the payload reports ready makes the model loaded; a
          name reported not-ready does not
        - The readiness key is the triton_name, not the registry name
        - A model with no Triton mapping is answered from ModelManager, and the
          real catalogue's triton map is what keys it
        - The live URL resolvers still produce the two URLs this test pins
        """
        light = make_health({"reid": True, "threat": False})
        root = make_health({"yolo26": True})

        async def mock_get(url: str, *args: Any, **kwargs: Any) -> httpx.Response:
            if url == HEALTH_LIGHT:
                return httpx.Response(200, json=light)
            if url == HEALTH_ROOT:
                return httpx.Response(200, json=root)
            raise AssertionError(f"unexpected probe URL from list_models: {url}")

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=mock_get)

        with override_http_client(mock_http):
            response = await client.get("/api/system/models")

        assert response.status_code == 200
        data = response.json()

        by_name = {m["name"]: m for m in data["models"]}

        # Light router reported reid ready -> loaded. Triton exposes no
        # per-model VRAM over HTTP, so actual_vram_mb stays None.
        reid = by_name["osnet-ain-x1-0"]
        assert reid["runtime"]["loaded"] is True
        assert reid["runtime"]["actual_vram_mb"] is None

        # A backend-process row is ModelManager state, never a router's; the
        # mock above records no per-model probe because the route does not
        # issue one (the union below is fetched once for the whole list).
        assert by_name["paddleocr"]["runtime"]["loaded"] is False

        probed = probed_urls(mock_http)
        assert sorted(probed) == sorted([HEALTH_ROOT, HEALTH_LIGHT]), (
            f"readiness fan-out changed: {probed}"
        )
        assert RETIRED_HEALTH_HEAVY not in probed

        # The two URLs above are what the live resolvers produce; pinning them
        # as literals AND against the resolvers means a settings edit surfaces
        # here rather than turning this test into a probe of nothing.
        from backend.api.routes.model_management import (
            get_gateway_root_url,
            get_router_urls,
        )

        assert get_router_urls() == ("http://ai-gateway:8090/enrich-lt",)
        assert get_gateway_root_url() == "http://ai-gateway:8090"
        assert [f"{u}/health" for u in get_router_urls()] == [HEALTH_LIGHT]

        assert data["service_status"] == {
            "ai-enrichment-light": "healthy",
            "ai-gateway": "healthy",
        }

    @pytest.mark.asyncio
    async def test_list_models_not_ready_when_the_router_reports_it_false(
        self,
        client: AsyncClient,
    ) -> None:
        """The same lane member, the same endpoints, the opposite payload: a
        router that answers "reid: false" answers not-loaded.

        Kept separate from the ready case on purpose. The old pair of asserts
        (ready/not-ready) lived in one test whose fixture 404'd; split, a
        regression that only breaks the negative arm still shows up as one red
        test naming the arm, not as a lost assert.
        """
        light = make_health({"reid": False, "threat": True})
        root = make_health({"yolo26": True})

        async def mock_get(url: str, *args: Any, **kwargs: Any) -> httpx.Response:
            if url == HEALTH_LIGHT:
                return httpx.Response(200, json=light)
            if url == HEALTH_ROOT:
                return httpx.Response(200, json=root)
            raise AssertionError(f"unexpected probe URL from list_models: {url}")

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=mock_get)

        with override_http_client(mock_http):
            response = await client.get("/api/system/models")

        assert response.status_code == 200
        by_name = {m["name"]: m for m in response.json()["models"]}
        assert by_name["osnet-ain-x1-0"]["runtime"]["loaded"] is False
        # A healthy payload with a negative verdict is still a healthy surface:
        # the service rollup measures reachability, not model verdicts.
        assert response.json()["service_status"]["ai-enrichment-light"] == "healthy"

    def test_root_health_answers_a_name_the_router_does_not(self) -> None:
        """The union rule, pinned on the live helper.

        This claim used to be driven end-to-end through fashion-clip, which sat
        on the heavy router and was answered by the gateway ROOT payload. No
        registry row is root-only any more (osnet is the sole Triton-mapped row
        and the light router reports it), so the HTTP surface cannot express
        the rule -- but the rule is live and load-bearing: yolo26 is served
        through the gateway's own /detections router and appears in no router
        payload, so root-only readiness is the only way it is ever reported
        (model_management.py:422-469, list_models' fan-out at :622). Driven on
        _triton_ready directly, which is the shipped function.

        Non-vacuity: "root answers what the router omits" is trivially true if
        the union read only the FIRST payload, so the router-alone arm is
        asserted False for the same input. And because a name missing from
        every payload also reads False, the root-only-True arm above is the
        only thing distinguishing a union from a silent not-ready -- which is
        why it is the first assertion rather than a comment.
        """
        from backend.api.routes.model_management import _triton_ready

        root_only = make_health({"yolo26": True})
        router = make_health({"reid": True})

        # Root says ready, the router never names it -> ready.
        assert _triton_ready(("yolo26",), root_only, router) is True
        # The same call with NO root payload must be False: that is what makes
        # the line above a union and not a coincidence.
        assert _triton_ready(("yolo26",), None, router) is False
        # A name the router reports is answerable without the root at all.
        assert _triton_ready(("reid",), None, router) is True
        # Racing-probe rule: any reporting payload that says True wins, so a
        # stale False from the other surface must not mask it.
        assert _triton_ready(("reid",), make_health({"reid": False}), router) is True
        # ...and when every reporting payload says False, it is not ready.
        all_false = make_health({"reid": False})
        assert _triton_ready(("reid",), all_false, all_false) is False
        # A 1:many entry is ready only when ALL of its Triton names are.
        assert _triton_ready(("reid", "yolo26"), root_only, router) is True
        assert _triton_ready(("reid", "vanished"), root_only, router) is False

    @pytest.mark.usefixtures("fake_catalogue")
    def test_catalogue_drift_warns_instead_of_a_silent_not_ready(
        self,
        caplog,
    ) -> None:
        """models.yml names a Triton model the gateway does not report -> the
        gap is logged, not hidden behind a permanent not-loaded.

        Driven through the patched catalogue so the drifting row is real
        catalogue content rather than a synthetic argument: the fake's
        "no_such_triton_model" is to the readiness map what a pruned Triton dir
        is to the live catalogue. S3 retired the residency-mode excuse ("the
        gateway may not be running the wider set") -- there is no wider set
        left, so a name models.yml lists and the gateway does not answer IS
        drift (model_management.py:437-441).
        """
        from backend.api.routes.model_management import (
            _load_triton_name_map,
            _triton_ready,
        )

        triton_map = _load_triton_name_map()
        assert triton_map == {
            "lane-member": ("reid",),
            "drifted": ("no_such_triton_model",),
        }, "the patched catalogue did not take, so this test proves nothing"

        answering = make_health({"reid": True})
        with caplog.at_level(logging.WARNING, logger="backend.api.routes.model_management"):
            assert _triton_ready(triton_map["drifted"], None, answering) is False
        assert "'no_such_triton_model'" in caplog.text

        # Non-vacuity: with every surface unreachable the helper must NOT emit
        # per-model drift noise (the connectivity warning already fired) -- a
        # caplog assertion that passed because warnings always appear would be
        # pinning nothing.
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="backend.api.routes.model_management"):
            assert _triton_ready(triton_map["drifted"], None, None) is False
        assert "no gateway health payload" not in caplog.text


class TestModelStatusEndpoint:
    """Integration tests for GET /api/system/models/{name}/status endpoint."""

    @pytest.mark.asyncio
    async def test_get_model_status_returns_detailed_info(
        self,
        client: AsyncClient,
        unreachble_gateway_client: AsyncMock,
    ) -> None:
        """Detail status answers with registry fields even with no gateway
        reachable; a Triton-mapped model reports unloaded rather than a
        fabricated up.

        Retargeted from fashion-clip (row deleted by ruling 2) onto
        osnet-ain-x1-0, the live Triton-mapped row. Same assertions on the same
        shape: this arm is about the detail contract, not about CLIP.
        """
        with override_http_client(unreachble_gateway_client):
            response = await client.get("/api/system/models/osnet-ain-x1-0/status")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "osnet-ain-x1-0"
        assert data["category"] == "embedding"
        assert data["estimated_vram_mb"] > 0
        assert data["enabled"] is True
        assert data["service"] == "ai-enrichment-light"
        assert data["gpu_id"] == 1
        runtime = data["runtime"]
        assert runtime["loaded"] is False
        assert "actual_vram_mb" in runtime
        assert "last_used" in runtime
        assert "load_count" in runtime

    @pytest.mark.asyncio
    async def test_get_model_status_backend_model_skips_router(
        self,
        client: AsyncClient,
    ) -> None:
        """A model with no Triton mapping is answered from ModelManager only --
        no router AND no gateway root is probed for it.

        Retargeted from weather-classification (deleted with the enrichment
        tier) onto paddleocr: no triton_name in the live catalogue, preload
        false, so nothing in the shipped path loads it and ModelManager must
        still hold no instance of it here.
        """
        from backend.services.model_zoo import get_model_manager

        assert get_model_manager().is_loaded("paddleocr") is False, (
            "ModelManager holds paddleocr; the loaded-is-False arm below would be "
            "answering a different question than this test asks"
        )

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=AssertionError("gateway probed for backend model"))

        with override_http_client(mock_http):
            response = await client.get("/api/system/models/paddleocr/status")

        assert response.status_code == 200
        data = response.json()
        assert data["runtime"]["loaded"] is False
        # Zero egress: not "no router" but "no probe at all" -- the root probe
        # is skipped too, since a backend row has no Triton name to look up.
        assert mock_http.get.await_count == 0
        assert mock_http.mock_calls == []


class TestVramSummaryIntegration:
    """Integration tests for GET /api/system/models/vram-summary endpoint."""

    @pytest.mark.asyncio
    async def test_vram_summary_reports_budgets_without_fabricated_usage(
        self,
        client: AsyncClient,
        unreachble_gateway_client: AsyncMock,
    ) -> None:
        """With no gateway reachable, the one lane reports its budget and zero
        usage.

        Retargeted from two lanes to one. The claim is the honesty claim and it
        is unchanged: an unreachable router yields an EMPTY lane (zero models,
        zero MB), never a plausible-looking number and never a phantom lane.
        The gpu0/6800 arm that used to sit here is dead and is pinned dead in
        TestRetiredHeavyLane.
        """
        with override_http_client(unreachble_gateway_client):
            response = await client.get("/api/system/models/vram-summary")

        assert response.status_code == 200
        data = response.json()

        assert "gpus" in data
        assert "totals" in data

        gpus = data["gpus"]
        assert len(gpus) == 1  # the /enrich-lt lane, the only lane left

        lane = gpus[0]
        assert lane["gpu_id"] == 1
        assert lane["service"] == "ai-enrichment-light"
        assert lane["budget_mb"] == 1200
        assert lane["used_mb"] == 0
        assert lane["available_mb"] == 1200
        assert lane["loaded_models"] == []
        assert lane["utilization_percent"] == 0.0

        totals = data["totals"]
        assert totals["budget_mb"] == 1200
        assert totals["used_mb"] == 0
        assert totals["available_mb"] == 1200
        assert totals["model_count"] == 0

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("real_lane_model_config")
    async def test_vram_summary_sums_registry_estimates_of_ready_models(
        self,
        client: AsyncClient,
    ) -> None:
        """Ready models on the lane sum the registry vram_mb estimates (the
        retired VRAM-manager accounting is gone and Triton exposes no live
        per-model figure).

        Retargeted from fashion-clip/gpu0 onto osnet-ain-x1-0/gpu1. The edge
        that keeps this sharp is the sentinel: the estimate is overridden to a
        value no other source holds, so used_mb proves the lane reads the
        catalogue estimate rather than a live or hard-coded figure. (That
        sentinel cannot tell a readiness-aware lane builder from a
        readiness-blind one -- the single lane member makes both produce this
        output -- which is what
        test_vram_summary_excludes_models_the_payload_marks_not_ready is for.)
        """
        light = make_health({"reid": True, "threat": False})

        async def mock_get(url: str, *args: Any, **kwargs: Any) -> httpx.Response:
            if url == HEALTH_LIGHT:
                return httpx.Response(200, json=light)
            raise AssertionError(f"unexpected probe URL from vram-summary: {url}")

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=mock_get)

        with override_http_client(mock_http):
            response = await client.get("/api/system/models/vram-summary")

        assert response.status_code == 200
        data = response.json()

        lane = next(g for g in data["gpus"] if g["gpu_id"] == 1)
        assert lane["loaded_models"] == ["osnet-ain-x1-0"]
        # proves the registry-estimate basis, not a live/other figure
        assert lane["used_mb"] == LANE_MODEL_VRAM_SENTINEL
        assert lane["available_mb"] == 1200 - LANE_MODEL_VRAM_SENTINEL

        totals = data["totals"]
        assert totals["model_count"] == 1
        assert totals["used_mb"] == LANE_MODEL_VRAM_SENTINEL
        assert totals["budget_mb"] == 1200

        # vram-summary reads the ROUTER payload only (the lane builder is handed
        # the router's answer, model_management.py:871): no root probe here.
        assert probed_urls(mock_http) == [HEALTH_LIGHT]

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("real_lane_model_config")
    async def test_vram_summary_excludes_models_the_payload_marks_not_ready(
        self,
        client: AsyncClient,
    ) -> None:
        """The lane sums READY models, not lane members: the same live row,
        marked not-ready by the payload, contributes nothing.

        This arm exists because its absence would be invisible. With only one
        registry row in LIGHT_MODELS, a lane builder that listed lane members
        while ignoring the health verdict would produce exactly the same
        loaded_models/used_mb the test above pins -- so the ready-case
        assertion alone cannot tell "sums estimates of ready models" apart from
        "sums estimates of lane members". Same fixture, same lane, opposite
        payload: that is the only input pair which distinguishes them.
        """
        light = make_health({"reid": False, "threat": True})

        async def mock_get(url: str, *args: Any, **kwargs: Any) -> httpx.Response:
            if url == HEALTH_LIGHT:
                return httpx.Response(200, json=light)
            raise AssertionError(f"unexpected probe URL from vram-summary: {url}")

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=mock_get)

        with override_http_client(mock_http):
            response = await client.get("/api/system/models/vram-summary")

        assert response.status_code == 200
        data = response.json()
        lane = next(g for g in data["gpus"] if g["gpu_id"] == 1)
        assert lane["loaded_models"] == []
        assert lane["used_mb"] == 0
        assert lane["available_mb"] == lane["budget_mb"] == 1200
        assert data["totals"]["model_count"] == 0


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
    every route answers 501 and must not issue any outbound HTTP call.

    Retargeted in S3 from fashion-clip and weather-classification onto live
    registry names. The 501 itself never moved -- both fixtures simply stopped
    resolving, and a 404 masquerading as a passing 501 test is exactly the
    silent-green failure this class exists to prevent.
    """

    @pytest.mark.asyncio
    async def test_load_known_model_returns_501_without_egress(
        self,
        client: AsyncClient,
        tripwire_http_client: AsyncMock,
    ) -> None:
        with override_http_client(tripwire_http_client):
            response = await client.post("/api/system/models/osnet-ain-x1-0/load")

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
            response = await client.post("/api/system/models/osnet-ain-x1-0/unload")

        assert response.status_code == 501
        assert no_egress_recorded(tripwire_http_client)

    @pytest.mark.asyncio
    async def test_reload_known_model_returns_501_without_egress(
        self,
        client: AsyncClient,
        tripwire_http_client: AsyncMock,
    ) -> None:
        with override_http_client(tripwire_http_client):
            response = await client.post("/api/system/models/osnet-ain-x1-0/reload")

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
        """Backend-process models load lazily via ModelManager on first use --
        the HTTP surface still refuses with 501 (no eager-load path)."""
        with override_http_client(tripwire_http_client):
            response = await client.post("/api/system/models/paddleocr/load")

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


# =============================================================================
# Tombstone -- the heavy lane R8 S3 deleted
# =============================================================================


class TestRetiredHeavyLane:
    """The heavy serving lane is gone, and so is the label that named it.

    WHAT USED TO BE TRUE. Each arm says whether it was still LIVE code at HEAD
    (S3's own red) or already dead one commit earlier (an S2b red this slice
    inherited) -- conflating the two is how a slice gets credited or blamed for
    a failure it did not cause:

      * LIVE AT HEAD -- ``GET /api/system/models/vram-summary`` returned TWO
        entries in ``gpus``: gpu_id 0 / service "ai-enrichment" / budget_mb
        6800 and gpu_id 1 / "ai-enrichment-light" / 1200, with totals
        budget_mb 8000. HEAD's model_management.py:123 still read
        ``HEAVY_VRAM_BUDGET_MB = 6800`` and :842 still passed it to the lane
        builder, and this file's literal
        ``assert totals["budget_mb"] == 8000  # 6800 + 1200`` passed against
        it. S3's red.
      * LIVE AT HEAD -- ``GET /api/system/models`` returned a ``service_status``
        row keyed "ai-enrichment" (HEAD returned that literal from
        ``get_service_name_for_model``, line 227) and fanned out to
        ``GET {ai-gateway}/enrichment/health`` as one of two readiness probes.
        S3's reds.
      * ALREADY RED BEFORE S3 -- the arms that NAMED fashion-clip
        (``service="ai-enrichment"``, ``gpu_id=0``, readiness from the heavy
        payload). fashion-clip left models.yml in S2b (602379e2) and the
        backend registry is built only from that file, so those asserts could
        not have been passing at HEAD either. They are listed here because this
        file asserted them, not because S3 broke them.

    WHY IT DIED, AND WHICH RULING KILLED IT: the heavy router was the gateway's
    ``/enrichment`` mount, backed by ``ai/enrichment``. Owner ruling 4 of
    2026-09-29 ordered ALL retired serving dirs swept -- ``ai/florence``,
    ``ai/clip``, ``ai/enrichment``, ``ai/enrichment-light`` -- and ruling 5's
    prune to yolo26/reid/threat made the ``/enrichment`` router unbootable
    (its models were pruned), so the mount, the ``enrichment_url`` settings
    field, ``HEAVY_MODELS``, ``HEAVY_VRAM_BUDGET_MB`` and the router's
    ``/health`` answer all left in the same slice. Ruling 2 deleted that
    slice's models.yml rows -- nemotron-3-nano-30b-a3b-q4km, florence-2-base
    and yolov8n-pose (measured as the HEAD-minus-index name diff); the
    fashion-clip and weather-classification rows were ruling 2's S2b
    predecessors, not S3 edits. ``get_service_name_for_model`` no longer
    returns "ai-enrichment" at all: the module says why -- a card labelled with
    an unmounted router renders permanently unreachable, which is "a red
    assertion about nothing", the mirror of S2b's permanently-green compose
    pin.

    WHY THIS IS A TOMBSTONE AND NOT A RETARGET: the lanes above the read
    endpoints describe are still live, and they are still asserted (see
    TestVramSummaryIntegration). What is gone is the SECOND lane and its label.
    There is nothing left to retarget a two-lane topology onto -- the surviving
    answer to "how many lanes" is one, and it is pinned there. This class
    keeps the record and asserts the ABSENCE against live forms only: module
    attributes, the mounted-router list, the label function's answers over the
    live registry, and the live catalogue file's rows.

    NON-VACUITY, stated in code below: an absence scan over an empty or
    unrelated collection passes happily on nothing (the S2b compose lesson this
    repo keeps naming). Each arm here is anchored to a LIVE non-empty
    collection that must exist for the absence to mean anything -- the router
    tuple must hold exactly the light router, the registry must be non-empty
    AND contain a light-lane member AND contain a non-light row (otherwise the
    label scan would iterate a single decorative name), and the catalogue must
    still be a parsed list of rows. A "restored provenance" edit that puts the
    heavy lane back fails this class.
    """

    def test_heavy_lane_config_is_not_reachable_from_the_route(self) -> None:
        """The heavy lane's config symbols are gone from the live module.

        Asserted as attribute absence on the imported module -- a live form.
        Comments naming them (the module has several, to explain the deletion)
        cannot fail or satisfy this, by design.
        """
        from backend.api.routes import model_management as mm

        assert not hasattr(mm, "HEAVY_MODELS"), (
            "HEAVY_MODELS is back; it was the heavy lane's membership set and the "
            "lane has no router to be a member of"
        )
        assert not hasattr(mm, "HEAVY_VRAM_BUDGET_MB"), (
            "a 6800 MB budget restored would fund nothing -- the router it budgeted is unmounted"
        )
        # The one lane's config IS present, or the two absences above would be
        # the trivial "module is empty" reading.
        assert mm.LIGHT_VRAM_BUDGET_MB == 1200
        assert mm._GPU_LANE_ID == 1
        assert set(mm.LIGHT_MODELS) == {"threat-detection-yolov8n", "osnet-ain-x1-0"}

    def test_only_the_light_router_is_mounted(self) -> None:
        """The readiness fan-out reaches one router, no heavy URL, and the
        settings field that fed the heavy URL is gone.

        Non-vacuity: the tuple must be exactly the light router -- an empty
        tuple would make "no heavy router is probed" true for the wrong reason.
        And the surviving field must still be there: asserting "enrichment_url
        is not a settings field" proves nothing if enrichment_light_url left
        with it, which is why BOTH are checked.
        """
        from backend.api.routes.model_management import (
            ROUTER_SUFFIXES,
            get_gateway_root_url,
            get_router_urls,
        )
        from backend.core.config import Settings

        routers = get_router_urls()
        assert routers == ("http://ai-gateway:8090/enrich-lt",)
        assert not any(url.endswith("/enrichment") for url in routers), routers
        assert "/enrichment" not in ROUTER_SUFFIXES
        assert ROUTER_SUFFIXES == ("/enrich-lt",)
        # Root derivation still works off the one router -- if it returned None
        # the root readiness probe would silently stop, which is how a union
        # rule dies without any test turning red.
        assert get_gateway_root_url() == "http://ai-gateway:8090"
        # config.py:1490-1501 -- the field that supplied the heavy router's URL
        # at HEAD (``return settings.enrichment_url, settings.enrichment_light_url``)
        # was deleted with the router; the light field survives.
        assert "enrichment_url" not in Settings.model_fields
        assert "enrichment_light_url" in Settings.model_fields

    def test_ai_enrichment_is_not_an_available_service_label(self) -> None:
        """No live registry row is labelled "ai-enrichment" any more.

        Driven over the LIVE registry (every row the list endpoint can emit),
        so the scan iterates what ships. Non-vacuity: the row set must be
        non-empty, must include a light-lane member, and must include a row
        OUTSIDE the lane -- otherwise this would be one decorative iteration.
        """
        from backend.api.routes.model_management import (
            LIGHT_MODELS,
            get_service_name_for_model,
        )
        from backend.services.model_zoo import get_model_zoo

        registry = get_model_zoo()
        assert registry, "live registry empty: the label scan below proves nothing"
        assert set(registry) & set(LIGHT_MODELS), (
            "no registry row is in LIGHT_MODELS; the lane split this pins is gone"
        )
        assert set(registry) - set(LIGHT_MODELS), (
            "every registry row is in the lane; the non-lane label is untested"
        )

        labels = {get_service_name_for_model(name) for name in registry}
        assert "ai-enrichment" not in labels, labels
        assert labels == {"ai-enrichment-light", "ai-gateway"}, labels

    @pytest.mark.asyncio
    async def test_retired_models_404_on_every_registry_validating_endpoint(
        self,
        client: AsyncClient,
    ) -> None:
        """fashion-clip and weather-classification are not registry rows, so
        detail-status answers 404 and load answers 404 -- NOT the 501 they used
        to earn.

        The hazard this pins forward: a 501-shaped lifecycle test whose model
        name has left the registry goes red as 404 (loud, good); a 404-shaped
        test whose model name has left the registry stays green forever
        (silent, the bad one). That is why this class asserts the dead names by
        name instead of letting the retargeted tests above imply it.

        Non-vacuity: the SAME client must answer 200/501 for the live rows the
        retargeted tests now drive -- otherwise "404 for everything" would look
        like a retirement pin when it is a broken route.
        """
        for name in RETIRED_REGISTRY_NAMES:
            detail = await client.get(f"/api/system/models/{name}/status")
            assert detail.status_code == 404, f"{name} still resolves"
            load = await client.post(f"/api/system/models/{name}/load")
            assert load.status_code == 404, f"{name} still loads"

        # The mirror arm: live names do NOT 404, so the loop above is a
        # retirement signal and not a route outage.
        assert (await client.get("/api/system/models/osnet-ain-x1-0/status")).status_code == 200
        assert (await client.get("/api/system/models/paddleocr/status")).status_code == 200

    def test_live_catalogue_has_no_rows_for_the_pruned_models(self) -> None:
        """models.yml carries no row for the pruned models -- the three S3
        deletions (nemotron-3-nano-30b-a3b-q4km, florence-2-base,
        yolov8n-pose) and the two S2b ones this file used to drive
        (fashion-clip, weather-classification).

        Ruling 2 chose deletion over ``enabled: false``, so provenance is git +
        the ledger, not the file. Read as PARSED YAML names (a live form),
        never as text: models.yml:72-73 names florence-2-base and yolov8n-pose
        in prose to explain their deletion, so a text grep would read that
        tombstone as a violation -- and conversely a grep for fashion-clip
        passes today only because that file happens not to comment on it. Name
        extraction from the parse is the method that is correct for both.

        Non-vacuity: the parse must yield a non-empty catalogue that still
        contains the KEPT names -- an empty or truncated models.yml would make
        every absence below pass.
        """
        catalogue_path = REPO_ROOT / "models.yml"
        assert catalogue_path.exists(), f"{catalogue_path} moved; this pin reads nothing"
        rows = yaml.safe_load(catalogue_path.read_text())["models"]
        names = {row["name"] for row in rows}
        assert names, "catalogue parsed to zero rows; the absences below are theatre"
        assert {"osnet-ain-x1-0", "threat-detection-yolov8n", "yolo26"} <= names, names
        for gone in (
            "nemotron-3-nano-30b-a3b-q4km",
            "florence-2-base",
            "yolov8n-pose",
            "fashion-clip",
            "weather-classification",
        ):
            assert gone not in names, f"{gone} is back in models.yml"

    def test_pruned_serving_dirs_are_off_disk(self) -> None:
        """``ai/clip``, ``ai/enrichment``, ``ai/enrichment-light`` and
        ``ai/florence`` are not on disk, and importing their modules raises.

        Both live forms: a filesystem check and an import failure. Ruling 4
        swept them via ``git rm``, so a reintroduced directory (a revert, a
        "helpful" restore) trips this.

        Non-vacuity: ``ai/`` must exist and still ship the gateway -- the
        sibling that survived the prune -- so "these four are gone" is not
        "the whole tree is gone" wearing a costume.
        """
        import importlib

        ai_root = REPO_ROOT / "ai"
        assert ai_root.is_dir(), "ai/ is gone entirely; the absences below prove nothing"
        assert (ai_root / "gateway").is_dir(), "ai/gateway must survive the prune"

        for dead in ("clip", "enrichment", "enrichment-light", "florence"):
            assert not (ai_root / dead).exists(), f"ai/{dead} is back on disk"

        for module in ("ai.clip.model", "ai.enrichment.model", "ai.enrichment_light.model"):
            with pytest.raises(ModuleNotFoundError):
                importlib.import_module(module)
