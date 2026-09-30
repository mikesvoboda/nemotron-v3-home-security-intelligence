"""Unit tests for the AI Gateway request-duration/error metrics wiring.

Closes the production gap flagged in the 2026-09-22 gateway follow-up plan:
GATEWAY_REQUEST_DURATION (hsi_ai_inference_duration_seconds) and
GATEWAY_REQUEST_ERRORS (hsi_ai_inference_errors_total) in ai/gateway/main.py
were defined but never observed. These tests drive real requests through the
mounted app (Triton fully mocked, like test_main.py) and assert the families
are observed with the documented labels:

    service  = adapter prefix the route is mounted under (yolo26, enrich-lt)
    endpoint = route path under that prefix (detect, threat-detect, ...)

plus the honest exclusions: /health-family and /metrics traffic is NOT
observed (scrape/health chatter must not skew latency panels), 4xx responses
count as duration but NOT as errors, and unmatched paths land in the bounded
("other", "other") bucket instead of exploding cardinality.

R8 S3 (2026-09-29) retired three of the five adapter prefixes this file used to
name. Two consequences, both retargeted rather than dropped:
* the ``_ADAPTER_PATCH_TARGETS`` list named the swept modules and every fixture
  that used it ERRORED (``patch()`` resolves eagerly); it is now the two
  adapters that ship — see test_main.TestPatchSurface, which pins that the list
  covers every live adapter binding;
* the label table named dead routes, and dead routes derive ("other","other")
  now. The retired rows were pinning three shapes: a one-segment endpoint under
  an adapter prefix (was /clip/embed), a hyphenated endpoint under the light
  prefix (was /enrich-lt/pose-analyze), and a prefix that is NOT an adapter
  mount (was /enrichment/vehicle-classify). All three shapes survive on live
  routes — /yolo26/detect, /enrich-lt/threat-detect, and the derived sweep of
  every mounted route — so the table is derived from the live route table
  (WP4.2) and only the shape anchors stay literal.
"""

from __future__ import annotations

import asyncio
import io
from collections.abc import Iterator
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

# Exactly the adapter modules ai/gateway/adapters ships after the R8 S3 prune.
# The three entries naming swept modules were an AttributeError at fixture
# setup — the cause of the 14 errors this file was throwing.
_ADAPTER_PATCH_TARGETS = [
    "ai.gateway.adapters.yolo26.get_triton_client",
    "ai.gateway.adapters.enrichment_light.get_triton_client",
]


