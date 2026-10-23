"""Unit tests for backend.services.ai_health (B4.11)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.services import ai_health

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_ai_health_state():
    ai_health.reset_ai_health_state()
    yield
    ai_health.reset_ai_health_state()


def _mock_settings(
    *,
    yolo26_url: str | None = "http://ai-gateway:8090/yolo26",
    ai_vlm_url: str | None = "http://ai-vlm:8098",
    vlm_sleep_idle_seconds: int = 300,
) -> MagicMock:
    return MagicMock(
        yolo26_url=yolo26_url,
        ai_vlm_url=ai_vlm_url,
        vlm_sleep_idle_seconds=vlm_sleep_idle_seconds,
    )


class TestVlmPassiveState:
    async def test_vlm_unknown_before_first_call_and_unconfigured_url(self) -> None:
        settings = _mock_settings()
        res = await ai_health.state("ai_vlm", settings=settings)
        assert res.service == "ai_vlm"
        assert res.state == "unknown"
        assert res.detail == "No VLM call recorded since startup"
        assert res.to_dict()["service"] == "ai_vlm"

        unconfigured = await ai_health.state("ai_vlm", settings=_mock_settings(ai_vlm_url=None))
        assert unconfigured.state == "unknown"
        assert unconfigured.detail == "Service URL not configured"

    async def test_vlm_ready_then_idle_after_sleep_window(self) -> None:
        settings = _mock_settings(vlm_sleep_idle_seconds=10)
        t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
        ai_health.record_vlm_call("ready", at=t0, monotonic_at=100.0)

        ready = await ai_health.state(
            "ai-vlm",
            settings=settings,
            now=t0 + timedelta(seconds=5),
            now_monotonic=105.0,
        )
        assert ready.state == "ready"
        assert ready.since == t0

        idle = await ai_health.state(
            "nemotron",
            settings=settings,
            now=t0 + timedelta(seconds=11),
            now_monotonic=111.0,
        )
        assert idle.state == "idle"
        assert idle.detail == "Idle (asleep)"

        # Datetime fallback when monotonic_at is None
        ai_health._vlm_record.monotonic_at = None
        idle_dt = await ai_health.state(
            "ai_vlm",
            settings=settings,
            now=t0 + timedelta(seconds=15),
        )
        assert idle_dt.state == "idle"

    async def test_vlm_loading_and_failing_do_not_decay_to_idle(self) -> None:
        settings = _mock_settings(vlm_sleep_idle_seconds=1)
        ai_health.record_vlm_call("loading", "HTTP 503", monotonic_at=10.0)
        loading = await ai_health.state("ai_vlm", settings=settings, now_monotonic=100.0)
        assert loading.state == "loading"
        assert loading.detail == "HTTP 503"

        ai_health.record_vlm_call("failing", "Connection refused", monotonic_at=10.0)
        failing = await ai_health.state("ai_vlm", settings=settings, now_monotonic=100.0)
        assert failing.state == "failing"
        assert failing.detail == "Connection refused"

    async def test_vlm_open_circuit_breaker_reports_failing(self) -> None:
        settings = _mock_settings()
        with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_reg:
            breaker = MagicMock()
            breaker.state.value = "open"
            mock_reg.return_value.get.side_effect = lambda name: (
                breaker if name == "ai-vlm" else None
            )
            res = await ai_health.state("ai_vlm", settings=settings)
        assert res.state == "failing"
        assert res.detail == "Circuit breaker is open"


class TestYolo26ActiveState:
    async def test_yolo26_url_unconfigured(self) -> None:
        settings = _mock_settings(yolo26_url=None)
        res = await ai_health.state("yolo26", settings=settings)
        assert res.state == "unknown"

    async def test_yolo26_open_circuit_breaker(self) -> None:
        settings = _mock_settings()
        with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_reg:
            breaker = MagicMock()
            breaker.state.value = "open"
            mock_reg.return_value.get.return_value = breaker
            res = await ai_health.state("yolo26", settings=settings)
        assert res.state == "failing"
        assert res.detail == "Circuit breaker is open"

    async def test_yolo26_model_loaded_true_and_false(self) -> None:
        settings = _mock_settings()
        client = AsyncMock(spec=httpx.AsyncClient)

        resp_loading = MagicMock()
        resp_loading.status_code = 200
        resp_loading.content = b'{"status":"degraded","model_loaded":false}'
        resp_loading.json.return_value = {"status": "degraded", "model_loaded": False}
        client.get.return_value = resp_loading

        st_loading = await ai_health.state("yolo26", settings=settings, http_client=client)
        assert st_loading.state == "loading"
        assert st_loading.detail == "model not loaded"

        resp_ready = MagicMock()
        resp_ready.status_code = 200
        resp_ready.content = b'{"status":"healthy","model_loaded":true}'
        resp_ready.json.return_value = {"status": "healthy", "model_loaded": True}
        client.get.return_value = resp_ready

        st_ready = await ai_health.state("rtdetr", settings=settings, http_client=client)
        assert st_ready.state == "ready"
        assert st_ready.detail is None

    async def test_yolo26_models_map_status_fallback_and_error_cases(self) -> None:
        settings = _mock_settings()
        client = AsyncMock(spec=httpx.AsyncClient)

        # Gateway root /health fallback with models.yolo26
        resp_models = MagicMock(status_code=200, content=b'{"models":{"yolo26":false}}')
        resp_models.json.return_value = {"models": {"yolo26": False}}
        client.get.return_value = resp_models
        assert (
            await ai_health.state("yolo26", settings=settings, http_client=client)
        ).state == "loading"

        resp_models_true = MagicMock(status_code=200, content=b'{"models":{"yolo26":true}}')
        resp_models_true.json.return_value = {"models": {"yolo26": True}}
        client.get.return_value = resp_models_true
        assert (
            await ai_health.state("yolo26", settings=settings, http_client=client)
        ).state == "ready"

        # Status string fallback when model_loaded is absent
        for status_val, expected in (
            ("healthy", "ready"),
            ("loading", "loading"),
            ("broken", "failing"),
        ):
            resp_status = MagicMock(status_code=200, content=b"{}")
            resp_status.json.return_value = {"status": status_val}
            client.get.return_value = resp_status
            assert (
                await ai_health.state("yolo26", settings=settings, http_client=client)
            ).state == expected

        # Non-dict JSON body (e.g. list) and invalid JSON
        resp_list = MagicMock(status_code=200, content=b"[]")
        resp_list.json.return_value = []
        client.get.return_value = resp_list
        assert (
            await ai_health.state("yolo26", settings=settings, http_client=client)
        ).state == "failing"

        resp_bad_json = MagicMock(status_code=200, content=b"not-json")
        resp_bad_json.json.side_effect = ValueError("bad json")
        client.get.return_value = resp_bad_json
        assert (
            await ai_health.state("yolo26", settings=settings, http_client=client)
        ).state == "failing"

        # Empty 200 body
        resp_empty = MagicMock(status_code=200, content=b"")
        client.get.return_value = resp_empty
        assert (
            await ai_health.state("yolo26", settings=settings, http_client=client)
        ).state == "ready"

        # HTTP 503 and HTTP 500
        client.get.return_value = MagicMock(status_code=503, content=b"loading")
        assert (
            await ai_health.state("yolo26", settings=settings, http_client=client)
        ).state == "loading"

        client.get.return_value = MagicMock(status_code=500, content=b"err")
        assert (
            await ai_health.state("yolo26", settings=settings, http_client=client)
        ).state == "failing"

        # ConnectError / TimeoutException / generic Exception
        client.get.side_effect = httpx.ConnectError("refused")
        assert (
            await ai_health.state("yolo26", settings=settings, http_client=client)
        ).state == "failing"

        client.get.side_effect = httpx.TimeoutException("timed out")
        assert (
            await ai_health.state("yolo26", settings=settings, http_client=client)
        ).state == "failing"

        client.get.side_effect = RuntimeError("unexpected")
        assert (
            await ai_health.state("yolo26", settings=settings, http_client=client)
        ).state == "failing"


class TestOnChangeAndSnapshot:
    async def test_on_change_fires_only_on_transition_and_unsubscribes(self) -> None:
        settings = _mock_settings()
        events: list[tuple[str, str]] = []

        def _sync_listener(st: ai_health.ServiceState) -> None:
            events.append((st.service, st.state))

        def _failing_listener(_st: ai_health.ServiceState) -> None:
            raise RuntimeError("listener failure is swallowed")

        unsub = ai_health.on_change(_sync_listener)
        unsub_fail = ai_health.on_change(_failing_listener)
        await ai_health.record_vlm_call_and_notify("loading", "HTTP 503", settings=settings)
        # Same state again -> no duplicate callback
        await ai_health.record_vlm_call_and_notify("loading", "HTTP 503", settings=settings)
        await ai_health.record_vlm_call_and_notify("ready", settings=settings)

        assert events == [("ai_vlm", "loading"), ("ai_vlm", "ready")]

        unsub()
        unsub_fail()
        await ai_health.record_vlm_call_and_notify("failing", "boom", settings=settings)
        assert events == [("ai_vlm", "loading"), ("ai_vlm", "ready")]

    async def test_snapshot_returns_both_services(self) -> None:
        settings = _mock_settings()
        client = AsyncMock(spec=httpx.AsyncClient)
        resp = MagicMock(status_code=200, content=b'{"status":"healthy","model_loaded":true}')
        resp.json.return_value = {"status": "healthy", "model_loaded": True}
        client.get.return_value = resp

        ai_health.record_vlm_call("ready")
        snap = await ai_health.snapshot(settings=settings, http_client=client)
        assert snap["yolo26"].state == "ready"
        assert snap["ai_vlm"].state == "ready"

    def test_unknown_service_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown AI service"):
            ai_health._normalize_service_name("florence")


class TestLatencyHistograms:
    def test_detector_and_vlm_latency_stats(self) -> None:
        assert ai_health.get_detector_latency_stats() == {"avg": 0.0, "p95": 0.0, "p99": 0.0}
        assert ai_health.get_vlm_latency_stats() == {"avg": 0.0, "p95": 0.0, "p99": 0.0}

        for val in (10.0, 20.0, 30.0):
            ai_health.record_detector_latency_ms(val)
        det = ai_health.get_detector_latency_stats()
        assert det["avg"] == 20.0
        assert det["p95"] >= 20.0
        assert det["p99"] >= 20.0

        for val in (100.0, 200.0, 300.0):
            ai_health.record_vlm_latency_ms(val)
        vlm = ai_health.get_vlm_latency_stats()
        assert vlm["avg"] == 200.0
        assert vlm["p95"] >= 200.0
