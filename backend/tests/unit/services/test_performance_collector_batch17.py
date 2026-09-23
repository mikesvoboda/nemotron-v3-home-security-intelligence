"""Batch-17 kill-test battery: backend/services/performance_collector.py.

Every literal below was MEASURED against the shipped module before the assert
was written (probes /tmp/b17-probe-{a,b,c,d,e}.py, consolidated to
/tmp/b17-probes.json, run 2026-09-23 with ``uv run python`` from the repo root).
Production was never bent to a mutant; where the shipped value and the WP4.4
dossier draft disagree, the shipped value is asserted and the divergence is
noted inline.

Dossier clusters covered (wp44-triage/performance_collector.md):
  C06b host sub-GiB totals, C09 mW->W floor division, C12 alert-threshold
  boundaries (both sides of every comparison), C13 pg alert arithmetic,
  C14 pg conn-ratio zero guard, C15b collect_all timestamp awareness,
  C16 gpu pynvml preference, C17 http client timeout, C18/C19 pynvml flag,
  C20 nvml call args, C21 gpu-fallback defaults, C22 yolo26 shapes,
  C23 nemotron slot semantics, C24 disk_usage path, C25 container wiring,
  C26 service-health request + branch outputs, C26b postgres/redis health
  except branches, C27 postgresql sentinel values, C28 redis info defaults,
  C29 redis hit-ratio guard, C30 redis unreachable literal, C31 throughput
  SQL/cutoff/rounding, C32 tracker call args, C33 throughput seeds,
  C34 latency dict contract, C35 queues.

EQUIVALENT clusters deliberately NOT targeted: C01-C05, C06a, C07, C08, C10,
C15a (C11 LOW-VALUE falls out of the unreachable-literal assert for free).

Shipped-vs-dossier / audit notes (shipped wins, per WP4.4 METHOD):
- This module has NO ``check_throttle_status`` and no ``THROTTLE_WARNINGS`` /
  ``THROTTLE_CRITICALS`` / ``THROTTLE_EMERGENCIES``; alert severities are the
  literal strings "warning"/"critical" and every threshold literal here equals
  the shipped ``THRESHOLDS`` registry (75/85 gpu temp etc.). The 200/500/1000
  "measured" throttle literals belong to other modules (e.g.
  ``job_progress_reporter.PROGRESS_THROTTLE_INTERVAL``) and appear nowhere in
  backend/services/performance_collector.py.
- C17: ``httpx.AsyncClient(timeout=5.0)`` -> ``httpx.AsyncClient(timeout=None)``
  is killed (Timeout(timeout=None) != Timeout(5.0), measured), but dropping the
  kwarg entirely is a TRUE EQUIVALENT — httpx's own default timeout IS
  ``Timeout(5.0)`` (measured: ``httpx.AsyncClient().timeout == Timeout(5.0)``).
- C06a ("equivalent after the guard") holds only for the ram_total side: the
  except-branch ``ram_used_gb``/``disk_used_gb`` fillers are observable through
  the returned ``ram_percent``/``disk_percent`` computed fields, so those
  mutations are pinned here via full ``model_dump()`` equality.
"""

import copy
import operator
import sys
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.api.schemas.performance import (
    ContainerMetrics,
    DatabaseMetrics,
    GpuMetrics,
    HostMetrics,
    RedisMetrics,
)
from backend.services.performance_collector import THRESHOLDS, PerformanceCollector

pytestmark = pytest.mark.unit


# =============================================================================
# Helpers
# =============================================================================


@pytest.fixture(autouse=True)
def _restore_module_state():
    """Save/restore module-level globals so alert-threshold asserts cannot leak."""
    saved_thresholds = copy.deepcopy(THRESHOLDS)
    saved_pynvml = "pynvml" in sys.modules
    saved_module = sys.modules.get("pynvml")
    yield
    THRESHOLDS.clear()
    THRESHOLDS.update(saved_thresholds)
    if saved_pynvml:
        sys.modules["pynvml"] = saved_module
    else:
        sys.modules.pop("pynvml", None)


@contextmanager
def _stub_pynvml(stub):
    """Make ``import pynvml`` inside the service resolve to the stub."""
    had = "pynvml" in sys.modules
    previous = sys.modules.get("pynvml")
    sys.modules["pynvml"] = stub
    try:
        yield stub
    finally:
        if had:
            sys.modules["pynvml"] = previous
        else:
            del sys.modules["pynvml"]


def _collector(**settings) -> PerformanceCollector:
    """Collector with patched settings (autospec, matching the covering file)."""
    with patch(
        "backend.services.performance_collector.get_settings", autospec=True
    ) as mock_settings:
        mock_settings.return_value = MagicMock(**settings)
        return PerformanceCollector()


def _http_client(payload=None, status=200, exc=None) -> AsyncMock:
    """AsyncMock stand-in for the collector's shared httpx client."""
    client = AsyncMock()
    if exc is not None:
        client.get.side_effect = exc
        return client
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload
    client.get.return_value = response
    return client


def _shape(alerts) -> list[tuple[str, str, float, float]]:
    """(severity, metric, value, threshold) for every alert, in emission order."""
    return [(a.severity, a.metric, a.value, a.threshold) for a in alerts]


class _SessionCM:
    """Callable that hands the same session to ``async with``."""

    def __init__(self, session) -> None:
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info) -> None:
        return None


def _gpu_metrics(temperature: int = 50, vram_used: float = 1.0, vram_total: float = 24.0):
    return GpuMetrics(
        name="G",
        utilization=50.0,
        vram_used_gb=vram_used,
        vram_total_gb=vram_total,
        temperature=temperature,
        power_watts=150,
    )


def _host_metrics(
    cpu: float = 1.0,
    ram_used: float = 1.0,
    ram_total: float = 20.0,
    disk_used: float = 1.0,
    disk_total: float = 500.0,
):
    return HostMetrics(
        cpu_percent=cpu,
        ram_used_gb=ram_used,
        ram_total_gb=ram_total,
        disk_used_gb=disk_used,
        disk_total_gb=disk_total,
    )


def _redis_metrics(memory_mb: float = 10.0, hit_ratio: float = 90.0):
    return RedisMetrics(
        status="healthy",
        connected_clients=1,
        memory_mb=memory_mb,
        hit_ratio=hit_ratio,
        blocked_clients=0,
    )


def _db_metrics(active: int = 1, maximum: int = 20, cache_hit_ratio: float = 95.0):
    return DatabaseMetrics(
        status="healthy",
        connections_active=active,
        connections_max=maximum,
        cache_hit_ratio=cache_hit_ratio,
        transactions_per_min=100,
    )


# =============================================================================
# Threshold registration (full-value equality, not membership)
# =============================================================================


