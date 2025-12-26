"""Unit tests for service manager implementations.

Tests for ServiceConfig, ShellServiceManager, and DockerServiceManager.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.services.service_managers import (
    DockerServiceManager,
    ServiceConfig,
    ShellServiceManager,
)

# Fixtures


@pytest.fixture
def sample_config():
    """Sample service configuration for testing."""
    return ServiceConfig(
        name="test_service",
        health_url="http://localhost:9999/health",
        restart_cmd="echo success",
        health_timeout=1.0,
        max_retries=3,
        backoff_base=1.0,
    )


@pytest.fixture
def redis_config():
    """Redis service configuration for testing."""
    return ServiceConfig(
        name="redis",
        health_url="redis://localhost:6379",
        restart_cmd="sudo systemctl restart redis",
    )


@pytest.fixture
def shell_manager():
    """Shell service manager instance."""
    return ShellServiceManager(subprocess_timeout=5.0)


@pytest.fixture
def docker_manager():
    """Docker service manager instance."""
    return DockerServiceManager(subprocess_timeout=5.0)


# ShellServiceManager Tests - Health Checks


@pytest.mark.asyncio
async def test_shell_health_check_success(shell_manager, sample_config):
    """Test health check when service responds with HTTP 200."""
    with patch("backend.services.service_managers.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()  # Does not raise
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await shell_manager.check_health(sample_config)

        assert result is True
        mock_client.get.assert_called_once_with(sample_config.health_url)


@pytest.mark.asyncio
async def test_shell_health_check_connection_error(shell_manager, sample_config):
    """Test health check when service is not reachable (connection error)."""
    with patch("backend.services.service_managers.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await shell_manager.check_health(sample_config)

        assert result is False


@pytest.mark.asyncio
async def test_shell_health_check_timeout(shell_manager, sample_config):
    """Test health check when service times out."""
    with patch("backend.services.service_managers.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await shell_manager.check_health(sample_config)

        assert result is False


@pytest.mark.asyncio
async def test_shell_health_check_http_error(shell_manager, sample_config):
    """Test health check when service returns HTTP 500 error."""
    with patch("backend.services.service_managers.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Internal Server Error", request=MagicMock(), response=mock_response
            )
        )
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await shell_manager.check_health(sample_config)

        assert result is False


@pytest.mark.asyncio
async def test_shell_health_check_unexpected_exception(shell_manager, sample_config):
    """Test health check when unexpected exception occurs."""
    with patch("backend.services.service_managers.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=ValueError("Unexpected error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await shell_manager.check_health(sample_config)

        assert result is False


# ShellServiceManager Tests - Redis Health Checks


@pytest.mark.asyncio
async def test_shell_health_check_redis_ping_success(shell_manager, redis_config):
    """Test Redis health check when redis-cli ping returns PONG."""
    with patch("asyncio.create_subprocess_shell") as mock_proc:
        process = AsyncMock()
        process.returncode = 0
        process.communicate = AsyncMock(return_value=(b"PONG\n", b""))
        mock_proc.return_value = process

        result = await shell_manager.check_health(redis_config)

        assert result is True
        mock_proc.assert_called_once()
        # Verify redis-cli ping was called
        call_args = mock_proc.call_args
        assert "redis-cli ping" in call_args[0][0]


@pytest.mark.asyncio
async def test_shell_health_check_redis_ping_failure(shell_manager, redis_config):
    """Test Redis health check when redis-cli ping fails (not PONG)."""
    with patch("asyncio.create_subprocess_shell") as mock_proc:
        process = AsyncMock()
        process.returncode = 1
        process.communicate = AsyncMock(return_value=(b"", b"Could not connect to Redis"))
        mock_proc.return_value = process

        result = await shell_manager.check_health(redis_config)

        assert result is False


@pytest.mark.asyncio
async def test_shell_health_check_redis_ping_timeout(shell_manager, redis_config):
    """Test Redis health check when redis-cli ping times out."""
    with patch("asyncio.create_subprocess_shell") as mock_proc:
        process = AsyncMock()
        process.communicate = AsyncMock(side_effect=TimeoutError("Timed out"))
        process.kill = MagicMock()
        process.wait = AsyncMock()
        mock_proc.return_value = process

        result = await shell_manager.check_health(redis_config)

        assert result is False
        process.kill.assert_called_once()


@pytest.mark.asyncio
async def test_shell_health_check_redis_unexpected_exception(shell_manager, redis_config):
    """Test Redis health check when unexpected exception occurs."""
    with patch("asyncio.create_subprocess_shell") as mock_proc:
        mock_proc.side_effect = Exception("Unexpected subprocess error")

        result = await shell_manager.check_health(redis_config)

        assert result is False


# ShellServiceManager Tests - Restart


@pytest.mark.asyncio
async def test_shell_restart_success(shell_manager, sample_config):
    """Test restart when subprocess exits with code 0."""
    with patch("asyncio.create_subprocess_shell") as mock_proc:
        process = AsyncMock()
        process.returncode = 0
        process.communicate = AsyncMock(return_value=(b"success\n", b""))
        mock_proc.return_value = process

        result = await shell_manager.restart(sample_config)

        assert result is True
        mock_proc.assert_called_once()
        # Verify restart command was executed
        call_args = mock_proc.call_args
        assert sample_config.restart_cmd in call_args[0][0]


@pytest.mark.asyncio
async def test_shell_restart_failure(shell_manager, sample_config):
    """Test restart when subprocess exits with non-zero code."""
    with patch("asyncio.create_subprocess_shell") as mock_proc:
        process = AsyncMock()
        process.returncode = 1
        process.communicate = AsyncMock(return_value=(b"", b"Error: restart failed"))
        mock_proc.return_value = process

        result = await shell_manager.restart(sample_config)

        assert result is False


@pytest.mark.asyncio
async def test_shell_restart_timeout(shell_manager, sample_config):
    """Test restart when subprocess times out."""
    with patch("asyncio.create_subprocess_shell") as mock_proc:
        process = AsyncMock()
        process.communicate = AsyncMock(side_effect=TimeoutError("Subprocess timeout"))
        process.kill = MagicMock()
        process.wait = AsyncMock()
        mock_proc.return_value = process

        result = await shell_manager.restart(sample_config)

        assert result is False
        process.kill.assert_called_once()


@pytest.mark.asyncio
async def test_shell_restart_exception(shell_manager, sample_config):
    """Test restart when unexpected exception occurs."""
    with patch("asyncio.create_subprocess_shell") as mock_proc:
        mock_proc.side_effect = Exception("Failed to create subprocess")

        result = await shell_manager.restart(sample_config)

        assert result is False


# DockerServiceManager Tests - Health Check


@pytest.mark.asyncio
async def test_docker_health_check_delegates_to_shell(docker_manager, sample_config):
    """Test that DockerServiceManager delegates health checks to ShellServiceManager."""
    with patch.object(
        docker_manager._shell_manager, "check_health", new_callable=AsyncMock
    ) as mock_check:
        mock_check.return_value = True

        result = await docker_manager.check_health(sample_config)

        assert result is True
        mock_check.assert_called_once_with(sample_config)


@pytest.mark.asyncio
async def test_docker_health_check_failure_delegates(docker_manager, sample_config):
    """Test that health check failure is properly delegated."""
    with patch.object(
        docker_manager._shell_manager, "check_health", new_callable=AsyncMock
    ) as mock_check:
        mock_check.return_value = False

        result = await docker_manager.check_health(sample_config)

        assert result is False
        mock_check.assert_called_once_with(sample_config)


# DockerServiceManager Tests - Restart


@pytest.mark.asyncio
async def test_docker_restart_success(docker_manager, sample_config):
    """Test Docker restart when docker restart command succeeds."""
    with patch("asyncio.create_subprocess_shell") as mock_proc:
        process = AsyncMock()
        process.returncode = 0
        process.communicate = AsyncMock(return_value=(b"test_service\n", b""))
        mock_proc.return_value = process

        result = await docker_manager.restart(sample_config)

        assert result is True
        mock_proc.assert_called_once()
        # Verify docker restart command was used
        call_args = mock_proc.call_args
        assert "docker restart" in call_args[0][0]


@pytest.mark.asyncio
async def test_docker_restart_extracts_container_name():
    """Test that container name is correctly extracted from 'docker restart foo' command."""
    manager = DockerServiceManager()
    config = ServiceConfig(
        name="test_service",
        health_url="http://localhost:8000/health",
        restart_cmd="docker restart my_container",
    )

    container_name = manager._extract_container_name(config)

    assert container_name == "my_container"


@pytest.mark.asyncio
async def test_docker_restart_extracts_container_name_with_flags():
    """Test container name extraction when docker command has flags."""
    manager = DockerServiceManager()
    config = ServiceConfig(
        name="test_service",
        health_url="http://localhost:8000/health",
        restart_cmd="docker restart --time 10 my_container",
    )

    container_name = manager._extract_container_name(config)

    # Should take the last token as container name
    assert container_name == "my_container"


@pytest.mark.asyncio
async def test_docker_restart_uses_service_name_fallback():
    """Test that service name is used as fallback when restart_cmd is not a docker command."""
    manager = DockerServiceManager()
    config = ServiceConfig(
        name="my_service",
        health_url="http://localhost:8000/health",
        restart_cmd="systemctl restart my_service",
    )

    container_name = manager._extract_container_name(config)

    # Should fall back to config.name
    assert container_name == "my_service"


@pytest.mark.asyncio
async def test_docker_restart_failure(docker_manager, sample_config):
    """Test Docker restart when docker restart command fails."""
    with patch("asyncio.create_subprocess_shell") as mock_proc:
        process = AsyncMock()
        process.returncode = 1
        process.communicate = AsyncMock(
            return_value=(b"", b"Error: No such container: test_service")
        )
        mock_proc.return_value = process

        result = await docker_manager.restart(sample_config)

        assert result is False


@pytest.mark.asyncio
async def test_docker_restart_timeout(docker_manager, sample_config):
    """Test Docker restart when command times out."""
    with patch("asyncio.create_subprocess_shell") as mock_proc:
        process = AsyncMock()
        process.communicate = AsyncMock(side_effect=TimeoutError("Docker restart timeout"))
        process.kill = MagicMock()
        process.wait = AsyncMock()
        mock_proc.return_value = process

        result = await docker_manager.restart(sample_config)

        assert result is False
        process.kill.assert_called_once()


@pytest.mark.asyncio
async def test_docker_restart_exception(docker_manager, sample_config):
    """Test Docker restart when unexpected exception occurs."""
    with patch("asyncio.create_subprocess_shell") as mock_proc:
        mock_proc.side_effect = Exception("Docker daemon not running")

        result = await docker_manager.restart(sample_config)

        assert result is False


# ServiceConfig Tests


def test_service_config_defaults():
    """Test ServiceConfig default values."""
    config = ServiceConfig(
        name="test",
        health_url="http://localhost:8000/health",
        restart_cmd="restart.sh",
    )

    assert config.name == "test"
    assert config.health_url == "http://localhost:8000/health"
    assert config.restart_cmd == "restart.sh"
    assert config.health_timeout == 5.0  # Default
    assert config.max_retries == 3  # Default
    assert config.backoff_base == 5.0  # Default


def test_service_config_custom_values():
    """Test ServiceConfig with custom values."""
    config = ServiceConfig(
        name="custom_service",
        health_url="http://localhost:9000/health",
        restart_cmd="custom_restart.sh",
        health_timeout=10.0,
        max_retries=5,
        backoff_base=2.0,
    )

    assert config.name == "custom_service"
    assert config.health_url == "http://localhost:9000/health"
    assert config.restart_cmd == "custom_restart.sh"
    assert config.health_timeout == 10.0
    assert config.max_retries == 5
    assert config.backoff_base == 2.0


# Edge Cases


@pytest.mark.asyncio
async def test_shell_manager_subprocess_timeout_configuration():
    """Test that ShellServiceManager uses configured subprocess timeout."""
    manager = ShellServiceManager(subprocess_timeout=120.0)
    assert manager._subprocess_timeout == 120.0


@pytest.mark.asyncio
async def test_docker_manager_subprocess_timeout_configuration():
    """Test that DockerServiceManager uses configured subprocess timeout."""
    manager = DockerServiceManager(subprocess_timeout=180.0)
    assert manager._subprocess_timeout == 180.0


@pytest.mark.asyncio
async def test_shell_health_check_detects_redis_by_name_case_insensitive(shell_manager):
    """Test that Redis detection is case-insensitive."""
    config = ServiceConfig(
        name="REDIS_CACHE",  # Uppercase
        health_url="redis://localhost:6379",
        restart_cmd="restart-redis.sh",
    )

    with patch("asyncio.create_subprocess_shell") as mock_proc:
        process = AsyncMock()
        process.returncode = 0
        process.communicate = AsyncMock(return_value=(b"PONG\n", b""))
        mock_proc.return_value = process

        result = await shell_manager.check_health(config)

        assert result is True
        # Should use redis-cli ping, not HTTP
        call_args = mock_proc.call_args
        assert "redis-cli ping" in call_args[0][0]


@pytest.mark.asyncio
async def test_docker_restart_with_empty_restart_cmd():
    """Test container name extraction with empty restart_cmd."""
    manager = DockerServiceManager()
    config = ServiceConfig(
        name="fallback_name",
        health_url="http://localhost:8000/health",
        restart_cmd="",
    )

    container_name = manager._extract_container_name(config)

    # Should fall back to config.name
    assert container_name == "fallback_name"


@pytest.mark.asyncio
async def test_docker_restart_with_whitespace_only_restart_cmd():
    """Test container name extraction with whitespace-only restart_cmd."""
    manager = DockerServiceManager()
    config = ServiceConfig(
        name="fallback_name",
        health_url="http://localhost:8000/health",
        restart_cmd="   ",
    )

    container_name = manager._extract_container_name(config)

    # Should fall back to config.name after strip()
    assert container_name == "fallback_name"
