"""Service manager abstraction for health checks and restarts.

This module provides a strategy pattern for managing external services
(Redis, RT-DETRv2, Nemotron) with support for both shell scripts (dev)
and Docker containers (prod).

Service Management Flow:
    1. Health check via HTTP GET to service health endpoint
    2. On failure, attempt restart via configured command
    3. Verify health after restart
    4. Report status via logging

Implementations:
    - ShellServiceManager: Restart via shell scripts (asyncio subprocess)
    - DockerServiceManager: Restart via docker restart command
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from backend.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ServiceConfig:
    """Configuration for a managed service.

    Attributes:
        name: Service identifier (e.g., "rtdetr", "nemotron", "redis")
        health_url: HTTP endpoint for health checks (e.g., "http://localhost:8001/health")
        restart_cmd: Command to restart the service (script path or container name)
        health_timeout: Timeout in seconds for health check requests
        max_retries: Maximum number of restart attempts before giving up
        backoff_base: Base time in seconds for exponential backoff (5s, 10s, 20s...)
    """

    name: str
    health_url: str
    restart_cmd: str
    health_timeout: float = 5.0
    max_retries: int = 3
    backoff_base: float = 5.0


class ServiceManager(ABC):
    """Abstract base class for service management strategies.

    Defines the interface for health checking and restarting services.
    Implementations can use shell scripts, Docker, systemd, or other
    mechanisms.
    """

    @abstractmethod
    async def check_health(self, config: ServiceConfig) -> bool:
        """Check if a service is healthy and responding.

        Args:
            config: Service configuration with health endpoint

        Returns:
            True if the service is healthy, False otherwise
        """
        pass

    @abstractmethod
    async def restart(self, config: ServiceConfig) -> bool:
        """Attempt to restart a service.

        Args:
            config: Service configuration with restart command

        Returns:
            True if the restart command succeeded, False otherwise
        """
        pass


class ShellServiceManager(ServiceManager):
    """Service manager that uses shell scripts for restarts.

    Health checks are performed via HTTP requests to the service's
    health endpoint. For Redis, uses redis-cli ping instead of HTTP.

    Restarts are executed via asyncio subprocess running the configured
    shell script or command.
    """

    def __init__(self, subprocess_timeout: float = 60.0) -> None:
        """Initialize the shell service manager.

        Args:
            subprocess_timeout: Maximum time in seconds to wait for restart
                commands to complete before killing them
        """
        self._subprocess_timeout = subprocess_timeout

    async def check_health(self, config: ServiceConfig) -> bool:
        """Check service health via HTTP GET or Redis ping.

        For services with "redis" in their name, uses redis-cli ping.
        For all other services, performs HTTP GET to health_url.

        Args:
            config: Service configuration

        Returns:
            True if the service responds successfully, False otherwise
        """
        # Redis uses redis-cli ping instead of HTTP
        if "redis" in config.name.lower():
            return await self._check_redis_health(config)

        return await self._check_http_health(config)

    async def _check_http_health(self, config: ServiceConfig) -> bool:
        """Check health via HTTP GET request.

        Args:
            config: Service configuration with health_url

        Returns:
            True if HTTP 2xx response, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=config.health_timeout) as client:
                response = await client.get(config.health_url)
                response.raise_for_status()
                logger.debug(
                    f"Health check passed for {config.name}",
                    extra={"service": config.name, "url": config.health_url},
                )
                return True

        except httpx.ConnectError as e:
            logger.warning(
                f"Health check failed for {config.name}: connection error",
                extra={"service": config.name, "error": str(e)},
            )
            return False

        except httpx.TimeoutException as e:
            logger.warning(
                f"Health check failed for {config.name}: timeout",
                extra={"service": config.name, "timeout": config.health_timeout, "error": str(e)},
            )
            return False

        except httpx.HTTPStatusError as e:
            logger.warning(
                f"Health check failed for {config.name}: HTTP {e.response.status_code}",
                extra={"service": config.name, "status_code": e.response.status_code},
            )
            return False

        except Exception as e:
            logger.error(
                f"Health check failed for {config.name}: unexpected error",
                extra={"service": config.name, "error": str(e)},
                exc_info=True,
            )
            return False

    async def _check_redis_health(self, config: ServiceConfig) -> bool:
        """Check Redis health via redis-cli ping.

        Args:
            config: Service configuration

        Returns:
            True if Redis responds with PONG, False otherwise
        """
        try:
            process = await asyncio.create_subprocess_shell(
                "redis-cli ping",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=config.health_timeout,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                logger.warning(
                    f"Redis health check timed out for {config.name}",
                    extra={"service": config.name, "timeout": config.health_timeout},
                )
                return False

            if process.returncode == 0 and b"PONG" in stdout:
                logger.debug(
                    f"Health check passed for {config.name}: Redis PONG",
                    extra={"service": config.name},
                )
                return True
            else:
                logger.warning(
                    f"Health check failed for {config.name}: Redis did not respond with PONG",
                    extra={
                        "service": config.name,
                        "returncode": process.returncode,
                        "stdout": stdout.decode().strip(),
                        "stderr": stderr.decode().strip(),
                    },
                )
                return False

        except Exception as e:
            logger.error(
                f"Health check failed for {config.name}: unexpected error",
                extra={"service": config.name, "error": str(e)},
                exc_info=True,
            )
            return False

    async def restart(self, config: ServiceConfig) -> bool:
        """Restart service via shell command.

        Executes the restart_cmd as a subprocess and waits for it to
        complete. If the subprocess takes longer than subprocess_timeout,
        it is killed and the restart is considered failed.

        Args:
            config: Service configuration with restart_cmd

        Returns:
            True if the command exits with code 0, False otherwise
        """
        logger.info(
            f"Attempting to restart {config.name} via shell",
            extra={"service": config.name, "command": config.restart_cmd},
        )

        try:
            process = await asyncio.create_subprocess_shell(
                config.restart_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self._subprocess_timeout,
                )
            except TimeoutError:
                logger.error(
                    f"Restart command timed out for {config.name}, killing process",
                    extra={"service": config.name, "timeout": self._subprocess_timeout},
                )
                process.kill()
                await process.wait()
                return False

            if process.returncode == 0:
                logger.info(
                    f"Restart command succeeded for {config.name}",
                    extra={
                        "service": config.name,
                        "returncode": 0,
                        "stdout": stdout.decode().strip()[:500],  # Truncate long output
                    },
                )
                return True
            else:
                logger.error(
                    f"Restart command failed for {config.name} with exit code {process.returncode}",
                    extra={
                        "service": config.name,
                        "returncode": process.returncode,
                        "stderr": stderr.decode().strip()[:500],
                    },
                )
                return False

        except Exception as e:
            logger.error(
                f"Restart failed for {config.name}: unexpected error",
                extra={"service": config.name, "error": str(e)},
                exc_info=True,
            )
            return False


class DockerServiceManager(ServiceManager):
    """Service manager that uses Docker for restarts.

    Health checks are performed via HTTP requests to the service's
    health endpoint, same as ShellServiceManager. For Redis, uses
    redis-cli ping.

    Restarts are executed via `docker restart <container_name>` command.
    The container name is either extracted from the restart_cmd config
    or defaults to the service name.
    """

    def __init__(self, subprocess_timeout: float = 60.0) -> None:
        """Initialize the Docker service manager.

        Args:
            subprocess_timeout: Maximum time in seconds to wait for
                docker restart commands to complete
        """
        self._subprocess_timeout = subprocess_timeout
        # Delegate health checks to shell manager since they're the same
        self._shell_manager = ShellServiceManager(subprocess_timeout)

    async def check_health(self, config: ServiceConfig) -> bool:
        """Check service health via HTTP GET or Redis ping.

        Delegates to ShellServiceManager since health check logic is identical.

        Args:
            config: Service configuration

        Returns:
            True if the service responds successfully, False otherwise
        """
        return await self._shell_manager.check_health(config)

    def _extract_container_name(self, config: ServiceConfig) -> str:
        """Extract Docker container name from config.

        If restart_cmd starts with 'docker restart ', extract the container name.
        Otherwise, use the service name as the container name.

        Args:
            config: Service configuration

        Returns:
            Docker container name to restart
        """
        restart_cmd = config.restart_cmd.strip()

        # Check if restart_cmd is already a docker restart command
        if restart_cmd.startswith("docker restart "):
            # Extract container name after "docker restart "
            container_name = restart_cmd[len("docker restart ") :].strip()
            # Handle any flags by taking the last token
            parts = container_name.split()
            if parts:
                return parts[-1]

        # Default to service name as container name
        return config.name

    async def restart(self, config: ServiceConfig) -> bool:
        """Restart service via docker restart command.

        Extracts the container name from config.restart_cmd or uses
        config.name as the container name. Executes `docker restart`
        and waits for completion.

        Args:
            config: Service configuration

        Returns:
            True if docker restart exits with code 0, False otherwise
        """
        container_name = self._extract_container_name(config)

        logger.info(
            f"Attempting to restart {config.name} via Docker",
            extra={"service": config.name, "container": container_name},
        )

        try:
            docker_cmd = f"docker restart {container_name}"

            process = await asyncio.create_subprocess_shell(
                docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                _stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self._subprocess_timeout,
                )
            except TimeoutError:
                logger.error(
                    f"Docker restart timed out for {config.name}, killing process",
                    extra={
                        "service": config.name,
                        "container": container_name,
                        "timeout": self._subprocess_timeout,
                    },
                )
                process.kill()
                await process.wait()
                return False

            if process.returncode == 0:
                logger.info(
                    f"Docker restart succeeded for {config.name}",
                    extra={
                        "service": config.name,
                        "container": container_name,
                        "returncode": 0,
                    },
                )
                return True
            else:
                logger.error(
                    f"Docker restart failed for {config.name} with exit code {process.returncode}",
                    extra={
                        "service": config.name,
                        "container": container_name,
                        "returncode": process.returncode,
                        "stderr": stderr.decode().strip()[:500],
                    },
                )
                return False

        except Exception as e:
            logger.error(
                f"Docker restart failed for {config.name}: unexpected error",
                extra={"service": config.name, "container": container_name, "error": str(e)},
                exc_info=True,
            )
            return False