class TestThresholdRegistration:
    """THRESHOLDS is a module-level registry: pinned as one exact value."""

    def test_thresholds_registry_exact_value(self) -> None:
        assert THRESHOLDS == {
            "gpu_temperature": {"warning": 75, "critical": 85},
            "gpu_utilization": {"warning": 90, "critical": 98},
            "gpu_vram": {"warning": 90, "critical": 95},
            "gpu_power": {"warning": 300, "critical": 350},
            "yolo26_latency_p95": {"warning": 200, "critical": 500},
            "nemotron_latency_p95": {"warning": 10000, "critical": 30000},
            "pg_connections": {"warning": 0.8, "critical": 0.95},
            "pg_cache_hit": {"warning": 90, "critical": 80},
            "redis_memory_mb": {"warning": 100, "critical": 500},
            "redis_hit_ratio": {"warning": 50, "critical": 10},
            "host_cpu": {"warning": 80, "critical": 95},
            "host_ram": {"warning": 85, "critical": 95},
            "host_disk": {"warning": 80, "critical": 90},
        }


# =============================================================================
# C12 / C13 / C14 — alert threshold boundaries and alert payload arithmetic
# =============================================================================


class TestAlertBoundaries:
    """Both sides of every comparison, with full alert-list equality."""

    def test_gpu_temperature_boundary(self) -> None:
        collector = _collector()
        assert _shape(collector.check_gpu_alerts(_gpu_metrics(temperature=74))) == []
        assert _shape(collector.check_gpu_alerts(_gpu_metrics(temperature=75))) == [
            ("warning", "gpu_temperature", 75.0, 75.0)
        ]
        assert _shape(collector.check_gpu_alerts(_gpu_metrics(temperature=84))) == [
            ("warning", "gpu_temperature", 84.0, 75.0)
        ]
        assert _shape(collector.check_gpu_alerts(_gpu_metrics(temperature=85))) == [
            ("critical", "gpu_temperature", 85.0, 85.0)
        ]
        assert _shape(collector.check_gpu_alerts(_gpu_metrics(temperature=86))) == [
            ("critical", "gpu_temperature", 86.0, 85.0)
        ]

    def test_gpu_vram_boundary(self) -> None:
        collector = _collector()
        just_under_warn = _gpu_metrics(vram_used=21.5999, vram_total=24.0)
        assert just_under_warn.vram_percent == 89.99958333333335
        assert _shape(collector.check_gpu_alerts(just_under_warn)) == []

        at_warn = _gpu_metrics(vram_used=21.6, vram_total=24.0)
        assert at_warn.vram_percent == 90.0
        assert _shape(collector.check_gpu_alerts(at_warn)) == [("warning", "gpu_vram", 90.0, 90.0)]

        just_under_crit = _gpu_metrics(vram_used=22.7999, vram_total=24.0)
        assert just_under_crit.vram_percent == 94.99958333333333
        assert _shape(collector.check_gpu_alerts(just_under_crit)) == [
            ("warning", "gpu_vram", 94.99958333333333, 90.0)
        ]

        at_crit = _gpu_metrics(vram_used=22.8, vram_total=24.0)
        assert at_crit.vram_percent == 95.0
        assert _shape(collector.check_gpu_alerts(at_crit)) == [("critical", "gpu_vram", 95.0, 95.0)]

    def test_host_alerts_boundary(self) -> None:
        collector = _collector()
        assert _shape(collector.check_host_alerts(_host_metrics())) == []

        warn = _host_metrics(cpu=80.0, ram_used=17.0, ram_total=20.0, disk_used=400.0)
        assert (warn.cpu_percent, warn.ram_percent, warn.disk_percent) == (80.0, 85.0, 80.0)
        assert _shape(collector.check_host_alerts(warn)) == [
            ("warning", "host_cpu", 80.0, 80.0),
            ("warning", "host_ram", 85.0, 85.0),
            ("warning", "host_disk", 80.0, 80.0),
        ]

        crit = _host_metrics(cpu=95.0, ram_used=19.0, ram_total=20.0, disk_used=450.0)
        assert (crit.cpu_percent, crit.ram_percent, crit.disk_percent) == (95.0, 95.0, 90.0)
        assert _shape(collector.check_host_alerts(crit)) == [
            ("critical", "host_cpu", 95.0, 95.0),
            ("critical", "host_ram", 95.0, 95.0),
            ("critical", "host_disk", 90.0, 90.0),
        ]

    def test_host_cpu_just_below_boundaries(self) -> None:
        collector = _collector()
        assert _shape(collector.check_host_alerts(_host_metrics(cpu=79.9))) == []
        assert _shape(collector.check_host_alerts(_host_metrics(cpu=94.9))) == [
            ("warning", "host_cpu", 94.9, 80.0)
        ]

    def test_host_ram_just_below_boundaries(self) -> None:
        collector = _collector()
        under_warn = _host_metrics(ram_used=16.9998, ram_total=20.0)
        assert under_warn.ram_percent == 84.999
        assert _shape(collector.check_host_alerts(under_warn)) == []

        under_crit = _host_metrics(ram_used=18.9998, ram_total=20.0)
        assert under_crit.ram_percent == 94.999
        assert _shape(collector.check_host_alerts(under_crit)) == [
            ("warning", "host_ram", 94.999, 85.0)
        ]

    def test_host_disk_just_below_boundaries(self) -> None:
        collector = _collector()
        under_warn = _host_metrics(disk_used=399.995, disk_total=500.0)
        assert under_warn.disk_percent == 79.999
        assert _shape(collector.check_host_alerts(under_warn)) == []

        under_crit = _host_metrics(disk_used=449.995, disk_total=500.0)
        assert under_crit.disk_percent == 89.999
        assert _shape(collector.check_host_alerts(under_crit)) == [
            ("warning", "host_disk", 89.999, 80.0)
        ]

    def test_redis_alert_boundaries(self) -> None:
        collector = _collector()
        assert _shape(collector.check_redis_alerts(_redis_metrics())) == []
        # `memory_mb >= 500` is inclusive; 499.99 and the 100 warning level
        # (unused by this checker) emit nothing.
        assert _shape(collector.check_redis_alerts(_redis_metrics(memory_mb=499.99))) == []
        assert _shape(collector.check_redis_alerts(_redis_metrics(memory_mb=100.0))) == []
        assert _shape(collector.check_redis_alerts(_redis_metrics(memory_mb=500.0))) == [
            ("critical", "redis_memory", 500.0, 500.0)
        ]
        # `hit_ratio < 10` is exclusive at exactly 10.
        assert _shape(collector.check_redis_alerts(_redis_metrics(hit_ratio=10.0))) == []
        assert _shape(collector.check_redis_alerts(_redis_metrics(hit_ratio=9.99))) == [
            ("critical", "redis_hit_ratio", 9.99, 10.0)
        ]
        assert _shape(collector.check_redis_alerts(_redis_metrics(hit_ratio=0.0))) == [
            ("critical", "redis_hit_ratio", 0.0, 10.0)
        ]

    def test_postgresql_connection_ratio_boundaries_and_payload(self) -> None:
        collector = _collector()
        assert _shape(collector.check_postgresql_alerts(_db_metrics(active=15))) == []
        assert _shape(collector.check_postgresql_alerts(_db_metrics(active=16))) == []
        # 19/20 == 0.95 hits the critical boundary exactly; value/threshold
        # arithmetic (conn_ratio*100, threshold*100) is pinned as measured.
        assert _shape(collector.check_postgresql_alerts(_db_metrics(active=19))) == [
            ("critical", "pg_connections", 95.0, 95.0)
        ]
        assert _shape(collector.check_postgresql_alerts(_db_metrics(active=1, maximum=1))) == [
            ("critical", "pg_connections", 100.0, 95.0)
        ]

    def test_postgresql_zero_guard(self) -> None:
        collector = _collector()
        assert _shape(collector.check_postgresql_alerts(_db_metrics(active=0, maximum=0))) == []
        assert _shape(collector.check_postgresql_alerts(_db_metrics(active=0, maximum=1))) == []

    def test_postgresql_cache_hit_boundaries(self) -> None:
        collector = _collector()
        assert _shape(collector.check_postgresql_alerts(_db_metrics(cache_hit_ratio=90.0))) == []
        # `cache_hit_ratio < 80` is exclusive at exactly 80.
        assert _shape(collector.check_postgresql_alerts(_db_metrics(cache_hit_ratio=80.0))) == []
        assert _shape(collector.check_postgresql_alerts(_db_metrics(cache_hit_ratio=79.99))) == [
            ("critical", "pg_cache_hit", 79.99, 80.0)
        ]

    def test_postgresql_both_alerts_emitted_in_order(self) -> None:
        collector = _collector()
        assert _shape(
            collector.check_postgresql_alerts(_db_metrics(active=19, cache_hit_ratio=79.0))
        ) == [
            ("critical", "pg_connections", 95.0, 95.0),
            ("critical", "pg_cache_hit", 79.0, 80.0),
        ]


