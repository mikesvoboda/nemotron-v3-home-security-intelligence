"""Service health checking."""

import asyncio
import time

import httpx

from scripts.redeploy.core import output
from scripts.redeploy.models import (
    ContainerStatus,
    DeployConfig,
    HealthCheckError,
    HealthStatus,
)


class HealthChecker:
    """Check health of deployed services."""

    def __init__(self, config: DeployConfig):
        """Initialize health checker.

        Args:
            config: Deployment configuration
        """
        self.config = config
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # Individual service checks
    # =========================================================================

    async def check_backend(self) -> HealthStatus:
        """Check backend health.

        Returns:
            HealthStatus for backend
        """
        url = f"http://localhost:{self.config.api_port}/api/system/health/ready"
        return await self._check_http(url, "backend")

    async def check_postgres(self) -> HealthStatus:
        """Check PostgreSQL health via backend.

        Returns:
            HealthStatus for postgres
        """
        # We check postgres indirectly through the backend health endpoint
        url = f"http://localhost:{self.config.api_port}/api/system/health/ready"
        status = await self._check_http(url, "postgres")

        if status.healthy and status.details:
            db_status = status.details.get("services", {}).get("database", {})
            if db_status.get("status") != "healthy":
                return HealthStatus(
                    service="postgres",
                    status=ContainerStatus.UNHEALTHY,
                    message=db_status.get("message", "Database unhealthy"),
                )

        return status

    async def check_redis(self) -> HealthStatus:
        """Check Redis health via backend.

        Returns:
            HealthStatus for redis
        """
        url = f"http://localhost:{self.config.api_port}/api/system/health/ready"
        status = await self._check_http(url, "redis")

        if status.healthy and status.details:
            redis_status = status.details.get("services", {}).get("redis", {})
            if redis_status.get("status") != "healthy":
                return HealthStatus(
                    service="redis",
                    status=ContainerStatus.UNHEALTHY,
                    message=redis_status.get("message", "Redis unhealthy"),
                )

        return status

    async def check_yolo26(self) -> HealthStatus:
        """Check YOLO26 health.

        Returns:
            HealthStatus for ai-yolo26
        """
        url = f"http://localhost:{self.config.yolo26_port}/health"
        return await self._check_http(url, "ai-yolo26")

    async def check_llm(self) -> HealthStatus:
        """Check LLM health.

        Returns:
            HealthStatus for ai-llm
        """
        url = f"http://localhost:{self.config.llm_port}/health"
        return await self._check_http(url, "ai-llm")

    async def check_florence(self) -> HealthStatus:
        """Check Florence health.

        Returns:
            HealthStatus for ai-florence
        """
        url = f"http://localhost:{self.config.florence_port}/health"
        return await self._check_http(url, "ai-florence")

    async def check_clip(self) -> HealthStatus:
        """Check CLIP health.

        Returns:
            HealthStatus for ai-clip
        """
        url = f"http://localhost:{self.config.clip_port}/health"
        return await self._check_http(url, "ai-clip")

    async def check_enrichment(self) -> HealthStatus:
        """Check Enrichment health.

        Returns:
            HealthStatus for ai-enrichment
        """
        url = f"http://localhost:{self.config.enrichment_port}/health"
        return await self._check_http(url, "ai-enrichment")

    async def check_frontend(self) -> HealthStatus:
        """Check frontend health.

        Returns:
            HealthStatus for frontend
        """
        # Frontend on HTTP port 5173 (mapped from 8080)
        url = "http://localhost:5173"
        return await self._check_http(url, "frontend")

    async def _check_http(self, url: str, service: str) -> HealthStatus:
        """Check health via HTTP endpoint.

        Args:
            url: Health check URL
            service: Service name

        Returns:
            HealthStatus
        """
        try:
            client = await self._get_client()
            response = await client.get(url)

            if response.status_code == 200:
                # Try to parse JSON response for details (ignore parse errors)
                details = None
                try:
                    details = response.json()
                except (ValueError, TypeError):
                    details = None  # Non-JSON response is OK

                return HealthStatus(
                    service=service,
                    status=ContainerStatus.HEALTHY,
                    message="OK",
                    details=details,
                )
            else:
                return HealthStatus(
                    service=service,
                    status=ContainerStatus.UNHEALTHY,
                    message=f"HTTP {response.status_code}",
                )

        except httpx.ConnectError:
            return HealthStatus(
                service=service,
                status=ContainerStatus.STOPPED,
                message="Connection refused",
            )
        except httpx.TimeoutException:
            return HealthStatus(
                service=service,
                status=ContainerStatus.UNHEALTHY,
                message="Timeout",
            )
        except Exception as e:
            return HealthStatus(
                service=service,
                status=ContainerStatus.UNHEALTHY,
                message=str(e),
            )

    # =========================================================================
    # Batch operations
    # =========================================================================

    async def check_all(self) -> dict[str, HealthStatus]:
        """Check health of all services.

        Returns:
            Dict of service name -> HealthStatus
        """
        checks = [
            self.check_backend(),
            self.check_yolo26(),
            self.check_llm(),
            self.check_florence(),
            self.check_clip(),
            self.check_enrichment(),
            self.check_frontend(),
        ]

        results = await asyncio.gather(*checks, return_exceptions=True)

        services = [
            "backend",
            "ai-yolo26",
            "ai-llm",
            "ai-florence",
            "ai-clip",
            "ai-enrichment",
            "frontend",
        ]

        statuses: dict[str, HealthStatus] = {}
        for service, result in zip(services, results, strict=False):
            if isinstance(result, Exception):
                statuses[service] = HealthStatus(
                    service=service,
                    status=ContainerStatus.UNHEALTHY,
                    message=str(result),
                )
            else:
                statuses[service] = result

        return statuses

    async def check_ai_services(self) -> dict[str, HealthStatus]:
        """Check health of AI services only.

        Returns:
            Dict of service name -> HealthStatus
        """
        checks = [
            self.check_yolo26(),
            self.check_llm(),
            self.check_florence(),
            self.check_clip(),
            self.check_enrichment(),
        ]

        results = await asyncio.gather(*checks, return_exceptions=True)

        services = ["ai-yolo26", "ai-llm", "ai-florence", "ai-clip", "ai-enrichment"]

        statuses: dict[str, HealthStatus] = {}
        for service, result in zip(services, results, strict=False):
            if isinstance(result, Exception):
                statuses[service] = HealthStatus(
                    service=service,
                    status=ContainerStatus.UNHEALTHY,
                    message=str(result),
                )
            else:
                statuses[service] = result

        return statuses

    # =========================================================================
    # Wait operations
    # =========================================================================

    async def wait_healthy(
        self,
        services: list[str],
        timeout: int = 120,
        interval: int = 5,
    ) -> bool:
        """Wait for services to become healthy.

        Args:
            services: List of service names to wait for
            timeout: Maximum seconds to wait
            interval: Seconds between checks

        Returns:
            True if all services healthy within timeout

        Raises:
            HealthCheckError: If timeout exceeded
        """
        output.step(f"Waiting for services to become healthy (timeout: {timeout}s)...")

        service_checks = {
            "backend": self.check_backend,
            "postgres": self.check_postgres,
            "redis": self.check_redis,
            "ai-yolo26": self.check_yolo26,
            "ai-llm": self.check_llm,
            "ai-florence": self.check_florence,
            "ai-clip": self.check_clip,
            "ai-enrichment": self.check_enrichment,
            "frontend": self.check_frontend,
        }

        start = time.monotonic()
        pending = set(services)

        while pending and (time.monotonic() - start) < timeout:
            for service in list(pending):
                if service not in service_checks:
                    output.warn(f"Unknown service: {service}")
                    pending.discard(service)
                    continue

                status = await service_checks[service]()
                if status.healthy:
                    output.success(f"{service} is healthy")
                    pending.discard(service)

            if pending:
                await asyncio.sleep(interval)

        if pending:
            raise HealthCheckError(
                next(iter(pending)),
                f"Services not healthy after {timeout}s: {pending}",
            )

        return True

    async def wait_backend_ready(self, timeout: int = 120) -> bool:
        """Wait for backend to be ready (includes DB and Redis).

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if backend ready

        Raises:
            HealthCheckError: If timeout exceeded
        """
        return await self.wait_healthy(["backend"], timeout=timeout)

    async def wait_ai_ready(self, timeout: int = 180) -> bool:
        """Wait for all AI services to be ready.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if all AI services ready

        Raises:
            HealthCheckError: If timeout exceeded
        """
        ai_services = [
            "ai-yolo26",
            "ai-llm",
            "ai-florence",
            "ai-clip",
            "ai-enrichment",
        ]
        return await self.wait_healthy(ai_services, timeout=timeout)

    # =========================================================================
    # Verification
    # =========================================================================

    async def verify_deployment(self) -> bool:
        """Verify entire deployment is healthy.

        Returns:
            True if all services healthy
        """
        output.header("Verifying Deployment")

        statuses = await self.check_all()

        # Print status table
        status_dict = {name: (hs.status.value, hs.message or "") for name, hs in statuses.items()}
        output.status_table(status_dict)

        # Check if all healthy
        all_healthy = all(s.healthy for s in statuses.values())

        if all_healthy:
            output.success("All services healthy")
        else:
            unhealthy = [n for n, s in statuses.items() if not s.healthy]
            output.fail(f"Unhealthy services: {unhealthy}")

        return all_healthy
