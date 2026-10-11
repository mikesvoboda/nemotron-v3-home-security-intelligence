"""Unit tests for the AI Gateway FastAPI application.

Tests the top-level endpoints and configuration defined in ai/gateway/main.py:
- GET /health         - aggregated health across the active Triton models
- GET /metrics        - merged Prometheus + Triton metrics
- CORS middleware     - allowed origins / methods
- Lifespan            - startup connectivity check and shutdown cleanup
- Router mounting     - adapter prefixes are reachable

All Triton and adapter internals are mocked so the tests run purely on CPU
with no real Triton server.

R8 S3 (2026-09-29, owner rulings 1/3/4/5) swept the clip, florence and heavy
enrichment adapters, and this suite's pins over those three prefixes retired
with them BY DELETION rather than by a re-litigating tombstone here: the
historical record for that retirement lives in exactly one place,
``backend/tests/unit/test_r8_s3_florence_provider_retirement.py``
(``TestFlorenceProviderRowRetired.test_adapter_module_is_gone`` and
``test_gateway_main_no_longer_mounts_florence``,
``TestTritonRepositoryPruned.test_adapters_whose_models_are_all_pruned_retire_with_them``,
``test_clip_the_debug_endpoint_retires_with_the_prune``). A second copy of
"the route is gone" in the tier that owned the route would be a pin with no
owner.

What was RETARGETED instead is the gateway-level property those deleted tests
pinned, because that property does not die with a model:
* prefix reachability + a ``status`` field on an adapter health route
  -> the two mounts main.py still performs (/yolo26, /enrich-lt), discovered
  from the live route table rather than remembered;
* "a route taking a JSON body with a base64 image answers inference through
  the mounted app and the mocked Triton seam, in its product shape"
  -> the light adapter's JSON-body inference routes (multipart uploads were
  already pinned by the /yolo26 detect tests, and stay pinned there);
* "an adapter health payload reports all-ready as healthy with a models map"
  -> the light adapter's health route, over the probe set it actually builds.
"""

from __future__ import annotations

import contextlib
import io
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# The single patch target: every call to get_triton_client() in the gateway
# ultimately resolves to the module-level function in ai.gateway.triton_client.
_PATCH_TARGET = "ai.gateway.triton_client.get_triton_client"

# Each adapter module imports get_triton_client at the top level, creating a
# local binding, so an adapter-level patch is still needed per surviving module.
# R8 S3: this list is exactly the adapter modules ai/gateway/adapters ships
# (measured: yolo26.py + enrichment_light.py). The three entries naming the
# swept modules are gone, because patch() resolves its target eagerly — a dead
# module name is an AttributeError out of the fixture, which is how 29 tests in
# this file and test_metrics_middleware.py were erroring at setup. The list is
# a patch-target list, not evidence: it stays explicit, and
# TestPatchSurface below pins that it covers every live adapter binding.
_ADAPTER_PATCH_TARGETS = [
    "ai.gateway.adapters.yolo26.get_triton_client",
    "ai.gateway.adapters.enrichment_light.get_triton_client",
]


def _make_test_image_bytes(width: int = 64, height: int = 64) -> bytes:
    """Create a small JPEG image as raw bytes for multipart uploads."""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_b64_image(width: int = 224, height: int = 224) -> str:
    """Create a small PNG image encoded as base64 (JSON-body routes)."""
    import base64

    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _make_mock_triton_client(
    server_ready: bool = True,
    all_models_ready: bool = True,
) -> MagicMock:
    """Build a MagicMock that quacks like TritonClient."""
    mock = MagicMock()
    mock.is_server_ready = AsyncMock(return_value=server_ready)
    mock.is_model_ready = AsyncMock(return_value=all_models_ready)
    mock.close = AsyncMock()
    mock.get_model_metadata = AsyncMock(
        return_value={
            "name": "yolo26",
            "versions": ["1"],
            "platform": "tensorrt_plan",
            "inputs": [{"name": "images", "datatype": "FP32", "shape": [1, 3, 640, 640]}],
            "outputs": [{"name": "output0", "datatype": "FP32", "shape": [1, 84, 8400]}],
        }
    )
    # Default infer returns an empty-ish detection array (no detections).
    # Every key here is read by a module that ships, by name:
    #   "output0"   adapters/yolo26.py:370/:420/:495 and adapters/
    #               enrichment_light.py:153 both index it after requesting
    #               outputs=["output0"];
    #   "embedding" adapters/enrichment_light.py:200 indexes it after
    #               requesting outputs=["embedding"].
    # The pre-S3 default also carried "result", "pooler_output", "OUTPUT_*" and
    # "text_embedding". Their only readers were the swept adapters' handlers,
    # so those keys were a mock describing a surface no shipped code reads —
    # kept alive by a comment that justified them with files the slice deleted.
    mock.infer = AsyncMock(
        return_value={
            "output0": np.zeros((1, 84, 8400), dtype=np.float32),
            "embedding": np.zeros((1, 512), dtype=np.float32),
        }
    )
    return mock


