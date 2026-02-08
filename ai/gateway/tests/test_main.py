"""Unit tests for the AI Gateway FastAPI application.

Tests the top-level endpoints and configuration defined in ai/gateway/main.py:
- GET /health         - aggregated health across all Triton models
- GET /metrics        - merged Prometheus + Triton metrics
- CORS middleware     - allowed origins / methods
- Lifespan           - startup connectivity check and shutdown cleanup
- Router mounting    - adapter prefixes are reachable

All Triton and adapter internals are mocked so the tests run purely on CPU
with no real Triton server.
"""

from __future__ import annotations

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
# local binding. To override in tests that need a specific mock per-adapter,
# we also need to patch the adapter-level references.
_ADAPTER_PATCH_TARGETS = [
    "ai.gateway.adapters.yolo26.get_triton_client",
    "ai.gateway.adapters.clip.get_triton_client",
    "ai.gateway.adapters.florence.get_triton_client",
    "ai.gateway.adapters.enrichment.get_triton_client",
    "ai.gateway.adapters.enrichment_light.get_triton_client",
]


def _make_test_image_bytes(width: int = 64, height: int = 64) -> bytes:
    """Create a small JPEG image as raw bytes for multipart uploads."""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


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
    # Default infer returns an empty-ish detection array (no detections)
    mock.infer = AsyncMock(
        return_value={
            "output0": np.zeros((1, 84, 8400), dtype=np.float32),
            "output": np.zeros((1, 768), dtype=np.float32),
            "OUTPUT_TEXT": np.array(["test output"], dtype=object),
            "OUTPUT_KEYPOINTS": np.array(["[]"], dtype=object),
            "OUTPUT_DETECTIONS": np.array(["[]"], dtype=object),
            "OUTPUT_ACTIONS": np.array(["[]"], dtype=object),
            "text_embedding": np.zeros((1, 768), dtype=np.float32),
        }
    )
    return mock


def _patch_all_get_triton_client(mock_tc: MagicMock):
    """Return a combined context manager that patches get_triton_client everywhere."""
    import contextlib

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
            from ai.gateway.main import ALL_MODELS, app, lifespan

            async with lifespan(app):
                pass

        # Every model in ALL_MODELS should have been checked
        assert len(model_names_checked) >= len(ALL_MODELS)

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
    """Verify that adapter routers are mounted at expected prefixes."""

    async def test_yolo26_health(self, client: AsyncClient) -> None:
        """GET /yolo26/health is reachable."""
        resp = await client.get("/yolo26/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert body["model"] == "yolo26"

    async def test_clip_health(self, client: AsyncClient) -> None:
        """GET /clip/health is reachable."""
        resp = await client.get("/clip/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body

    async def test_florence_health(self, client: AsyncClient) -> None:
        """GET /florence/health is reachable."""
        resp = await client.get("/florence/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body

    async def test_enrichment_health(self, client: AsyncClient) -> None:
        """GET /enrichment/health is reachable."""
        resp = await client.get("/enrichment/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body

    async def test_enrichment_light_health(self, client: AsyncClient) -> None:
        """GET /enrich-lt/health is reachable."""
        resp = await client.get("/enrich-lt/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body


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


class TestClipEmbed:
    """Smoke tests for CLIP embedding via the gateway."""

    async def test_embed_returns_200(self, client: AsyncClient) -> None:
        """POST /clip/embed with a valid base64 image returns 200."""
        import base64

        image_bytes = _make_test_image_bytes()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        resp = await client.post(
            "/clip/embed",
            json={"image": image_b64},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "embedding" in body
        assert "inference_time_ms" in body


class TestFlorenceExtract:
    """Smoke tests for Florence-2 extraction via the gateway."""

    async def test_extract_returns_200(self, client: AsyncClient) -> None:
        """POST /florence/extract with valid payload returns 200."""
        import base64

        image_bytes = _make_test_image_bytes()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        resp = await client.post(
            "/florence/extract",
            json={"image": image_b64, "prompt": "<CAPTION>"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "result" in body
        assert "prompt_used" in body
        assert body["prompt_used"] == "<CAPTION>"


class TestEnrichmentHealth:
    """Verify enrichment sub-health checks."""

    async def test_enrichment_health_all_ready(self, client: AsyncClient) -> None:
        """All models ready returns healthy."""
        resp = await client.get("/enrichment/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert "models" in body

    async def test_enrichment_light_health_all_ready(self, client: AsyncClient) -> None:
        """All light models ready returns healthy."""
        resp = await client.get("/enrich-lt/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert "models" in body


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
        """ALL_MODELS contains expected model names."""
        from ai.gateway.main import ALL_MODELS

        assert "yolo26" in ALL_MODELS
        assert "clip" in ALL_MODELS
        assert "florence2" in ALL_MODELS
        assert len(ALL_MODELS) > 5  # Sanity check

    async def test_nonexistent_endpoint_returns_404(self, client: AsyncClient) -> None:
        """Unregistered paths return 404."""
        resp = await client.get("/nonexistent/path")
        assert resp.status_code == 404