def _make_test_image_bytes(width: int = 64, height: int = 64) -> bytes:
    img = Image.new("RGB", (width, height), color=(10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _b64_image() -> str:
    """base64 of the test JPEG, for the JSON-body routes."""
    import base64

    return base64.b64encode(_make_test_image_bytes()).decode()


def _make_mock_triton_client() -> MagicMock:
    mock = MagicMock()
    mock.is_server_ready = AsyncMock(return_value=True)
    mock.is_model_ready = AsyncMock(return_value=True)
    mock.close = AsyncMock()
    mock.get_model_metadata = AsyncMock(
        return_value={"name": "yolo26", "outputs": [{"name": "output0"}]}
    )
    # "output0" is the key both surviving adapters index after requesting it
    # (adapters/yolo26.py:370, adapters/enrichment_light.py:153).
    mock.infer = AsyncMock(
        return_value={
            "output0": np.zeros((1, 84, 8400), dtype=np.float32),
            "embedding": np.zeros((1, 512), dtype=np.float32),
        }
    )
    return mock


@contextmanager
def _patch_all_get_triton_client(mock_tc: MagicMock) -> Iterator[MagicMock]:
    with patch(_PATCH_TARGET, return_value=mock_tc):
        patches = [patch(t, return_value=mock_tc) for t in _ADAPTER_PATCH_TARGETS]
        for p in patches:
            p.start()
        try:
            yield mock_tc
        finally:
            for p in patches:
                p.stop()


def _labels(method: str, path: str) -> tuple[str, str]:
    """Run the production label derivation on a synthetic request scope."""
    from ai.gateway.main import _gateway_labels, app

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [],
        "root_path": "",
        "router": app.router,
    }
    # matches() only needs router state beyond type/method/path for full match
    return _gateway_labels(scope)


def _live_route_rows() -> list[tuple[str, str]]:
    """Every (method, path) the live app actually routes, derived.

    Two sources, because FastAPI splits them: ``app.openapi()["paths"]`` is
    generated from the mounted routers (so an adapter route appears only if
    ``include_router`` ran), while the app's own Starlette routes (/docs, /health,
    /metrics, ...) carry a ``.path`` attribute but are absent from the OpenAPI
    body. HEAD is a GET alias and is not a distinct contract, so it is skipped.
    """
    from ai.gateway.main import app

    rows: list[tuple[str, str]] = []
    for path, operations in app.openapi()["paths"].items():
        for method in operations:
            rows.append((method.upper(), path))
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path is None or not methods:
            continue
        for method in sorted(methods):
            if method != "HEAD":
                rows.append((method, path))
    return sorted(set(rows))


def _health_paths() -> list[str]:
    """The health routes the live app answers, derived from the route table."""
    return sorted(p for _m, p in _live_route_rows() if p == "/health" or p.endswith("/health"))


def _derived_service_pairs() -> set[tuple[str, str]]:
    """The (service, endpoint) pairs the live route table implies, via the
    production derivation itself (not a restatement of its rule)."""
    return {_labels(method, path) for method, path in _live_route_rows()}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


def _observed_services() -> set[str]:
    """Every ``service`` label value the duration family has ever carried."""
    seen: set[str] = set()
    for metric in REGISTRY.collect():
        if metric.name == _DURATION:
            for sample in metric.samples:
                seen.add(sample.labels.get("service", ""))
    return seen


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

    async def test_light_adapter_route_observed_under_its_service(
        self, client: AsyncClient, mock_triton: MagicMock
    ) -> None:
        """Retargeted from the retired CLIP-embed row.

        Old subject: POST /clip/embed observed under service "clip". That route
        died with its models in the Triton prune (absence pinned by the S3 guard
        file, not here); the property that transfers is "an adapter route served
        through a NON-yolo26 prefix gets its own service bucket", which is what
        the retired row was really pinning — the yolo26 row above could not pin
        it, being the only other live prefix.
        """
        mock_triton.infer = AsyncMock(return_value={"output0": np.zeros((1, 8, 8400), np.float32)})
        before = _duration_count("enrich-lt", "threat-detect")
        resp = await client.post("/enrich-lt/threat-detect", json={"image": _b64_image()})
        assert resp.status_code == 200
        assert _duration_count("enrich-lt", "threat-detect") == before + 1

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


# ---------------------------------------------------------------------------
# Health / scrape exclusions
# ---------------------------------------------------------------------------


class TestHealthAndScrapeExcluded:
    """Health checks and Prometheus' own scrape must not pollute the family."""

    async def test_root_health_not_observed(self, client: AsyncClient) -> None:
        before = _family_duration_total()
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert _family_duration_total() == before

    async def test_live_adapter_health_routes_not_observed(self, client: AsyncClient) -> None:
        """Every LIVE adapter health route stays out of the family.

        This replaced a loop over five prefixes, three of which 404 after the
        prune: a 404 proves nothing about health-traffic exclusion, so those
        iterations were passing on dead paths. The prefixes come from the live
        route table now (a retired mount cannot quietly re-join the list), and
        each probe is asserted 200 — a health route that stopped answering would
        fail here rather than silently "not being observed".
        """
        paths = _health_paths()
        assert len(paths) >= 3, f"derived health paths {paths}"
        before = _family_duration_total()
        for path in paths:
            resp = await client.get(path)
            assert resp.status_code == 200, path
            assert _family_duration_total() == before, path
        assert _family_duration_total() == before

    async def test_service_buckets_are_bounded_by_the_live_route_table(
        self, client: AsyncClient
    ) -> None:
        """No request can mint a ``service`` bucket the route table does not imply.

        This is the cardinality guarantee the pre-S3 five-prefix loop was
        standing in for, stated without naming a single retired prefix — which is
        both the doctrine (an assertion reads live forms; the dead names belong
        in prose) and the stronger claim: instead of "these three specific dead
        paths mint nothing", it says NOTHING outside the derived live set can
        mint a series, dead provider, typo, or attacker-crafted URL alike. A
        dashboard series named after a service the image does not ship is a
        phantom, and this is the arm that refuses it.

        Two mechanisms meet here and the pin states which does what:
        * ``_is_health_path`` is a bare path-string test, so a 404 whose path
          happens to END in ``/health`` is excluded from observation entirely —
          harmless for cardinality, and pinned as such below;
        * ``_gateway_labels`` is route-derived, so an unmatched path resolves to
          the bounded ("other","other") pair instead of a prefix-shaped bucket.
        """
        allowed = {s for s, _ in _derived_service_pairs()} | {"other", "__probe__"}
        assert len(allowed) >= 4, sorted(allowed)  # non-vacuity

        # Live traffic first, so the family has real buckets to be bounded by.
        for method, path in _live_route_rows():
            if path in {"/openapi.json", "/docs/oauth2-redirect"}:
                continue
            await client.request(method, path)

        # Then the fuzz: unmatched paths, including one that ends in /health and
        # ones shaped like an adapter mount. None may mint a service bucket.
        before = _family_duration_total()
        resp = await client.get("/not-an-adapter/health")
        assert resp.status_code == 404
        # The path-string exclusion swallows this one wholesale — pinned so the
        # mechanism is not mistaken for the label rule.
        assert _family_duration_total() == before
        assert _labels("GET", "/not-an-adapter/health") == ("other", "other")

        for probe in (
            "/no-such-adapter/embed",
            "/yolo26/no/such/deep/path/4f9c",
            "/enrich-lt/%2e%2e/whatever",
        ):
            await client.get(probe)

        services = _observed_services()
        assert services <= allowed, f"unbounded service buckets: {sorted(services - allowed)}"
        # Non-vacuity: the sweep really minted live buckets, so the subset check
        # above is about routing and not an empty registry.
        assert {"yolo26", "enrich-lt"} <= services, sorted(services)

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
    """_gateway_labels unit coverage of the documented label contract.

    Two arms, deliberately different in kind:

    * ``test_shape_anchors`` pins the load-bearing shapes LITERALLY — a matched
      two-segment route (/yolo26/detect/batch, whose endpoint keeps its inner
      slash), a real app route with no tail (/docs -> "root"), and an unmatched
      prefix ((other, other)). These are the contract; the derivation arm below
      cannot substitute for them because both would use the same rule.
    * ``test_live_route_labels`` walks EVERY route the live app exposes and
      asserts the documented rule holds for each. It replaces the pre-S3 table
      that hand-listed /clip/embed, /enrich-lt/pose-analyze and
      /enrichment/vehicle-classify: those three rows pinned (i) a one-segment
      endpoint under an adapter prefix, (ii) a hyphenated endpoint under the
      light prefix, and (iii) a non-adapter prefix. All three shapes stay in the
      sweep, on live routes, and a route added later is covered without anyone
      remembering to extend a table (WP4.2: derived, not hand-pinned).
    """

    @pytest.mark.parametrize(
        ("method", "path", "expected"),
        [
            ("POST", "/yolo26/detect/batch", ("yolo26", "detect/batch")),
            ("POST", "/enrich-lt/threat-detect", ("enrich-lt", "threat-detect")),
            # /docs IS a real app route (FastAPI swagger), so it gets its own
            # bounded bucket pair rather than the unmatched ("other","other").
            ("GET", "/docs", ("docs", "root")),
            # Root-level app endpoints take the "root" endpoint form too.
            ("GET", "/health", ("health", "root")),
            # An unmatched path never borrows a prefix-shaped label, even when
            # it is shaped like one (two segments, adapter-ish first segment).
            # Pre-S3 this arm used a real retired route; the property is about
            # the SHAPE being unmatched, so it now uses a made-up prefix and
            # names no dead service in code (prose may, assertions may not).
            ("POST", "/not-an-adapter/embed", ("other", "other")),
        ],
    )
    def test_shape_anchors(self, method: str, path: str, expected: tuple[str, str]) -> None:
        assert _labels(method, path) == expected

    @pytest.mark.parametrize(
        ("method", "path"),
        _live_route_rows(),
        ids=[f"{m}-{p}" for m, p in _live_route_rows()],
    )
    def test_live_route_labels(self, method: str, path: str) -> None:
        """Every mounted route follows the documented label rule."""
        service, _, tail = path.lstrip("/").partition("/")
        expected = (service or "root", tail.lstrip("/") or "root")
        assert _labels(method, path) == expected, f"{method} {path}"

    def test_derived_sweep_covers_the_shapes_the_retired_table_pinned(self) -> None:
        """Non-vacuity for the sweep above, against the three retired rows.

        If _live_route_rows() ever comes back thin (an import-order bug, a
        router that stopped mounting), the parametrized arm would still pass on
        whatever tiny list it got. This pins that it still sees the shapes the
        deleted rows stood for: a hyphenated light endpoint, a non-root adapter
        service, and at least as many routes as the two shipped adapters plus the
        app's own endpoints.
        """
        rows = _live_route_rows()
        paths = {p for _m, p in rows}
        assert len(rows) >= 9, f"route table collapsed to {len(rows)} rows"
        assert "/enrich-lt/threat-detect" in paths, "the hyphenated-endpoint shape vanished"
        assert "/yolo26/detect/batch" in paths, "the two-segment shape vanished"
        assert "/docs" in paths, "the bounded-root-bucket shape vanished"
        services = {_labels(m, p)[0] for m, p in rows}
        assert {"yolo26", "enrich-lt", "docs"} <= services, sorted(services)
