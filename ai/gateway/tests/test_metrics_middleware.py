"""Unit tests for the AI Gateway request-duration/error metrics wiring.

Closes the production gap flagged in the 2026-09-22 gateway follow-up plan:
GATEWAY_REQUEST_DURATION (hsi_ai_inference_duration_seconds) and
GATEWAY_REQUEST_ERRORS (hsi_ai_inference_errors_total) in ai/gateway/main.py
were defined but never observed. These tests drive real requests through the
mounted app (Triton fully mocked, like test_main.py) and assert the families
are observed with the documented labels:

    service  = adapter prefix the route is mounted under (yolo26, clip, ...)
    endpoint = route path under that prefix (detect, embed, ...)

plus the honest exclusions: /health-family and /metrics traffic is NOT
observed (scrape/health chatter must not skew latency panels), 4xx responses
count as duration but NOT as errors, and unmatched paths land in the bounded
("other", "other") bucket instead of exploding cardinality.
"""

from __future__ import annotations

import asyncio
import io
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from prometheus_client import REGISTRY

_DURATION = "hsi_ai_inference_duration_seconds"
_ERRORS = "hsi_ai_inference_errors_total"

# ---------------------------------------------------------------------------
# Triton mocking (same pattern as test_main.py)
# ---------------------------------------------------------------------------

_PATCH_TARGET = "ai.gateway.triton_client.get_triton_client"

_ADAPTER_PATCH_TARGETS = [
    "ai.gateway.adapters.yolo26.get_triton_client",
    "ai.gateway.adapters.clip.get_triton_client",
    "ai.gateway.adapters.florence.get_triton_client",
    "ai.gateway.adapters.enrichment.get_triton_client",
    "ai.gateway.adapters.enrichment_light.get_triton_client",
]


