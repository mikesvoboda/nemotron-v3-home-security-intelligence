"""Unit tests for service_managers module."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.services.service_managers import (
    ALLOWED_RESTART_SCRIPTS,
    DockerServiceManager,
    ServiceConfig,
    ShellServiceManager,
    validate_container_name,
    validate_restart_command,
)

# Fixtures


@pytest.fixture
def sample_config():
    """Sample service configuration for testing.

    Uses an allowed restart command from the security allowlist.
    """
    return ServiceConfig(
        name="yolo26",
        health_url="http://localhost:9999/health",
        restart_cmd="ai/start_detector.sh",  # Allowed restart script
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
        restart_cmd="scripts/restart_redis.sh",  # Allowed restart script
    )


@pytest.fixture
def shell_manager():
    """Create a ShellServiceManager."""
    return ShellServiceManager(subprocess_timeout=5.0)


@pytest.fixture
def docker_manager():
    """Create a DockerServiceManager."""
    return DockerServiceManager(subprocess_timeout=5.0)


@pytest.fixture
def config_with_restart():
    """Create a ServiceConfig with restart_cmd (allowed)."""
    return ServiceConfig(
        name="test_service",
        health_url="http://localhost:9999/health",
        restart_cmd="ai/start_detector.sh",  # Use allowed script
        health_timeout=1.0,
        max_retries=3,
        backoff_base=5.0,
    )


@pytest.fixture
def config_no_restart():
    """Create a ServiceConfig without restart_cmd."""
    return ServiceConfig(
        name="test_service_no_restart",
        health_url="http://localhost:9999/health",
        restart_cmd=None,
        health_timeout=1.0,
        max_retries=3,
        backoff_base=5.0,
    )


# ShellServiceManager Tests - Health Checks


@pytest.mark.asyncio
async def test_shell_health_check_success(shell_manager, sample_config):
    """Test health check when service responds with HTTP 200."""
    with patch("backend.services.service_managers.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock(spec=httpx.Response)
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
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Internal Server Error",
                request=MagicMock(spec=httpx.Request),
                response=mock_response,
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
    """Test restart when subprocess exits with code 0.

    Security: Tests that shell=False is used (create_subprocess_exec) to prevent
    command injection.
    """
    with patch("asyncio.create_subprocess_exec") as mock_proc:
        process = AsyncMock()
        process.returncode = 0
        process.communicate = AsyncMock(return_value=(b"success\n", b""))
        mock_proc.return_value = process

        result = await shell_manager.restart(sample_config)

        assert result is True
        mock_proc.assert_called_once()
        # Verify restart command was parsed and passed as arguments
        call_args = mock_proc.call_args
        # First argument should be the script path
        assert call_args[0][0] == "ai/start_detector.sh"


@pytest.mark.asyncio
async def test_shell_restart_failure(shell_manager, sample_config):
    """Test restart when subprocess exits with non-zero code."""
    with patch("asyncio.create_subprocess_exec") as mock_proc:
        process = AsyncMock()
        process.returncode = 1
        process.communicate = AsyncMock(return_value=(b"", b"Error: restart failed"))
        mock_proc.return_value = process

        result = await shell_manager.restart(sample_config)

        assert result is False


@pytest.mark.asyncio
async def test_shell_restart_timeout(shell_manager, sample_config):
    """Test restart when subprocess times out."""
    with patch("asyncio.create_subprocess_exec") as mock_proc:
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
    with patch("asyncio.create_subprocess_exec") as mock_proc:
        mock_proc.side_effect = Exception("Failed to create subprocess")

        result = await shell_manager.restart(sample_config)

        assert result is False


@pytest.mark.asyncio
async def test_shell_restart_rejected_command(shell_manager):
    """Test that commands not in allowlist are rejected.

    Security: Verifies command injection protection by rejecting arbitrary commands.
    """
    malicious_config = ServiceConfig(
        name="malicious",
        health_url="http://localhost:9999/health",
        restart_cmd="echo pwned; cat /etc/passwd",  # Not in allowlist
    )

    result = await shell_manager.restart(malicious_config)

    # Should reject the command without executing it
    assert result is False


@pytest.mark.asyncio
async def test_shell_manager_restart_returns_false_when_restart_cmd_none(
    shell_manager, config_no_restart
):
    """Test that ShellServiceManager.restart returns False when restart_cmd is None."""
    result = await shell_manager.restart(config_no_restart)
    assert result is False


@pytest.mark.asyncio
async def test_shell_manager_restart_works_with_restart_cmd(shell_manager, config_with_restart):
    """Test that ShellServiceManager.restart works when restart_cmd is set."""
    with patch("asyncio.create_subprocess_exec") as mock_proc:
        process = AsyncMock()
        process.returncode = 0
        process.communicate = AsyncMock(return_value=(b"success\n", b""))
        mock_proc.return_value = process

        result = await shell_manager.restart(config_with_restart)

        assert result is True


# Security validation tests


def test_validate_restart_command_allowed():
    """Test that allowed restart scripts are accepted."""
    for cmd in ALLOWED_RESTART_SCRIPTS:
        assert validate_restart_command(cmd) is True


def test_validate_restart_command_docker():
    """Test that valid docker restart commands are accepted."""
    assert validate_restart_command("docker restart yolo26") is True
    assert validate_restart_command("docker restart nemotron-service") is True
    assert validate_restart_command("docker restart my_container_123") is True


def test_validate_restart_command_rejected():
    """Test that dangerous commands are rejected."""
    # Command injection attempts
    assert validate_restart_command("echo pwned") is False
    assert validate_restart_command("docker restart foo; rm -rf /") is False
    assert validate_restart_command("ai/start_detector.sh; cat /etc/passwd") is False
    # Path traversal
    assert validate_restart_command("../../../bin/bash") is False


def test_validate_container_name_valid():
    """Test valid container names are accepted."""
    assert validate_container_name("yolo26") is True
    assert validate_container_name("nemotron-service") is True
    assert validate_container_name("my_container_123") is True
    assert validate_container_name("A1") is True


def test_validate_container_name_invalid():
    """Test invalid container names are rejected."""
    # Empty or None
    assert validate_container_name("") is False
    # Shell injection
    assert validate_container_name("foo; rm -rf /") is False
    assert validate_container_name("$(whoami)") is False
    assert validate_container_name("foo`id`bar") is False
    # Path characters
    assert validate_container_name("foo/bar") is False
    assert validate_container_name("../etc") is False
    # Too long
    assert validate_container_name("a" * 200) is False


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


@pytest.fixture
def docker_sample_config():
    """Docker service configuration for testing.

    Uses a docker restart command with valid container name.
    """
    return ServiceConfig(
        name="yolo26",
        health_url="http://localhost:8090/health",
        restart_cmd="docker restart yolo26",
    )


@pytest.mark.asyncio
async def test_docker_restart_success(docker_manager, docker_sample_config):
    """Test Docker restart when docker restart command succeeds.

    Security: Tests that shell=False is used (create_subprocess_exec) to prevent
    command injection through container names.
    """
    with patch("asyncio.create_subprocess_exec") as mock_proc:
        process = AsyncMock()
        process.returncode = 0
        process.communicate = AsyncMock(return_value=(b"yolo26\n", b""))
        mock_proc.return_value = process

        result = await docker_manager.restart(docker_sample_config)

        assert result is True
        mock_proc.assert_called_once()
        # Verify docker restart command was executed with exec (not shell)
        call_args = mock_proc.call_args
        assert call_args[0] == ("docker", "restart", "yolo26")


@pytest.mark.asyncio
async def test_docker_restart_extracts_container_name():
    """Test that container name is correctly extracted from 'docker restart foo' command."""
    manager = DockerServiceManager()
    config = ServiceConfig(
        name="test_service",
        health_url="http://localhost:9999/health",
        restart_cmd="docker restart my_container",
    )

    container_name = manager._extract_container_name(config)

    assert container_name == "my_container"


@pytest.mark.asyncio
async def test_docker_restart_uses_service_name_fallback():
    """Test that service name is used as fallback when restart_cmd is not a docker command."""
    manager = DockerServiceManager()
    config = ServiceConfig(
        name="my_service",
        health_url="http://localhost:8000/health",
        restart_cmd="ai/start_detector.sh",  # Not a docker command
    )

    container_name = manager._extract_container_name(config)

    # Should fall back to config.name
    assert container_name == "my_service"


@pytest.mark.asyncio
async def test_docker_restart_rejects_invalid_container_name():
    """Test that invalid container names are rejected.

    Security: Verifies protection against command injection through container names.
    """
    manager = DockerServiceManager()
    config = ServiceConfig(
        name="test_service",
        health_url="http://localhost:8000/health",
        restart_cmd="docker restart foo;rm -rf /",  # Injection attempt
    )

    container_name = manager._extract_container_name(config)

    # Should reject the invalid container name
    assert container_name is None


@pytest.mark.asyncio
async def test_docker_restart_failure(docker_manager, docker_sample_config):
    """Test Docker restart when docker restart command fails."""
    with patch("asyncio.create_subprocess_exec") as mock_proc:
        process = AsyncMock()
        process.returncode = 1
        process.communicate = AsyncMock(return_value=(b"", b"Error: No such container: yolo26"))
        mock_proc.return_value = process

        result = await docker_manager.restart(docker_sample_config)

        assert result is False


@pytest.mark.asyncio
async def test_docker_restart_timeout(docker_manager, docker_sample_config):
    """Test Docker restart when command times out."""
    with patch("asyncio.create_subprocess_exec") as mock_proc:
        process = AsyncMock()
        process.communicate = AsyncMock(side_effect=TimeoutError("Docker restart timeout"))
        process.kill = MagicMock()
        process.wait = AsyncMock()
        mock_proc.return_value = process

        result = await docker_manager.restart(docker_sample_config)

        assert result is False
        process.kill.assert_called_once()


@pytest.mark.asyncio
async def test_docker_restart_exception(docker_manager, docker_sample_config):
    """Test Docker restart when unexpected exception occurs."""
    with patch("asyncio.create_subprocess_exec") as mock_proc:
        mock_proc.side_effect = Exception("Docker daemon not running")

        result = await docker_manager.restart(docker_sample_config)

        assert result is False


# ServiceConfig Tests


def test_service_config_defaults():
    """Test ServiceConfig default values."""
    config = ServiceConfig(
        name="test",
        health_url="http://localhost:9999/health",
    )
    assert config.restart_cmd is None
    assert config.health_timeout == 5.0
    assert config.max_retries == 3
    assert config.backoff_base == 5.0


def test_service_manager_config_restart_cmd_can_be_set():
    """Test that restart_cmd can be explicitly set for service managers."""
    config = ServiceConfig(
        name="test",
        health_url="http://localhost:9999/health",
        restart_cmd="echo restart",
    )
    assert config.restart_cmd == "echo restart"


# DockerServiceManager._extract_container_name with None restart_cmd


def test_docker_manager_extract_container_name_returns_none_when_restart_cmd_none(
    docker_manager, config_no_restart
):
    """Test that _extract_container_name returns None when restart_cmd is None."""
    result = docker_manager._extract_container_name(config_no_restart)
    assert result is None


def test_docker_manager_extract_container_name_with_docker_restart_prefix(docker_manager):
    """Test container name extraction from 'docker restart <name>' command."""
    config = ServiceConfig(
        name="test",
        health_url="http://localhost:9999/health",
        restart_cmd="docker restart my_container",
    )
    result = docker_manager._extract_container_name(config)
    assert result == "my_container"


def test_docker_manager_extract_container_name_without_docker_prefix(docker_manager):
    """Test container name falls back to service name when no docker prefix."""
    config = ServiceConfig(
        name="my_service",
        health_url="http://localhost:9999/health",
        restart_cmd="some_script.sh",
    )
    result = docker_manager._extract_container_name(config)
    assert result == "my_service"


# DockerServiceManager.restart with None restart_cmd


@pytest.mark.asyncio
async def test_docker_manager_restart_returns_false_when_restart_cmd_none(
    docker_manager, config_no_restart
):
    """Test that DockerServiceManager.restart returns False when restart_cmd is None."""
    result = await docker_manager.restart(config_no_restart)
    assert result is False


# FileNotFoundError Handling Tests (NEM-1241)


@pytest.mark.asyncio
async def test_shell_restart_handles_file_not_found(shell_manager, sample_config):
    """Test that ShellServiceManager handles FileNotFoundError gracefully.

    This occurs when the restart script/command is not found (e.g., missing executable).
    The fix for NEM-1241 ensures this doesn't crash but returns False with a warning.
    """
    with patch("asyncio.create_subprocess_exec") as mock_proc:
        mock_proc.side_effect = FileNotFoundError(
            "No such file or directory: 'ai/start_detector.sh'"
        )

        result = await shell_manager.restart(sample_config)

        assert result is False


@pytest.mark.asyncio
async def test_docker_restart_handles_file_not_found(docker_manager):
    """Test that DockerServiceManager handles FileNotFoundError gracefully.

    This occurs when docker/podman CLI is not installed in the container.
    The fix for NEM-1241 ensures this doesn't crash but returns False with a warning.
    """
    config = ServiceConfig(
        name="yolo26",
        health_url="http://localhost:8090/health",
        restart_cmd="docker restart yolo26",
    )

    with patch("asyncio.create_subprocess_exec") as mock_proc:
        mock_proc.side_effect = FileNotFoundError("No such file or directory: 'docker'")

        result = await docker_manager.restart(config)

        assert result is False


@pytest.mark.asyncio
async def test_shell_restart_file_not_found_logs_warning(shell_manager, sample_config):
    """Test that FileNotFoundError in ShellServiceManager logs a warning, not error.

    NEM-1241: Changed from ERROR to WARNING since this is an expected condition
    when running in containerized environments.
    """
    with patch("asyncio.create_subprocess_exec") as mock_proc:
        mock_proc.side_effect = FileNotFoundError("ai/start_detector.sh not found")

        with patch("backend.services.service_managers.logger") as mock_logger:
            await shell_manager.restart(sample_config)

            # Should log warning, not error
            mock_logger.warning.assert_called_once()
            mock_logger.error.assert_not_called()


@pytest.mark.asyncio
async def test_docker_restart_file_not_found_logs_warning(docker_manager):
    """Test that FileNotFoundError in DockerServiceManager logs a warning, not error.

    NEM-1241: Changed from ERROR to WARNING since this is an expected condition
    when running in containerized environments without docker CLI.
    """
    config = ServiceConfig(
        name="yolo26",
        health_url="http://localhost:8090/health",
        restart_cmd="docker restart yolo26",
    )

    with patch("asyncio.create_subprocess_exec") as mock_proc:
        mock_proc.side_effect = FileNotFoundError("docker not found")

        with patch("backend.services.service_managers.logger") as mock_logger:
            await docker_manager.restart(config)

            # Should log warning, not error
            mock_logger.warning.assert_called_once()
            mock_logger.error.assert_not_called()