# =============================================================================
# C18 / C19 / C20 / C09 — pynvml init flag, call args, unit conversion
# =============================================================================


def _nvml_stub():
    """Stub pynvml module with a device-0 handle and fractional-watt power."""
    stub = MagicMock()
    stub.nvmlInit.return_value = None
    stub.NVML_TEMPERATURE_GPU = 42
    handle = MagicMock(name="handle")
    stub.nvmlDeviceGetHandleByIndex.return_value = handle
    stub.nvmlDeviceGetName.return_value = b"Test GPU"
    stub.nvmlDeviceGetUtilizationRates.return_value = MagicMock(gpu=50, memory=60)
    stub.nvmlDeviceGetMemoryInfo.return_value = MagicMock(used=10 * 1024**3, total=24 * 1024**3)
    stub.nvmlDeviceGetTemperature.return_value = 65
    stub.nvmlDeviceGetPowerUsage.return_value = 124600
    return stub, handle


class TestPynvmlContract:
    def test_init_success_sets_flag_true(self) -> None:
        stub = MagicMock()
        stub.nvmlInit.return_value = None
        with _stub_pynvml(stub):
            collector = _collector()
        assert stub.nvmlInit.call_count == 1
        assert collector._pynvml_available is True

    def test_init_failure_sets_flag_false(self) -> None:
        stub = MagicMock()
        stub.nvmlInit.side_effect = Exception("NVML down")
        with _stub_pynvml(stub):
            collector = _collector()
        assert collector._pynvml_available is False
        assert collector._collect_gpu_pynvml() is None

    def test_pynvml_queries_device_zero_with_handle(self) -> None:
        stub, handle = _nvml_stub()
        with _stub_pynvml(stub):
            collector = _collector()
            data = collector._collect_gpu_pynvml()

        assert data == {
            "name": "Test GPU",
            "utilization": 50.0,
            "vram_used_gb": 10.0,
            "vram_total_gb": 24.0,
            "temperature": 65,
            "power_watts": 124,
        }
        assert stub.nvmlDeviceGetHandleByIndex.call_args == ((0,), {})
        for fn in (
            stub.nvmlDeviceGetName,
            stub.nvmlDeviceGetUtilizationRates,
            stub.nvmlDeviceGetMemoryInfo,
            stub.nvmlDeviceGetPowerUsage,
        ):
            assert fn.call_args == ((handle,), {})
        assert stub.nvmlDeviceGetTemperature.call_args == ((handle, 42), {})
        # 124600 mW // 1000 -> 124 W (true division would give 124.6)
        assert data["power_watts"] == 124

    async def test_collect_gpu_metrics_prefers_pynvml(self) -> None:
        stub, _ = _nvml_stub()
        with _stub_pynvml(stub):
            collector = _collector()
            with patch.object(collector, "_collect_gpu_fallback", autospec=True) as fallback:
                result = await collector.collect_gpu_metrics()
        assert fallback.call_count == 0
        assert result.model_dump() == {
            "name": "Test GPU",
            "utilization": 50.0,
            "vram_used_gb": 10.0,
            "vram_total_gb": 24.0,
            "temperature": 65,
            "power_watts": 124,
            "vram_percent": 41.66666666666667,
        }

    async def test_pynvml_collection_failure_falls_back(self) -> None:
        stub = MagicMock()
        stub.nvmlInit.return_value = None
        stub.nvmlDeviceGetHandleByIndex.side_effect = Exception("no device")
        with _stub_pynvml(stub):
            collector = _collector()
            assert collector._pynvml_available is True
            assert collector._collect_gpu_pynvml() is None
            with patch.object(collector, "_collect_gpu_fallback", autospec=True) as fallback:
                fallback.return_value = None
                assert await collector.collect_gpu_metrics() is None
        assert fallback.call_count == 1

    async def test_fallback_path_feeds_gpu_metrics(self) -> None:
        stub = MagicMock()
        stub.nvmlInit.side_effect = Exception("NVML down")
        with _stub_pynvml(stub):
            collector = _collector()
            with patch.object(collector, "_collect_gpu_fallback", autospec=True) as fallback:
                fallback.return_value = {
                    "name": "FB GPU",
                    "utilization": 1.0,
                    "vram_used_gb": 2.0,
                    "vram_total_gb": 3.0,
                    "temperature": 40,
                    "power_watts": 50,
                }
                result = await collector.collect_gpu_metrics()
        assert fallback.call_count == 1
        assert result.model_dump() == {
            "name": "FB GPU",
            "utilization": 1.0,
            "vram_used_gb": 2.0,
            "vram_total_gb": 3.0,
            "temperature": 40,
            "power_watts": 50,
            "vram_percent": 66.66666666666666,
        }

    async def test_close_shuts_down_pynvml_and_client(self) -> None:
        stub = MagicMock()
        stub.nvmlInit.return_value = None
        with _stub_pynvml(stub):
            collector = _collector()
            client = await collector._get_http_client()
            await collector.close()
        assert client.is_closed is True
        assert stub.nvmlShutdown.call_count == 1

    async def test_close_without_client_is_safe(self) -> None:
        collector = _collector()
        assert collector._http_client is None
        await collector.close()
        assert collector._http_client is None