def _make_test_image_bytes(width: int = 64, height: int = 64) -> bytes:
    img = Image.new("RGB", (width, height), color=(10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_mock_triton_client() -> MagicMock:
    mock = MagicMock()
    mock.is_server_ready = AsyncMock(return_value=True)
    mock.is_model_ready = AsyncMock(return_value=True)
    mock.close = AsyncMock()
    mock.get_model_metadata = AsyncMock(
        return_value={"name": "yolo26", "outputs": [{"name": "output0"}]}
    )
    mock.infer = AsyncMock(
        return_value={
            "output0": np.zeros((1, 84, 8400), dtype=np.float32),
            "pooler_output": np.zeros((1, 768), dtype=np.float32),
        }
    )
    return mock


@contextmanager
def _patch_all_get_triton_client(mock_tc: MagicMock):
    with patch(_PATCH_TARGET, return_value=mock_tc):
        patches = [patch(t, return_value=mock_tc) for t in _ADAPTER_PATCH_TARGETS]
        for p in patches:
            p.start()
        try:
            yield mock_tc
        finally:
            for p in patches:
                p.stop()


@pytest.fixture(autouse=True)
def _reset_triton_singleton() -> None:
    import ai.gateway.triton_client as tc_mod

    tc_mod._client = None


@pytest.fixture
def mock_triton() -> MagicMock:
    return _make_mock_triton_client()


@pytest.fixture
async def client(mock_triton: MagicMock) -> AsyncClient:
    with _patch_all_get_triton_client(mock_triton):
        from ai.gateway.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Prometheus sample readers
# ---------------------------------------------------------------------------


def _duration_count(service: str, endpoint: str) -> float:
    """Observations recorded so far for one label pair (0.0 if unseen)."""
    return (
        REGISTRY.get_sample_value(f"{_DURATION}_count", {"service": service, "endpoint": endpoint})
        or 0.0
    )


def _duration_sum(service: str, endpoint: str) -> float:
    return (
        REGISTRY.get_sample_value(f"{_DURATION}_sum", {"service": service, "endpoint": endpoint})
        or 0.0
    )


def _errors_total(service: str, endpoint: str) -> float:
    return REGISTRY.get_sample_value(_ERRORS, {"service": service, "endpoint": endpoint}) or 0.0


def _family_duration_total() -> float:
    """Total observations of the duration family across every label pair."""
    total = 0.0
    for metric in REGISTRY.collect():
        if metric.name == _DURATION:
            for sample in metric.samples:
                if sample.name == f"{_DURATION}_count":
                    total += sample.value
    return total


# ---------------------------------------------------------------------------
# Metric registration truth
# ---------------------------------------------------------------------------


class TestMetricRegistration:
    """The registered family names must match what prometheus.yml documents."""

    def test_families_registered_with_documented_names(self) -> None:
        from ai.gateway.main import GATEWAY_REQUEST_DURATION, GATEWAY_REQUEST_ERRORS

        # Force one observation per family on a probe label pair so the
        # exposed samples exist regardless of test order (an unobserved
        # histogram exposes only HELP/TYPE — no *_count sample).
        GATEWAY_REQUEST_DURATION.labels(service="__probe__", endpoint="__probe__").observe(0.123)
        GATEWAY_REQUEST_ERRORS.labels(service="__probe__", endpoint="__probe__").inc()

        # prometheus_client strips the "_total" suffix from a Counter's base
        # name; the EXPOSED sample keeps it. Assert what a scrape sees.
        sample_names: set[str] = set()
        base_names: set[str] = set()
        for metric in REGISTRY.collect():
            base_names.add(metric.name)
            for sample in metric.samples:
                sample_names.add(sample.name)
        assert _DURATION in base_names
        assert f"{_DURATION}_count" in sample_names
        assert "hsi_ai_inference_errors" in base_names  # counter base (suffix stripped)
        assert _ERRORS in sample_names  # exposed series keeps _total

    def test_error_counter_exposes_total_sample(self) -> None:
        # A Counter named *_total exposes samples under exactly that name.
        from ai.gateway.main import GATEWAY_REQUEST_ERRORS

        pair = {"service": "__probe__", "endpoint": "errors"}
        before = REGISTRY.get_sample_value(_ERRORS, pair) or 0.0
        GATEWAY_REQUEST_ERRORS.labels(**pair).inc()
        assert (REGISTRY.get_sample_value(_ERRORS, pair) or 0.0) == before + 1.0


# ---------------------------------------------------------------------------
# Duration observed on the request path
# ---------------------------------------------------------------------------


class TestDurationObserved:
    """GATEWAY_REQUEST_DURATION observes real inference requests."""

    async def test_yolo26_detect_observed_with_labels(self, client: AsyncClient) -> None:
        before = _duration_count("yolo26", "detect")
        image_bytes = _make_test_image_bytes()
        resp = await client.post(
            "/yolo26/detect", files={"file": ("t.jpg", image_bytes, "image/jpeg")}
        )
        assert resp.status_code == 200
        assert _duration_count("yolo26", "detect") == before + 1
        # Duration is real (bounded away from negative/absurd for a mocked call)
        assert _duration_sum("yolo26", "detect") > 0.0

    async def test_clip_embed_observed_under_clip_service(self, client: AsyncClient) -> None:
        import base64

        before = _duration_count("clip", "embed")
        b64 = base64.b64encode(_make_test_image_bytes()).decode()
        resp = await client.post("/clip/embed", json={"image": b64})
        assert resp.status_code == 200
        assert _duration_count("clip", "embed") == before + 1

    async def test_duration_is_measured_not_zero(
        self, client: AsyncClient, mock_triton: MagicMock
    ) -> None:
        """The timer actually brackets the handler: a slow inference lengthens
        the observed sum by at least its sleep."""

        async def slow_infer(**kwargs):
            await asyncio.sleep(0.05)
            return {"output0": np.zeros((1, 84, 8400), dtype=np.float32)}

        mock_triton.infer = AsyncMock(side_effect=slow_infer)

        sum_before = _duration_sum("yolo26", "detect")
        resp = await client.post(
            "/yolo26/detect",
            files={"file": ("t.jpg", _make_test_image_bytes(), "image/jpeg")},
        )
        assert resp.status_code == 200
        assert _duration_sum("yolo26", "detect") >= sum_before + 0.05


class TestHealthAndScrapeExcluded:
    """Health checks and Prometheus' own scrape must not pollute the family."""

    async def test_root_health_not_observed(self, client: AsyncClient) -> None:
        before = _family_duration_total()
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert _family_duration_total() == before

    async def test_adapter_health_not_observed(self, client: AsyncClient) -> None:
        before = _family_duration_total()
        for path in (
            "/yolo26/health",
            "/clip/health",
            "/florence/health",
            "/enrichment/health",
            "/enrich-lt/health",
        ):
            resp = await client.get(path)
            assert resp.status_code == 200
        assert _family_duration_total() == before

    async def test_metrics_scrape_not_observed(self, client: AsyncClient) -> None:
        before = _family_duration_total()
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        assert _family_duration_total() == before


# ---------------------------------------------------------------------------
# Error counter
# ---------------------------------------------------------------------------


class TestErrorCounter:
    """GATEWAY_REQUEST_ERRORS counts 5xx responses, not 4xx, not success."""

    async def test_5xx_increments_error_counter(self, mock_triton: MagicMock) -> None:
        from ai.gateway.triton_client import TritonClientError

        mock_triton.infer = AsyncMock(side_effect=TritonClientError("GPU exploded"))

        with _patch_all_get_triton_client(mock_triton):
            from ai.gateway.main import app

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
                err_before = _errors_total("yolo26", "detect")
                dur_before = _duration_count("yolo26", "detect")
                resp = await ac.post(
                    "/yolo26/detect",
                    files={"file": ("t.jpg", _make_test_image_bytes(), "image/jpeg")},
                )

        assert resp.status_code == 503
        assert _errors_total("yolo26", "detect") == err_before + 1
        # Duration is still recorded for failed requests
        assert _duration_count("yolo26", "detect") == dur_before + 1

    async def test_4xx_records_duration_but_not_error(self, client: AsyncClient) -> None:
        err_before = _errors_total("yolo26", "detect")
        dur_before = _duration_count("yolo26", "detect")
        resp = await client.post(
            "/yolo26/detect",
            files={"file": ("t.txt", b"definitely not an image", "text/plain")},
        )
        assert resp.status_code == 400
        assert _duration_count("yolo26", "detect") == dur_before + 1
        assert _errors_total("yolo26", "detect") == err_before

    async def test_success_does_not_increment_error_counter(self, client: AsyncClient) -> None:
        err_before = _errors_total("yolo26", "detect")
        resp = await client.post(
            "/yolo26/detect",
            files={"file": ("t.jpg", _make_test_image_bytes(), "image/jpeg")},
        )
        assert resp.status_code == 200
        assert _errors_total("yolo26", "detect") == err_before


class TestUnmatchedPathsAreBounded:
    """404s must land in the fixed ("other", "other") bucket — never the raw
    attacker-controlled path (cardinality protection)."""

    async def test_404_observed_as_other_other(self, client: AsyncClient) -> None:
        dur_before = _duration_count("other", "other")
        resp = await client.get("/no/such/inference/path")
        assert resp.status_code == 404
        assert _duration_count("other", "other") == dur_before + 1

    async def test_raw_404_path_never_becomes_a_label(self, client: AsyncClient) -> None:
        unique = "/yolo26/never-a-route-9f3a1c"
        await client.get(unique)
        seen_endpoints = set()
        for metric in REGISTRY.collect():
            if metric.name == _DURATION:
                for sample in metric.samples:
                    seen_endpoints.add(sample.labels.get("endpoint", ""))
        assert "never-a-route-9f3a1c" not in seen_endpoints
        assert not any(str(ls).startswith("/yolo26/") for ls in seen_endpoints)


class TestLabelDerivation:
    """_gateway_labels unit coverage of the documented label contract."""

    @pytest.mark.parametrize(
        ("method", "path", "expected"),
        [
            ("POST", "/yolo26/detect", ("yolo26", "detect")),
            ("POST", "/yolo26/detect/batch", ("yolo26", "detect/batch")),
            ("POST", "/clip/embed", ("clip", "embed")),
            ("POST", "/enrich-lt/pose-analyze", ("enrich-lt", "pose-analyze")),
            ("POST", "/enrichment/vehicle-classify", ("enrichment", "vehicle-classify")),
            # /docs IS a real app route (FastAPI swagger), so it gets its own
            # bounded bucket pair rather than the unmatched ("other","other").
            ("GET", "/docs", ("docs", "root")),
        ],
    )
    def test_expected_labels(self, method: str, path: str, expected: tuple[str, str]) -> None:
        from ai.gateway.main import _gateway_labels, app

        scope = {"type": "http", "method": method, "path": path, "headers": [], "root_path": ""}
        # matches() only needs router state beyond type/method/path for full match
        app_scope = dict(scope, router=app.router)
        assert _gateway_labels(app_scope) == expected
