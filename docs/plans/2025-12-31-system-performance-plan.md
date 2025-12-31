# System Performance Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance the existing `/system` monitoring page with comprehensive GPU, AI models, inference stats, databases, and host metrics with real-time WebSocket updates.

**Architecture:** Backend PerformanceCollector service aggregates metrics from nvidia-smi, AI containers, PostgreSQL, Redis, and psutil every 5 seconds. SystemBroadcaster pushes updates via WebSocket. Frontend maintains circular buffers for 5m/15m/60m historical charts.

**Tech Stack:** Python (FastAPI, pynvml, psutil), React (TypeScript, Tremor v3.17.4 charts), WebSocket

**Beads Epic:** `home_security_intelligence-mb89` (21 tasks)

---

## Execution Order

Tasks are ordered for TDD workflow: tests alongside implementation, backend before frontend.

### Phase 1: Backend Foundation (Tasks 1-5)

1. `mb89.1` - Add psutil dependency
2. `mb89.2` - Create Performance schemas (with `mb89.18` tests)
3. `mb89.3` - Create PerformanceCollector service (with `mb89.17` tests)
4. `mb89.4` - Enhance SystemBroadcaster
5. `mb89.5` - Initialize on startup

### Phase 2: Frontend Components (Tasks 6-11)

6. `mb89.6` - TimeRangeSelector
7. `mb89.7` - PerformanceAlerts
8. `mb89.8` - AiModelsPanel
9. `mb89.9` - DatabasesPanel
10. `mb89.10` - HostSystemPanel
11. `mb89.11` - ContainersPanel

All with `mb89.19` component tests.

### Phase 3: Integration (Tasks 12-16)

12. `mb89.12` - usePerformanceMetrics hook (with `mb89.20` tests)
13. `mb89.13` - Enhance GpuStats
14. `mb89.14` - Enhance SystemMonitoringPage
15. `mb89.15` - Update exports
16. `mb89.16` - Remove ObservabilityPanel

### Phase 4: Integration Testing (Task 21)

17. `mb89.21` - WebSocket integration test

---

## Task 1: Backend - Add psutil dependency

**Bead:** `home_security_intelligence-mb89.1`
**Estimate:** 5 min

**Files:**

- Modify: `backend/requirements.txt`

**Step 1: Add psutil to requirements**

```bash
echo "psutil>=5.9.0" >> backend/requirements.txt
```

**Step 2: Install dependency**

```bash
source .venv/bin/activate
pip install psutil
```

**Step 3: Verify installation**

```bash
python -c "import psutil; print(psutil.cpu_percent())"
```

Expected: A number like `12.5`

**Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add psutil for host system metrics"
```

**Step 5: Close bead**

```bash
bd close mb89.1
```

---

## Task 2: Backend - Create Performance schemas

**Bead:** `home_security_intelligence-mb89.2` + `home_security_intelligence-mb89.18`
**Estimate:** 30 min

**Files:**

- Create: `backend/api/schemas/performance.py`
- Create: `backend/tests/unit/test_performance_schemas.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_performance_schemas.py
"""Unit tests for performance schemas."""

import pytest
from api.schemas.performance import (
    GpuMetrics,
    AiModelMetrics,
    NemotronMetrics,
    InferenceMetrics,
    DatabaseMetrics,
    RedisMetrics,
    HostMetrics,
    ContainerMetrics,
    PerformanceAlert,
    PerformanceUpdate,
    TimeRange,
)


class TestGpuMetrics:
    """Tests for GpuMetrics schema."""

    def test_valid_gpu_metrics(self):
        metrics = GpuMetrics(
            name="NVIDIA RTX A5500",
            utilization=38.0,
            vram_used_gb=22.7,
            vram_total_gb=24.0,
            temperature=38,
            power_watts=31,
        )
        assert metrics.name == "NVIDIA RTX A5500"
        assert metrics.utilization == 38.0

    def test_vram_percentage(self):
        metrics = GpuMetrics(
            name="RTX",
            utilization=50,
            vram_used_gb=12.0,
            vram_total_gb=24.0,
            temperature=40,
            power_watts=100,
        )
        assert metrics.vram_percent == 50.0


class TestAiModelMetrics:
    """Tests for AI model metrics schemas."""

    def test_rtdetr_metrics(self):
        metrics = AiModelMetrics(
            status="healthy",
            vram_gb=0.17,
            model="rtdetr_r50vd_coco_o365",
            device="cuda:0",
        )
        assert metrics.status == "healthy"

    def test_nemotron_metrics(self):
        metrics = NemotronMetrics(
            status="healthy",
            slots_active=1,
            slots_total=2,
            context_size=4096,
        )
        assert metrics.slots_active == 1