# =============================================================================
# C17 — shared http client (timeout + singleton/caching)
# =============================================================================


class TestHttpClientContract:
    async def test_client_timeout_is_exactly_5_seconds(self) -> None:
        collector = _collector()
        try:
            client = await collector._get_http_client()
            assert client.timeout == httpx.Timeout(5.0)
            assert client.timeout.connect == 5.0
            assert client.timeout.read == 5.0
            assert client.timeout.write == 5.0
            assert client.timeout.pool == 5.0
        finally:
            await collector.close()

    async def test_client_is_cached_then_recreated_when_closed(self) -> None:
        collector = _collector()
        try:
            first = await collector._get_http_client()
            assert await collector._get_http_client() is first
            await first.aclose()
            second = await collector._get_http_client()
            assert second is not first
            assert second.is_closed is False
            assert second.timeout == httpx.Timeout(5.0)
        finally:
            await collector.close()


# =============================================================================
# C21 — GPU fallback endpoint, defaults, and truncation
# =============================================================================


class TestGpuFallbackContract:
    async def test_fallback_defaults_when_keys_missing(self) -> None:
        collector = _collector(yolo26_url="http://ai-yolo26:8095")
        client = _http_client({"status": "healthy"})
        with patch.object(collector, "_get_http_client", autospec=True) as get_client:
            get_client.return_value = client
            result = await collector._collect_gpu_fallback()
        assert client.get.call_args == (("http://ai-yolo26:8095/health",), {})
        assert result == {
            "name": "Unknown GPU",
            "utilization": 0,
            "vram_used_gb": 0,
            "vram_total_gb": 24.0,
            "temperature": 0,
            "power_watts": 0,
        }

    async def test_fallback_keeps_reported_values_and_truncates(self) -> None:
        collector = _collector(yolo26_url="http://ai-yolo26:8095")
        client = _http_client(
            {
                "device": "RTX A5500",
                "gpu_utilization": 45.5,
                "vram_used_gb": 12.3,
                "temperature": 65.7,
                "power_watts": 125.9,
            }
        )
        with patch.object(collector, "_get_http_client", autospec=True) as get_client:
            get_client.return_value = client
            result = await collector._collect_gpu_fallback()
        assert client.get.call_args == (("http://ai-yolo26:8095/health",), {})
        assert result == {
            "name": "RTX A5500",
            "utilization": 45.5,
            "vram_used_gb": 12.3,
            "vram_total_gb": 24.0,
            "temperature": 65,
            "power_watts": 125,
        }

    async def test_fallback_null_temperature_and_power_become_zero(self) -> None:
        collector = _collector(yolo26_url="http://ai-yolo26:8095")
        client = _http_client(
            {
                "device": "X",
                "gpu_utilization": 3.25,
                "vram_used_gb": 4.5,
                "temperature": None,
                "power_watts": None,
            }
        )
        with patch.object(collector, "_get_http_client", autospec=True) as get_client:
            get_client.return_value = client
            result = await collector._collect_gpu_fallback()
        assert result == {
            "name": "X",
            "utilization": 3.25,
            "vram_used_gb": 4.5,
            "vram_total_gb": 24.0,
            "temperature": 0,
            "power_watts": 0,
        }

    async def test_fallback_returns_none_when_unavailable(self) -> None:
        collector = _collector(yolo26_url="http://ai-yolo26:8095")
        client = _http_client({"status": "healthy"}, status=503)
        with patch.object(collector, "_get_http_client", autospec=True) as get_client:
            get_client.return_value = client
            assert await collector._collect_gpu_fallback() is None

        failing = _http_client(exc=Exception("refused"))
        with patch.object(collector, "_get_http_client", autospec=True) as get_client:
            get_client.return_value = failing
            assert await collector._collect_gpu_fallback() is None


# =============================================================================
# C22 / C23 — yolo26 and nemotron metric shapes
# =============================================================================