def _patch_all_get_triton_client(mock_tc: MagicMock):
    """Return a combined context manager that patches get_triton_client everywhere."""

    @contextlib.contextmanager
    def _combined():
        with patch(_PATCH_TARGET, return_value=mock_tc):
            patches = [patch(t, return_value=mock_tc) for t in _ADAPTER_PATCH_TARGETS]
            for p in patches:
                p.start()
            try:
                yield mock_tc
            finally:
                for p in patches:
                    p.stop()

    return _combined()


def _live_adapter_prefixes() -> set[str]:
    """Adapter prefixes the app actually mounts, read from the live route table.

    ``app.openapi()["paths"]`` is generated from the routers mounted on ``app``,
    so a prefix appears here only if ``include_router`` ran. Two-segment paths
    are adapter routes; ``/health`` and ``/metrics`` are the app's own top-level
    endpoints and have no tail segment.
    """
    from ai.gateway.main import app

    prefixes: set[str] = set()
    for path in app.openapi()["paths"]:
        head, _, tail = path.lstrip("/").partition("/")
        if tail:
            prefixes.add(f"/{head}")
    return prefixes


@pytest.fixture(autouse=True)
def _reset_triton_singleton() -> None:
    """Ensure the triton_client singleton is reset between tests."""
    import ai.gateway.triton_client as tc_mod

    tc_mod._client = None


@pytest.fixture
def mock_triton() -> MagicMock:
    """Provide a mock TritonClient."""
    return _make_mock_triton_client()


@pytest.fixture
async def client(mock_triton: MagicMock) -> AsyncClient:
    """Yield an httpx AsyncClient wired to the gateway app.

    Patches get_triton_client at every import site so no real Triton
    connectivity is needed.
    """
    with _patch_all_get_triton_client(mock_triton):
        from ai.gateway.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


# ---------------------------------------------------------------------------
# The patch seam itself
# ---------------------------------------------------------------------------


