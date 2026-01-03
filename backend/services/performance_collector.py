"""Service for collecting system performance metrics.

This service aggregates metrics from:
- GPU (via pynvml or AI container health endpoints)
- AI models (RT-DETRv2 and Nemotron)
- PostgreSQL database
- Redis cache
- Host system (via psutil)
- Container health

Metrics are collected every 5 seconds and broadcast via WebSocket.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import psutil

from backend.api.schemas.performance import (
    AiModelMetrics,
    ContainerMetrics,
    DatabaseMetrics,
    GpuMetrics,
    HostMetrics,
    InferenceMetrics,
    NemotronMetrics,
    PerformanceAlert,
    PerformanceUpdate,
    RedisMetrics,
)
from backend.core.config import get_settings

logger = logging.getLogger(__name__)

# Alert thresholds
THRESHOLDS: dict[str, dict[str, float]] = {
    "gpu_temperature": {"warning": 75, "critical": 85},
    "gpu_utilization": {"warning": 90, "critical": 98},
    "gpu_vram": {"warning": 90, "critical": 95},
    "gpu_power": {"warning": 300, "critical": 350},
    "rtdetr_latency_p95": {"warning": 200, "critical": 500},
    "nemotron_latency_p95": {"warning": 10000, "critical": 30000},
    "pg_connections": {"warning": 0.8, "critical": 0.95},  # ratio
    "pg_cache_hit": {"warning": 90, "critical": 80},  # below these = alert
    "redis_memory_mb": {"warning": 100, "critical": 500},
    "redis_hit_ratio": {"warning": 50, "critical": 10},  # below these = alert
    "host_cpu": {"warning": 80, "critical": 95},
    "host_ram": {"warning": 85, "critical": 95},
    "host_disk": {"warning": 80, "critical": 90},
}


class PerformanceCollector:
    """Collects performance metrics from all system components."""

    def __init__(self) -> None:
        """Initialize the collector."""
        self._pynvml_available = False
        self._init_pynvml()
        self._http_client: httpx.AsyncClient | None = None
        self._settings = get_settings()

    def _init_pynvml(self) -> None:
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
            timestamp=datetime.now(UTC),
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
            resp = await client.get(f"{self._settings.rtdetr_url}/health")
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
            resp = await client.get(f"{self._settings.rtdetr_url}/health")
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
        return AiModelMetrics(status="unreachable", vram_gb=0, model="rtdetr", device="unknown")

    async def collect_nemotron_metrics(self) -> NemotronMetrics | None:
        """Collect Nemotron LLM metrics."""
        try:
            client = await self._get_http_client()
            resp = await client.get(f"{self._settings.nemotron_url}/slots")
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
        return NemotronMetrics(status="unreachable", slots_active=0, slots_total=0, context_size=0)

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
            from sqlalchemy import text

            from backend.core.database import get_session_factory

            session_factory = get_session_factory()
            async with session_factory() as session:
                # Get active connection count
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

                # Get transaction count
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
                    connections_max=30,  # Default pool size
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
            from backend.core.redis import init_redis

            redis_client = await init_redis()
            if redis_client is None:
                return RedisMetrics(
                    status="unreachable",
                    connected_clients=0,
                    memory_mb=0,
                    hit_ratio=0,
                    blocked_clients=0,
                )
            # Get the underlying redis-py client to access info()
            raw_client = redis_client._ensure_connected()
            info = await raw_client.info()
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
        """Collect health status of all containers.

        Uses the following health check endpoints:
        - backend: GET /health (simple liveness probe)
        - frontend: GET /health (nginx health endpoint, configurable via FRONTEND_URL)
        - postgres: None (checked via database metrics)
        - redis: None (checked via redis ping)
        - ai-detector: GET /health (RT-DETRv2 health endpoint)
        - ai-llm: GET /health (Nemotron/llama.cpp health endpoint)
        """
        # Build frontend health URL from configurable frontend_url setting
        frontend_health_url = f"{self._settings.frontend_url.rstrip('/')}/health"
        containers = [
            ("backend", "http://localhost:8000/health"),
            ("frontend", frontend_health_url),
            ("postgres", None),  # Check via psql
            ("redis", None),  # Check via ping
            ("ai-detector", f"{self._settings.rtdetr_url}/health"),
            ("ai-llm", f"{self._settings.nemotron_url}/health"),
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

    async def collect_inference_metrics(self) -> InferenceMetrics | None:
        """Collect inference latency metrics from PipelineLatencyTracker."""
        try:
            from backend.core.metrics import get_pipeline_latency_tracker

            tracker = get_pipeline_latency_tracker()

            # Get stats for each pipeline stage (returns dict with avg_ms, p95_ms, p99_ms, etc.)
            rtdetr_stats = tracker.get_stage_stats("watch_to_detect", window_minutes=5)
            nemotron_stats = tracker.get_stage_stats("batch_to_analyze", window_minutes=5)
            pipeline_stats = tracker.get_stage_stats("total_pipeline", window_minutes=5)

            return InferenceMetrics(
                rtdetr_latency_ms={
                    "avg": rtdetr_stats.get("avg_ms") or 0,
                    "p95": rtdetr_stats.get("p95_ms") or 0,
                    "p99": rtdetr_stats.get("p99_ms") or 0,
                },
                nemotron_latency_ms={
                    "avg": nemotron_stats.get("avg_ms") or 0,
                    "p95": nemotron_stats.get("p95_ms") or 0,
                    "p99": nemotron_stats.get("p99_ms") or 0,
                },
                pipeline_latency_ms={
                    "avg": pipeline_stats.get("avg_ms") or 0,
                    "p95": pipeline_stats.get("p95_ms") or 0,
                },
                throughput={"images_per_min": 0, "events_per_min": 0},
                queues={"detection": 0, "analysis": 0},
            )
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

    async def close(self) -> None:
        """Close resources."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
        if self._pynvml_available:
            try:
                import pynvml

                pynvml.nvmlShutdown()
            except Exception as e:
                logger.debug(f"Error shutting down pynvml: {e}")