class TestAiModelMetricShapes:
    async def test_yolo26_defaults_when_keys_missing(self) -> None:
        collector = _collector(yolo26_url="http://ai-yolo26:8095")
        client = _http_client({"status": "healthy"})
        with patch.object(collector, "_get_http_client", autospec=True) as get_client:
            get_client.return_value = client
            result = await collector.collect_yolo26_metrics()
        assert client.get.call_args == (("http://ai-yolo26:8095/health",), {})
        assert result.model_dump() == {
            "status": "healthy",
            "vram_gb": 0.0,
            "model": "yolo26",
            "device": "unknown",
        }

    async def test_yolo26_reports_payload_values(self) -> None:
        collector = _collector(yolo26_url="http://ai-yolo26:8095")
        client = _http_client(
            {
                "status": "degraded",
                "vram_used_gb": 7.5,
                "model_name": "yolo26_r50vd",
                "device": "cuda:0",
            }
        )
        with patch.object(collector, "_get_http_client", autospec=True) as get_client:
            get_client.return_value = client
            result = await collector.collect_yolo26_metrics()
        assert result.model_dump() == {
            "status": "unhealthy",
            "vram_gb": 7.5,
            "model": "yolo26_r50vd",
            "device": "cuda:0",
        }

    async def test_yolo26_unreachable_literal(self) -> None:
        collector = _collector(yolo26_url="http://ai-yolo26:8095")
        for client in (
            _http_client({"status": "healthy"}, status=500),
            _http_client(exc=Exception("refused")),
        ):
            with patch.object(collector, "_get_http_client", autospec=True) as get_client:
                get_client.return_value = client
                result = await collector.collect_yolo26_metrics()
            assert result.model_dump() == {
                "status": "unreachable",
                "vram_gb": 0.0,
                "model": "yolo26",
                "device": "unknown",
            }

    async def test_nemotron_slot_state_semantics(self) -> None:
        collector = _collector(nemotron_url="http://ai-llm:8091")
        # A slot with no "state" key counts as idle; the *first* slot supplies
        # context_size (4096 default when it carries no "n_ctx").
        client = _http_client([{"n_ctx": 8192}, {"state": 0, "n_ctx": 4096}])
        with patch.object(collector, "_get_http_client", autospec=True) as get_client:
            get_client.return_value = client
            result = await collector.collect_nemotron_metrics()
        assert client.get.call_args == (("http://ai-llm:8091/slots",), {})
        assert result.model_dump() == {
            "status": "healthy",
            "slots_active": 0,
            "slots_total": 2,
            "context_size": 8192,
        }

        active = _http_client([{"state": 1}, {"state": 2, "n_ctx": 2048}])
        with patch.object(collector, "_get_http_client", autospec=True) as get_client:
            get_client.return_value = active
            result = await collector.collect_nemotron_metrics()
        assert result.model_dump() == {
            "status": "healthy",
            "slots_active": 2,
            "slots_total": 2,
            "context_size": 4096,
        }

        explicit_none = _http_client([{"state": None}])
        with patch.object(collector, "_get_http_client", autospec=True) as get_client:
            get_client.return_value = explicit_none
            result = await collector.collect_nemotron_metrics()
        assert result.model_dump() == {
            "status": "healthy",
            "slots_active": 1,
            "slots_total": 1,
            "context_size": 4096,
        }

    async def test_nemotron_empty_and_mixed_slots(self) -> None:
        collector = _collector(nemotron_url="http://ai-llm:8091")
        empty = _http_client([])
        with patch.object(collector, "_get_http_client", autospec=True) as get_client:
            get_client.return_value = empty
            result = await collector.collect_nemotron_metrics()
        assert result.model_dump() == {
            "status": "healthy",
            "slots_active": 0,
            "slots_total": 0,
            "context_size": 4096,
        }

        mixed = _http_client([{"state": 1, "n_ctx": 4096}, {"state": 0}])
        with patch.object(collector, "_get_http_client", autospec=True) as get_client:
            get_client.return_value = mixed
            result = await collector.collect_nemotron_metrics()
        assert result.model_dump() == {
            "status": "healthy",
            "slots_active": 1,
            "slots_total": 2,
            "context_size": 4096,
        }

    async def test_nemotron_unreachable_literal(self) -> None:
        collector = _collector(nemotron_url="http://ai-llm:8091")
        for client in (_http_client([], status=503), _http_client(exc=Exception("refused"))):
            with patch.object(collector, "_get_http_client", autospec=True) as get_client:
                get_client.return_value = client
                result = await collector.collect_nemotron_metrics()
            assert result.model_dump() == {
                "status": "unreachable",
                "slots_active": 0,
                "slots_total": 0,
                "context_size": 0,
            }


# =============================================================================
# C06b / C24 — host metrics psutil contract
# =============================================================================


class TestHostMetricsContract:
    async def test_reads_root_path_and_keeps_sub_gigabyte_totals(self) -> None:
        with patch("backend.services.performance_collector.psutil", autospec=True) as mock_psutil:
            mock_psutil.cpu_percent.return_value = 10.0
            mock_psutil.virtual_memory.return_value = MagicMock(
                used=0.25 * 1024**3, total=0.5 * 1024**3
            )
            mock_psutil.disk_usage.return_value = MagicMock(
                used=0.1 * 1024**3, total=0.25 * 1024**3
            )
            collector = _collector()
            result = await collector.collect_host_metrics()

        assert mock_psutil.cpu_percent.call_args == ((), {"interval": None})
        assert mock_psutil.disk_usage.call_args == (("/",), {})
        # full model shape, including the computed percents (C06b boundary +
        # any ram_percent/disk_percent computed_field mutation)
        assert result.model_dump() == {
            "cpu_percent": 10.0,
            "ram_used_gb": 0.25,
            "ram_total_gb": 0.5,
            "disk_used_gb": 0.1,
            "disk_total_gb": 0.25,
            "ram_percent": 50.0,
            "disk_percent": 40.0,
        }
        assert _shape(collector.check_host_alerts(result)) == []

    async def test_zero_totals_fall_back_to_one_gigabyte(self) -> None:
        with patch("backend.services.performance_collector.psutil", autospec=True) as mock_psutil:
            mock_psutil.cpu_percent.return_value = 0.0
            mock_psutil.virtual_memory.return_value = MagicMock(used=0, total=0)
            mock_psutil.disk_usage.return_value = MagicMock(used=0, total=0)
            collector = _collector()
            result = await collector.collect_host_metrics()
        assert result.model_dump() == {
            "cpu_percent": 0.0,
            "ram_used_gb": 0.0,
            "ram_total_gb": 1.0,
            "disk_used_gb": 0.0,
            "disk_total_gb": 1.0,
            "ram_percent": 0.0,
            "disk_percent": 0.0,
        }

    async def test_psutil_failures_degrade_to_zeros(self) -> None:
        with patch("backend.services.performance_collector.psutil", autospec=True) as mock_psutil:
            mock_psutil.cpu_percent.side_effect = RuntimeError("no cpu")
            mock_psutil.virtual_memory.side_effect = RuntimeError("no ram")
            mock_psutil.disk_usage.side_effect = RuntimeError("no disk")
            collector = _collector()
            result = await collector.collect_host_metrics()
        assert result.model_dump() == {
            "cpu_percent": 0.0,
            "ram_used_gb": 0.0,
            "ram_total_gb": 1.0,
            "disk_used_gb": 0.0,
            "disk_total_gb": 1.0,
            "ram_percent": 0.0,
            "disk_percent": 0.0,
        }


# =============================================================================
# C25 / C26 / C26b — container health wiring and per-service contracts
# =============================================================================


