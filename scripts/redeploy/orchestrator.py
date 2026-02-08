"""Deployment orchestrator - coordinates the full deployment workflow."""

import re
import time
from datetime import datetime
from pathlib import Path

from scripts.redeploy.core import output
from scripts.redeploy.models import (
    DeployConfig,
    DeployError,
    DeployMode,
    DeployResult,
)
from scripts.redeploy.services.builder import ImageBuilder
from scripts.redeploy.services.containers import ContainerManager
from scripts.redeploy.services.database import DatabaseManager
from scripts.redeploy.services.git import GitManager
from scripts.redeploy.services.health import HealthChecker
from scripts.redeploy.services.storage import StorageManager
from scripts.redeploy.services.tensorrt import TensorRTBuilder


class DeployOrchestrator:
    """Coordinates the full deployment workflow."""

    def __init__(
        self,
        config: DeployConfig,
        containers: ContainerManager,
        builder: ImageBuilder,
        health: HealthChecker,
        tensorrt: TensorRTBuilder,
        git: GitManager,
        database: DatabaseManager,
        storage: StorageManager,
    ):
        """Initialize orchestrator with all services.

        Args:
            config: Deployment configuration
            containers: Container lifecycle manager
            builder: Image builder
            health: Health checker
            tensorrt: TensorRT builder
            git: Git manager
            database: Database manager
            storage: Storage manager
        """
        self.config = config
        self.containers = containers
        self.builder = builder
        self.health = health
        self.tensorrt = tensorrt
        self.git = git
        self.database = database
        self.storage = storage

    async def deploy(self) -> DeployResult:
        """Execute full deployment workflow.

        Returns:
            DeployResult with success status and details
        """
        start = time.monotonic()
        services_started: list[str] = []

        try:
            # Print banner
            self._print_banner()

            # Phase 1: Pre-flight checks
            await self._pre_flight_checks()

            # Phase 2: Stop containers
            await self._stop_phase()

            # Phase 3: Build images (if not GHCR mode)
            build_results = {}
            if self.config.mode != DeployMode.GHCR:
                build_results = await self._build_phase()

            # Phase 4: Start containers
            services_started = await self._start_phase()

            # Phase 5: Post-deploy tasks
            await self._post_deploy()

            # Phase 6: Verify deployment
            await self._verify_phase()

            # Phase 7: Prune unused images (after containers started)
            self.storage.prune_unused_images()

            duration = time.monotonic() - start
            self._print_success(duration)

            return DeployResult(
                success=True,
                duration=duration,
                services_started=services_started,
                build_results=build_results,
            )

        except DeployError as e:
            duration = time.monotonic() - start
            output.fail(f"Deployment failed: {e}")
            return DeployResult(
                success=False,
                duration=duration,
                error=str(e),
                phase_failed=self._get_phase_name(e),
                services_started=services_started,
            )

        except Exception as e:
            duration = time.monotonic() - start
            output.error(f"Unexpected error: {e}")
            return DeployResult(
                success=False,
                duration=duration,
                error=str(e),
                services_started=services_started,
            )

        finally:
            await self.health.close()

    def _print_banner(self) -> None:
        """Print startup banner."""
        mode_desc = {
            DeployMode.LOCAL: "Local (build all)",
            DeployMode.HYBRID: "Hybrid (GHCR core + local AI)",
            DeployMode.GHCR: "GHCR only (no AI)",
        }

        # Gateway mode reduces AI containers from 6 to 2 (gateway + llm)
        if self.config.use_ai_gateway:
            service_count = {
                DeployMode.LOCAL: 5,  # postgres, redis, ai-gateway, ai-llm, backend, frontend -> but banner shows AI+core
                DeployMode.HYBRID: 5,
                DeployMode.GHCR: 4,
            }
        else:
            service_count = {
                DeployMode.LOCAL: 9,
                DeployMode.HYBRID: 9,
                DeployMode.GHCR: 4,
            }

        output.banner(
            title="Home Security Intelligence Redeploy",
            mode=mode_desc[self.config.mode],
            services=service_count[self.config.mode],
            runtime=self.containers.runtime.compose_cmd,
            dry_run_mode=self.config.dry_run,
            keep_volumes=self.config.keep_volumes,
        )

        output.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    async def _pre_flight_checks(self) -> None:
        """Pre-flight checks: git pull, prerequisites, .env bootstrap."""
        output.header("Pre-flight Checks")

        # Bootstrap .env if missing, then always sync ports from .env.example
        env_path = self.config.project_root / ".env"
        if not env_path.exists():
            output.step("Bootstrapping .env with defaults...")
            self._bootstrap_env()
            output.success(".env created with defaults")

        # Always sync ports from .env.example into .env
        self._sync_env_ports(env_path)

        # Git pull (unless skipped)
        if not self.config.skip_git_pull:
            self.git.update_to_main()
        else:
            output.info("Skipping git pull (--no-git-pull)")

        # Show current state
        branch = self.git.get_current_branch()
        commit = self.git.get_current_commit()
        output.info(f"Branch: {branch} @ {commit}")

    async def _stop_phase(self) -> None:
        """Stop phase: stop containers, verify ports, reset storage."""
        # Volume destruction warning
        if not self.config.keep_volumes:
            output.destructive_warning(
                items=[
                    "PostgreSQL database (all events, detections, settings)",
                    "Redis cache",
                ],
                timeout=5 if not self.config.dry_run else 0,
            )

        # Stop privileged monitoring containers (run with sudo)
        await self.containers.stop_privileged_monitoring()

        # Stop all containers
        await self.containers.stop_all()

        # Reset storage if requested (before building)
        if self.config.reset_storage:
            self.storage.reset_storage()

        # Verify ports are available
        await self.containers.ensure_ports_available()

    async def _build_phase(self) -> dict:
        """Build phase: build all images.

        OPTIMIZATION: Starts infrastructure in parallel with AI builds to reduce
        total deployment time. Infrastructure typically takes 10-15s to become
        healthy, which overlaps with AI build time.
        """
        import asyncio

        # Pre-build cleanup
        self.builder.pre_build_cleanup()

        # Build base image
        base_result = await self.builder.build_base()
        if not base_result.success:
            output.warn("Base image build failed, continuing...")

        # Build core images (backend, frontend)
        core_results = await self.builder.build_core()

        # OPTIMIZATION: Start infrastructure early while building AI images
        # This runs postgres/redis startup in parallel with AI builds
        output.header("Starting Infrastructure + Building AI (parallel)")

        async def start_infra_early() -> None:
            """Start infrastructure services early."""
            try:
                # Process monitoring templates before starting infrastructure
                self.containers.process_monitoring_templates()
                await self.containers.start_infrastructure()
                output.success("Infrastructure started (parallel with AI builds)")
            except Exception as e:
                output.warn(f"Early infrastructure start failed: {e}")

        # Start infrastructure task
        infra_task = asyncio.create_task(start_infra_early())

        # Build AI images in parallel, with TensorRT starting as soon as ai-yolo26 completes
        # This saves ~4 minutes by overlapping TensorRT build with other AI builds
        yolo26_ready: asyncio.Future[object] = asyncio.get_event_loop().create_future()

        async def build_tensorrt_when_ready() -> None:
            """Wait for ai-yolo26 to complete, then start TensorRT build."""
            try:
                result = await yolo26_ready
                if hasattr(result, "success") and result.success:
                    output.info("ai-yolo26 ready, starting TensorRT build in parallel...")
                    await self.tensorrt.rebuild_yolo26_engine()
                else:
                    output.warn("ai-yolo26 build failed, skipping TensorRT rebuild")
            except Exception as e:
                output.warn(f"TensorRT build skipped due to error: {e}")

        # Start TensorRT builder task (will wait for yolo26_ready signal)
        tensorrt_task = asyncio.create_task(build_tensorrt_when_ready())

        # Build all AI images, signaling when ai-yolo26 completes
        ai_results = await self.builder.build_ai_with_yolo26_callback(yolo26_ready)

        # Wait for TensorRT and infrastructure to complete
        await tensorrt_task
        await infra_task

        # Post-build cleanup
        self.storage.prune_build_artifacts()

        return {
            "base": base_result,
            **core_results,
            **ai_results,
        }

    async def _start_phase(self) -> list[str]:
        """Start phase: start all containers in order.

        OPTIMIZATION: Infrastructure may already be started during build phase
        for parallel startup. This phase handles the remaining services.
        """
        output.header("Starting Containers")
        started: list[str] = []

        # Phase 1: Infrastructure (postgres, redis)
        # May already be running from parallel start during build phase
        infra_running = self._check_infrastructure_running()
        if not infra_running:
            # Process monitoring templates before starting infrastructure
            self.containers.process_monitoring_templates()
            output.step("Phase 1: Starting infrastructure services...")
            await self.containers.start_infrastructure()
        else:
            output.info("Infrastructure already running (started during build)")
        started.extend(["postgres", "redis"])

        # Phase 2: AI services
        if self.config.mode != DeployMode.GHCR:
            ai_mode = "gateway" if self.config.use_ai_gateway else "legacy"
            output.step(f"Phase 2: Starting AI services ({ai_mode} mode)...")
            await self.containers.start_ai_services()
            started.extend(self.config.ai_services)

        # Phase 3: Backend
        output.step("Phase 3: Starting backend...")
        await self.containers.start_backend()
        started.append("backend")

        # Phase 4: Frontend
        output.step("Phase 4: Starting frontend...")
        await self.containers.start_frontend()
        started.append("frontend")

        # Phase 5: Privileged monitoring (dcgm-exporter, cadvisor)
        output.step("Phase 5: Starting privileged monitoring...")
        await self.containers.start_privileged_monitoring()
        started.extend(["dcgm-exporter", "cadvisor"])

        output.success("All containers started")
        return started

    def _check_infrastructure_running(self) -> bool:
        """Check if infrastructure services are already running."""
        try:
            containers = self.containers.runtime.ps()
            names = [c.name.lower() for c in containers]
            postgres_up = any("postgres" in n for n in names)
            redis_up = any("redis" in n for n in names)
            return postgres_up and redis_up
        except Exception:
            return False

    async def _post_deploy(self) -> None:
        """Post-deploy tasks: migrations, seeding."""
        output.header("Post-Deploy Tasks")

        # Run migrations
        self.database.run_migrations()

        # Seed files if requested
        if self.config.seed_files_count > 0:
            self.database.seed_files(self.config.seed_files_count)

    async def _verify_phase(self) -> None:
        """Verify phase: health checks."""
        # Wait for all services to be healthy
        services_to_check = ["backend", "frontend"]
        if self.config.mode != DeployMode.GHCR:
            if self.config.use_ai_gateway:
                services_to_check.extend(["ai-gateway", "ai-llm"])
            else:
                services_to_check.extend(
                    [
                        "ai-yolo26",
                        "ai-llm",
                        "ai-florence",
                        "ai-clip",
                        "ai-enrichment",
                    ]
                )

        await self.health.wait_healthy(services_to_check, timeout=180)

        # Final verification
        await self.health.verify_deployment()

    def _print_success(self, duration: float) -> None:
        """Print success message with summary."""
        output.header("Deployment Complete")
        output.success(f"Total time: {duration:.1f}s")

        # Print access URLs
        output.info("Frontend: https://localhost:8444")
        output.info(f"Backend:  http://localhost:{self.config.api_port}")
        output.info(f"API Docs: http://localhost:{self.config.api_port}/docs")

    def _bootstrap_env(self) -> None:
        """Bootstrap .env file using setup.py --defaults."""
        import subprocess

        setup_script = self.config.project_root / "setup.py"
        if not setup_script.exists():
            raise DeployError(f"setup.py not found at {setup_script}")

        result = subprocess.run(
            ["python3", str(setup_script), "--defaults"],
            check=False,
            cwd=self.config.project_root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            output.error(f"setup.py failed: {result.stderr}")
            raise DeployError("Failed to bootstrap .env")

    def _sync_env_ports(self, env_path: Path) -> None:
        """Sync port values from .env.example into .env.

        .env.example is the single source of truth for ports.
        This preserves secrets (passwords, JWT, paths) in .env while
        ensuring port assignments never drift from .env.example.
        """
        env_example_path = self.config.project_root / ".env.example"
        if not env_example_path.exists():
            output.warn(".env.example not found, skipping port sync")
            return

        # Extract all *_PORT= lines from .env.example
        example_content = env_example_path.read_text(encoding="utf-8")
        port_pattern = re.compile(r"^([A-Z_]+_PORT)=(\d+)$", re.MULTILINE)
        example_ports = dict(port_pattern.findall(example_content))

        if not example_ports:
            return

        # Update matching lines in .env
        env_content = env_path.read_text(encoding="utf-8")
        updated = 0
        for var_name, port_value in example_ports.items():
            env_pattern = re.compile(rf"^{re.escape(var_name)}=\d+$", re.MULTILINE)
            if env_pattern.search(env_content):
                new_line = f"{var_name}={port_value}"
                old_match = env_pattern.search(env_content)
                if old_match and old_match.group() != new_line:
                    env_content = env_pattern.sub(new_line, env_content)
                    updated += 1

        if updated > 0:
            env_path.write_text(env_content, encoding="utf-8")
            output.info(f"Synced {updated} port(s) from .env.example into .env")
        else:
            output.info("All ports in .env match .env.example")

    def _get_phase_name(self, error: DeployError) -> str:
        """Get phase name from error type."""
        from scripts.redeploy.models import (
            BuildError,
            ContainerError,
            HealthCheckError,
            MigrationError,
            PortConflictError,
            StorageError,
        )

        if isinstance(error, PortConflictError | StorageError):
            return "stop"
        elif isinstance(error, BuildError):
            return "build"
        elif isinstance(error, ContainerError):
            return "start"
        elif isinstance(error, HealthCheckError):
            return "verify"
        elif isinstance(error, MigrationError):
            return "post-deploy"
        else:
            return "unknown"
