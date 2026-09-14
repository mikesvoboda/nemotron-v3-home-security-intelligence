"""Unit tests for Docker client wrapper.

Tests for the DockerClient async wrapper around docker-py for container management.
Follows TDD approach - tests written before implementation.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from docker.errors import DockerException, NotFound

from backend.core.docker_client import DockerClient

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_docker_client():
    """Mock docker-py DockerClient."""
    mock_client = MagicMock()
    mock_client.ping.return_value = True
    mock_client.close = MagicMock()
    mock_client.version.return_value = {"Version": "24.0.0", "ApiVersion": "1.43"}
    return mock_client


@pytest.fixture
def mock_container():
    """Mock Docker container object."""
    container = MagicMock()
    container.id = "test-container-id-123"
    container.short_id = "abc123"
    container.name = "test-container"
    container.status = "running"
    container.attrs = {
        "State": {"Status": "running", "Running": True},
        "Config": {"Image": "test-image:latest"},
    }
    container.start = MagicMock()
    container.stop = MagicMock()
    container.restart = MagicMock()
    container.exec_run = MagicMock(return_value=(0, b"output"))
    return container


@pytest.fixture
def docker_client(mock_docker_client):
    """Create a DockerClient with mocked docker-py client."""
    with patch("backend.core.docker_client.BaseDockerClient") as mock_base:
        mock_base.return_value = mock_docker_client
        client = DockerClient()
        client._client = mock_docker_client
        yield client


# =============================================================================
# Initialization Tests
# =============================================================================


class TestDockerClientInit:
    """Tests for DockerClient initialization."""

    def test_init_with_default_host(self):
        """Test initialization with default Docker host."""
        with patch("backend.core.docker_client.BaseDockerClient") as mock_base:
            mock_base.return_value = MagicMock()
            _client = DockerClient()

            # Default should use from_env()
            mock_base.from_env.assert_called_once()

    def test_init_with_custom_host(self):
        """Test initialization with custom Docker host URL."""
        custom_host = "unix:///var/run/docker.sock"

        with patch("backend.core.docker_client.BaseDockerClient") as mock_base:
            mock_base.return_value = MagicMock()
            _client = DockerClient(docker_host=custom_host)

            mock_base.assert_called_once_with(base_url=custom_host)

    def test_init_with_tcp_host(self):
        """Test initialization with TCP Docker host."""
        tcp_host = "tcp://192.168.1.100:2375"

        with patch("backend.core.docker_client.BaseDockerClient") as mock_base:
            mock_base.return_value = MagicMock()
            _client = DockerClient(docker_host=tcp_host)

            mock_base.assert_called_once_with(base_url=tcp_host)

    def test_init_stores_docker_host(self):
        """Test that docker_host is stored for reconnection."""
        custom_host = "unix:///custom/docker.sock"

        with patch("backend.core.docker_client.BaseDockerClient") as mock_base:
            mock_base.return_value = MagicMock()
            client = DockerClient(docker_host=custom_host)

            assert client._docker_host == custom_host


# =============================================================================
# Connection Tests
# =============================================================================


class TestDockerClientConnect:
    """Tests for Docker connection management."""

    @pytest.mark.asyncio
    async def test_connect_success(self, docker_client, mock_docker_client):
        """Test successful connection to Docker daemon."""
        result = await docker_client.connect()

        assert result is True
        mock_docker_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure(self, mock_docker_client):
        """Test connection failure to Docker daemon."""
        mock_docker_client.ping.side_effect = DockerException("Cannot connect")

        with patch("backend.core.docker_client.BaseDockerClient") as mock_base:
            mock_base.return_value = mock_docker_client
            mock_base.from_env.return_value = mock_docker_client
            client = DockerClient()
            client._client = mock_docker_client

            result = await client.connect()

            assert result is False

    @pytest.mark.asyncio
    async def test_connect_returns_true_when_already_connected(self, docker_client):
        """Test connect returns True if already connected."""
        # First connection
        await docker_client.connect()

        # Second connection should still return True
        result = await docker_client.connect()
        assert result is True

    @pytest.mark.asyncio
    async def test_close_disconnects(self, docker_client, mock_docker_client):
        """Test closing the Docker client connection."""
        await docker_client.close()

        mock_docker_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_none_client(self):
        """Test close handles None client gracefully."""
        with patch("backend.core.docker_client.BaseDockerClient") as mock_base:
            mock_base.from_env.return_value = MagicMock()
            client = DockerClient()
            client._client = None

            # Should not raise
            await client.close()


# =============================================================================
# Container List Tests
# =============================================================================


class TestDockerClientListContainers:
    """Tests for listing containers."""

    @pytest.mark.asyncio
    async def test_list_containers_all(self, docker_client, mock_docker_client, mock_container):
        """Test listing all containers."""
        mock_docker_client.containers.list.return_value = [mock_container]

        containers = await docker_client.list_containers(all=True)

        assert len(containers) == 1
        assert containers[0].id == "test-container-id-123"
        mock_docker_client.containers.list.assert_called_once_with(all=True)

    @pytest.mark.asyncio
    async def test_list_containers_running_only(
        self, docker_client, mock_docker_client, mock_container
    ):
        """Test listing only running containers."""
        mock_docker_client.containers.list.return_value = [mock_container]

        _containers = await docker_client.list_containers(all=False)

        mock_docker_client.containers.list.assert_called_once_with(all=False)

    @pytest.mark.asyncio
    async def test_list_containers_empty(self, docker_client, mock_docker_client):
        """Test listing containers when none exist."""
        mock_docker_client.containers.list.return_value = []

        containers = await docker_client.list_containers()

        assert containers == []

    @pytest.mark.asyncio
    async def test_list_containers_handles_docker_error(self, docker_client, mock_docker_client):
        """Test list_containers handles DockerException gracefully."""
        mock_docker_client.containers.list.side_effect = DockerException("Docker error")

        containers = await docker_client.list_containers()

        assert containers == []


# =============================================================================
# Get Container Tests
# =============================================================================


class TestDockerClientGetContainer:
    """Tests for getting containers by ID or name."""

    @pytest.mark.asyncio
    async def test_get_container_by_id(self, docker_client, mock_docker_client, mock_container):
        """Test getting a container by ID."""
        mock_docker_client.containers.get.return_value = mock_container

        container = await docker_client.get_container("test-container-id-123")

        assert container is not None
        assert container.id == "test-container-id-123"
        mock_docker_client.containers.get.assert_called_once_with("test-container-id-123")

    @pytest.mark.asyncio
    async def test_get_container_not_found(self, docker_client, mock_docker_client):
        """Test getting a container that doesn't exist."""
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")

        container = await docker_client.get_container("nonexistent")

        assert container is None

    @pytest.mark.asyncio
    async def test_get_container_handles_docker_error(self, docker_client, mock_docker_client):
        """Test get_container handles DockerException gracefully."""
        mock_docker_client.containers.get.side_effect = DockerException("Docker error")

        container = await docker_client.get_container("some_id")

        assert container is None

    @pytest.mark.asyncio
    async def test_get_container_by_name(self, docker_client, mock_docker_client, mock_container):
        """Test getting a container by name pattern."""
        mock_docker_client.containers.list.return_value = [mock_container]

        container = await docker_client.get_container_by_name("test-container")

        assert container is not None
        assert container.name == "test-container"

    @pytest.mark.asyncio
    async def test_get_container_by_name_partial_match(
        self, docker_client, mock_docker_client, mock_container
    ):
        """Test getting a container by partial name match."""
        mock_container.name = "my-app-container-1"
        mock_docker_client.containers.list.return_value = [mock_container]

        container = await docker_client.get_container_by_name("my-app")

        assert container is not None
        assert "my-app" in container.name

    @pytest.mark.asyncio
    async def test_get_container_by_name_not_found(self, docker_client, mock_docker_client):
        """Test getting a container by name that doesn't exist."""
        mock_docker_client.containers.list.return_value = []

        container = await docker_client.get_container_by_name("nonexistent")

        assert container is None

    @pytest.mark.asyncio
    async def test_get_container_by_name_multiple_matches_returns_first(
        self, docker_client, mock_docker_client
    ):
        """Test that when multiple containers match, the first is returned."""
        container1 = MagicMock()
        container1.name = "app-container-1"
        container2 = MagicMock()
        container2.name = "app-container-2"
        mock_docker_client.containers.list.return_value = [container1, container2]

        container = await docker_client.get_container_by_name("app-container")

        assert container is not None
        assert container.name == "app-container-1"


