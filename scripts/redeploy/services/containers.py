"""Container lifecycle management."""

import asyncio
import re
from typing import ClassVar

from scripts.redeploy.core import output
from scripts.redeploy.core.runtime import ContainerRuntime
from scripts.redeploy.models import (
    ContainerError,
    ContainerStatus,
    DeployConfig,
    HealthStatus,
    PortConflictError,
    PortStatus,
)


class ContainerManager:
    """High-level container lifecycle management."""

    # Required ports for the application
    REQUIRED_PORTS: ClassVar[dict[int, str]] = {
        5432: "PostgreSQL",
        6379: "Redis",
        8000: "Backend API",
        8091: "LLM",
        8092: "Florence",
        8093: "CLIP",
        8094: "Enrichment",
        8095: "YOLO26",
    }

    # Container name patterns to match across all worktrees/sessions
    PROJECT_PATTERNS: ClassVar[list[str]] = [
        "nemotron",
        "security",
        "ai-yolo",
        "ai-llm",
        "ai-florence",
        "ai-clip",
        "ai-enrichment",
        "backend",
        "frontend",
        "postgres",
        "redis",
        # Observability services
        "pyroscope",
        "loki",
        "alloy",
        "prometheus",
        "grafana",
        "alertmanager",
        "cadvisor",
        "node-exporter",
        "jaeger",
    ]

    # Standalone containers (started with 'run', not compose)
    STANDALONE_CONTAINERS: ClassVar[list[str]] = [
        "ai-yolo26",
        "ai-llm",
        "ai-florence",
        "ai-clip",
        "ai-enrichment",
        "backend",
        "frontend",
    ]

    def __init__(self, runtime: ContainerRuntime, config: DeployConfig):
        """Initialize container manager.

        Args:
            runtime: Container runtime instance
            config: Deployment configuration
        """
        self.runtime = runtime
        self.config = config

    # =========================================================================
    # Stop operations
    # =========================================================================

    async def stop_all(self) -> None:
        """Stop all project containers in correct order."""
        output.header("Stopping All Containers")

        # 1. Stop standalone containers (AI services, backend, frontend)
        output.step("Stopping standalone containers...")
        await self.stop_standalone()

        # 2. Stop compose containers from both compose files
        output.step("Stopping compose containers...")
        await self.stop_compose(self.config.compose_file_prod)
        await self.stop_compose(self.config.compose_file_ghcr)

        # 3. Clean up pods (Podman)
        if self.runtime.is_podman:
            output.step("Cleaning up pods...")
            self.runtime.pod_rm(all=True, force=True)

        # 4. Prune stopped containers
        output.step("Pruning stopped containers...")
        self.runtime.process.run(
            [self.runtime.cmd, "container", "prune", "-f"],
            check=False,
            capture=True,
        )

        output.success("Containers stopped")

    async def stop_standalone(self) -> None:
        """Stop containers started with 'run' (not compose)."""
        for name in self.STANDALONE_CONTAINERS:
            if self.runtime.exists(name):
                output.info(f"Stopping {name}...")
                self.runtime.stop(name, timeout=10)
                self.runtime.rm(name, force=True)

    async def stop_compose(self, compose_file: Path) -> None:  # noqa: F821
        """Stop containers from a compose file.

        Args:
            compose_file: Path to compose file
        """
        if not compose_file.exists():
            return

        volumes = not self.config.keep_volumes
        success = self.runtime.compose_down(
            compose_file,
            volumes=volumes,
            remove_orphans=True,
        )

        if success:
            output.success(f"Stopped containers from {compose_file.name}")
        else:
            output.info(f"No containers from {compose_file.name}")

    async def stop_all_matching(self) -> int:
        """Stop ALL containers matching project patterns.

        This is the nuclear option - stops containers from any worktree
        or session that match our patterns.

        Returns:
            Number of containers stopped
        """
        output.step("Stopping all project-related containers...")

        containers = self.runtime.ps(all=True)
        stopped = 0

        for container in containers:
            for pattern in self.PROJECT_PATTERNS:
                if pattern in container.name.lower():
                    output.info(f"Stopping: {container.name}")
                    self.runtime.stop(container.name, timeout=10)
                    self.runtime.rm(container.name, force=True)
                    stopped += 1
                    break

        # Also remove all pods
        if self.runtime.is_podman:
            self.runtime.pod_rm(all=True, force=True)

        if stopped > 0:
            output.success(f"Stopped {stopped} containers")

        return stopped

    # =========================================================================
    # Port verification
    # =========================================================================

    def verify_ports_available(self) -> PortStatus:
        """Check if required ports are free.

        Returns:
            PortStatus with ports_in_use and blocking_containers
        """
        ports_in_use: dict[int, str] = {}
        blocking_containers: list[str] = []

        # Use ss to check listening ports
        result = self.runtime.process.run(
            ["ss", "-tlnp"],
            check=False,
            capture=True,
        )

        if not result.success:
            # Can't check ports, assume they're free
            return PortStatus(ports_in_use={}, blocking_containers=[])

        for port, service in self.config.required_ports.items():
            # Check if port is in ss output
            pattern = rf":{port}\s"
            if re.search(pattern, result.stdout):
                ports_in_use[port] = service

                # Try to identify what's using the port
                for line in result.stdout.split("\n"):
                    if f":{port} " in line:
                        # Extract PID from ss output
                        pid_match = re.search(r"pid=(\d+)", line)
                        if pid_match:
                            pid = pid_match.group(1)
                            # Check if it's a container process
                            if "conmon" in line or "rootlessport" in line:
                                # Find container using this port
                                container = self._find_container_by_port(port)
                                if container and container not in blocking_containers:
                                    blocking_containers.append(container)

        return PortStatus(
            ports_in_use=ports_in_use,
            blocking_containers=blocking_containers,
        )

    def _find_container_by_port(self, port: int) -> str | None:
        """Find container using a specific port."""
        for container in self.runtime.ps():
            if port in container.ports.values():
                return container.name
        return None

    def kill_port_holders(self) -> None:
        """Force-kill processes holding required ports."""
        result = self.runtime.process.run(
            ["ss", "-tlnp"],
            check=False,
            capture=True,
        )

        if not result.success:
            return

        pids_to_kill: set[str] = set()

        for port in self.config.required_ports:
            for line in result.stdout.split("\n"):
                if f":{port} " in line:
                    pid_match = re.search(r"pid=(\d+)", line)
                    if pid_match:
                        pids_to_kill.add(pid_match.group(1))

        for pid in pids_to_kill:
            output.info(f"Killing process {pid}")
            self.runtime.process.run(
                ["kill", pid],
                check=False,
                capture=True,
            )

    def ensure_ports_available(self) -> None:
        """Ensure all required ports are available, escalating if needed.

        Raises:
            PortConflictError: If ports cannot be freed
        """
        # First check
        status = self.verify_ports_available()
        if status.all_free:
            output.success("All required ports are available")
            return

        output.warn(f"Ports in use: {list(status.ports_in_use.keys())}")

        # Try stopping matching containers
        output.step("Attempting to free ports...")
        asyncio.get_event_loop().run_until_complete(self.stop_all_matching())

        # Check again
        status = self.verify_ports_available()
        if status.all_free:
            output.success("Ports freed")
            return

        # Last resort: kill processes directly
        output.warn("Still have ports in use, killing processes...")
        self.kill_port_holders()

        # Give processes time to die
        import time

        time.sleep(2)

        # Final check
        status = self.verify_ports_available()
        if not status.all_free:
            raise PortConflictError(status.ports_in_use)

        output.success("All required ports are available")

    # =========================================================================
    # Start operations
    # =========================================================================

    async def start_infrastructure(self) -> None:
        """Start PostgreSQL, Redis, and observability services."""
        output.step("Starting infrastructure services...")

        # Ensure network exists
        network = f"{self.config.project_name}_security-net"
        if not self.runtime.network_exists(network):
            self.runtime.network_create(network)

        # Start core infrastructure (postgres, redis)
        success = self.runtime.compose_up(
            self.config.compose_file_prod,
            services=["postgres", "redis"],
            detach=True,
        )

        if not success:
            raise ContainerError("infrastructure", "start", "Failed to start postgres/redis")

        output.success("Core infrastructure started")

        # Start observability services (pyroscope, loki must start before alloy)
        # NOTE: cadvisor and dcgm-exporter are started separately with sudo podman
        # because they require privileged access (see start_privileged_monitoring)
        output.step("Starting observability services...")
        observability_services = [
            "pyroscope",
            "loki",
            "prometheus",
            "grafana",
            "blackbox-exporter",
            "json-exporter",
            "redis-exporter",
            "node-exporter",
            "jaeger",
            "alertmanager",
        ]

        success = self.runtime.compose_up(
            self.config.compose_file_prod,
            services=observability_services,
            detach=True,
        )

        if not success:
            output.warn("Some observability services failed to start (non-fatal)")
        else:
            output.success("Observability services started")

        # Start alloy after pyroscope and loki are up (has depends_on)
        success = self.runtime.compose_up(
            self.config.compose_file_prod,
            services=["alloy"],
            detach=True,
        )

        if not success:
            output.warn("Alloy failed to start (non-fatal)")
        else:
            output.success("Alloy started")

        output.success("Infrastructure services started")

    async def start_ai_services(self) -> None:
        """Start all AI services with GPU assignments."""
        output.step("Starting AI services...")

        network = f"{self.config.project_name}_security-net"

        # AI service configurations
        ai_configs = [
            {
                "name": "ai-yolo26",
                "image": "ai-yolo26",
                "port": self.config.yolo26_port,
                "gpu": self.config.gpu_ai_services,
                "volumes": [
                    f"{self.config.ai_models_path}/model-zoo/yolo26:/models/yolo26:ro,z",
                ],
                "env": {
                    "YOLO26_CONFIDENCE": str(self.config.yolo26_confidence),
                    "YOLO26_MODEL_PATH": "/models/yolo26/exports/yolo26m_fp16.engine",
                },
            },
            {
                "name": "ai-llm",
                "image": "ai-llm",
                "port": self.config.llm_port,
                "gpu": self.config.gpu_llm,
                "volumes": [
                    f"{self.config.ai_models_path}/nemotron/nemotron-3-nano-30b-a3b-q4km:/models:ro,z",
                ],
                "env": {
                    "GPU_LAYERS": "40",
                    "CTX_SIZE": "65536",
                },
            },
            {
                "name": "ai-florence",
                "image": "ai-florence",
                "port": self.config.florence_port,
                "gpu": self.config.gpu_florence,
                "volumes": [
                    f"{self.config.ai_models_path}/model-zoo/florence-2-large:/models/florence-2-large:ro,z",
                ],
                "env": {
                    "MODEL_PATH": "/models/florence-2-large",
                },
            },
            {
                "name": "ai-clip",
                "image": "ai-clip",
                "port": self.config.clip_port,
                "gpu": self.config.gpu_clip,
                "volumes": [
                    f"{self.config.ai_models_path}/model-zoo/clip-vit-l:/models/clip-vit-l:ro,z",
                ],
                "env": {
                    "CLIP_MODEL_PATH": "/models/clip-vit-l",
                },
            },
            {
                "name": "ai-enrichment",
                "image": "ai-enrichment",
                "port": self.config.enrichment_port,
                "gpu": self.config.gpu_enrichment,
                "volumes": [
                    f"{self.config.ai_models_path}/model-zoo/vehicle-segment-classification:/models/vehicle-segment-classification:ro,z",
                    f"{self.config.ai_models_path}/model-zoo/pet-classifier:/models/pet-classifier:ro,z",
                    f"{self.config.ai_models_path}/model-zoo/fashion-clip:/models/fashion-clip:ro,z",
                    f"{self.config.ai_models_path}/model-zoo/depth-anything-v2-small:/models/depth-anything-v2-small:ro,z",
                ],
                "env": {
                    "VEHICLE_MODEL_PATH": "/models/vehicle-segment-classification",
                    "PET_MODEL_PATH": "/models/pet-classifier",
                    "CLOTHING_MODEL_PATH": "/models/fashion-clip",
                    "DEPTH_MODEL_PATH": "/models/depth-anything-v2-small",
                },
            },
        ]

        for ai_config in ai_configs:
            output.info(f"Starting {ai_config['name']}...")

            container_id = self.runtime.run(
                image=ai_config["image"],
                name=ai_config["name"],
                network=network,
                ports={ai_config["port"]: ai_config["port"]},
                volumes=ai_config["volumes"],
                env={
                    **ai_config["env"],
                    "CUDA_VISIBLE_DEVICES": "0",
                },
                devices=[f"nvidia.com/gpu={ai_config['gpu']}"],
                restart="unless-stopped",
                extra_args=["--security-opt=label=disable"],
            )

            if not container_id:
                raise ContainerError(ai_config["name"], "start", "Failed to start container")

        output.success("AI services started")

    async def start_backend(self) -> None:
        """Start backend service."""
        output.step("Starting backend...")

        network = f"{self.config.project_name}_security-net"
        postgres_host = f"{self.config.project_name}_postgres_1"
        redis_host = f"{self.config.project_name}_redis_1"

        container_id = self.runtime.run(
            image=f"localhost/{self.config.project_name}_backend:latest",
            name="backend",
            network=network,
            ports={self.config.api_port: self.config.api_port},
            volumes=[
                "./backend/data:/app/data:z,U",
                f"{self.config.foscam_base_path}:/cameras:ro,z",
                f"{self.config.ai_models_path}/model-zoo:/models/model-zoo:ro,z",
            ],
            env={
                "DATABASE_URL": f"postgresql+asyncpg://{self.config.postgres_user}:{self.config.postgres_password}@{postgres_host}:5432/{self.config.postgres_db}",
                "REDIS_URL": f"redis://{redis_host}:6379",
                "REDIS_PASSWORD": self.config.redis_password,
                "YOLO26_URL": f"http://ai-yolo26:{self.config.yolo26_port}",
                "NEMOTRON_URL": f"http://ai-llm:{self.config.llm_port}",
                "FLORENCE_URL": f"http://ai-florence:{self.config.florence_port}",
                "CLIP_URL": f"http://ai-clip:{self.config.clip_port}",
                "ENRICHMENT_URL": f"http://ai-enrichment:{self.config.enrichment_port}",
                "FRONTEND_URL": "http://frontend:8080",
                "FOSCAM_BASE_PATH": "/cameras",
                "DEBUG": str(self.config.debug).lower(),
            },
            restart="unless-stopped",
            extra_args=["--network-alias", "backend"],
        )

        if not container_id:
            raise ContainerError("backend", "start", "Failed to start container")

        output.success("Backend started")

    async def start_frontend(self) -> None:
        """Start frontend service."""
        output.step("Starting frontend...")

        network = f"{self.config.project_name}_security-net"

        # Ensure certs volume exists
        certs_volume = f"{self.config.project_name}_frontend_certs"
        if not self.runtime.volume_exists(certs_volume):
            self.runtime.volume_create(certs_volume)

        container_id = self.runtime.run(
            image=f"localhost/{self.config.project_name}_frontend:latest",
            name="frontend",
            network=network,
            ports={5173: 8080},  # Map to HTTP port for simplicity
            volumes=[
                f"{certs_volume}:/etc/nginx/certs:U",
            ],
            env={
                "SSL_ENABLED": "false",
            },
            restart="unless-stopped",
            extra_args=["--network-alias", "frontend"],
        )

        if not container_id:
            raise ContainerError("frontend", "start", "Failed to start container")

        output.success("Frontend started")

    async def start_privileged_monitoring(self) -> None:
        """Start privileged monitoring containers (dcgm-exporter, cadvisor).

        These containers require root access and must be started with sudo podman.
        They run in rootful mode with host networking.
        """
        output.step("Starting privileged monitoring containers...")

        # Stop any existing privileged containers first
        for name in ["dcgm-exporter", "cadvisor"]:
            # Stop in rootless namespace
            self.runtime.process.run(
                [self.runtime.cmd, "rm", "-f", name],
                check=False,
                capture=True,
            )
            # Stop in rootful namespace
            self.runtime.process.run(
                ["sudo", self.runtime.cmd, "rm", "-f", name],
                check=False,
                capture=True,
            )

        # Start DCGM Exporter (GPU metrics)
        output.info("Starting dcgm-exporter (privileged)...")
        dcgm_result = self.runtime.process.run(
            [
                "sudo",
                self.runtime.cmd,
                "run",
                "-d",
                "--name",
                "dcgm-exporter",
                "--network",
                "host",
                "--privileged",
                "--device",
                "nvidia.com/gpu=all",
                "-v",
                f"{self.config.project_root}/monitoring/dcgm/custom-counters.csv:"
                "/etc/dcgm-exporter/default-counters.csv:ro",
                "-e",
                f"DCGM_EXPORTER_LISTEN=:{self.config.dcgm_exporter_port}",
                "-e",
                "DCGM_EXPORTER_KUBERNETES=false",
                "--restart",
                "unless-stopped",
                "nvcr.io/nvidia/k8s/dcgm-exporter:3.3.5-3.4.0-ubuntu22.04",
            ],
            check=False,
            capture=True,
        )

        if dcgm_result.success:
            output.success("dcgm-exporter started")
        else:
            output.warn(f"Failed to start dcgm-exporter: {dcgm_result.stderr}")

        # Start cAdvisor (container metrics)
        output.info("Starting cadvisor (privileged)...")
        cadvisor_result = self.runtime.process.run(
            [
                "sudo",
                self.runtime.cmd,
                "run",
                "-d",
                "--name",
                "cadvisor",
                "--network",
                "host",
                "--privileged",
                "--device",
                "/dev/kmsg",
                "-v",
                "/:/rootfs:ro",
                "-v",
                "/var/run:/var/run:ro",
                "-v",
                "/sys:/sys:ro",
                "-v",
                "/var/lib/containers:/var/lib/containers:ro",
                "--restart",
                "unless-stopped",
                "gcr.io/cadvisor/cadvisor:v0.49.1",
                f"--port={self.config.cadvisor_port}",
            ],
            check=False,
            capture=True,
        )

        if cadvisor_result.success:
            output.success("cadvisor started")
        else:
            output.warn(f"Failed to start cadvisor: {cadvisor_result.stderr}")

        output.success("Privileged monitoring containers started")

    async def stop_privileged_monitoring(self) -> None:
        """Stop privileged monitoring containers."""
        output.step("Stopping privileged monitoring containers...")

        for name in ["dcgm-exporter", "cadvisor"]:
            # Stop in rootful namespace
            self.runtime.process.run(
                ["sudo", self.runtime.cmd, "stop", name],
                check=False,
                capture=True,
                timeout=10,
            )
            self.runtime.process.run(
                ["sudo", self.runtime.cmd, "rm", "-f", name],
                check=False,
                capture=True,
            )

        output.success("Privileged monitoring containers stopped")

    # =========================================================================
    # Status operations
    # =========================================================================

    def get_status(self) -> dict[str, HealthStatus]:
        """Get status of all project containers.

        Returns:
            Dict of container name -> HealthStatus
        """
        statuses: dict[str, HealthStatus] = {}

        for container in self.runtime.ps(all=True):
            # Check if it's one of our containers
            is_ours = any(p in container.name.lower() for p in self.PROJECT_PATTERNS)
            if not is_ours:
                continue

            # Parse status
            status_str = container.status.lower()
            if "healthy" in status_str:
                status = ContainerStatus.HEALTHY
            elif "unhealthy" in status_str:
                status = ContainerStatus.UNHEALTHY
            elif "starting" in status_str:
                status = ContainerStatus.STARTING
            elif "up" in status_str or "running" in status_str:
                status = ContainerStatus.RUNNING
            else:
                status = ContainerStatus.STOPPED

            statuses[container.name] = HealthStatus(
                service=container.name,
                status=status,
                message=container.status,
            )

        return statuses

    def print_status(self) -> None:
        """Print status table of all containers."""
        statuses = self.get_status()
        if not statuses:
            output.info("No containers found")
            return

        status_dict = {name: (hs.status.value, hs.message or "") for name, hs in statuses.items()}
        output.status_table(status_dict)