class TestPerformanceAlert:
    """Tests for alert schema."""

    def test_warning_alert(self):
        alert = PerformanceAlert(
            severity="warning",
            metric="gpu_temperature",
            value=82,
            threshold=80,
            message="GPU temperature high: 82C",
        )
        assert alert.severity == "warning"

    def test_critical_alert(self):
        alert = PerformanceAlert(
            severity="critical",
            metric="vram_usage",
            value=96,
            threshold=95,
            message="VRAM critically high",
        )
        assert alert.severity == "critical"


class TestPerformanceUpdate:
    """Tests for complete performance update."""

    def test_full_update(self):
        update = PerformanceUpdate(
            gpu=GpuMetrics(
                name="RTX",
                utilization=50,
                vram_used_gb=12,
                vram_total_gb=24,
                temperature=40,
                power_watts=100,
            ),
            ai_models={
                "rtdetr": AiModelMetrics(
                    status="healthy", vram_gb=0.17, model="rtdetr", device="cuda:0"
                )
            },
            inference=InferenceMetrics(
                rtdetr_latency_ms={"avg": 45, "p95": 82, "p99": 120},
                nemotron_latency_ms={"avg": 2100, "p95": 4800, "p99": 8200},
                pipeline_latency_ms={"avg": 3200, "p95": 6100},
                throughput={"images_per_min": 12.4, "events_per_min": 2.1},
                queues={"detection": 0, "analysis": 0},
            ),
            databases={
                "postgresql": DatabaseMetrics(
                    status="healthy",
                    connections_active=5,
                    connections_max=30,
                    cache_hit_ratio=98.2,
                    transactions_per_min=1200,
                )
            },
            host=HostMetrics(
                cpu_percent=12,
                ram_used_gb=8.2,
                ram_total_gb=32,
                disk_used_gb=156,
                disk_total_gb=500,
            ),
            containers=[
                ContainerMetrics(name="backend", status="running", health="healthy")
            ],
            alerts=[],
        )
        assert update.gpu.utilization == 50


class TestTimeRange:
    """Tests for time range enum."""

    def test_time_ranges(self):
        assert TimeRange.FIVE_MIN.value == "5m"
        assert TimeRange.FIFTEEN_MIN.value == "15m"
        assert TimeRange.SIXTY_MIN.value == "60m"
```

**Step 2: Run test to verify it fails**

```bash
pytest backend/tests/unit/test_performance_schemas.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'api.schemas.performance'`

**Step 3: Write minimal implementation**

```python
# backend/api/schemas/performance.py
"""Pydantic schemas for system performance metrics."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, computed_field


class TimeRange(str, Enum):
    """Time range options for historical data."""

    FIVE_MIN = "5m"
    FIFTEEN_MIN = "15m"
    SIXTY_MIN = "60m"


class GpuMetrics(BaseModel):
    """GPU metrics from nvidia-smi."""

    name: str
    utilization: float = Field(ge=0, le=100)
    vram_used_gb: float = Field(ge=0)
    vram_total_gb: float = Field(gt=0)
    temperature: int = Field(ge=0)
    power_watts: int = Field(ge=0)

    @computed_field
    @property
    def vram_percent(self) -> float:
        """Calculate VRAM usage percentage."""
        return (self.vram_used_gb / self.vram_total_gb) * 100


class AiModelMetrics(BaseModel):
    """Metrics for RT-DETRv2 model."""

    status: str
    vram_gb: float = Field(ge=0)
    model: str
    device: str


class NemotronMetrics(BaseModel):
    """Metrics for Nemotron LLM."""

    status: str
    slots_active: int = Field(ge=0)
    slots_total: int = Field(ge=0)
    context_size: int = Field(ge=0)


class InferenceMetrics(BaseModel):
    """AI inference latency and throughput metrics."""

    rtdetr_latency_ms: dict[str, float]  # avg, p95, p99
    nemotron_latency_ms: dict[str, float]  # avg, p95, p99
    pipeline_latency_ms: dict[str, float]  # avg, p95
    throughput: dict[str, float]  # images_per_min, events_per_min
    queues: dict[str, int]  # detection, analysis


class DatabaseMetrics(BaseModel):
    """PostgreSQL database metrics."""

    status: str
    connections_active: int = Field(ge=0)
    connections_max: int = Field(ge=0)
    cache_hit_ratio: float = Field(ge=0, le=100)
    transactions_per_min: float = Field(ge=0)


class RedisMetrics(BaseModel):
    """Redis cache metrics."""

    status: str
    connected_clients: int = Field(ge=0)
    memory_mb: float = Field(ge=0)
    hit_ratio: float = Field(ge=0, le=100)
    blocked_clients: int = Field(ge=0)


class HostMetrics(BaseModel):
    """Host system metrics from psutil."""

    cpu_percent: float = Field(ge=0, le=100)
    ram_used_gb: float = Field(ge=0)
    ram_total_gb: float = Field(gt=0)
    disk_used_gb: float = Field(ge=0)
    disk_total_gb: float = Field(gt=0)

    @computed_field
    @property
    def ram_percent(self) -> float:
        """Calculate RAM usage percentage."""
        return (self.ram_used_gb / self.ram_total_gb) * 100

    @computed_field
    @property
    def disk_percent(self) -> float:
        """Calculate disk usage percentage."""
        return (self.disk_used_gb / self.disk_total_gb) * 100


class ContainerMetrics(BaseModel):
    """Container health status."""

    name: str
    status: str  # running, stopped, etc.
    health: str  # healthy, unhealthy, starting


class PerformanceAlert(BaseModel):
    """Alert when metric exceeds threshold."""

    severity: str  # warning, critical
    metric: str
    value: float
    threshold: float
    message: str


class PerformanceUpdate(BaseModel):
    """Complete performance update sent via WebSocket."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    gpu: GpuMetrics | None = None
    ai_models: dict[str, AiModelMetrics | NemotronMetrics] = Field(default_factory=dict)
    nemotron: NemotronMetrics | None = None
    inference: InferenceMetrics | None = None
    databases: dict[str, DatabaseMetrics | RedisMetrics] = Field(default_factory=dict)
    host: HostMetrics | None = None
    containers: list[ContainerMetrics] = Field(default_factory=list)
    alerts: list[PerformanceAlert] = Field(default_factory=list)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}