class TestContainerHealthWiring:
    async def test_collect_container_health_wiring(self) -> None:
        collector = _collector(
            frontend_url="http://frontend:8080/",
            yolo26_url="http://ai-yolo26:8095",
            nemotron_url="http://ai-llm:8091",
        )
        sentinel = object()
        with (
            patch.object(collector, "_get_http_client", autospec=True) as get_client,
            patch.object(collector, "_check_service_health", autospec=True) as service,
            patch.object(collector, "_check_postgres_health", autospec=True) as postgres,
            patch.object(collector, "_check_redis_health", autospec=True) as redis,
        ):
            get_client.return_value = sentinel
            service.return_value = ContainerMetrics(name="x", status="unknown", health="unhealthy")
            postgres.return_value = ContainerMetrics(
                name="postgres", status="unknown", health="unhealthy"
            )
            redis.return_value = ContainerMetrics(
                name="redis", status="unknown", health="unhealthy"
            )
            result = await collector.collect_container_health()

        assert service.call_count == 3
        assert [call.args for call in service.call_args_list] == [
            (sentinel, "frontend", "http://frontend:8080/health"),
            (sentinel, "ai-yolo26", "http://ai-yolo26:8095/health"),
            (sentinel, "ai-llm", "http://ai-llm:8091/health"),
        ]
        assert [call.kwargs for call in service.call_args_list] == [{}, {}, {}]
        assert postgres.call_count == 1
        assert redis.call_count == 1
        assert [c.model_dump() for c in result] == [
            {"name": "backend", "status": "running", "health": "healthy"},
            {"name": "x", "status": "unknown", "health": "unhealthy"},
            {"name": "postgres", "status": "unknown", "health": "unhealthy"},
            {"name": "redis", "status": "unknown", "health": "unhealthy"},
            {"name": "x", "status": "unknown", "health": "unhealthy"},
            {"name": "x", "status": "unknown", "health": "unhealthy"},
        ]

    async def test_check_service_health_request_contract(self) -> None:
        collector = _collector()
        response = MagicMock()
        response.status_code = 200
        client = MagicMock()
        client.get = AsyncMock(return_value=response)
        await collector._check_service_health(client, "svc", "http://svc:1/health")
        assert client.get.call_args == (("http://svc:1/health",), {"timeout": 2.0})

    @pytest.mark.parametrize(
        ("status_code", "exception", "expected"),
        [
            (200, None, ("svc", "running", "healthy")),
            (500, None, ("svc", "running", "unhealthy")),
            (302, None, ("svc", "running", "unhealthy")),
            (None, httpx.ConnectError("nope"), ("svc", "unknown", "unhealthy")),
            (None, httpx.TimeoutException("slow"), ("svc", "running", "unhealthy")),
            (None, ValueError("weird"), ("svc", "unknown", "unhealthy")),
        ],
    )
    async def test_check_service_health_branch_outputs(
        self, status_code, exception, expected
    ) -> None:
        collector = _collector()
        client = MagicMock()
        if exception is not None:
            client.get = AsyncMock(side_effect=exception)
        else:
            response = MagicMock()
            response.status_code = status_code
            client.get = AsyncMock(return_value=response)
        result = await collector._check_service_health(client, "svc", "http://svc:1/health")
        assert (result.name, result.status, result.health) == expected


class TestDatabaseHealthChecks:
    async def test_postgres_health_runs_select_1(self) -> None:
        session = MagicMock()
        queries: list[str] = []

        async def execute(query):
            queries.append(str(query))
            return MagicMock()

        session.execute = execute
        with patch("backend.core.database.get_session_factory", autospec=True) as factory:
            factory.return_value = _SessionCM(session)
            collector = _collector()
            result = await collector._check_postgres_health()
        assert queries == ["SELECT 1"]
        assert (result.name, result.status, result.health) == ("postgres", "running", "healthy")

    async def test_postgres_health_failure_branches(self) -> None:
        for patcher in (
            patch("backend.core.database.get_session_factory", autospec=True, return_value=None),
            patch(
                "backend.core.database.get_session_factory",
                autospec=True,
                side_effect=Exception("db down"),
            ),
        ):
            with patcher:
                collector = _collector()
                result = await collector._check_postgres_health()
            assert (result.name, result.status, result.health) == (
                "postgres",
                "unknown",
                "unhealthy",
            )

    async def test_redis_health_success(self) -> None:
        raw = MagicMock()

        async def ping():
            return True

        raw.ping = ping
        client = MagicMock()
        client._ensure_connected.return_value = raw

        async def init_ok():
            return client

        with patch("backend.core.redis.init_redis", new=init_ok):
            collector = _collector()
            result = await collector._check_redis_health()
        assert (result.name, result.status, result.health) == ("redis", "running", "healthy")

    async def test_redis_health_failure_branches(self) -> None:
        async def init_none():
            return None

        async def init_raises():
            raise Exception("redis down")

        for init in (init_none, init_raises):
            with patch("backend.core.redis.init_redis", new=init):
                collector = _collector()
                result = await collector._check_redis_health()
            assert (result.name, result.status, result.health) == (
                "redis",
                "unknown",
                "unhealthy",
            )


# =============================================================================
# C27 — postgresql metrics query flow and sentinel values
# =============================================================================


class TestPostgresqlMetricsContract:
    async def test_healthy_values_from_query_flow(self) -> None:
        queries: list[str] = []
        session = MagicMock()

        async def execute(query):
            text = str(query)
            queries.append(text)
            result = MagicMock()
            if "pg_stat_activity" in text:
                result.scalar.return_value = 7
            elif "blks_hit" in text:
                result.scalar.return_value = 98.0
            else:
                result.scalar.return_value = 100
            return result

        session.execute = execute
        with patch("backend.core.database.get_session_factory", autospec=True) as factory:
            factory.return_value = _SessionCM(session)
            collector = _collector(database_pool_size=10, database_pool_overflow=20)
            result = await collector.collect_postgresql_metrics()

        assert queries[0] == "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
        assert queries[1].strip().startswith("SELECT")
        assert "blks_hit + blks_read > 0" in queries[1]
        assert "pg_stat_database" in queries[1]
        assert queries[2].strip().startswith("SELECT")
        assert "xact_commit + xact_rollback" in queries[2]
        assert result.model_dump() == {
            "status": "healthy",
            "connections_active": 7,
            "connections_max": 30,
            "cache_hit_ratio": 98.0,
            "transactions_per_min": 100.0,
        }

    async def test_null_and_zero_scalars_use_sentinels(self) -> None:
        for scalar in (None, 0):
            session = MagicMock()

            async def execute(query, scalar_value=scalar):
                result = MagicMock()
                result.scalar.return_value = scalar_value
                return result

            session.execute = execute
            with patch("backend.core.database.get_session_factory", autospec=True) as factory:
                factory.return_value = _SessionCM(session)
                collector = _collector(database_pool_size=10, database_pool_overflow=20)
                result = await collector.collect_postgresql_metrics()
            assert result.model_dump() == {
                "status": "healthy",
                "connections_active": 0,
                "connections_max": 30,
                "cache_hit_ratio": 100.0,
                "transactions_per_min": 0.0,
            }

    async def test_per_query_failures_degrade_inside_session(self) -> None:
        session = MagicMock()

        async def execute(query):
            raise RuntimeError("query down")

        session.execute = execute
        with patch("backend.core.database.get_session_factory", autospec=True) as factory:
            factory.return_value = _SessionCM(session)
            collector = _collector(database_pool_size=10, database_pool_overflow=20)
            result = await collector.collect_postgresql_metrics()
        assert result.model_dump() == {
            "status": "healthy",
            "connections_active": 0,
            "connections_max": 30,
            "cache_hit_ratio": 0.0,
            "transactions_per_min": 0.0,
        }

    async def test_unreachable_literals(self) -> None:
        for patcher in (
            patch("backend.core.database.get_session_factory", autospec=True, return_value=None),
            patch(
                "backend.core.database.get_session_factory",
                autospec=True,
                side_effect=Exception("boom"),
            ),
        ):
            with patcher:
                collector = _collector(database_pool_size=10, database_pool_overflow=20)
                result = await collector.collect_postgresql_metrics()
            assert result.model_dump() == {
                "status": "unreachable",
                "connections_active": 0,
                "connections_max": 30,
                "cache_hit_ratio": 0.0,
                "transactions_per_min": 0.0,
            }


