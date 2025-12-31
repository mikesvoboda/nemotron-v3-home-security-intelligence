"""Unit tests for service_managers module."""

import pytest

from backend.services.service_managers import (
    DockerServiceManager,
    ServiceConfig,
    ShellServiceManager,
)

# Fixtures


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
    """Create a ServiceConfig with restart_cmd."""
    return ServiceConfig(
        name="test_service",
        health_url="http://localhost:9999/health",
        restart_cmd="echo test",
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


# Test: ServiceConfig defaults


def test_service_config_restart_cmd_defaults_to_none():
    """Test that restart_cmd defaults to None when not specified."""
    config = ServiceConfig(
        name="test",
        health_url="http://localhost:9999/health",
    )
    assert config.restart_cmd is None


def test_service_config_restart_cmd_can_be_set():
    """Test that restart_cmd can be explicitly set."""
    config = ServiceConfig(
        name="test",
        health_url="http://localhost:9999/health",
        restart_cmd="echo restart",
    )
    assert config.restart_cmd == "echo restart"


def test_service_config_other_defaults():
    """Test that other ServiceConfig fields have correct defaults."""
    config = ServiceConfig(
        name="test",
        health_url="http://localhost:9999/health",
    )
    assert config.health_timeout == 5.0
    assert config.max_retries == 3
    assert config.backoff_base == 5.0


# Test: ShellServiceManager.restart with None restart_cmd


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
    result = await shell_manager.restart(config_with_restart)
    # echo test returns exit code 0
    assert result is True


# Test: DockerServiceManager._extract_container_name with None restart_cmd


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


# Test: DockerServiceManager.restart with None restart_cmd


@pytest.mark.asyncio
async def test_docker_manager_restart_returns_false_when_restart_cmd_none(
    docker_manager, config_no_restart
):
    """Test that DockerServiceManager.restart returns False when restart_cmd is None."""
    result = await docker_manager.restart(config_no_restart)
    assert result is False
