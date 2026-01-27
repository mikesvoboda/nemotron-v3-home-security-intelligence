"""Service for collecting system performance metrics.

This service aggregates metrics from:
- GPU (via pynvml or AI container health endpoints)
- AI models (YOLO26v2 and Nemotron)
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
    "yolo26_latency_p95": {"warning": 200, "critical": 500},
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
        yolo26 = await self.collect_yolo26_metrics()
        nemotron = await self.collect_nemotron_metrics()
        host = await self.collect_host_metrics()
        postgresql = await self.collect_postgresql_metrics()
        redis = await self.collect_redis_metrics()
        containers = await self.collect_container_health()
        inference = await self.collect_inference_metrics()

        # Build AI models dict
        ai_models: dict[str, AiModelMetrics | NemotronMetrics] = {}
        if yolo26:
            ai_models["yolo26"] = yolo26
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
        """Fallback GPU metrics from AI container health endpoints.

        Note: The AI container health endpoints may return float values for
        temperature and power_watts. We cast these to int since the GpuMetrics
        schema expects integer values for these fields.
        """
        try:
            client = await self._get_http_client()
            # Try YOLO26 health endpoint
            resp = await client.get(f"{self._settings.yolo26_url}/health")
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "name": data.get("device", "Unknown GPU"),
                    "utilization": data.get("gpu_utilization", 0),
                    "vram_used_gb": data.get("vram_used_gb", 0),
                    "vram_total_gb": 24.0,  # Assume A5500
                    "temperature": int(data.get("temperature", 0)),
                    "power_watts": int(data.get("power_watts", 0)),
                }
        except Exception as e:
            logger.warning(f"GPU fallback failed: {e}")
        return None

    async def collect_yolo26_metrics(self) -> AiModelMetrics | None:
        """Collect YOLO26 model metrics."""
        try:
            client = await self._get_http_client()
            resp = await client.get(f"{self._settings.yolo26_url}/health")
            if resp.status_code == 200:
                data = resp.json()
                return AiModelMetrics(
                    status="healthy" if data.get("status") == "healthy" else "unhealthy",
                    vram_gb=data.get("vram_used_gb", 0),
                    model=data.get("model_name", "yolo26"),
                    device=data.get("device", "unknown"),
                )
        except Exception as e:
            logger.warning(f"YOLO26 metrics failed: {e}")
        return AiModelMetrics(status="unreachable", vram_gb=0, model="yolo26", device="unknown")

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
        """Collect host system metrics via psutil.

        This method gracefully handles container environments where some
        metrics may not be available (e.g., restricted /proc access).
        """
        try:
            # cpu_percent with interval=None uses the delta since last call
            # First call may return 0.0 - this is expected behavior
            cpu = psutil.cpu_percent(interval=None)
            logger.debug(f"Host CPU: {cpu}%")
        except Exception as e:
            logger.warning(f"Host CPU metrics failed (may be container-restricted): {e}")
            cpu = 0.0

        try:
            mem = psutil.virtual_memory()
            ram_used_gb = mem.used / (1024**3)
            ram_total_gb = mem.total / (1024**3)
            logger.debug(f"Host RAM: {ram_used_gb:.2f}/{ram_total_gb:.2f} GB")
        except Exception as e:
            logger.warning(f"Host memory metrics failed (may be container-restricted): {e}")
            ram_used_gb = 0.0
            ram_total_gb = 0.0

        try:
            disk = psutil.disk_usage("/")
            disk_used_gb = disk.used / (1024**3)
            disk_total_gb = disk.total / (1024**3)
            logger.debug(f"Host disk: {disk_used_gb:.2f}/{disk_total_gb:.2f} GB")
        except Exception as e:
            logger.warning(f"Host disk metrics failed (may be container-restricted): {e}")
            disk_used_gb = 0.0
            disk_total_gb = 0.0

        # Return metrics even if some values are zero - partial data is better than no data
        # Note: Schema requires ram_total_gb and disk_total_gb > 0, so use defaults if unavailable
        return HostMetrics(
            cpu_percent=cpu,
            ram_used_gb=ram_used_gb,
            ram_total_gb=ram_total_gb
            if ram_total_gb > 0
            else 1.0,  # Avoid division by zero in percent calc
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb
            if disk_total_gb > 0
            else 1.0,  # Avoid division by zero in percent calc
        )

    async def collect_postgresql_metrics(self) -> DatabaseMetrics | None:
        """Collect PostgreSQL metrics.

        Queries pg_stat_activity and pg_stat_database for connection and
        performance statistics. Returns partial data on errors rather than None.
        """
        try:
            from sqlalchemy import text

            from backend.core.database import get_session_factory

            session_factory = get_session_factory()
            if session_factory is None:
                logger.warning("PostgreSQL session factory is None - database not initialized")
                return DatabaseMetrics(
                    status="unreachable",
                    connections_active=0,
                    connections_max=30,
                    cache_hit_ratio=0,
                    transactions_per_min=0,
                )

            async with session_factory() as session:
                # Get active connection count
                try:
                    result = await session.execute(
                        text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                    )
                    active = result.scalar() or 0
                    logger.debug(f"PostgreSQL active connections: {active}")
                except Exception as e:
                    logger.warning(f"Failed to get PostgreSQL connection count: {e}")
                    active = 0

                # Get cache hit ratio
                try:
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
                    logger.debug(f"PostgreSQL cache hit ratio: {cache_hit:.1f}%")
                except Exception as e:
                    logger.warning(f"Failed to get PostgreSQL cache hit ratio: {e}")
                    cache_hit = 0.0

                # Get transaction count
                try:
                    result = await session.execute(
                        text("""
                            SELECT xact_commit + xact_rollback
                            FROM pg_stat_database
                            WHERE datname = current_database()
                        """)
                    )
                    txns = result.scalar() or 0
                    logger.debug(f"PostgreSQL transactions: {txns}")
                except Exception as e:
                    logger.warning(f"Failed to get PostgreSQL transaction count: {e}")
                    txns = 0

                return DatabaseMetrics(
                    status="healthy",
                    connections_active=active,
                    connections_max=self._settings.database_pool_size
                    + self._settings.database_pool_overflow,
                    cache_hit_ratio=float(cache_hit),
                    transactions_per_min=float(txns),  # Simplified
                )
        except Exception as e:
            logger.error(f"PostgreSQL metrics collection failed: {e}", exc_info=True)
            return DatabaseMetrics(
                status="unreachable",
                connections_active=0,
                connections_max=30,
                cache_hit_ratio=0,
                transactions_per_min=0,
            )

    async def collect_redis_metrics(self) -> RedisMetrics | None:
        """Collect Redis metrics.

        Uses the RedisClient wrapper's _ensure_connected() method to get the
        underlying redis-py client, then calls info() for server statistics.
        """
        try:
            from backend.core.redis import init_redis

            redis_client = await init_redis()
            if redis_client is None:
                logger.warning("Redis client is None - cannot collect metrics")
                return RedisMetrics(
                    status="unreachable",
                    connected_clients=0,
                    memory_mb=0,
                    hit_ratio=0,
                    blocked_clients=0,
                )

            # Get the underlying redis-py client to access info()
            # _ensure_connected() returns the Redis instance from redis-py
            try:
                raw_client = redis_client._ensure_connected()
            except RuntimeError as e:
                logger.warning(f"Redis not connected: {e}")
                return RedisMetrics(
                    status="unreachable",
                    connected_clients=0,
                    memory_mb=0,
                    hit_ratio=0,
                    blocked_clients=0,
                )

            # Call info() to get server statistics
            info = await raw_client.info()
            logger.debug(f"Redis info keys: {list(info.keys())[:10]}...")

            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)
            hit_ratio = (hits / (hits + misses) * 100) if (hits + misses) > 0 else 0

            connected_clients = info.get("connected_clients", 0)
            used_memory = info.get("used_memory", 0)
            blocked_clients = info.get("blocked_clients", 0)

            logger.debug(
                f"Redis metrics: clients={connected_clients}, "
                f"memory={used_memory / (1024 * 1024):.2f}MB, "
                f"hit_ratio={hit_ratio:.1f}%"
            )

            return RedisMetrics(
                status="healthy",
                connected_clients=connected_clients,
                memory_mb=used_memory / (1024 * 1024),
                hit_ratio=hit_ratio,
                blocked_clients=blocked_clients,
            )
        except Exception as e:
            logger.error(f"Redis metrics collection failed: {e}", exc_info=True)
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
        - backend: GET /health (local check - always healthy if we're running)
        - frontend: GET /health (nginx health endpoint, configurable via FRONTEND_URL)
        - postgres: Checked via database metrics (status from collect_postgresql_metrics)
        - redis: Checked via redis ping (status from collect_redis_metrics)
        - ai-yolo26: GET /health (YOLO26 TensorRT health endpoint)
        - ai-llm: GET /health (Nemotron/llama.cpp health endpoint)

        Note: Backend is checked locally since we ARE the backend - if this code is
        running, the backend is healthy. For Docker deployments, frontend/AI services
        use Docker network hostnames configured in settings.
        """
        results: list[ContainerMetrics] = []
        client = await self._get_http_client()

        # Backend: We ARE the backend, so if this code runs, we're healthy
        results.append(ContainerMetrics(name="backend", status="running", health="healthy"))

        # Frontend: Use configurable frontend_url (e.g., http://frontend:80 in Docker)
        frontend_health_url = f"{self._settings.frontend_url.rstrip('/')}/health"
        frontend_health = await self._check_service_health(client, "frontend", frontend_health_url)
        results.append(frontend_health)

        # PostgreSQL: Check via database session (already done in collect_postgresql_metrics)
        # We check if we can reach the database directly
        postgres_health = await self._check_postgres_health()
        results.append(postgres_health)

        # Redis: Check via ping (already done in collect_redis_metrics)
        redis_health = await self._check_redis_health()
        results.append(redis_health)

        # AI YOLO26 (TensorRT): Use configurable yolo26_url
        detector_health = await self._check_service_health(
            client, "ai-yolo26", f"{self._settings.yolo26_url}/health"
        )
        results.append(detector_health)

        # AI LLM (Nemotron): Use configurable nemotron_url
        llm_health = await self._check_service_health(
            client, "ai-llm", f"{self._settings.nemotron_url}/health"
        )
        results.append(llm_health)

        # Log summary of container health
        healthy_count = sum(1 for r in results if r.health == "healthy")
        logger.debug(f"Container health: {healthy_count}/{len(results)} healthy")

        return results

    async def _check_service_health(
        self, client: httpx.AsyncClient, name: str, url: str
    ) -> ContainerMetrics:
        """Check health of an HTTP service.

        Args:
            client: HTTP client to use
            name: Service name for logging/metrics
            url: Health check URL

        Returns:
            ContainerMetrics with health status
        """
        try:
            resp = await client.get(url, timeout=2.0)
            if resp.status_code == 200:
                logger.debug(f"Service {name} healthy at {url}")
                return ContainerMetrics(name=name, status="running", health="healthy")
            else:
                logger.warning(f"Service {name} unhealthy: HTTP {resp.status_code} from {url}")
                return ContainerMetrics(name=name, status="running", health="unhealthy")
        except httpx.ConnectError as e:
            logger.warning(f"Service {name} unreachable: connection failed to {url}: {e}")
            return ContainerMetrics(name=name, status="unknown", health="unhealthy")
        except httpx.TimeoutException:
            logger.warning(f"Service {name} unhealthy: timeout connecting to {url}")
            return ContainerMetrics(name=name, status="running", health="unhealthy")
        except Exception as e:
            logger.warning(f"Service {name} health check failed: {e}")
            return ContainerMetrics(name=name, status="unknown", health="unhealthy")

    async def _check_postgres_health(self) -> ContainerMetrics:
        """Check PostgreSQL health via a simple query."""
        try:
            from sqlalchemy import text

            from backend.core.database import get_session_factory

            session_factory = get_session_factory()
            if session_factory is None:
                return ContainerMetrics(name="postgres", status="unknown", health="unhealthy")

            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
                return ContainerMetrics(name="postgres", status="running", health="healthy")
        except Exception as e:
            logger.warning(f"PostgreSQL health check failed: {e}")
            return ContainerMetrics(name="postgres", status="unknown", health="unhealthy")

    async def _check_redis_health(self) -> ContainerMetrics:
        """Check Redis health via ping."""
        try:
            from backend.core.redis import init_redis

            redis_client = await init_redis()
            if redis_client is None:
                return ContainerMetrics(name="redis", status="unknown", health="unhealthy")

            raw_client = redis_client._ensure_connected()
            await raw_client.ping()  # type: ignore[misc]
            return ContainerMetrics(name="redis", status="running", health="healthy")
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return ContainerMetrics(name="redis", status="unknown", health="unhealthy")

    async def _get_detections_per_minute(self, session: Any) -> float:
        """Get average detections per minute over the last 5 minutes.

        Calculates throughput by counting detections in the last 5 minutes
        and dividing by 5 to get detections per minute. This provides a more
        stable metric than a 60-second window and aligns with other metrics
        like latency calculations.

        Args:
            session: SQLAlchemy async session

        Returns:
            Average number of detections per minute over the last 5 minutes
        """
        try:
            from datetime import timedelta

            from sqlalchemy import func, select

            from backend.models.detection import Detection

            # Use 5-minute window to align with latency metrics
            cutoff = datetime.now(UTC) - timedelta(minutes=5)
            result = await session.execute(
                select(func.count(Detection.id)).where(Detection.detected_at >= cutoff)
            )
            detection_count = result.scalar() or 0
            # Convert to detections per minute
            return round(detection_count / 5.0, 1)
        except Exception as e:
            logger.warning(f"Failed to get detections per minute: {e}")
            return 0.0

    async def _get_events_per_minute(self, session: Any) -> float:
        """Get average events per minute over the last 5 minutes.

        Calculates throughput by counting events in the last 5 minutes
        and dividing by 5 to get events per minute. This provides a more
        stable metric than a 60-second window and aligns with other metrics
        like latency calculations.

        Args:
            session: SQLAlchemy async session

        Returns:
            Average number of events per minute over the last 5 minutes
        """
        try:
            from datetime import timedelta

            from sqlalchemy import func, select

            from backend.models.event import Event

            # Use 5-minute window to align with latency metrics
            cutoff = datetime.now(UTC) - timedelta(minutes=5)
            result = await session.execute(
                select(func.count(Event.id)).where(Event.started_at >= cutoff)
            )
            event_count = result.scalar() or 0
            # Convert to events per minute
            return round(event_count / 5.0, 1)
        except Exception as e:
            logger.warning(f"Failed to get events per minute: {e}")
            return 0.0

    async def collect_inference_metrics(self) -> InferenceMetrics | None:
        """Collect inference latency metrics from PipelineLatencyTracker."""
        try:
            from backend.core.database import get_session
            from backend.core.metrics import get_pipeline_latency_tracker

            tracker = get_pipeline_latency_tracker()

            # Get stats for each pipeline stage (returns dict with avg_ms, p95_ms, p99_ms, etc.)
            yolo26_stats = tracker.get_stage_stats("watch_to_detect", window_minutes=5)
            nemotron_stats = tracker.get_stage_stats("batch_to_analyze", window_minutes=5)
            pipeline_stats = tracker.get_stage_stats("total_pipeline", window_minutes=5)

            # Calculate throughput from database (5-minute window average)
            images_per_min = 0.0
            events_per_min = 0.0
            try:
                async with get_session() as session:
                    images_per_min = await self._get_detections_per_minute(session)
                    events_per_min = await self._get_events_per_minute(session)
            except Exception as e:
                logger.warning(f"Failed to get throughput metrics: {e}")

            return InferenceMetrics(
                yolo26_latency_ms={
                    "avg": yolo26_stats.get("avg_ms") or 0,
                    "p95": yolo26_stats.get("p95_ms") or 0,
                    "p99": yolo26_stats.get("p99_ms") or 0,
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
                throughput={"images_per_min": images_per_min, "events_per_min": events_per_min},
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
        elif host.ram_percent >= t["host_ram"]["warning"]:
            alerts.append(
                PerformanceAlert(
                    severity="warning",
                    metric="host_ram",
                    value=host.ram_percent,
                    threshold=t["host_ram"]["warning"],
                    message=f"RAM high: {host.ram_percent:.1f}%",
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
        elif host.disk_percent >= t["host_disk"]["warning"]:
            alerts.append(
                PerformanceAlert(
                    severity="warning",
                    metric="host_disk",
                    value=host.disk_percent,
                    threshold=t["host_disk"]["warning"],
                    message=f"Disk high: {host.disk_percent:.1f}%",
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