# =============================================================================
# Container Lifecycle Tests
# =============================================================================


class TestDockerClientContainerLifecycle:
    """Tests for container start/stop/restart operations."""

    @pytest.mark.asyncio
    async def test_start_container_success(self, docker_client, mock_docker_client, mock_container):
        """Test successfully starting a container."""
        mock_docker_client.containers.get.return_value = mock_container

        result = await docker_client.start_container("test-container-id-123")

        assert result is True
        mock_container.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_container_not_found(self, docker_client, mock_docker_client):
        """Test starting a container that doesn't exist."""
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")

        result = await docker_client.start_container("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_start_container_error(self, docker_client, mock_docker_client, mock_container):
        """Test starting a container that fails."""
        mock_docker_client.containers.get.return_value = mock_container
        mock_container.start.side_effect = DockerException("Cannot start")

        result = await docker_client.start_container("test-container-id-123")

        assert result is False

    @pytest.mark.asyncio
    async def test_stop_container_success(self, docker_client, mock_docker_client, mock_container):
        """Test successfully stopping a container."""
        mock_docker_client.containers.get.return_value = mock_container

        result = await docker_client.stop_container("test-container-id-123")

        assert result is True
        mock_container.stop.assert_called_once_with(timeout=10)

    @pytest.mark.asyncio
    async def test_stop_container_with_custom_timeout(
        self, docker_client, mock_docker_client, mock_container
    ):
        """Test stopping a container with custom timeout."""
        mock_docker_client.containers.get.return_value = mock_container

        result = await docker_client.stop_container("test-container-id-123", timeout=30)

        assert result is True
        mock_container.stop.assert_called_once_with(timeout=30)

    @pytest.mark.asyncio
    async def test_stop_container_not_found(self, docker_client, mock_docker_client):
        """Test stopping a container that doesn't exist."""
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")

        result = await docker_client.stop_container("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_restart_container_success(
        self, docker_client, mock_docker_client, mock_container
    ):
        """Test successfully restarting a container."""
        mock_docker_client.containers.get.return_value = mock_container

        result = await docker_client.restart_container("test-container-id-123")

        assert result is True
        mock_container.restart.assert_called_once_with(timeout=10)

    @pytest.mark.asyncio
    async def test_restart_container_with_custom_timeout(
        self, docker_client, mock_docker_client, mock_container
    ):
        """Test restarting a container with custom timeout."""
        mock_docker_client.containers.get.return_value = mock_container

        result = await docker_client.restart_container("test-container-id-123", timeout=60)

        assert result is True
        mock_container.restart.assert_called_once_with(timeout=60)

    @pytest.mark.asyncio
    async def test_restart_container_not_found(self, docker_client, mock_docker_client):
        """Test restarting a container that doesn't exist."""
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")

        result = await docker_client.restart_container("nonexistent")

        assert result is False


# =============================================================================
# Container Exec Tests
# =============================================================================


class TestDockerClientExec:
    """Tests for executing commands in containers."""

    @pytest.mark.asyncio
    async def test_exec_run_success(self, docker_client, mock_docker_client, mock_container):
        """Test executing a command in a container."""
        mock_docker_client.containers.get.return_value = mock_container
        mock_container.exec_run.return_value = (0, b"command output")

        exit_code = await docker_client.exec_run("test-container-id-123", "echo hello")

        assert exit_code == 0
        mock_container.exec_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_exec_run_failure(self, docker_client, mock_docker_client, mock_container):
        """Test executing a command that fails."""
        mock_docker_client.containers.get.return_value = mock_container
        mock_container.exec_run.return_value = (1, b"error")

        exit_code = await docker_client.exec_run("test-container-id-123", "invalid_command")

        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_exec_run_container_not_found(self, docker_client, mock_docker_client):
        """Test exec_run when container doesn't exist."""
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")

        exit_code = await docker_client.exec_run("nonexistent", "echo hello")

        assert exit_code == -1

    @pytest.mark.asyncio
    async def test_exec_run_docker_error(self, docker_client, mock_docker_client, mock_container):
        """Test exec_run handles DockerException."""
        mock_docker_client.containers.get.return_value = mock_container
        mock_container.exec_run.side_effect = DockerException("Exec failed")

        exit_code = await docker_client.exec_run("test-container-id-123", "echo hello")

        assert exit_code == -1

    @pytest.mark.asyncio
    async def test_exec_run_with_timeout(self, docker_client, mock_docker_client, mock_container):
        """Test exec_run passes command correctly."""
        mock_docker_client.containers.get.return_value = mock_container
        mock_container.exec_run.return_value = (0, b"output")

        exit_code = await docker_client.exec_run("test-container-id-123", "sleep 1", timeout=5)

        assert exit_code == 0
        # Verify the command was passed
        call_args = mock_container.exec_run.call_args
        assert "sleep 1" in str(call_args)


# =============================================================================
# Container Status Tests
# =============================================================================


class TestDockerClientStatus:
    """Tests for getting container status."""

    @pytest.mark.asyncio
    async def test_get_container_status_running(
        self, docker_client, mock_docker_client, mock_container
    ):
        """Test getting status of a running container."""
        mock_container.status = "running"
        mock_docker_client.containers.get.return_value = mock_container

        status = await docker_client.get_container_status("test-container-id-123")

        assert status == "running"

    @pytest.mark.asyncio
    async def test_get_container_status_exited(
        self, docker_client, mock_docker_client, mock_container
    ):
        """Test getting status of an exited container."""
        mock_container.status = "exited"
        mock_docker_client.containers.get.return_value = mock_container

        status = await docker_client.get_container_status("test-container-id-123")

        assert status == "exited"

    @pytest.mark.asyncio
    async def test_get_container_status_not_found(self, docker_client, mock_docker_client):
        """Test getting status of a container that doesn't exist."""
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")

        status = await docker_client.get_container_status("nonexistent")

        assert status is None

    @pytest.mark.asyncio
    async def test_get_container_status_paused(
        self, docker_client, mock_docker_client, mock_container
    ):
        """Test getting status of a paused container."""
        mock_container.status = "paused"
        mock_docker_client.containers.get.return_value = mock_container

        status = await docker_client.get_container_status("test-container-id-123")

        assert status == "paused"

    @pytest.mark.asyncio
    async def test_get_container_status_restarting(
        self, docker_client, mock_docker_client, mock_container
    ):
        """Test getting status of a restarting container."""
        mock_container.status = "restarting"
        mock_docker_client.containers.get.return_value = mock_container

        status = await docker_client.get_container_status("test-container-id-123")

        assert status == "restarting"


# =============================================================================
# Context Manager Tests
# =============================================================================


class TestDockerClientContextManager:
    """Tests for context manager support."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self, mock_docker_client):
        """Test DockerClient as async context manager."""
        with patch("backend.core.docker_client.BaseDockerClient") as mock_base:
            mock_base.from_env.return_value = mock_docker_client
            mock_docker_client.ping.return_value = True

            async with DockerClient() as client:
                assert client._client is not None

            mock_docker_client.close.assert_called_once()


# =============================================================================
# Thread Safety / Async Tests
# =============================================================================


class TestDockerClientAsync:
    """Tests for async behavior and thread safety."""

    @pytest.mark.asyncio
    async def test_operations_are_async(self, docker_client, mock_docker_client, mock_container):
        """Test that operations properly use asyncio.to_thread."""
        mock_docker_client.containers.list.return_value = [mock_container]

        # Run multiple operations concurrently
        results = await asyncio.gather(
            docker_client.list_containers(),
            docker_client.connect(),
        )

        assert len(results) == 2
        # First result is list of containers
        assert isinstance(results[0], list)
        # Second result is connect success
        assert results[1] is True

    @pytest.mark.asyncio
    async def test_not_connected_raises_error_for_operations(self):
        """Test that operations fail gracefully when not connected."""
        with patch("backend.core.docker_client.BaseDockerClient") as mock_base:
            mock_base.from_env.return_value = None
            client = DockerClient()
            client._client = None

            # list_containers should return empty list
            containers = await client.list_containers()
            assert containers == []


# =============================================================================
# Podman Compatibility Tests
# =============================================================================


class TestDockerClientPodmanCompatibility:
    """Tests for Podman compatibility."""

    def test_supports_podman_socket(self):
        """Test that client can be configured for Podman socket."""
        podman_socket = "unix:///run/user/1000/podman/podman.sock"

        with patch("backend.core.docker_client.BaseDockerClient") as mock_base:
            mock_base.return_value = MagicMock()
            _client = DockerClient(docker_host=podman_socket)

            mock_base.assert_called_once_with(base_url=podman_socket)

    def test_supports_podman_tcp(self):
        """Test that client can be configured for Podman TCP."""
        podman_tcp = "tcp://localhost:8888"

        with patch("backend.core.docker_client.BaseDockerClient") as mock_base:
            mock_base.return_value = MagicMock()
            _client = DockerClient(docker_host=podman_tcp)

            mock_base.assert_called_once_with(base_url=podman_tcp)


# =============================================================================
# Logging Tests
# =============================================================================


class TestDockerClientLogging:
    """Tests for logging behavior."""

    @pytest.mark.asyncio
    async def test_logs_connection_success(self, docker_client, mock_docker_client, caplog):
        """Test that successful connection is logged."""
        import logging

        with caplog.at_level(logging.INFO):
            await docker_client.connect()

        assert any("docker" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_logs_connection_failure(self, mock_docker_client, caplog):
        """Test that connection failure is logged."""
        import logging

        mock_docker_client.ping.side_effect = DockerException("Cannot connect")

        with patch("backend.core.docker_client.BaseDockerClient") as mock_base:
            mock_base.from_env.return_value = mock_docker_client
            client = DockerClient()
            client._client = mock_docker_client

            with caplog.at_level(logging.WARNING):
                await client.connect()

        assert any(
            "docker" in record.message.lower() or "connect" in record.message.lower()
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_logs_container_not_found(self, docker_client, mock_docker_client, caplog):
        """Test that container not found is logged appropriately."""
        import logging

        mock_docker_client.containers.get.side_effect = NotFound("Container not found")

        with caplog.at_level(logging.DEBUG):
            await docker_client.get_container("nonexistent")

        # NotFound should be logged at debug level (expected case)
        assert any("not found" in record.message.lower() for record in caplog.records)


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestDockerClientErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_handles_api_error_gracefully(self, docker_client, mock_docker_client):
        """Test that API errors are handled gracefully."""
        from docker.errors import APIError

        mock_docker_client.containers.list.side_effect = APIError("API Error")

        containers = await docker_client.list_containers()

        assert containers == []

    @pytest.mark.asyncio
    async def test_handles_image_not_found(self, docker_client, mock_docker_client):
        """Test handling of image not found errors."""
        from docker.errors import ImageNotFound

        mock_docker_client.containers.get.side_effect = ImageNotFound("Image not found")

        container = await docker_client.get_container("some_id")

        assert container is None

    @pytest.mark.asyncio
    async def test_handles_unexpected_exception(self, docker_client, mock_docker_client):
        """Test handling of unexpected exceptions."""
        mock_docker_client.containers.list.side_effect = RuntimeError("Unexpected error")

        containers = await docker_client.list_containers()

        assert containers == []