# =============================================================================
# C28 / C29 / C30 — redis info parsing, hit-ratio guard, unreachable literal
# =============================================================================


def _redis_client(info=None, ensure_exc=None):
    raw = MagicMock()

    async def info_coro():
        return info

    raw.info = info_coro
    client = MagicMock()
    if ensure_exc is not None:
        client._ensure_connected.side_effect = ensure_exc
    else:
        client._ensure_connected.return_value = raw
    return client


def _redis_init(client):
    """Build a zero-arg awaitable ``init_redis`` replacement."""

    async def init():
        return client

    return init


async def _redis_init_returning_none():
    return None


async def _redis_init_raising():
    raise Exception("redis down")


class TestRedisMetricsContract:
    async def test_empty_info_payload_stays_healthy_and_zeroed(self) -> None:
        with patch(
            "backend.core.redis.init_redis",
            new=_redis_init(_redis_client({})),
        ):
            collector = _collector()
            result = await collector.collect_redis_metrics()
        assert result.model_dump() == {
            "status": "healthy",
            "connected_clients": 0,
            "memory_mb": 0.0,
            "hit_ratio": 0.0,
            "blocked_clients": 0,
        }

    async def test_full_info_payload(self) -> None:
        info = {
            "connected_clients": 5,
            "used_memory": 2 * 1024 * 1024,
            "keyspace_hits": 1,
            "keyspace_misses": 0,
            "blocked_clients": 7,
        }
        with patch(
            "backend.core.redis.init_redis",
            new=_redis_init(_redis_client(info)),
        ):
            collector = _collector()
            result = await collector.collect_redis_metrics()
        assert result.model_dump() == {
            "status": "healthy",
            "connected_clients": 5,
            "memory_mb": 2.0,
            "hit_ratio": 100.0,
            "blocked_clients": 7,
        }

    async def test_partial_info_payload_hit_ratio_arithmetic(self) -> None:
        info = {
            "connected_clients": 2,
            "used_memory": 1048576,
            "keyspace_hits": 3,
            "keyspace_misses": 1,
        }
        with patch(
            "backend.core.redis.init_redis",
            new=_redis_init(_redis_client(info)),
        ):
            collector = _collector()
            result = await collector.collect_redis_metrics()
        # 3 / (3 + 1) * 100 == 75.0 and blocked_clients defaults to 0.
        assert result.model_dump() == {
            "status": "healthy",
            "connected_clients": 2,
            "memory_mb": 1.0,
            "hit_ratio": 75.0,
            "blocked_clients": 0,
        }

    async def test_zero_total_keeps_ratio_zero(self) -> None:
        for info in (
            {"keyspace_hits": 0, "keyspace_misses": 0, "used_memory": 0},
            {"keyspace_hits": 0, "keyspace_misses": 4},
        ):
            with patch(
                "backend.core.redis.init_redis",
                new=_redis_init(_redis_client(info)),
            ):
                collector = _collector()
                result = await collector.collect_redis_metrics()
            assert result.hit_ratio == 0.0
            assert result.status == "healthy"

    async def test_unreachable_literals(self) -> None:
        for patcher in (
            patch("backend.core.redis.init_redis", new=_redis_init_returning_none),
            patch("backend.core.redis.init_redis", new=_redis_init_raising),
            patch(
                "backend.core.redis.init_redis",
                new=_redis_init(_redis_client(ensure_exc=RuntimeError("down"))),
            ),
        ):
            with patcher:
                collector = _collector()
                result = await collector.collect_redis_metrics()
            assert result.model_dump() == {
                "status": "unreachable",
                "connected_clients": 0,
                "memory_mb": 0.0,
                "hit_ratio": 0.0,
                "blocked_clients": 0,
            }


# =============================================================================
# C31 — throughput helper SQL, cutoff window, and rounding
# =============================================================================


class TestThroughputHelpers:
    async def test_detections_per_minute_query_and_rounding(self) -> None:
        collector = _collector()
        session = AsyncMock()
        result = MagicMock()
        result.scalar.return_value = 151
        session.execute.return_value = result

        value = await collector._get_detections_per_minute(session)
        assert value == 30.2

        statement = session.execute.call_args.args[0]
        assert " ".join(str(statement).split()) == (
            "SELECT count(detections.id) AS count_1 FROM detections "
            "WHERE detections.detected_at >= :detected_at_1"
        )
        whereclause = statement.whereclause
        assert " ".join(str(whereclause).split()) == "detections.detected_at >= :detected_at_1"
        assert whereclause.operator is operator.ge
        cutoff = whereclause.right.value
        assert cutoff.utcoffset() == timedelta(0)
        elapsed = (datetime.now(UTC) - cutoff).total_seconds()
        assert 299.0 <= elapsed <= 306.0

    async def test_events_per_minute_query_and_rounding(self) -> None:
        collector = _collector()
        session = AsyncMock()
        result = MagicMock()
        result.scalar.return_value = 26
        session.execute.return_value = result

        assert await collector._get_events_per_minute(session) == 5.2

        statement = session.execute.call_args.args[0]
        assert " ".join(str(statement).split()) == (
            "SELECT count(events.id) AS count_1 FROM events "
            "WHERE events.started_at >= :started_at_1"
        )
        whereclause = statement.whereclause
        assert whereclause.operator is operator.ge
        assert str(whereclause.left) == "events.started_at"
        assert whereclause.right.value.utcoffset() == timedelta(0)
        elapsed = (datetime.now(UTC) - whereclause.right.value).total_seconds()
        assert 299.0 <= elapsed <= 306.0

        result.scalar.return_value = 1
        assert await collector._get_events_per_minute(session) == 0.2

    async def test_throughput_zero_and_failure_paths(self) -> None:
        collector = _collector()
        for scalar in (0, None):
            session = AsyncMock()
            result = MagicMock()
            result.scalar.return_value = scalar
            session.execute.return_value = result
            assert await collector._get_detections_per_minute(session) == 0.0
            assert await collector._get_events_per_minute(session) == 0.0

        broken = AsyncMock()
        broken.execute.side_effect = Exception("db down")
        assert await collector._get_detections_per_minute(broken) == 0.0
        assert await collector._get_events_per_minute(broken) == 0.0


# =============================================================================
# C32 / C33 / C34 / C35 — inference metrics contract
# =============================================================================