```

**Step 4: Run test to verify it passes**

```bash
pytest backend/tests/unit/test_performance_schemas.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/api/schemas/performance.py backend/tests/unit/test_performance_schemas.py
git commit -m "feat: add performance metrics schemas with tests"
```

**Step 6: Close beads**

```bash
bd close mb89.2
bd close mb89.18
```

---

## Task 3: Backend - Create PerformanceCollector service

**Bead:** `home_security_intelligence-mb89.3` + `home_security_intelligence-mb89.17`
**Estimate:** 90 min

**Files:**

- Create: `backend/services/performance_collector.py`
- Create: `backend/tests/unit/test_performance_collector.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_performance_collector.py
"""Unit tests for PerformanceCollector service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.performance_collector import PerformanceCollector


@pytest.fixture
def collector():
    """Create a PerformanceCollector instance."""
    return PerformanceCollector()


class TestGpuMetrics:
    """Tests for GPU metrics collection."""

    @pytest.mark.asyncio
    async def test_collect_gpu_metrics_with_pynvml(self, collector):
        """Test GPU metrics collection via pynvml."""
        with patch.object(collector, "_collect_gpu_pynvml") as mock_gpu:
            mock_gpu.return_value = {
                "name": "NVIDIA RTX A5500",
                "utilization": 38.0,
                "vram_used_gb": 22.7,
                "vram_total_gb": 24.0,
                "temperature": 38,
                "power_watts": 31,
            }
            metrics = await collector.collect_gpu_metrics()
            assert metrics is not None
            assert metrics.name == "NVIDIA RTX A5500"
            assert metrics.utilization == 38.0

    @pytest.mark.asyncio
    async def test_collect_gpu_metrics_fallback(self, collector):
        """Test GPU metrics fallback when pynvml unavailable."""
        with patch.object(collector, "_collect_gpu_pynvml", return_value=None):
            with patch.object(collector, "_collect_gpu_fallback") as mock_fallback:
                mock_fallback.return_value = {
                    "name": "Unknown GPU",
                    "utilization": 0,
                    "vram_used_gb": 0,
                    "vram_total_gb": 24.0,
                    "temperature": 0,
                    "power_watts": 0,
                }
                metrics = await collector.collect_gpu_metrics()
                assert metrics is not None
                mock_fallback.assert_called_once()


class TestAiModelMetrics:
    """Tests for AI model metrics collection."""

    @pytest.mark.asyncio
    async def test_collect_rtdetr_metrics(self, collector):
        """Test RT-DETRv2 metrics collection."""
        mock_response = {
            "status": "healthy",
            "vram_used_gb": 0.17,
            "model_name": "rtdetr_r50vd_coco_o365",
            "device": "cuda:0",
        }
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = AsyncMock(
                status_code=200, json=lambda: mock_response
            )
            metrics = await collector.collect_rtdetr_metrics()
            assert metrics is not None
            assert metrics.status == "healthy"

    @pytest.mark.asyncio
    async def test_collect_nemotron_metrics(self, collector):
        """Test Nemotron metrics collection."""
        mock_slots = [
            {"state": 0, "n_ctx": 4096},
            {"state": 1, "n_ctx": 4096},
        ]
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = AsyncMock(status_code=200, json=lambda: mock_slots)
            metrics = await collector.collect_nemotron_metrics()
            assert metrics is not None
            assert metrics.slots_total == 2
            assert metrics.context_size == 4096


class TestHostMetrics:
    """Tests for host system metrics."""

    @pytest.mark.asyncio
    async def test_collect_host_metrics(self, collector):
        """Test host metrics collection via psutil."""
        with patch("psutil.cpu_percent", return_value=12.5):
            with patch("psutil.virtual_memory") as mock_mem:
                mock_mem.return_value = MagicMock(
                    used=8_800_000_000, total=34_359_738_368
                )
                with patch("psutil.disk_usage") as mock_disk:
                    mock_disk.return_value = MagicMock(
                        used=167_503_724_544, total=536_870_912_000
                    )
                    metrics = await collector.collect_host_metrics()
                    assert metrics is not None
                    assert metrics.cpu_percent == 12.5
                    assert metrics.ram_total_gb == pytest.approx(32.0, rel=0.1)


class TestDatabaseMetrics:
    """Tests for database metrics."""

    @pytest.mark.asyncio
    async def test_collect_postgresql_metrics(self, collector):
        """Test PostgreSQL metrics collection."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (5, 98.2, 1200)
        with patch.object(collector, "_execute_pg_query", return_value=mock_result):
            metrics = await collector.collect_postgresql_metrics()
            assert metrics is not None
            assert metrics.connections_active == 5
            assert metrics.cache_hit_ratio == 98.2

    @pytest.mark.asyncio
    async def test_collect_redis_metrics(self, collector):
        """Test Redis metrics collection."""
        mock_info = {
            "connected_clients": 8,
            "used_memory": 1_509_949,
            "keyspace_hits": 100,
            "keyspace_misses": 9900,
            "blocked_clients": 2,
        }
        with patch.object(collector, "_get_redis_info", return_value=mock_info):
            metrics = await collector.collect_redis_metrics()
            assert metrics is not None
            assert metrics.connected_clients == 8
            assert metrics.hit_ratio == pytest.approx(1.0, rel=0.1)


