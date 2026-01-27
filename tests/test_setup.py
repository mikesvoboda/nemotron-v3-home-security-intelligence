# tests/test_setup.py
import socket
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add project root to path for setup.py import
sys.path.insert(0, str(Path(__file__).parent.parent))

from setup import (
    check_port_available,
    configure_firewall,
    find_available_port,
    generate_docker_override_content,
    generate_env_content,
    generate_password,
    prompt_with_default,
    run_guided_mode,
    run_quick_mode,
    write_config_files,
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
        "foscam_base_path": "/export/foscam",
        "ai_models_path": "/export/ai_models",
        "postgres_password": "testpass123",
        "ftp_password": "ftppass456",
        "ports": {
            "backend": 8000,
            "postgres": 5432,
            "redis": 6379,
            "grafana": 3002,
            "yolo26": 8095,
            "nemotron": 8091,
            "florence": 8092,
            "clip": 8093,
            "enrichment": 8094,
        },
    }
    content = generate_env_content(config)
    assert "FOSCAM_BASE_PATH=/export/foscam" in content  # pragma: allowlist secret
    assert "POSTGRES_PASSWORD=testpass123" in content
    assert "GRAFANA_URL=http://localhost:3002" in content
    assert "YOLO26_URL=http://ai-yolo26:8095" in content


def test_generate_docker_override_content():
    """Test docker-compose.override.yml generation."""
    config = {
        "foscam_base_path": "/export/foscam",
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

    assert "foscam_base_path" in config
    assert "ai_models_path" in config
    assert "postgres_password" in config
    assert "ftp_password" in config
    assert "ports" in config
    assert isinstance(config["ports"], dict)


def test_run_quick_mode_accepts_custom_paths():
    """Test run_quick_mode accepts custom path values."""
    # Return custom values for paths, then defaults for everything else
    # Input flow:
    # 1. Foscam path: "/custom/cameras"
    # 2. "Create it now?" (dir doesn't exist): "n"
    # 3. AI models path: "/custom/models"
    # 4. Database password: "" (uses existing .env default if present, or generated)
    # 5. If weak password warning: "Use this weak password anyway?": "y"
    # 6. Redis password: ""
    # 7. Grafana password: ""
    # 8. FTP password: ""
    # 9-23. Port prompts (15 services): "" * 15
    inputs = iter(["/custom/cameras", "n", "/custom/models", "", "y", "", "", ""] + [""] * 20)

    with (
        patch("builtins.input", side_effect=lambda _: next(inputs)),
        patch("setup.check_port_available", return_value=True),
    ):
        config = run_quick_mode()

    assert config["foscam_base_path"] == "/custom/cameras"
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


# Tests for file writing (Task 9)


def test_write_config_files_creates_env():
    """Test that write_config_files creates .env file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "foscam_base_path": "/test/cameras",
            "ai_models_path": "/test/models",
            "postgres_password": "testpass",
            "ftp_password": "ftppass",
            "ports": {"backend": 8000, "postgres": 5432, "redis": 6379, "grafana": 3002},
        }
        write_config_files(config, output_dir=tmpdir)

        env_path = Path(tmpdir) / ".env"
        assert env_path.exists()
        content = env_path.read_text()
        assert "FOSCAM_BASE_PATH=/test/cameras" in content


def test_write_config_files_creates_docker_override():
    """Test that write_config_files creates docker-compose.override.yml."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "foscam_base_path": "/test/cameras",
            "ai_models_path": "/test/models",
            "postgres_password": "testpass",
            "ftp_password": "ftppass",
            "ports": {"backend": 8000, "frontend": 5173},
        }
        write_config_files(config, output_dir=tmpdir)

        override_path = Path(tmpdir) / "docker-compose.override.yml"
        assert override_path.exists()
        content = override_path.read_text()
        assert "services:" in content


def test_write_config_files_returns_paths():
    """Test that write_config_files returns the created file paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "foscam_base_path": "/test/cameras",
            "ai_models_path": "/test/models",
            "postgres_password": "testpass",
            "ftp_password": "ftppass",
            "ports": {"backend": 8000},
        }
        env_path, override_path, secrets_path = write_config_files(config, output_dir=tmpdir)

        assert env_path == Path(tmpdir) / ".env"
        assert override_path == Path(tmpdir) / "docker-compose.override.yml"
        assert secrets_path is None  # Secrets not created by default


def test_write_config_files_creates_output_dir():
    """Test that write_config_files creates output directory if needed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        nested_dir = Path(tmpdir) / "nested" / "path"
        config = {
            "foscam_base_path": "/test/cameras",
            "ai_models_path": "/test/models",
            "postgres_password": "testpass",
            "ftp_password": "ftppass",
            "ports": {},
        }
        write_config_files(config, output_dir=str(nested_dir))

        assert nested_dir.exists()
        assert (nested_dir / ".env").exists()
        assert (nested_dir / "docker-compose.override.yml").exists()


# Tests for firewall configuration (Task 9)


def test_configure_firewall_non_linux():
    """Test configure_firewall returns False on non-Linux."""
    with patch("setup.platform.system", return_value="Darwin"):
        result = configure_firewall([8000, 3002])
    assert result is False


def test_configure_firewall_no_firewall_tool():
    """Test configure_firewall returns False when no firewall tool available."""
    with (
        patch("setup.platform.system", return_value="Linux"),
        patch("setup.shutil.which", return_value=None),
    ):
        result = configure_firewall([8000, 3002])
    assert result is False


def test_configure_firewall_firewalld_success():
    """Test configure_firewall with firewalld succeeds."""
    with (
        patch("setup.platform.system", return_value="Linux"),
        patch(
            "setup.shutil.which",
            side_effect=lambda cmd: "/usr/bin/firewall-cmd" if cmd == "firewall-cmd" else None,
        ),
        patch("setup.subprocess.run") as mock_run,
    ):
        mock_run.return_value.returncode = 0
        result = configure_firewall([8000, 3002])

    assert result is True
    # Should call firewall-cmd for each port plus reload
    assert mock_run.call_count == 3


def test_configure_firewall_ufw_success():
    """Test configure_firewall with ufw succeeds."""
    with (
        patch("setup.platform.system", return_value="Linux"),
        patch(
            "setup.shutil.which", side_effect=lambda cmd: "/usr/sbin/ufw" if cmd == "ufw" else None
        ),
        patch("setup.subprocess.run") as mock_run,
    ):
        mock_run.return_value.returncode = 0
        result = configure_firewall([8000, 3002])

    assert result is True
    # Should call ufw for each port
    assert mock_run.call_count == 2


# Tests for guided mode (Task 11)


def test_run_guided_mode_returns_config():
    """Test guided mode returns complete config dict."""
    inputs = [
        "/test/cameras",  # foscam base path
        "n",  # don't create dir
        "/test/models",  # ai models path
        "",  # accept generated postgres password
        "",  # redis password (optional)
        "",  # grafana password (optional)
        "",  # ftp password (accept generated)
        # 14 ports (all default - no input needed since ports are available)
        "y",  # confirm
    ]
    with (
        patch("builtins.input", side_effect=inputs),
        patch("setup.check_port_available", return_value=True),
        patch.object(Path, "exists", return_value=False),
    ):
        config = run_guided_mode()

    assert "foscam_base_path" in config
    assert "ai_models_path" in config
    assert "postgres_password" in config
    assert "ftp_password" in config
    assert "ports" in config
    assert config["foscam_base_path"] == "/test/cameras"
    assert config["ai_models_path"] == "/test/models"
