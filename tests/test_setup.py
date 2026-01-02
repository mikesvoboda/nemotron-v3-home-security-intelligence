# tests/test_setup.py
import socket
import sys
from pathlib import Path
from unittest.mock import patch

# Add project root to path for setup.py import
sys.path.insert(0, str(Path(__file__).parent.parent))

from setup import (
    check_port_available,
    find_available_port,
    generate_docker_override_content,
    generate_env_content,
    generate_password,
    prompt_with_default,
    run_quick_mode,
)


def test_check_port_available_open_port():
    """Test detecting an available port."""
    # Find a port that's likely free
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]
    # Port is now closed, should be available
    assert check_port_available(port) is True


def test_check_port_available_used_port():
    """Test detecting a port in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]
        s.listen(1)
        # Port is bound, should not be available
        assert check_port_available(port) is False


def test_find_available_port():
    """Test finding next available port."""
    port = find_available_port(49000)
    assert port >= 49000
    assert check_port_available(port)


def test_generate_password_length():
    """Test password generation length."""
    password = generate_password(16)
    assert len(password) == 16


def test_generate_password_unique():
    """Test passwords are unique."""
    p1 = generate_password(16)
    p2 = generate_password(16)
    assert p1 != p2


def test_generate_env_content():
    """Test .env file content generation."""
    config = {
        "camera_path": "/export/foscam",
        "ai_models_path": "/export/ai_models",
        "postgres_password": "testpass123",
        "ftp_password": "ftppass456",
        "ports": {
            "backend": 8000,
            "postgres": 5432,
            "redis": 6379,
            "grafana": 3002,
            "rtdetr": 8090,
            "nemotron": 8091,
            "florence": 8092,
            "clip": 8093,
            "enrichment": 8094,
        },
    }
    content = generate_env_content(config)
    assert "CAMERA_PATH=/export/foscam" in content
    assert "POSTGRES_PASSWORD=testpass123" in content
    assert "GRAFANA_URL=http://localhost:3002" in content
    assert "RTDETR_URL=http://ai-detector:8090" in content


def test_generate_docker_override_content():
    """Test docker-compose.override.yml generation."""
    config = {
        "camera_path": "/export/foscam",
        "ai_models_path": "/export/ai_models",
        "ports": {
            "backend": 8000,
            "frontend": 5173,
            "postgres": 5432,
        },
    }
    content = generate_docker_override_content(config)
    assert "services:" in content
    assert '"8000:8000"' in content or "'8000:8000'" in content
    assert "backend:" in content


# Tests for interactive prompts (Task 8)


def test_prompt_with_default_accepts_default():
    """Test prompt accepts default value on empty input."""
    with patch("builtins.input", return_value=""):
        result = prompt_with_default("Test", "default_value")
    assert result == "default_value"


def test_prompt_with_default_accepts_custom():
    """Test prompt accepts custom value."""
    with patch("builtins.input", return_value="custom_value"):
        result = prompt_with_default("Test", "default_value")
    assert result == "custom_value"


def test_prompt_with_default_strips_whitespace():
    """Test prompt strips whitespace from input."""
    with patch("builtins.input", return_value="  trimmed  "):
        result = prompt_with_default("Test", "default")
    assert result == "trimmed"


def test_prompt_with_default_handles_eof():
    """Test prompt handles EOF gracefully."""
    with patch("builtins.input", side_effect=EOFError):
        result = prompt_with_default("Test", "fallback")
    assert result == "fallback"


def test_prompt_with_default_handles_keyboard_interrupt():
    """Test prompt handles Ctrl+C gracefully."""
    with patch("builtins.input", side_effect=KeyboardInterrupt):
        result = prompt_with_default("Test", "fallback")
    assert result == "fallback"


def test_run_quick_mode_returns_config():
    """Test run_quick_mode returns complete configuration."""
    # Mock all user inputs to return empty (accept defaults)
    with (
        patch("builtins.input", return_value=""),
        patch("setup.check_port_available", return_value=True),
    ):
        config = run_quick_mode()

    assert "camera_path" in config
    assert "ai_models_path" in config
    assert "postgres_password" in config
    assert "ftp_password" in config
    assert "ports" in config
    assert isinstance(config["ports"], dict)


def test_run_quick_mode_accepts_custom_paths():
    """Test run_quick_mode accepts custom path values."""
    # Return custom values for paths, then defaults for everything else
    inputs = iter(["/custom/cameras", "/custom/models"] + [""] * 20)

    with (
        patch("builtins.input", side_effect=lambda _: next(inputs)),
        patch("setup.check_port_available", return_value=True),
    ):
        config = run_quick_mode()

    assert config["camera_path"] == "/custom/cameras"
    assert config["ai_models_path"] == "/custom/models"


def test_run_quick_mode_handles_port_conflicts():
    """Test run_quick_mode handles port conflicts gracefully."""
    # First port check returns False (conflict), rest return True
    port_check_results = iter([False] + [True] * 100)

    with (
        patch("builtins.input", return_value=""),
        patch(
            "setup.check_port_available",
            side_effect=lambda _: next(port_check_results),
        ),
        patch("setup.find_available_port", return_value=8001),
    ):
        config = run_quick_mode()

    # Should still return valid config
    assert "ports" in config
    assert isinstance(config["ports"], dict)