class TestAlertGeneration:
    """Tests for alert threshold checking."""

    def test_gpu_temperature_warning(self, collector):
        """Test GPU temperature warning alert."""
        from api.schemas.performance import GpuMetrics

        gpu = GpuMetrics(
            name="RTX",
            utilization=50,
            vram_used_gb=12,
            vram_total_gb=24,
            temperature=78,
            power_watts=200,
        )
        alerts = collector.check_gpu_alerts(gpu)
        assert len(alerts) == 1
        assert alerts[0].severity == "warning"
        assert "temperature" in alerts[0].metric

    def test_gpu_temperature_critical(self, collector):
        """Test GPU temperature critical alert."""
        from api.schemas.performance import GpuMetrics

        gpu = GpuMetrics(
            name="RTX",
            utilization=50,
            vram_used_gb=12,
            vram_total_gb=24,
            temperature=88,
            power_watts=200,
        )
        alerts = collector.check_gpu_alerts(gpu)
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"


class TestFullCollection:
    """Tests for full metrics collection."""

    @pytest.mark.asyncio
    async def test_collect_all(self, collector):
        """Test collecting all metrics."""
        with patch.object(collector, "collect_gpu_metrics", new_callable=AsyncMock):
            with patch.object(
                collector, "collect_rtdetr_metrics", new_callable=AsyncMock
            ):
                with patch.object(
                    collector, "collect_nemotron_metrics", new_callable=AsyncMock
                ):
                    with patch.object(
                        collector, "collect_host_metrics", new_callable=AsyncMock
                    ):
                        with patch.object(
                            collector,
                            "collect_postgresql_metrics",
                            new_callable=AsyncMock,
                        ):
                            with patch.object(
                                collector, "collect_redis_metrics", new_callable=AsyncMock
                            ):
                                with patch.object(
                                    collector,
                                    "collect_container_health",
                                    new_callable=AsyncMock,
                                ):
                                    update = await collector.collect_all()
                                    assert update is not None
                                    assert update.timestamp is not None
```

**Step 2: Run test to verify it fails**

```bash
pytest backend/tests/unit/test_performance_collector.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'services.performance_collector'`

**Step 3: Write implementation**

```python
# backend/services/performance_collector.py
"""Service for collecting system performance metrics."""

import logging
from datetime import datetime
from typing import Any

import httpx
import psutil