class TestPatchSurface:
    """The fixture's patch list must match the adapters that ship.

    Not decoration: a stale entry raises AttributeError at fixture setup (the
    pre-S3 state, 29 errors), and a MISSING entry is worse and silent — that
    adapter would keep talking to a real TritonClient during the test.
    """

    def test_targets_cover_every_shipped_adapter(self) -> None:
        import importlib
        import pkgutil

        import ai.gateway.adapters as adapters_pkg

        live_modules = {
            info.name for info in pkgutil.iter_modules(adapters_pkg.__path__) if not info.ispkg
        }
        # Non-vacuity: the scan sees the modules, so a missing target is a real
        # miss rather than an empty-set equality.
        assert {"yolo26", "enrichment_light"} <= live_modules, sorted(live_modules)

        targeted: set[str] = set()
        for target in _ADAPTER_PATCH_TARGETS:
            module_name, _, attr = target.rpartition(".")
            assert attr == "get_triton_client", target
            module = importlib.import_module(module_name)
            targeted.add(module.__name__.rpartition(".")[2])
            assert hasattr(module, attr), target

        assert targeted == live_modules, (
            f"_ADAPTER_PATCH_TARGETS covers {sorted(targeted)}, adapters ship "
            f"{sorted(live_modules)} — an untargeted adapter reaches real gRPC"
        )


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Tests for the aggregated health check."""

    async def test_healthy_when_all_models_ready(self, client: AsyncClient) -> None:
        """Returns 'healthy' when server and all models report ready."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["triton_server_ready"] is True
        assert body["models_total"] > 0
        assert body["models_loaded"] == body["models_total"]

    async def test_degraded_when_server_not_ready(self, mock_triton: MagicMock) -> None:
        """Returns 'degraded' when Triton server itself is not ready."""
        mock_triton.is_server_ready = AsyncMock(return_value=False)

        with _patch_all_get_triton_client(mock_triton):
            from ai.gateway.main import app

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
                resp = await ac.get("/health")

        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"
        assert resp.json()["triton_server_ready"] is False

    async def test_degraded_when_some_models_not_ready(self, mock_triton: MagicMock) -> None:
        """Returns 'degraded' when at least one model is not loaded."""
        call_count = 0

        async def model_ready_some(name: str) -> bool:
            nonlocal call_count
            call_count += 1
            # First model returns False, rest True
            return call_count != 1

        mock_triton.is_model_ready = model_ready_some

        with _patch_all_get_triton_client(mock_triton):
            from ai.gateway.main import app

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
                resp = await ac.get("/health")

        body = resp.json()
        assert body["status"] == "degraded"
        assert body["models_loaded"] < body["models_total"]

    async def test_health_response_schema(self, client: AsyncClient) -> None:
        """The health response contains all expected fields."""
        resp = await client.get("/health")
        body = resp.json()
        assert "status" in body
        assert "triton_server_ready" in body
        assert "models" in body
        assert isinstance(body["models"], dict)
        assert "models_loaded" in body
        assert "models_total" in body


# ---------------------------------------------------------------------------
# GET /metrics
# ---------------------------------------------------------------------------


class TestMetricsEndpoint:
    """Tests for the Prometheus metrics scrape endpoint."""

    async def test_metrics_returns_text(self, client: AsyncClient) -> None:
        """Metrics endpoint returns plain text."""
        with patch("ai.gateway.main.httpx.AsyncClient") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "# HELP nv_inference_count Total inference count\n"

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(
                return_value=MagicMock(get=AsyncMock(return_value=mock_resp))
            )
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_ctx

            resp = await client.get("/metrics")

        assert resp.status_code == 200
        assert "text/plain" in resp.headers.get("content-type", "")

    async def test_metrics_when_triton_unavailable(self, client: AsyncClient) -> None:
        """Metrics still returns 200 even if Triton metrics endpoint is down."""
        with patch("ai.gateway.main.httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(
                return_value=MagicMock(get=AsyncMock(side_effect=Exception("connection refused")))
            )
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_ctx

            resp = await client.get("/metrics")

        assert resp.status_code == 200
        # Should contain a comment about unavailability
        assert "unavailable" in resp.text.lower() or len(resp.text) > 0


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


