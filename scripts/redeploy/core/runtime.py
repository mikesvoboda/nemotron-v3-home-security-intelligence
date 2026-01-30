"""Container runtime abstraction for Podman/Docker."""

import shutil
from dataclasses import dataclass
from pathlib import Path

from scripts.redeploy.core.process import ProcessRunner
from scripts.redeploy.models import CommandResult


@dataclass
class Container:
    """Container information."""

    id: str
    name: str
    status: str
    image: str
    ports: dict[int, int]  # container_port -> host_port


@dataclass
class Image:
    """Image information."""

    id: str
    repository: str
    tag: str
    size: str
    created: str


class ContainerRuntime:
    """Abstraction over Podman/Docker container commands."""

    def __init__(self, process: ProcessRunner, prefer_podman: bool = True):
        """Initialize container runtime.

        Args:
            process: ProcessRunner instance for executing commands
            prefer_podman: Prefer podman over docker if both available
        """
        self.process = process
        self.cmd = self._detect_runtime(prefer_podman)
        self.compose_cmd = self._detect_compose()

    def _detect_runtime(self, prefer_podman: bool) -> str:
        """Detect available container runtime."""
        podman_available = shutil.which("podman") is not None
        docker_available = shutil.which("docker") is not None

        if prefer_podman and podman_available:
            return "podman"
        elif docker_available:
            return "docker"
        elif podman_available:
            return "podman"
        else:
            raise RuntimeError("Neither podman nor docker found in PATH")

    def _detect_compose(self) -> str:
        """Detect available compose command."""
        compose_cmd = f"{self.cmd}-compose"
        if shutil.which(compose_cmd):
            return compose_cmd

        # Fallback: docker compose (v2 plugin)
        if self.cmd == "docker":
            return "docker compose"

        raise RuntimeError(f"{compose_cmd} not found in PATH")

    @property
    def is_podman(self) -> bool:
        """Check if using Podman."""
        return self.cmd == "podman"

    @property
    def is_docker(self) -> bool:
        """Check if using Docker."""
        return self.cmd == "docker"

    # =========================================================================
    # Container operations
    # =========================================================================

    def ps(
        self,
        all: bool = False,
    ) -> list[Container]:
        """List containers.

        Args:
            all: Include stopped containers

        Returns:
            List of Container objects
        """
        cmd = [self.cmd, "ps"]
        if all:
            cmd.append("-a")

        # Use JSON format for parsing
        cmd.extend(["--format", "json"])

        result = self.process.run(cmd, check=False, capture=True)
        if not result.success or not result.stdout.strip():
            return []

        import json

        containers = []
        # Podman outputs one JSON object per line, Docker outputs an array
        lines = result.stdout.strip().split("\n")
        for line in lines:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                # Handle both podman and docker JSON formats
                if isinstance(data, list):
                    # Docker format
                    for item in data:
                        containers.append(self._parse_container(item))
                else:
                    # Podman format (one object per line)
                    containers.append(self._parse_container(data))
            except json.JSONDecodeError:
                continue

        return containers

    def _parse_container(self, data: dict) -> Container:
        """Parse container JSON into Container object."""
        # Handle different key names between podman and docker
        container_id = data.get("Id") or data.get("ID") or data.get("id", "")
        name = data.get("Names") or data.get("Name", "")
        if isinstance(name, list):
            name = name[0] if name else ""
        # Remove leading slash if present (docker adds it)
        name = name.lstrip("/")

        status = data.get("Status") or data.get("State", "")
        image = data.get("Image", "")

        # Parse ports
        ports: dict[int, int] = {}
        ports_data = data.get("Ports", [])
        if isinstance(ports_data, list):
            for port_info in ports_data:
                if isinstance(port_info, dict):
                    container_port = port_info.get("containerPort") or port_info.get(
                        "PrivatePort", 0
                    )
                    host_port = port_info.get("hostPort") or port_info.get("PublicPort", 0)
                    if container_port and host_port:
                        ports[int(container_port)] = int(host_port)

        return Container(
            id=container_id[:12] if container_id else "",
            name=name,
            status=status,
            image=image,
            ports=ports,
        )

    def stop(self, name: str, timeout: int = 10) -> bool:
        """Stop a container.

        Args:
            name: Container name or ID
            timeout: Seconds to wait before killing

        Returns:
            True if stopped successfully
        """
        cmd = [self.cmd, "stop", "-t", str(timeout), name]
        result = self.process.run(cmd, check=False, capture=True)
        return result.success

    def rm(self, name: str, force: bool = False, volumes: bool = False) -> bool:
        """Remove a container.

        Args:
            name: Container name or ID
            force: Force removal of running container
            volumes: Remove associated volumes

        Returns:
            True if removed successfully
        """
        cmd = [self.cmd, "rm"]
        if force:
            cmd.append("-f")
        if volumes:
            cmd.append("-v")
        cmd.append(name)

        result = self.process.run(cmd, check=False, capture=True)
        return result.success

    def run(
        self,
        image: str,
        name: str,
        detach: bool = True,
        network: str | None = None,
        ports: dict[int, int] | None = None,
        volumes: list[str] | None = None,
        env: dict[str, str] | None = None,
        devices: list[str] | None = None,
        restart: str | None = None,
        extra_args: list[str] | None = None,
    ) -> str | None:
        """Run a new container.

        Args:
            image: Image name
            name: Container name
            detach: Run in background
            network: Network to connect to
            ports: Port mappings (host_port -> container_port)
            volumes: Volume mounts
            env: Environment variables
            devices: Device mappings
            restart: Restart policy
            extra_args: Additional arguments

        Returns:
            Container ID if successful, None otherwise
        """
        cmd = [self.cmd, "run"]

        if detach:
            cmd.append("-d")
        cmd.extend(["--name", name])

        if network:
            cmd.extend(["--network", network])

        if ports:
            for host_port, container_port in ports.items():
                cmd.extend(["-p", f"{host_port}:{container_port}"])

        if volumes:
            for vol in volumes:
                cmd.extend(["-v", vol])

        if env:
            for key, value in env.items():
                cmd.extend(["-e", f"{key}={value}"])

        if devices:
            for device in devices:
                cmd.extend(["--device", device])

        if restart:
            cmd.extend(["--restart", restart])

        if extra_args:
            cmd.extend(extra_args)

        cmd.append(image)

        result = self.process.run(cmd, check=False, capture=True)
        if result.success:
            return result.stdout.strip()[:12]  # Return short container ID
        return None

    def logs(self, name: str, tail: int | None = None, follow: bool = False) -> str:
        """Get container logs.

        Args:
            name: Container name or ID
            tail: Number of lines from end
            follow: Follow log output (streaming)

        Returns:
            Log output as string
        """
        cmd = [self.cmd, "logs"]
        if tail:
            cmd.extend(["--tail", str(tail)])
        if follow:
            cmd.append("-f")
        cmd.append(name)

        if follow:
            # For streaming, use the stream method
            lines = []
            for line in self.process.stream(cmd):
                lines.append(line)
            return "\n".join(lines)
        else:
            result = self.process.run(cmd, check=False, capture=True)
            return result.stdout + result.stderr

    def exec(
        self,
        name: str,
        command: list[str],
        interactive: bool = False,
        tty: bool = False,
        user: str | None = None,
        workdir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        """Execute command in running container.

        Args:
            name: Container name or ID
            command: Command to execute
            interactive: Keep STDIN open
            tty: Allocate pseudo-TTY
            user: Run as user
            workdir: Working directory
            env: Environment variables

        Returns:
            CommandResult with output
        """
        cmd = [self.cmd, "exec"]

        if interactive:
            cmd.append("-i")
        if tty:
            cmd.append("-t")
        if user:
            cmd.extend(["-u", user])
        if workdir:
            cmd.extend(["-w", workdir])
        if env:
            for key, value in env.items():
                cmd.extend(["-e", f"{key}={value}"])

        cmd.append(name)
        cmd.extend(command)

        return self.process.run(cmd, check=False, capture=True)

    def port(self, name: str) -> dict[int, int]:
        """Get port mappings for a container.

        Args:
            name: Container name or ID

        Returns:
            Dict of container_port -> host_port
        """
        cmd = [self.cmd, "port", name]
        result = self.process.run(cmd, check=False, capture=True)
        if not result.success:
            return {}

        ports: dict[int, int] = {}
        for line in result.stdout.strip().split("\n"):
            if not line or "->" not in line:
                continue
            # Expected format: container_port/protocol -> host_ip:host_port
            try:
                left, right = line.split("->")
                container_port = int(left.strip().split("/")[0])
                host_port = int(right.strip().split(":")[-1])
                ports[container_port] = host_port
            except (ValueError, IndexError):
                continue

        return ports

    def exists(self, name: str) -> bool:
        """Check if a container exists.

        Args:
            name: Container name or ID

        Returns:
            True if container exists
        """
        cmd = [self.cmd, "container", "exists", name]
        return self.process.run_silent(cmd)

    def inspect(self, name: str) -> dict | None:
        """Inspect a container.

        Args:
            name: Container name or ID

        Returns:
            Container inspection data or None
        """
        import json

        cmd = [self.cmd, "inspect", name]
        result = self.process.run(cmd, check=False, capture=True)
        if not result.success:
            return None

        try:
            data = json.loads(result.stdout)
            return data[0] if isinstance(data, list) else data
        except (json.JSONDecodeError, IndexError):
            return None

    # =========================================================================
    # Compose operations
    # =========================================================================

    def compose_up(
        self,
        file: Path,
        services: list[str] | None = None,
        detach: bool = True,
        build: bool = False,
        remove_orphans: bool = True,
    ) -> bool:
        """Start services with compose.

        Args:
            file: Compose file path
            services: Specific services to start (all if None)
            detach: Run in background
            build: Build images before starting
            remove_orphans: Remove orphaned containers

        Returns:
            True if successful
        """
        cmd = [*self._compose_base(file), "up"]

        if detach:
            cmd.append("-d")
        if build:
            cmd.append("--build")
        if remove_orphans:
            cmd.append("--remove-orphans")

        if services:
            cmd.extend(services)

        result = self.process.run(cmd, check=False, capture=True)
        return result.success

    def compose_down(
        self,
        file: Path,
        volumes: bool = False,
        remove_orphans: bool = True,
        timeout: int = 10,
    ) -> bool:
        """Stop services with compose.

        Args:
            file: Compose file path
            volumes: Remove named volumes
            remove_orphans: Remove orphaned containers
            timeout: Seconds to wait before killing

        Returns:
            True if successful
        """
        cmd = [*self._compose_base(file), "down"]

        if volumes:
            cmd.append("-v")
        if remove_orphans:
            cmd.append("--remove-orphans")
        cmd.extend(["-t", str(timeout)])

        result = self.process.run(cmd, check=False, capture=True)
        return result.success

    def compose_build(
        self,
        file: Path,
        services: list[str] | None = None,
        no_cache: bool = False,
        parallel: bool = True,
    ) -> bool:
        """Build services with compose.

        Args:
            file: Compose file path
            services: Specific services to build
            no_cache: Don't use cache
            parallel: Build in parallel

        Returns:
            True if successful
        """
        cmd = [*self._compose_base(file), "build"]

        if no_cache:
            cmd.append("--no-cache")
        if parallel and self.is_docker:
            cmd.append("--parallel")

        if services:
            cmd.extend(services)

        result = self.process.run(cmd, check=False, capture=True)
        return result.success

    def _compose_base(self, file: Path) -> list[str]:
        """Build base compose command."""
        if " " in self.compose_cmd:
            # docker compose (v2 plugin)
            return [*self.compose_cmd.split(), "-f", str(file)]
        else:
            return [self.compose_cmd, "-f", str(file)]

    # =========================================================================
    # Image operations
    # =========================================================================

    def build(
        self,
        context: Path,
        tag: str,
        file: Path | None = None,
        no_cache: bool = False,
        build_args: dict[str, str] | None = None,
    ) -> bool:
        """Build an image.

        Args:
            context: Build context directory
            tag: Image tag
            file: Dockerfile path (relative to context)
            no_cache: Don't use cache
            build_args: Build arguments

        Returns:
            True if successful
        """
        cmd = [self.cmd, "build", "-t", tag]

        if file:
            cmd.extend(["-f", str(file)])
        if no_cache:
            cmd.append("--no-cache")
        if build_args:
            for key, value in build_args.items():
                cmd.extend(["--build-arg", f"{key}={value}"])

        cmd.append(str(context))

        result = self.process.run(cmd, check=False, capture=True)
        return result.success

    def images(self, filter_str: str | None = None) -> list[Image]:
        """List images.

        Args:
            filter_str: Filter expression

        Returns:
            List of Image objects
        """
        cmd = [self.cmd, "images", "--format", "json"]
        if filter_str:
            cmd.extend(["--filter", filter_str])

        result = self.process.run(cmd, check=False, capture=True)
        if not result.success or not result.stdout.strip():
            return []

        import json

        images = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if isinstance(data, list):
                    for item in data:
                        images.append(self._parse_image(item))
                else:
                    images.append(self._parse_image(data))
            except json.JSONDecodeError:
                continue

        return images

    def _parse_image(self, data: dict) -> Image:
        """Parse image JSON into Image object."""
        return Image(
            id=data.get("Id", data.get("ID", ""))[:12],
            repository=data.get("Repository", data.get("repository", "")),
            tag=data.get("Tag", data.get("tag", "")),
            size=data.get("Size", data.get("size", "")),
            created=data.get("Created", data.get("CreatedAt", "")),
        )

    def rmi(self, image: str, force: bool = False) -> bool:
        """Remove an image.

        Args:
            image: Image name or ID
            force: Force removal

        Returns:
            True if successful
        """
        cmd = [self.cmd, "rmi"]
        if force:
            cmd.append("-f")
        cmd.append(image)

        result = self.process.run(cmd, check=False, capture=True)
        return result.success

    def prune_images(self, all: bool = False, force: bool = True) -> None:
        """Prune unused images.

        Args:
            all: Remove all unused images (not just dangling)
            force: Don't prompt for confirmation
        """
        cmd = [self.cmd, "image", "prune"]
        if all:
            cmd.append("-a")
        if force:
            cmd.append("-f")

        self.process.run(cmd, check=False, capture=True)

    def prune_system(
        self,
        all: bool = False,
        volumes: bool = False,
        force: bool = True,
    ) -> None:
        """Prune system (containers, networks, images, build cache).

        Args:
            all: Remove all unused data
            volumes: Also prune volumes
            force: Don't prompt for confirmation
        """
        cmd = [self.cmd, "system", "prune"]
        if all:
            cmd.append("-a")
        if volumes:
            cmd.append("--volumes")
        if force:
            cmd.append("-f")

        self.process.run(cmd, check=False, capture=True)

    def prune_builder(self, force: bool = True) -> None:
        """Prune build cache.

        Args:
            force: Don't prompt for confirmation
        """
        cmd = [self.cmd, "builder", "prune"]
        if force:
            cmd.append("-f")

        self.process.run(cmd, check=False, capture=True)

    # =========================================================================
    # Pod operations (Podman-specific)
    # =========================================================================

    def pod_rm(
        self,
        name: str | None = None,
        all: bool = False,
        force: bool = False,
    ) -> bool:
        """Remove pod(s).

        Args:
            name: Pod name (or None if all=True)
            all: Remove all pods
            force: Force removal

        Returns:
            True if successful
        """
        if not self.is_podman:
            return True  # No-op for Docker

        cmd = [self.cmd, "pod", "rm"]
        if force:
            cmd.append("-f")
        if all:
            cmd.append("-a")
        elif name:
            cmd.append(name)
        else:
            return True  # Nothing to do

        result = self.process.run(cmd, check=False, capture=True)
        return result.success

    # =========================================================================
    # Network operations
    # =========================================================================

    def network_exists(self, name: str) -> bool:
        """Check if a network exists.

        Args:
            name: Network name

        Returns:
            True if network exists
        """
        cmd = [self.cmd, "network", "exists", name]
        return self.process.run_silent(cmd)

    def network_create(self, name: str) -> bool:
        """Create a network.

        Args:
            name: Network name

        Returns:
            True if created successfully
        """
        cmd = [self.cmd, "network", "create", name]
        result = self.process.run(cmd, check=False, capture=True)
        return result.success

    # =========================================================================
    # Volume operations
    # =========================================================================

    def volume_exists(self, name: str) -> bool:
        """Check if a volume exists.

        Args:
            name: Volume name

        Returns:
            True if volume exists
        """
        cmd = [self.cmd, "volume", "exists", name]
        return self.process.run_silent(cmd)

    def volume_create(self, name: str) -> bool:
        """Create a volume.

        Args:
            name: Volume name

        Returns:
            True if created successfully
        """
        cmd = [self.cmd, "volume", "create", name]
        result = self.process.run(cmd, check=False, capture=True)
        return result.success