from api.schemas.performance import (
    AiModelMetrics,
    ContainerMetrics,
    DatabaseMetrics,
    GpuMetrics,
    HostMetrics,
    NemotronMetrics,
    PerformanceAlert,
    PerformanceUpdate,
    RedisMetrics,
)
from core.config import settings

logger = logging.getLogger(__name__)

# Alert thresholds
THRESHOLDS = {
    "gpu_temperature": {"warning": 75, "critical": 85},
    "gpu_utilization": {"warning": 90, "critical": 98},
    "gpu_vram": {"warning": 90, "critical": 95},
    "gpu_power": {"warning": 300, "critical": 350},
    "rtdetr_latency_p95": {"warning": 200, "critical": 500},
    "nemotron_latency_p95": {"warning": 10000, "critical": 30000},
    "pg_connections": {"warning": 0.8, "critical": 0.95},  # ratio
    "pg_cache_hit": {"warning": 90, "critical": 80},  # below
    "redis_memory_mb": {"warning": 100, "critical": 500},
    "redis_hit_ratio": {"warning": 50, "critical": 10},  # below
    "host_cpu": {"warning": 80, "critical": 95},
    "host_ram": {"warning": 85, "critical": 95},
    "host_disk": {"warning": 80, "critical": 90},
}


class PerformanceCollector:
    """Collects performance metrics from all system components."""

    def __init__(self):
        """Initialize the collector."""
        self._pynvml_available = False
        self._init_pynvml()
        self._http_client: httpx.AsyncClient | None = None

    def _init_pynvml(self):
        """Try to initialize pynvml for GPU metrics."""
        try:
            import pynvml

            pynvml.nvmlInit()
            self._pynvml_available = True
            logger.info("pynvml initialized successfully")
        except Exception as e:
            logger.warning(f"pynvml not available: {e}")
            self._pynvml_available = False

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=5.0)
        return self._http_client

    async def collect_all(self) -> PerformanceUpdate:
        """Collect all performance metrics."""
        gpu = await self.collect_gpu_metrics()
        rtdetr = await self.collect_rtdetr_metrics()
        nemotron = await self.collect_nemotron_metrics()
        host = await self.collect_host_metrics()
        postgresql = await self.collect_postgresql_metrics()
        redis = await self.collect_redis_metrics()
        containers = await self.collect_container_health()
        inference = await self.collect_inference_metrics()

        # Build AI models dict
        ai_models: dict[str, AiModelMetrics | NemotronMetrics] = {}
        if rtdetr:
            ai_models["rtdetr"] = rtdetr
        if nemotron:
            ai_models["nemotron"] = nemotron

        # Build databases dict
        databases: dict[str, DatabaseMetrics | RedisMetrics] = {}
        if postgresql:
            databases["postgresql"] = postgresql
        if redis:
            databases["redis"] = redis

        # Collect alerts
        alerts: list[PerformanceAlert] = []
        if gpu:
            alerts.extend(self.check_gpu_alerts(gpu))
        if host:
            alerts.extend(self.check_host_alerts(host))
        if postgresql:
            alerts.extend(self.check_postgresql_alerts(postgresql))
        if redis:
            alerts.extend(self.check_redis_alerts(redis))

        return PerformanceUpdate(
            timestamp=datetime.utcnow(),
            gpu=gpu,
            ai_models=ai_models,
            nemotron=nemotron,
            inference=inference,
            databases=databases,
            host=host,
            containers=containers,
            alerts=alerts,
        )

    async def collect_gpu_metrics(self) -> GpuMetrics | None:
        """Collect GPU metrics from pynvml or fallback."""
        data = self._collect_gpu_pynvml()
        if data is None:
            data = await self._collect_gpu_fallback()
        if data:
            return GpuMetrics(**data)
        return None

    def _collect_gpu_pynvml(self) -> dict[str, Any] | None:
        """Collect GPU metrics via pynvml."""
        if not self._pynvml_available:
            return None
        try:
            import pynvml

            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            power = pynvml.nvmlDeviceGetPowerUsage(handle) // 1000  # mW to W

            return {
                "name": name,
                "utilization": float(util.gpu),
                "vram_used_gb": mem.used / (1024**3),
                "vram_total_gb": mem.total / (1024**3),
                "temperature": temp,
                "power_watts": power,
            }
        except Exception as e:
            logger.warning(f"pynvml collection failed: {e}")
            return None

    async def _collect_gpu_fallback(self) -> dict[str, Any] | None:
        """Fallback GPU metrics from AI container health endpoints."""
        try:
            client = await self._get_http_client()
            # Try RT-DETRv2 health endpoint
            resp = await client.get(f"http://{settings.AI_HOST}:8090/health")
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "name": data.get("device", "Unknown GPU"),
                    "utilization": 0,  # Not available from health
                    "vram_used_gb": data.get("vram_used_gb", 0),
                    "vram_total_gb": 24.0,  # Assume A5500
                    "temperature": 0,
                    "power_watts": 0,
                }
        except Exception as e:
            logger.warning(f"GPU fallback failed: {e}")
        return None

    async def collect_rtdetr_metrics(self) -> AiModelMetrics | None:
        """Collect RT-DETRv2 model metrics."""
        try:
            client = await self._get_http_client()
            resp = await client.get(f"http://{settings.AI_HOST}:8090/health")
            if resp.status_code == 200:
                data = resp.json()
                return AiModelMetrics(
                    status="healthy" if data.get("status") == "healthy" else "unhealthy",
                    vram_gb=data.get("vram_used_gb", 0),
                    model=data.get("model_name", "rtdetr"),
                    device=data.get("device", "unknown"),
                )
        except Exception as e:
            logger.warning(f"RT-DETRv2 metrics failed: {e}")
        return AiModelMetrics(
            status="unreachable", vram_gb=0, model="rtdetr", device="unknown"
        )

    async def collect_nemotron_metrics(self) -> NemotronMetrics | None:
        """Collect Nemotron LLM metrics."""
        try:
            client = await self._get_http_client()
            resp = await client.get(f"http://{settings.AI_HOST}:8091/slots")
            if resp.status_code == 200:
                slots = resp.json()
                active = sum(1 for s in slots if s.get("state", 0) != 0)
                context = slots[0].get("n_ctx", 4096) if slots else 4096
                return NemotronMetrics(
                    status="healthy",
                    slots_active=active,
                    slots_total=len(slots),
                    context_size=context,
                )
        except Exception as e:
            logger.warning(f"Nemotron metrics failed: {e}")
        return NemotronMetrics(
            status="unreachable", slots_active=0, slots_total=0, context_size=0
        )

    async def collect_host_metrics(self) -> HostMetrics | None:
        """Collect host system metrics via psutil."""
        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            return HostMetrics(
                cpu_percent=cpu,
                ram_used_gb=mem.used / (1024**3),
                ram_total_gb=mem.total / (1024**3),
                disk_used_gb=disk.used / (1024**3),
                disk_total_gb=disk.total / (1024**3),
            )
        except Exception as e:
            logger.warning(f"Host metrics failed: {e}")
            return None

    async def collect_postgresql_metrics(self) -> DatabaseMetrics | None:
        """Collect PostgreSQL metrics."""
        try:
            from core.database import async_session_maker
            from sqlalchemy import text

            async with async_session_maker() as session:
                # Get connection count
                result = await session.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                )
                active = result.scalar() or 0

                # Get cache hit ratio
                result = await session.execute(
                    text("""
                        SELECT
                            CASE WHEN blks_hit + blks_read > 0
                            THEN 100.0 * blks_hit / (blks_hit + blks_read)
                            ELSE 100.0 END as ratio
                        FROM pg_stat_database
                        WHERE datname = current_database()
                    """)
                )
                cache_hit = result.scalar() or 100.0

                # Get transaction rate (approximate)
                result = await session.execute(
                    text("""
                        SELECT xact_commit + xact_rollback
                        FROM pg_stat_database
                        WHERE datname = current_database()
                    """)
                )
                txns = result.scalar() or 0

                return DatabaseMetrics(
                    status="healthy",
                    connections_active=active,
                    connections_max=settings.DATABASE_POOL_SIZE,
                    cache_hit_ratio=float(cache_hit),
                    transactions_per_min=float(txns),  # Simplified
                )
        except Exception as e:
            logger.warning(f"PostgreSQL metrics failed: {e}")
            return DatabaseMetrics(
                status="unreachable",
                connections_active=0,
                connections_max=30,
                cache_hit_ratio=0,
                transactions_per_min=0,
            )

    async def collect_redis_metrics(self) -> RedisMetrics | None:
        """Collect Redis metrics."""
        try:
            from core.redis_client import redis_client

            info = await redis_client.info()
            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)
            hit_ratio = (hits / (hits + misses) * 100) if (hits + misses) > 0 else 0

            return RedisMetrics(
                status="healthy",
                connected_clients=info.get("connected_clients", 0),
                memory_mb=info.get("used_memory", 0) / (1024 * 1024),
                hit_ratio=hit_ratio,
                blocked_clients=info.get("blocked_clients", 0),
            )
        except Exception as e:
            logger.warning(f"Redis metrics failed: {e}")
            return RedisMetrics(
                status="unreachable",
                connected_clients=0,
                memory_mb=0,
                hit_ratio=0,
                blocked_clients=0,
            )

    async def collect_container_health(self) -> list[ContainerMetrics]:
        """Collect health status of all containers."""
        containers = [
            ("backend", "http://localhost:8000/api/system/health/live"),
            ("frontend", "http://localhost:5173"),
            ("postgres", None),  # Check via psql
            ("redis", None),  # Check via ping
            ("ai-detector", f"http://{settings.AI_HOST}:8090/health"),
            ("ai-llm", f"http://{settings.AI_HOST}:8091/health"),
        ]
        results = []
        client = await self._get_http_client()

        for name, url in containers:
            status = "running"
            health = "healthy"
            if url:
                try:
                    resp = await client.get(url, timeout=2.0)
                    if resp.status_code != 200:
                        health = "unhealthy"
                except Exception:
                    health = "unhealthy"
            results.append(ContainerMetrics(name=name, status=status, health=health))

        return results

    async def collect_inference_metrics(self) -> dict[str, Any] | None:
        """Collect inference latency metrics from PipelineLatencyTracker."""
        try:
            from core.metrics import pipeline_latency

            return {
                "rtdetr_latency_ms": {
                    "avg": pipeline_latency.watch_to_detect.avg * 1000,
                    "p95": pipeline_latency.watch_to_detect.p95 * 1000,
                    "p99": pipeline_latency.watch_to_detect.p99 * 1000,
                },
                "nemotron_latency_ms": {
                    "avg": pipeline_latency.batch_to_analyze.avg * 1000,
                    "p95": pipeline_latency.batch_to_analyze.p95 * 1000,
                    "p99": pipeline_latency.batch_to_analyze.p99 * 1000,
                },
                "pipeline_latency_ms": {
                    "avg": pipeline_latency.total_pipeline.avg * 1000,
                    "p95": pipeline_latency.total_pipeline.p95 * 1000,
                },
                "throughput": {"images_per_min": 0, "events_per_min": 0},
                "queues": {"detection": 0, "analysis": 0},
            }
        except Exception as e:
            logger.warning(f"Inference metrics failed: {e}")
            return None

    def check_gpu_alerts(self, gpu: GpuMetrics) -> list[PerformanceAlert]:
        """Check GPU metrics against thresholds."""
        alerts = []
        t = THRESHOLDS

        if gpu.temperature >= t["gpu_temperature"]["critical"]:
            alerts.append(
                PerformanceAlert(
                    severity="critical",
                    metric="gpu_temperature",
                    value=gpu.temperature,
                    threshold=t["gpu_temperature"]["critical"],
                    message=f"GPU temperature critical: {gpu.temperature}C",
                )
            )
        elif gpu.temperature >= t["gpu_temperature"]["warning"]:
            alerts.append(
                PerformanceAlert(
                    severity="warning",
                    metric="gpu_temperature",
                    value=gpu.temperature,
                    threshold=t["gpu_temperature"]["warning"],
                    message=f"GPU temperature high: {gpu.temperature}C",
                )
            )

        vram_pct = gpu.vram_percent
        if vram_pct >= t["gpu_vram"]["critical"]:
            alerts.append(
                PerformanceAlert(
                    severity="critical",
                    metric="gpu_vram",
                    value=vram_pct,
                    threshold=t["gpu_vram"]["critical"],
                    message=f"GPU VRAM critical: {vram_pct:.1f}%",
                )
            )
        elif vram_pct >= t["gpu_vram"]["warning"]:
            alerts.append(
                PerformanceAlert(
                    severity="warning",
                    metric="gpu_vram",
                    value=vram_pct,
                    threshold=t["gpu_vram"]["warning"],
                    message=f"GPU VRAM high: {vram_pct:.1f}%",
                )
            )

        return alerts

    def check_host_alerts(self, host: HostMetrics) -> list[PerformanceAlert]:
        """Check host metrics against thresholds."""
        alerts = []
        t = THRESHOLDS

        if host.cpu_percent >= t["host_cpu"]["critical"]:
            alerts.append(
                PerformanceAlert(
                    severity="critical",
                    metric="host_cpu",
                    value=host.cpu_percent,
                    threshold=t["host_cpu"]["critical"],
                    message=f"CPU critically high: {host.cpu_percent:.1f}%",
                )
            )
        elif host.cpu_percent >= t["host_cpu"]["warning"]:
            alerts.append(
                PerformanceAlert(
                    severity="warning",
                    metric="host_cpu",
                    value=host.cpu_percent,
                    threshold=t["host_cpu"]["warning"],
                    message=f"CPU high: {host.cpu_percent:.1f}%",
                )
            )

        if host.ram_percent >= t["host_ram"]["critical"]:
            alerts.append(
                PerformanceAlert(
                    severity="critical",
                    metric="host_ram",
                    value=host.ram_percent,
                    threshold=t["host_ram"]["critical"],
                    message=f"RAM critically high: {host.ram_percent:.1f}%",
                )
            )

        if host.disk_percent >= t["host_disk"]["critical"]:
            alerts.append(
                PerformanceAlert(
                    severity="critical",
                    metric="host_disk",
                    value=host.disk_percent,
                    threshold=t["host_disk"]["critical"],
                    message=f"Disk critically full: {host.disk_percent:.1f}%",
                )
            )

        return alerts

    def check_postgresql_alerts(self, db: DatabaseMetrics) -> list[PerformanceAlert]:
        """Check PostgreSQL metrics against thresholds."""
        alerts = []
        t = THRESHOLDS

        conn_ratio = db.connections_active / db.connections_max if db.connections_max > 0 else 0
        if conn_ratio >= t["pg_connections"]["critical"]:
            alerts.append(
                PerformanceAlert(
                    severity="critical",
                    metric="pg_connections",
                    value=conn_ratio * 100,
                    threshold=t["pg_connections"]["critical"] * 100,
                    message=f"PostgreSQL connections critical: {db.connections_active}/{db.connections_max}",
                )
            )

        if db.cache_hit_ratio < t["pg_cache_hit"]["critical"]:
            alerts.append(
                PerformanceAlert(
                    severity="critical",
                    metric="pg_cache_hit",
                    value=db.cache_hit_ratio,
                    threshold=t["pg_cache_hit"]["critical"],
                    message=f"PostgreSQL cache hit ratio critical: {db.cache_hit_ratio:.1f}%",
                )
            )

        return alerts

    def check_redis_alerts(self, redis: RedisMetrics) -> list[PerformanceAlert]:
        """Check Redis metrics against thresholds."""
        alerts = []
        t = THRESHOLDS

        if redis.memory_mb >= t["redis_memory_mb"]["critical"]:
            alerts.append(
                PerformanceAlert(
                    severity="critical",
                    metric="redis_memory",
                    value=redis.memory_mb,
                    threshold=t["redis_memory_mb"]["critical"],
                    message=f"Redis memory critical: {redis.memory_mb:.1f}MB",
                )
            )

        if redis.hit_ratio < t["redis_hit_ratio"]["critical"]:
            alerts.append(
                PerformanceAlert(
                    severity="critical",
                    metric="redis_hit_ratio",
                    value=redis.hit_ratio,
                    threshold=t["redis_hit_ratio"]["critical"],
                    message=f"Redis hit ratio critical: {redis.hit_ratio:.1f}%",
                )
            )

        return alerts

    async def close(self):
        """Close resources."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
        if self._pynvml_available:
            try:
                import pynvml
                pynvml.nvmlShutdown()
            except Exception:
                pass
```

**Step 4: Run test to verify it passes**

```bash
pytest backend/tests/unit/test_performance_collector.py -v
```

**Step 5: Commit**

```bash
git add backend/services/performance_collector.py backend/tests/unit/test_performance_collector.py
git commit -m "feat: add PerformanceCollector service with tests"
```

**Step 6: Close beads**

```bash
bd close mb89.3
bd close mb89.17
```

---

## Remaining Tasks (Summary)

Due to length constraints, subsequent tasks follow the same TDD pattern:

### Task 4: Enhance SystemBroadcaster (mb89.4)

- Add `broadcast_performance()` method
- Integrate with PerformanceCollector for 5-second interval

### Task 5: Initialize on startup (mb89.5)

- Add to `main.py` lifespan handler

### Tasks 6-11: Frontend Components (mb89.6-11)

Each component follows:

1. Write test file (`*.test.tsx`)
2. Run test (expect fail)
3. Create component
4. Run test (expect pass)
5. Commit

### Task 12: usePerformanceMetrics hook (mb89.12)

- WebSocket subscription to `/ws/system`
- Circular buffer management for 5m/15m/60m

### Task 13: Enhance GpuStats (mb89.13)

- Add timeRange prop
- Add AreaCharts

### Task 14: Enhance SystemMonitoringPage (mb89.14)

- Integrate all new components
- Connect hook

### Task 15: Update exports (mb89.15)

- Export from `system/index.ts`

### Task 16: Remove ObservabilityPanel (mb89.16)

- Delete files

### Task 21: Integration test (mb89.21)

- Test WebSocket flow end-to-end

---

## Execution

**Plan complete and saved to `docs/plans/2025-12-31-system-performance-plan.md`.**

Use beads commands to track progress:

```bash
# View all tasks
bd show home_security_intelligence-mb89

# Start a task
bd update mb89.1 --status in_progress

# Complete a task
bd close mb89.1

# View epic progress
bd epic status home_security_intelligence-mb89
```
