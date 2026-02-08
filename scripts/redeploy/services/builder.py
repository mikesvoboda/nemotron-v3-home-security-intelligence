"""Image building with parallel support."""

import asyncio
import time
from typing import ClassVar

from scripts.redeploy.core import output
from scripts.redeploy.core.runtime import ContainerRuntime
from scripts.redeploy.models import (
    BuildError,
    BuildResult,
    BuildStatus,
    DeployConfig,
)


class ImageBuilder:
    """Build container images with parallel support for AI services."""

    # Legacy AI services (individual containers)
    AI_SERVICES_LEGACY: ClassVar[list[str]] = [
        "ai-yolo26",
        "ai-llm",
        "ai-florence",
        "ai-clip",
        "ai-enrichment",
        "ai-enrichment-light",
    ]

    # Gateway AI services (Triton replaces 5 containers, LLM stays separate)
    AI_SERVICES_GATEWAY: ClassVar[list[str]] = [
        "ai-gateway",
        "ai-llm",
    ]

    # Mapping of AI service to Dockerfile location
    AI_DOCKERFILES: ClassVar[dict[str, str]] = {
        "ai-yolo26": "ai/yolo26/Dockerfile",
        "ai-llm": "ai/nemotron/Dockerfile",
        "ai-florence": "ai/florence/Dockerfile",
        "ai-clip": "ai/clip/Dockerfile",
        "ai-enrichment": "ai/enrichment/Dockerfile",
        "ai-enrichment-light": "ai/enrichment-light/Dockerfile",
        "ai-gateway": "ai/gateway/Dockerfile",
    }

    @property
    def ai_services(self) -> list[str]:
        """Active AI services based on gateway mode."""
        if self.config.use_ai_gateway:
            return list(self.ai_services_GATEWAY)
        return list(self.ai_services_LEGACY)

    # Keep AI_SERVICES for backward compat
    AI_SERVICES: ClassVar[list[str]] = AI_SERVICES_LEGACY

    def __init__(self, runtime: ContainerRuntime, config: DeployConfig):
        """Initialize image builder.

        Args:
            runtime: Container runtime instance
            config: Deployment configuration
        """
        self.runtime = runtime
        self.config = config

    # =========================================================================
    # Base image
    # =========================================================================

    async def build_base(self) -> BuildResult:
        """Build the base image used by other services.

        Returns:
            BuildResult for base image
        """
        output.step("Building base image...")
        start = time.monotonic()

        if self.config.dry_run:
            output.dry_run("Would build base image")
            return BuildResult(
                service="base",
                status=BuildStatus.SKIPPED,
                duration=0.0,
            )

        # Build base image
        success = self.runtime.build(
            context=self.config.project_root,
            tag="ghcr.io/mikesvoboda/nemotron-base:latest",
            file=self.config.project_root / "docker" / "base.Dockerfile",
            no_cache=True,
        )

        duration = time.monotonic() - start

        if success:
            output.success(f"Base image built ({duration:.1f}s)")
            return BuildResult(
                service="base",
                status=BuildStatus.SUCCESS,
                duration=duration,
            )
        else:
            output.fail("Base image build failed")
            return BuildResult(
                service="base",
                status=BuildStatus.FAILED,
                duration=duration,
                error="Build failed",
            )

    # =========================================================================
    # Core images (backend, frontend)
    # =========================================================================

    async def build_core(self) -> dict[str, BuildResult]:
        """Build backend and frontend images.

        Returns:
            Dict of service -> BuildResult
        """
        output.header("Building Core Images")

        results: dict[str, BuildResult] = {}

        if self.config.dry_run:
            output.dry_run("Would build backend and frontend")
            return {
                "backend": BuildResult(
                    service="backend",
                    status=BuildStatus.SKIPPED,
                    duration=0.0,
                ),
                "frontend": BuildResult(
                    service="frontend",
                    status=BuildStatus.SKIPPED,
                    duration=0.0,
                ),
            }

        # Use compose to build both
        start = time.monotonic()

        success = self.runtime.compose_build(
            self.config.compose_file_prod,
            services=["backend", "frontend"],
            no_cache=True,
        )

        duration = time.monotonic() - start

        if success:
            output.success(f"Core images built ({duration:.1f}s)")
            results["backend"] = BuildResult(
                service="backend",
                status=BuildStatus.SUCCESS,
                duration=duration / 2,  # Approximate split
            )
            results["frontend"] = BuildResult(
                service="frontend",
                status=BuildStatus.SUCCESS,
                duration=duration / 2,
            )
        else:
            output.fail("Core image build failed")
            results["backend"] = BuildResult(
                service="backend",
                status=BuildStatus.FAILED,
                duration=duration,
                error="Build failed",
            )
            results["frontend"] = BuildResult(
                service="frontend",
                status=BuildStatus.FAILED,
                duration=duration,
                error="Build failed",
            )

        return results

    # =========================================================================
    # AI images (parallel)
    # =========================================================================

    async def build_ai_parallel(self) -> dict[str, BuildResult]:
        """Build all AI images in parallel.

        Returns:
            Dict of service -> BuildResult
        """
        output.header("Building AI Images (parallel)")

        if self.config.dry_run:
            output.dry_run("Would build AI images in parallel")
            return {
                svc: BuildResult(service=svc, status=BuildStatus.SKIPPED, duration=0.0)
                for svc in self.ai_services
            }

        output.step(f"Starting parallel builds for {len(self.ai_services)} AI services...")

        # Create build tasks
        tasks = [self._build_ai_service(service) for service in self.ai_services]

        # Run in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        build_results: dict[str, BuildResult] = {}
        all_success = True

        for service, result in zip(self.ai_services, results, strict=False):
            if isinstance(result, Exception):
                build_results[service] = BuildResult(
                    service=service,
                    status=BuildStatus.FAILED,
                    duration=0.0,
                    error=str(result),
                )
                all_success = False
            else:
                build_results[service] = result
                if not result.success:
                    all_success = False

        # Print summary
        output.build_summary(
            {svc: (r.status.value, r.duration) for svc, r in build_results.items()}
        )

        if all_success:
            output.success("All AI images built")
        else:
            failed = [s for s, r in build_results.items() if not r.success]
            output.fail(f"Some AI builds failed: {failed}")

        return build_results

    async def _build_ai_service(self, service: str) -> BuildResult:
        """Build a single AI service image.

        Args:
            service: Service name (e.g., 'ai-yolo26')

        Returns:
            BuildResult for the service
        """
        output.info(f"Starting {service} build...")
        start = time.monotonic()

        dockerfile = self.AI_DOCKERFILES.get(service)
        if not dockerfile:
            return BuildResult(
                service=service,
                status=BuildStatus.FAILED,
                duration=0.0,
                error=f"Unknown service: {service}",
            )

        dockerfile_path = self.config.project_root / dockerfile
        if not dockerfile_path.exists():
            return BuildResult(
                service=service,
                status=BuildStatus.FAILED,
                duration=0.0,
                error=f"Dockerfile not found: {dockerfile}",
            )

        # Run build asynchronously
        cmd = [
            self.runtime.cmd,
            "build",
            "-t",
            service,
            "-f",
            str(dockerfile_path),
            "--no-cache",
            str(self.config.project_root),
        ]

        result = await self.runtime.process.run_async(
            cmd,
            check=False,
            capture=True,
            timeout=1800,  # 30 minutes max
        )

        duration = time.monotonic() - start

        if result.success:
            output.success(f"{service} built ({duration:.1f}s)")
            return BuildResult(
                service=service,
                status=BuildStatus.SUCCESS,
                duration=duration,
            )
        else:
            output.fail(f"{service} build failed")
            return BuildResult(
                service=service,
                status=BuildStatus.FAILED,
                duration=duration,
                error=result.stderr[:500] if result.stderr else "Build failed",
            )

    async def build_ai_single(self, service: str) -> BuildResult:
        """Build a single AI service image (public interface).

        Args:
            service: Service name

        Returns:
            BuildResult for the service
        """
        return await self._build_ai_service(service)

    async def build_ai_with_yolo26_callback(
        self,
        on_yolo26_complete: asyncio.Future[BuildResult] | None = None,
    ) -> dict[str, BuildResult]:
        """Build AI images with early notification when ai-yolo26 completes.

        This allows TensorRT engine build to start immediately after ai-yolo26
        finishes, running in parallel with the other AI builds.

        Args:
            on_yolo26_complete: Optional future to set when ai-yolo26 build completes

        Returns:
            Dict of service -> BuildResult
        """
        output.header("Building AI Images (parallel)")

        if self.config.dry_run:
            output.dry_run("Would build AI images in parallel")
            if on_yolo26_complete:
                on_yolo26_complete.set_result(
                    BuildResult(service="ai-yolo26", status=BuildStatus.SKIPPED, duration=0.0)
                )
            return {
                svc: BuildResult(service=svc, status=BuildStatus.SKIPPED, duration=0.0)
                for svc in self.ai_services
            }

        output.step(f"Starting parallel builds for {len(self.ai_services)} AI services...")

        # Create individual tasks for each service
        tasks: dict[str, asyncio.Task[BuildResult]] = {}
        for service in self.ai_services:
            tasks[service] = asyncio.create_task(
                self._build_ai_service(service),
                name=f"build-{service}",
            )

        # If we have a callback for yolo26, wait for it specifically first
        # In gateway mode, yolo26 is not built separately — skip callback
        if on_yolo26_complete and "ai-yolo26" not in tasks:
            on_yolo26_complete.set_result(
                BuildResult(service="ai-yolo26", status=BuildStatus.SKIPPED, duration=0.0)
            )
        if on_yolo26_complete and "ai-yolo26" in tasks:
            yolo26_task = tasks["ai-yolo26"]
            try:
                result = await yolo26_task
                on_yolo26_complete.set_result(result)
            except Exception as e:
                on_yolo26_complete.set_exception(e)

        # Wait for all remaining tasks
        build_results: dict[str, BuildResult] = {}
        all_success = True

        for service, task in tasks.items():
            try:
                result = await task
                build_results[service] = result
                if not result.success:
                    all_success = False
            except Exception as e:
                build_results[service] = BuildResult(
                    service=service,
                    status=BuildStatus.FAILED,
                    duration=0.0,
                    error=str(e),
                )
                all_success = False

        # Print summary
        output.build_summary(
            {svc: (r.status.value, r.duration) for svc, r in build_results.items()}
        )

        if all_success:
            output.success("All AI images built")
        else:
            failed = [s for s, r in build_results.items() if not r.success]
            output.fail(f"Some AI builds failed: {failed}")

        return build_results

    # =========================================================================
    # Full build pipeline
    # =========================================================================

    async def build_all(self) -> dict[str, BuildResult]:
        """Build all images (base, core, AI).

        Returns:
            Dict of all service -> BuildResult
        """
        results: dict[str, BuildResult] = {}

        # Build base image
        base_result = await self.build_base()
        results["base"] = base_result
        if not base_result.success:
            raise BuildError("base", "Base image build failed")

        # Build core images
        core_results = await self.build_core()
        results.update(core_results)
        if not all(r.success for r in core_results.values()):
            output.warn("Core image build had failures, continuing with AI builds...")

        # Build AI images in parallel
        ai_results = await self.build_ai_parallel()
        results.update(ai_results)

        return results

    # =========================================================================
    # Pre-build cleanup
    # =========================================================================

    def pre_build_cleanup(self) -> None:
        """Clean up stale layers before building.

        This prevents "layer not known" errors during builds.
        """
        if not self.runtime.is_podman:
            return

        output.step("Pre-build cleanup: clearing stale layers...")

        if self.config.dry_run:
            output.dry_run("Would clean stale layers")
            return

        # Prune dangling images
        self.runtime.prune_images(all=False, force=True)

        # System prune (without volumes)
        self.runtime.prune_system(all=False, volumes=False, force=True)
