"""Docker API wrapper for container management.

This module provides an async wrapper around docker-py for managing Docker/Podman
containers. It abstracts Docker operations and provides async methods using
asyncio.to_thread() to make the synchronous docker-py calls non-blocking.

Features:
- Async wrapper around docker-py for non-blocking container operations
- Support for both Docker and Podman (they use the same API)
- Graceful error handling for DockerException and NotFound errors
- Proper logging for all operations
- Context manager support for automatic cleanup

Usage:
    async with DockerClient() as client:
        containers = await client.list_containers()
        status = await client.get_container_status("my-container")

    # Or manual connection management:
    client = DockerClient(docker_host="unix:///var/run/docker.sock")
    await client.connect()
    try:
        containers = await client.list_containers()
    finally:
        await client.close()
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from docker import DockerClient as BaseDockerClient  # type: ignore[attr-defined]
from docker.errors import APIError, DockerException, ImageNotFound, NotFound

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from docker.models.containers import Container

logger = get_logger(__name__)


class DockerClient:
    """Async wrapper around docker-py for container management.

    This class provides async methods for common Docker operations, making
    it suitable for use in async web frameworks like FastAPI. All blocking
    docker-py calls are run in a thread pool using asyncio.to_thread().

    The client supports both Docker and Podman since they share the same API.

    Attributes:
        _docker_host: The Docker host URL (e.g., unix:///var/run/docker.sock)
        _client: The underlying docker-py client instance
    """

    def __init__(self, docker_host: str | None = None) -> None:
        """Initialize Docker client.

        Args:
            docker_host: Docker host URL (e.g., unix:///var/run/docker.sock,
                        tcp://192.168.1.100:2375). If None, uses default from
                        environment (DOCKER_HOST) or the standard Docker socket.
        """
        self._docker_host = docker_host
        self._client: BaseDockerClient | None = None

        # Initialize the client
        if docker_host:
            self._client = BaseDockerClient(base_url=docker_host)
        else:
            self._client = BaseDockerClient.from_env()

    async def __aenter__(self) -> DockerClient:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> bool:
        """Test connection to Docker daemon.

        Attempts to ping the Docker daemon to verify connectivity.

        Returns:
            True if connection is successful, False otherwise.
        """
        if self._client is None:
            logger.warning("Docker client not initialized")
            return False

        try:
            # Run ping in thread pool since it's blocking
            await asyncio.to_thread(self._client.ping)
            logger.info(
                "Successfully connected to Docker daemon",
                extra={"docker_host": self._docker_host or "default"},
            )
            return True
        except DockerException as e:
            logger.warning(
                f"Failed to connect to Docker daemon: {e}",
                extra={"docker_host": self._docker_host or "default", "error": str(e)},
            )
            return False

    async def list_containers(self, all: bool = True) -> list[Container]:
        """List all containers (running and stopped if all=True).

        Args:
            all: If True, include stopped containers. If False, only running.

        Returns:
            List of Container objects. Returns empty list on error.
        """
        if self._client is None:
            logger.debug("Docker client not initialized, returning empty list")
            return []

        try:
            containers: list[Container] = await asyncio.to_thread(
                self._client.containers.list, all=all
            )
            logger.debug(
                f"Listed {len(containers)} containers",
                extra={"count": len(containers), "include_all": all},
            )
            return containers
        except (DockerException, APIError, RuntimeError) as e:
            logger.warning(
                f"Failed to list containers: {e}",
                extra={"error": str(e), "include_all": all},
            )
            return []

    async def get_container(self, container_id: str) -> Container | None:
        """Get container by ID.

        Args:
            container_id: Container ID (full or short form).

        Returns:
            Container object if found, None otherwise.
        """
        if self._client is None:
            logger.debug("Docker client not initialized")
            return None

        try:
            container = await asyncio.to_thread(self._client.containers.get, container_id)
            logger.debug(
                f"Found container {container_id}",
                extra={"container_id": container_id},
            )
            return container
        except NotFound:
            logger.debug(
                f"Container not found: {container_id}",
                extra={"container_id": container_id},
            )
            return None
        except (DockerException, APIError, ImageNotFound) as e:
            logger.warning(
                f"Error getting container {container_id}: {e}",
                extra={"container_id": container_id, "error": str(e)},
            )
            return None

    async def get_container_by_name(self, name: str) -> Container | None:
        """Get container by name pattern.

        Searches for containers whose name contains the given pattern.
        Returns the first matching container.

        Args:
            name: Name pattern to search for.

        Returns:
            Container object if found, None otherwise.
        """
        if self._client is None:
            logger.debug("Docker client not initialized")
            return None

        try:
            # List all containers and filter by name
            containers = await asyncio.to_thread(self._client.containers.list, all=True)
            for container in containers:
                if name in container.name:
                    logger.debug(
                        f"Found container by name pattern '{name}': {container.name}",
                        extra={"pattern": name, "container_name": container.name},
                    )
                    return container

            logger.debug(
                f"No container found matching name pattern: {name}",
                extra={"pattern": name},
            )
            return None
        except (DockerException, APIError) as e:
            logger.warning(
                f"Error searching for container by name '{name}': {e}",
                extra={"pattern": name, "error": str(e)},
            )
            return None

    async def start_container(self, container_id: str) -> bool:
        """Start a stopped container.

        Args:
            container_id: Container ID to start.

        Returns:
            True if successful, False otherwise.
        """
        if self._client is None:
            logger.debug("Docker client not initialized")
            return False

        try:
            container = await asyncio.to_thread(self._client.containers.get, container_id)
            await asyncio.to_thread(container.start)
            logger.info(
                f"Started container {container_id}",
                extra={"container_id": container_id},
            )
            return True
        except NotFound:
            logger.warning(
                f"Cannot start container - not found: {container_id}",
                extra={"container_id": container_id},
            )
            return False
        except DockerException as e:
            logger.error(
                f"Failed to start container {container_id}: {e}",
                extra={"container_id": container_id, "error": str(e)},
            )
            return False

    async def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """Stop a running container gracefully.

        Args:
            container_id: Container ID to stop.
            timeout: Seconds to wait for graceful stop before killing.

        Returns:
            True if successful, False otherwise.
        """
        if self._client is None:
            logger.debug("Docker client not initialized")
            return False

        try:
            container = await asyncio.to_thread(self._client.containers.get, container_id)
            await asyncio.to_thread(container.stop, timeout=timeout)
            logger.info(
                f"Stopped container {container_id}",
                extra={"container_id": container_id, "timeout": timeout},
            )
            return True
        except NotFound:
            logger.warning(
                f"Cannot stop container - not found: {container_id}",
                extra={"container_id": container_id},
            )
            return False
        except DockerException as e:
            logger.error(
                f"Failed to stop container {container_id}: {e}",
                extra={"container_id": container_id, "timeout": timeout, "error": str(e)},
            )
            return False

    async def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        """Restart a container.

        Args:
            container_id: Container ID to restart.
            timeout: Seconds to wait for graceful stop before killing.

        Returns:
            True if successful, False otherwise.
        """
        if self._client is None:
            logger.debug("Docker client not initialized")
            return False

        try:
            container = await asyncio.to_thread(self._client.containers.get, container_id)
            await asyncio.to_thread(container.restart, timeout=timeout)
            logger.info(
                f"Restarted container {container_id}",
                extra={"container_id": container_id, "timeout": timeout},
            )
            return True
        except NotFound:
            logger.warning(
                f"Cannot restart container - not found: {container_id}",
                extra={"container_id": container_id},
            )
            return False
        except DockerException as e:
            logger.error(
                f"Failed to restart container {container_id}: {e}",
                extra={"container_id": container_id, "timeout": timeout, "error": str(e)},
            )
            return False

    async def exec_run(self, container_id: str, cmd: str, timeout: int = 5) -> int:  # noqa: ARG002
        """Execute command in container and return exit code.

        Args:
            container_id: Container ID to execute command in.
            cmd: Command to execute.
            timeout: Timeout for command execution (reserved for future use).

        Returns:
            Exit code of the command. Returns -1 on error or if container not found.
        """
        if self._client is None:
            logger.debug("Docker client not initialized")
            return -1

        try:
            container = await asyncio.to_thread(self._client.containers.get, container_id)
            result: tuple[int, bytes] = await asyncio.to_thread(container.exec_run, cmd)
            exit_code = result[0]
            logger.debug(
                f"Executed command in container {container_id}",
                extra={
                    "container_id": container_id,
                    "command": cmd,
                    "exit_code": exit_code,
                },
            )
            return exit_code
        except NotFound:
            logger.warning(
                f"Cannot exec in container - not found: {container_id}",
                extra={"container_id": container_id, "command": cmd},
            )
            return -1
        except DockerException as e:
            logger.error(
                f"Failed to exec in container {container_id}: {e}",
                extra={"container_id": container_id, "command": cmd, "error": str(e)},
            )
            return -1

    async def get_container_status(self, container_id: str) -> str | None:
        """Get container status (running, exited, etc).

        Args:
            container_id: Container ID to check.

        Returns:
            Status string (e.g., 'running', 'exited', 'paused') or None if not found.
        """
        if self._client is None:
            logger.debug("Docker client not initialized")
            return None

        try:
            container = await asyncio.to_thread(self._client.containers.get, container_id)
            status: str = container.status
            logger.debug(
                f"Container {container_id} status: {status}",
                extra={"container_id": container_id, "status": status},
            )
            return status
        except NotFound:
            logger.debug(
                f"Container not found: {container_id}",
                extra={"container_id": container_id},
            )
            return None
        except DockerException as e:
            logger.warning(
                f"Error getting status for container {container_id}: {e}",
                extra={"container_id": container_id, "error": str(e)},
            )
            return None

    async def close(self) -> None:
        """Close the Docker client connection.

        Releases resources and closes the connection to the Docker daemon.
        Safe to call multiple times.
        """
        if self._client is not None:
            try:
                await asyncio.to_thread(self._client.close)
                logger.info("Docker client connection closed")
            except Exception as e:
                # Log but don't raise - we're cleaning up
                logger.debug(f"Error closing Docker client: {e}")
            finally:
                self._client = None