class TestCORSConfiguration:
    """Verify CORS headers are set for allowed origins."""

    async def test_cors_allows_localhost_8000(self, client: AsyncClient) -> None:
        """Preflight from http://localhost:8000 is allowed."""
        resp = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers

    async def test_cors_allows_127_0_0_1_8000(self, client: AsyncClient) -> None:
        """Preflight from http://127.0.0.1:8000 is allowed."""
        resp = await client.options(
            "/health",
            headers={
                "Origin": "http://127.0.0.1:8000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers

    async def test_cors_rejects_unknown_origin(self, client: AsyncClient) -> None:
        """Preflight from an unknown origin does not get allow-origin header."""
        resp = await client.options(
            "/health",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") != "http://evil.example.com"


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


class TestLifespan:
    """Tests for application startup and shutdown lifecycle.

    httpx's ASGITransport does not trigger ASGI lifespan events, so we
    test the lifespan context manager directly.
    """

    async def test_lifespan_startup_waits_for_triton(self) -> None:
        """Startup retries until the Triton server becomes ready."""
        mock_tc = _make_mock_triton_client(server_ready=False)
        call_count = 0

        async def eventually_ready() -> bool:
            nonlocal call_count
            call_count += 1
            return call_count >= 3

        mock_tc.is_server_ready = eventually_ready

        with _patch_all_get_triton_client(mock_tc), patch("asyncio.sleep", new_callable=AsyncMock):
            from ai.gateway.main import app, lifespan

            async with lifespan(app):
                pass

        # is_server_ready was called at least 3 times during startup
        assert call_count >= 3

    async def test_lifespan_shutdown_closes_client(self) -> None:
        """Shutdown calls triton.close()."""
        mock_tc = _make_mock_triton_client()

        with _patch_all_get_triton_client(mock_tc):
            from ai.gateway.main import app, lifespan

            async with lifespan(app):
                pass

        # After context exit, close should have been called
        mock_tc.close.assert_awaited()

    async def test_lifespan_logs_loaded_models(self) -> None:
        """Startup checks each model and classifies as loaded or not."""
        mock_tc = _make_mock_triton_client()
        model_names_checked: list[str] = []

        original_is_model_ready = mock_tc.is_model_ready

        async def track_model_ready(name: str) -> bool:
            model_names_checked.append(name)
            return await original_is_model_ready(name)

        mock_tc.is_model_ready = track_model_ready

        with _patch_all_get_triton_client(mock_tc):
            from ai.gateway.main import ACTIVE_MODELS, app, lifespan

            async with lifespan(app):
                pass

        # Every model the ACTIVE residency set serves should have been checked
        assert model_names_checked == list(ACTIVE_MODELS)
        # Non-vacuity: the active set this tier boots under is not empty, so
        # the equality above is a real coverage statement.
        assert len(ACTIVE_MODELS) >= 2

    async def test_lifespan_checks_the_active_residency_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rev 6 residency: with the vlm set active, startup checks ONLY its
        models — logging the retired models `not_loaded` on every start would
        be a permanent false alarm, and /health over them is false-degraded.

        Patched at the module attribute (the boot-time fact main.py binds at
        import), not by importlib.reload: reloading main.py re-registers its
        Prometheus metrics and dies on DuplicateTimeseries."""
        mock_tc = _make_mock_triton_client()
        checked: list[str] = []

        async def track(name: str) -> bool:
            checked.append(name)
            return True

        mock_tc.is_model_ready = track
        import ai.gateway.main as main_mod

        monkeypatch.setattr(main_mod, "ACTIVE_MODELS", ("yolo26", "reid"))
        with _patch_all_get_triton_client(mock_tc):
            async with main_mod.lifespan(main_mod.app):
                pass
        assert checked == ["yolo26", "reid"]

    async def test_health_over_vlm_set_is_not_degraded_by_retired_models(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """/health models map covers the ACTIVE set only; a vlm-mode gateway
        reports healthy with a full 2/2, not degraded 2/14."""
        import ai.gateway.main as main_mod

        active = ("yolo26", "reid")
        monkeypatch.setattr(main_mod, "ACTIVE_MODELS", active)
        mock_tc = _make_mock_triton_client()
        with _patch_all_get_triton_client(mock_tc):
            transport = ASGITransport(app=main_mod.app)
            async with AsyncClient(transport=transport, base_url="http://t") as ac:
                resp = await ac.get("/health")
        body = resp.json()
        assert body["status"] == "healthy"
        assert set(body["models"]) == set(active)
        # Derived from the set the monkeypatch installed, not a remembered 2.
        assert body["models_total"] == len(active)
        assert body["models_loaded"] == len(active)

    async def test_lifespan_handles_server_never_ready(self) -> None:
        """Startup completes even if Triton never becomes ready."""
        mock_tc = _make_mock_triton_client(server_ready=False)
        mock_tc.is_server_ready = AsyncMock(return_value=False)

        with _patch_all_get_triton_client(mock_tc), patch("asyncio.sleep", new_callable=AsyncMock):
            from ai.gateway.main import app, lifespan

            # Should not raise even if server never becomes ready
            async with lifespan(app):
                pass

        # close should still be called on shutdown
        mock_tc.close.assert_awaited()


# ---------------------------------------------------------------------------
# Adapter routes are mounted
# ---------------------------------------------------------------------------


class TestRouterMounting:
    """Verify that adapter routers are mounted at expected prefixes.

    Pre-S3 this class probed five prefixes. Three of them (the clip, florence
    and heavy-enrichment mounts) died with their adapters, and the per-prefix
    tests were deleted rather than tombstoned — the guard file owns that record
    (module docstring). What they pinned collectively, "every mount answers
    /health with a status field", is retargeted onto the whole LIVE mount set:
    the prefixes are derived from the live route table, so the test covers
    today's mounts and would follow a future one instead of remembering five.
    """

    async def test_yolo26_health(self, client: AsyncClient) -> None:
        """GET /yolo26/health is reachable."""
        resp = await client.get("/yolo26/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert body["model"] == "yolo26"

    async def test_enrichment_light_health(self, client: AsyncClient) -> None:
        """GET /enrich-lt/health is reachable."""
        resp = await client.get("/enrich-lt/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body

    async def test_every_live_mount_answers_health(self, client: AsyncClient) -> None:
        """Prefix reachability + response shape, over the derived mount set."""
        prefixes = _live_adapter_prefixes()
        # Non-vacuity: if the derived set were empty the loop would prove nothing.
        assert len(prefixes) >= 2, f"derived mount set {sorted(prefixes)}"
        for prefix in sorted(prefixes):
            resp = await client.get(f"{prefix}/health")
            assert resp.status_code == 200, prefix
            assert "status" in resp.json(), prefix

    async def test_live_mounts_are_the_two_shipped_adapters(self) -> None:
        """The mount set itself, as a SET EQUALITY (main.py:272-273).

        Equality is the whole claim: it says these two are mounted AND that
        nothing else is, so the retired prefixes need no separate "…is gone"
        assertion in this file. Their deadness is the S3 guard's record (module
        docstring), and a second copy here would be a pin with no owner.
        """
        assert _live_adapter_prefixes() == {"/yolo26", "/enrich-lt"}


# ---------------------------------------------------------------------------
# Adapter endpoint smoke tests (mocked inference)
# ---------------------------------------------------------------------------


class TestYolo26Detect:
    """Smoke tests for YOLO26 detection via the gateway."""

    async def test_detect_returns_200(self, client: AsyncClient) -> None:
        """POST /yolo26/detect with a valid image returns 200."""
        image_bytes = _make_test_image_bytes()
        resp = await client.post(
            "/yolo26/detect",
            files={"file": ("test.jpg", image_bytes, "image/jpeg")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "detections" in body
        assert "image_width" in body
        assert "image_height" in body
        assert "inference_time_ms" in body

    async def test_detect_triton_failure_returns_503(self, mock_triton: MagicMock) -> None:
        """When Triton inference fails, the endpoint returns 503."""
        from ai.gateway.triton_client import TritonClientError

        mock_triton.infer = AsyncMock(side_effect=TritonClientError("GPU error"))

        with _patch_all_get_triton_client(mock_triton):
            from ai.gateway.main import app

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
                image_bytes = _make_test_image_bytes()
                resp = await ac.post(
                    "/yolo26/detect",
                    files={"file": ("test.jpg", image_bytes, "image/jpeg")},
                )

        assert resp.status_code == 503


class TestJsonBodyInferenceRoutes:
    """JSON-body inference through the mounted app — retargeted.

    Old subjects: the /clip/embed smoke (base64 image in a JSON body,
    ``embedding`` + ``inference_time_ms`` out) and the /florence/extract smoke
    (image + prompt in, ``result`` + ``prompt_used`` out). Both routes died with
    their models in the Triton prune, and their absence is pinned by the guard
    file, so they are not re-pinned here.

    What transfers is the gateway-level property neither the /yolo26 multipart
    tests nor the adapter-tier tests cover on their own: a route mounted under
    an adapter prefix that takes a **JSON body with a base64 image** still
    reaches Triton through the gateway's middleware/mount stack and answers in
    its shipped response shape. The light adapter's two survivors are the live
    carriers of that property; the ``prompt_used`` echo had no heir, because no
    surviving gateway route takes a text prompt.
    """

    async def test_threat_detect_json_body_answers_in_product_shape(
        self, client: AsyncClient, mock_triton: MagicMock
    ) -> None:
        """POST /enrich-lt/threat-detect: JSON base64 in, ThreatResponse out."""
        output = np.zeros((1, 8, 8400), dtype=np.float32)
        output[0, 0, 0] = 55.0  # cx
        output[0, 1, 0] = 110.0  # cy
        output[0, 2, 0] = 90.0  # w
        output[0, 3, 0] = 180.0  # h
        output[0, 4, 0] = 0.92  # class 0 (knife) score
        mock_triton.infer = AsyncMock(return_value={"output0": output})

        resp = await client.post("/enrich-lt/threat-detect", json={"image": _make_b64_image()})

        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {
            "threats_detected",
            "is_threat",
            "max_confidence",
            "inference_time_ms",
        }
        assert body["is_threat"] is True
        assert body["threats_detected"][0]["class"] == "knife"
        # The Triton seam really was called with the resident threat model.
        assert mock_triton.infer.await_args.kwargs["model_name"] == "threat"

    async def test_person_reid_json_body_returns_normalized_vector(
        self, client: AsyncClient, mock_triton: MagicMock
    ) -> None:
        """POST /enrich-lt/person-reid: JSON base64 in, unit-norm embedding out."""
        import math

        raw = np.random.default_rng(7).standard_normal((1, 512)).astype(np.float32)
        mock_triton.infer = AsyncMock(return_value={"embedding": raw})

        resp = await client.post("/enrich-lt/person-reid", json={"image": _make_b64_image()})

        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"embedding", "embedding_dimension", "inference_time_ms", "model_id"}
        assert body["embedding_dimension"] == len(body["embedding"]) == raw.shape[1]
        norm = math.sqrt(sum(x * x for x in body["embedding"]))
        assert abs(norm - 1.0) < 1e-3
        assert mock_triton.infer.await_args.kwargs["model_name"] == "reid"


class TestLightAdapterHealth:
    """The light adapter's health payload as served through the gateway mount.

    Retargeted from the heavy adapter's ``/enrichment/health`` all-ready test,
    which pinned "an adapter health route reports healthy with a models map".
    The heavy adapter is gone with its models; the light adapter's route is the
    surviving carrier, and the probe set is derived from the residency set
    rather than remembered — a pruned model left in that payload would report
    ``degraded`` on every healthy boot.
    """

    async def test_enrichment_light_health_all_ready(self, client: AsyncClient) -> None:
        from ai.gateway.residency import FULL_MODEL_SET

        expected_probes = {m for m in FULL_MODEL_SET if m != "yolo26"}
        # Non-vacuity: the derivation must not collapse to an empty set.
        assert len(expected_probes) >= 2, expected_probes

        resp = await client.get("/enrich-lt/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert set(body["models"]) == expected_probes
        assert all(v is True for v in body["models"].values())


# ---------------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------------


class TestAppConfiguration:
    """Tests for FastAPI app metadata."""

    def test_app_title(self) -> None:
        """App title is set correctly."""
        from ai.gateway.main import app

        assert app.title == "AI Gateway"

    def test_app_version(self) -> None:
        """App version is set."""
        from ai.gateway.main import app

        assert app.version == "1.0.0"

    def test_all_models_list(self) -> None:
        """ALL_MODELS is the residency universe, derived — not a hand list.

        Pre-S3 this test enumerated the 14-model repository by name and pinned
        ``len(ALL_MODELS) > 5``. Both are unsatisfiable now that R8 S3 pruned
        FULL_MODEL_SET to the kept three, and the count pin was hand-numbered
        anyway (WP4.2). The retained ``yolo26`` membership line is the
        kept-model pin the S3 guard requires to survive the retarget.
        """
        from ai.gateway.main import ALL_MODELS
        from ai.gateway.residency import FULL_MODEL_SET

        assert "yolo26" in ALL_MODELS
        # Contents come from the one source of truth: main.py derives this list
        # from the tuple, so equality here is the drift pin for /health.
        assert set(ALL_MODELS) == set(FULL_MODEL_SET)
        # Derived sanity (replaces the retired ``len > 5`` hand pin): the
        # universe describes a multi-model repository and has no duplicates,
        # so /health cannot be reporting a single model or a doubled one.
        assert len(ALL_MODELS) == len(set(ALL_MODELS)) == len(FULL_MODEL_SET)
        assert len(ALL_MODELS) >= 2

    async def test_nonexistent_endpoint_returns_404(self, client: AsyncClient) -> None:
        """Unregistered paths return 404."""
        resp = await client.get("/nonexistent/path")
        assert resp.status_code == 404