class TestInferenceMetricsContract:
    async def test_stage_calls_and_latency_mapping(self) -> None:
        stage_stats = {
            "watch_to_detect": {"avg_ms": 11.5, "p95_ms": 12.25, "p99_ms": 13.125},
            "batch_to_analyze": {"avg_ms": 21.5, "p95_ms": 22.25, "p99_ms": 23.125},
            "total_pipeline": {"avg_ms": 31.5, "p95_ms": 32.25, "p99_ms": 33.125},
        }
        seen: list[tuple[str, int]] = []

        def stats(stage, window_minutes=None):
            seen.append((stage, window_minutes))
            return dict(stage_stats[stage])

        session = AsyncMock()
        with (
            patch("backend.core.metrics.get_pipeline_latency_tracker", autospec=True) as factory,
            patch("backend.core.database.get_session", autospec=True) as get_session,
        ):
            tracker = MagicMock()
            tracker.get_stage_stats.side_effect = stats
            factory.return_value = tracker
            get_session.return_value = _SessionCM(session)
            collector = _collector()

            async def detections_per_minute(session_arg):
                return 30.2

            async def events_per_minute(session_arg):
                return 5.2

            with (
                patch.object(
                    collector,
                    "_get_detections_per_minute",
                    autospec=True,
                    side_effect=detections_per_minute,
                ) as detections,
                patch.object(
                    collector,
                    "_get_events_per_minute",
                    autospec=True,
                    side_effect=events_per_minute,
                ) as events,
            ):
                result = await collector.collect_inference_metrics()

        assert seen == [
            ("watch_to_detect", 5),
            ("batch_to_analyze", 5),
            ("total_pipeline", 5),
        ]
        assert tracker.get_stage_stats.call_args_list == [
            (("watch_to_detect",), {"window_minutes": 5}),
            (("batch_to_analyze",), {"window_minutes": 5}),
            (("total_pipeline",), {"window_minutes": 5}),
        ]
        # the real session is handed to both throughput helpers
        assert detections.call_args.args[-1] is session
        assert events.call_args.args[-1] is session
        assert result.model_dump() == {
            "yolo26_latency_ms": {"avg": 11.5, "p95": 12.25, "p99": 13.125},
            "nemotron_latency_ms": {"avg": 21.5, "p95": 22.25, "p99": 23.125},
            "pipeline_latency_ms": {"avg": 31.5, "p95": 32.25},
            "throughput": {"images_per_min": 30.2, "events_per_min": 5.2},
            "queues": {"detection": 0, "analysis": 0},
        }

    async def test_partial_stats_fall_back_to_zero(self) -> None:
        def stats(stage, window_minutes=None):
            if stage == "watch_to_detect":
                return {"avg_ms": 5.5}
            if stage == "batch_to_analyze":
                return {"p95_ms": 6.5}
            return {"p99_ms": 7.5}

        session = AsyncMock()
        with (
            patch("backend.core.metrics.get_pipeline_latency_tracker", autospec=True) as factory,
            patch("backend.core.database.get_session", autospec=True) as get_session,
        ):
            tracker = MagicMock()
            tracker.get_stage_stats.side_effect = stats
            factory.return_value = tracker
            get_session.return_value = _SessionCM(session)
            collector = _collector()

            async def zero_throughput(session_arg):
                return 0.0

            with (
                patch.object(
                    collector,
                    "_get_detections_per_minute",
                    autospec=True,
                    side_effect=zero_throughput,
                ),
                patch.object(
                    collector,
                    "_get_events_per_minute",
                    autospec=True,
                    side_effect=zero_throughput,
                ),
            ):
                result = await collector.collect_inference_metrics()

        assert result.model_dump() == {
            "yolo26_latency_ms": {"avg": 5.5, "p95": 0.0, "p99": 0.0},
            "nemotron_latency_ms": {"avg": 0.0, "p95": 6.5, "p99": 0.0},
            "pipeline_latency_ms": {"avg": 0.0, "p95": 0.0},
            "throughput": {"images_per_min": 0.0, "events_per_min": 0.0},
            "queues": {"detection": 0, "analysis": 0},
        }

    async def test_empty_stats_and_db_failure_keep_zero_seeds(self) -> None:
        with (
            patch("backend.core.metrics.get_pipeline_latency_tracker", autospec=True) as factory,
            patch(
                "backend.core.database.get_session",
                autospec=True,
                side_effect=Exception("db down"),
            ),
        ):
            tracker = MagicMock()
            tracker.get_stage_stats.return_value = {}
            factory.return_value = tracker
            collector = _collector()
            result = await collector.collect_inference_metrics()

        assert result is not None
        assert result.model_dump() == {
            "yolo26_latency_ms": {"avg": 0.0, "p95": 0.0, "p99": 0.0},
            "nemotron_latency_ms": {"avg": 0.0, "p95": 0.0, "p99": 0.0},
            "pipeline_latency_ms": {"avg": 0.0, "p95": 0.0},
            "throughput": {"images_per_min": 0.0, "events_per_min": 0.0},
            "queues": {"detection": 0, "analysis": 0},
        }

    async def test_tracker_failure_returns_none(self) -> None:
        with patch(
            "backend.core.metrics.get_pipeline_latency_tracker",
            autospec=True,
            side_effect=Exception("no tracker"),
        ):
            collector = _collector()
            assert await collector.collect_inference_metrics() is None


# =============================================================================
# C15b — collect_all timestamp awareness
# =============================================================================


class TestCollectAllContract:
    async def test_timestamp_is_aware_utc(self) -> None:
        collector = _collector()
        with (
            patch.object(collector, "collect_gpu_metrics", autospec=True, return_value=None),
            patch.object(collector, "collect_yolo26_metrics", autospec=True, return_value=None),
            patch.object(collector, "collect_nemotron_metrics", autospec=True, return_value=None),
            patch.object(collector, "collect_host_metrics", autospec=True, return_value=None),
            patch.object(collector, "collect_postgresql_metrics", autospec=True, return_value=None),
            patch.object(collector, "collect_redis_metrics", autospec=True, return_value=None),
            patch.object(collector, "collect_container_health", autospec=True, return_value=[]),
            patch.object(collector, "collect_inference_metrics", autospec=True, return_value=None),
        ):
            result = await collector.collect_all()

        assert isinstance(result.timestamp, datetime)
        assert result.timestamp.tzinfo is UTC
        assert result.timestamp.utcoffset() == timedelta(0)
        assert 0.0 <= (datetime.now(UTC) - result.timestamp).total_seconds() < 5.0
        assert result.model_dump() == {
            "timestamp": result.timestamp,
            "gpu": None,
            "ai_models": {},
            "nemotron": None,
            "inference": None,
            "databases": {},
            "host": None,
            "containers": [],
            "alerts": [],
        }
