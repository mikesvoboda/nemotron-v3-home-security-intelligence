"""Installer tests returned to the live suite by O1.5 (UR-19, archive deletion).

These lived as ``archive/test_setup.py``; the package moved them under
``backend/tests/unit/setup_lib/``. Two changes rode the move:

* ``test_generate_docker_override_content`` was dropped — it exercised
  ``generate_docker_override_content``, which lives only in
  ``archive/scripts/setup_docker_override.py`` and is gone with the archive.
  The sibling ``test_write_config_files_no_docker_override`` pins the
  surviving contract ("no override file; .env is the source of truth").
* The import of the root ``setup`` module is function-level via
  ``_load_setup()``, matching the live-suite convention
  (``backend/tests/unit/core/test_frontend_expose_lan_bind.py`` and every
  sibling here). A module-level ``from setup import …`` is the repo's only
  module-scope import of setup.py and would pull the installer into the
  ``mypy backend/ synthbench/`` follow-graph, which reddens the type gate on
  25 pre-existing setup.py annotations outside this package's scope.
"""

import socket
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[4]


def _load_setup():
    """Import the root setup.py, adding the repo root to sys.path first.

    Function-level so setup.py stays out of the mypy follow-graph (see the
    module docstring); every test calls this before touching ``setup.*`` or
    patching ``setup.*``.
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import setup

    return setup


def test_check_port_available_open_port():
    """Test detecting an available port."""
    setup = _load_setup()
    # Find a port that's likely free
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]
    # Port is now closed, should be available
    assert setup.check_port_available(port) is True


def test_check_port_available_used_port():
    """Test detecting a port in use."""
    setup = _load_setup()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]
        s.listen(1)
        # Port is bound, should not be available
        assert setup.check_port_available(port) is False


def test_find_available_port():
    """Test finding next available port."""
    setup = _load_setup()
    port = setup.find_available_port(49000)
    assert port >= 49000
    assert setup.check_port_available(port)


def test_generate_password_length():
    """Test password generation length."""
    setup = _load_setup()
    password = setup.generate_password(16)
    assert len(password) == 16


def test_generate_password_unique():
    """Test passwords are unique."""
    setup = _load_setup()
    p1 = setup.generate_password(16)
    p2 = setup.generate_password(16)
    assert p1 != p2


def test_generate_env_content():
    """Test .env file content generation."""
    setup = _load_setup()
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
    content = setup.generate_env_content(config)
    assert "FOSCAM_BASE_PATH=/export/foscam" in content  # pragma: allowlist secret
    assert "POSTGRES_PASSWORD=testpass123" in content
    # Contract re-pinned on the O1.5 move: GRAFANA_URL is path-routed through the
    # frontend (/grafana, no port) and the per-port facts live in the *_PORT
    # vars; the retired ai-<model> service URLs became gateway-routed AI URLs.
    assert "GRAFANA_URL=/grafana" in content
    assert "GRAFANA_PORT=3002" in content
    assert "API_PORT=8000" in content
    assert "YOLO26_URL=http://ai-gateway:8090/yolo26" in content


# Tests for interactive prompts (Task 8)


def test_prompt_with_default_accepts_default():
    """Test prompt accepts default value on empty input."""
    setup = _load_setup()
    with patch("builtins.input", return_value=""):
        result = setup.prompt_with_default("Test", "default_value")
    assert result == "default_value"


def test_prompt_with_default_accepts_custom():
    """Test prompt accepts custom value."""
    setup = _load_setup()
    with patch("builtins.input", return_value="custom_value"):
        result = setup.prompt_with_default("Test", "default_value")
    assert result == "custom_value"


def test_prompt_with_default_strips_whitespace():
    """Test prompt strips whitespace from input."""
    setup = _load_setup()
    with patch("builtins.input", return_value="  trimmed  "):
        result = setup.prompt_with_default("Test", "default")
    assert result == "trimmed"


def test_prompt_with_default_handles_eof():
    """Test prompt handles EOF gracefully."""
    setup = _load_setup()
    with patch("builtins.input", side_effect=EOFError):
        result = setup.prompt_with_default("Test", "fallback")
    assert result == "fallback"


def test_prompt_with_default_handles_keyboard_interrupt():
    """Test prompt handles Ctrl+C gracefully."""
    setup = _load_setup()
    with patch("builtins.input", side_effect=KeyboardInterrupt):
        result = setup.prompt_with_default("Test", "fallback")
    assert result == "fallback"


def test_run_quick_mode_returns_config():
    """Test run_quick_mode returns complete configuration."""
    setup = _load_setup()
    # Mock all user inputs to return empty (accept defaults)
    with (
        patch("builtins.input", return_value=""),
        patch("setup.check_port_available", return_value=True),
    ):
        config = setup.run_quick_mode()

    assert "foscam_base_path" in config
    assert "ai_models_path" in config
    assert "postgres_password" in config
    assert "ftp_password" in config
    assert "ports" in config
    assert isinstance(config["ports"], dict)


def test_run_quick_mode_accepts_custom_paths():
    """Test run_quick_mode accepts custom path values."""
    setup = _load_setup()
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
        config = setup.run_quick_mode()

    assert config["foscam_base_path"] == "/custom/cameras"
    assert config["ai_models_path"] == "/custom/models"


def test_run_quick_mode_handles_port_conflicts():
    """Test run_quick_mode handles port conflicts gracefully."""
    setup = _load_setup()
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
        config = setup.run_quick_mode()

    # Should still return valid config
    assert "ports" in config
    assert isinstance(config["ports"], dict)


# Tests for file writing (Task 9)


def test_write_config_files_creates_env():
    """Test that write_config_files creates .env file."""
    setup = _load_setup()
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "foscam_base_path": "/test/cameras",
            "ai_models_path": "/test/models",
            "postgres_password": "testpass",
            "ftp_password": "ftppass",
            "ports": {"backend": 8000, "postgres": 5432, "redis": 6379, "grafana": 3002},
        }
        setup.write_config_files(config, output_dir=tmpdir)

        env_path = Path(tmpdir) / ".env"
        assert env_path.exists()
        content = env_path.read_text()
        assert "FOSCAM_BASE_PATH=/test/cameras" in content


def test_write_config_files_no_docker_override():
    """Test that write_config_files does NOT create docker-compose.override.yml.

    .env is the source of truth; docker-compose.prod.yml reads from .env.
    """
    setup = _load_setup()
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "foscam_base_path": "/test/cameras",
            "ai_models_path": "/test/models",
            "postgres_password": "testpass",
            "ftp_password": "ftppass",
            "ports": {"backend": 8000, "frontend": 5173},
        }
        setup.write_config_files(config, output_dir=tmpdir)

        override_path = Path(tmpdir) / "docker-compose.override.yml"
        assert not override_path.exists()


def test_write_config_files_returns_paths():
    """Test that write_config_files returns the created file paths."""
    setup = _load_setup()
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "foscam_base_path": "/test/cameras",
            "ai_models_path": "/test/models",
            "postgres_password": "testpass",
            "ftp_password": "ftppass",
            "ports": {"backend": 8000},
        }
        env_path, override_path, secrets_path = setup.write_config_files(config, output_dir=tmpdir)

        assert env_path == Path(tmpdir) / ".env"
        assert override_path is None  # No override file - .env is source of truth
        assert secrets_path is None  # Secrets not created by default


def test_write_config_files_creates_output_dir():
    """Test that write_config_files creates output directory if needed."""
    setup = _load_setup()
    with tempfile.TemporaryDirectory() as tmpdir:
        nested_dir = Path(tmpdir) / "nested" / "path"
        config = {
            "foscam_base_path": "/test/cameras",
            "ai_models_path": "/test/models",
            "postgres_password": "testpass",
            "ftp_password": "ftppass",
            "ports": {},
        }
        setup.write_config_files(config, output_dir=str(nested_dir))

        assert nested_dir.exists()
        assert (nested_dir / ".env").exists()


# Tests for firewall configuration (Task 9)


def test_configure_firewall_non_linux():
    """Test configure_firewall returns False on non-Linux."""
    setup = _load_setup()
    with patch("setup.platform.system", return_value="Darwin"):
        result = setup.configure_firewall([8000, 3002])
    assert result is False


def test_configure_firewall_no_firewall_tool():
    """Test configure_firewall returns False when no firewall tool available."""
    setup = _load_setup()
    with (
        patch("setup.platform.system", return_value="Linux"),
        patch("setup.shutil.which", return_value=None),
    ):
        result = setup.configure_firewall([8000, 3002])
    assert result is False


def test_configure_firewall_firewalld_success():
    """Test configure_firewall with firewalld succeeds."""
    setup = _load_setup()
    with (
        patch("setup.platform.system", return_value="Linux"),
        patch(
            "setup.shutil.which",
            side_effect=lambda cmd: "/usr/bin/firewall-cmd" if cmd == "firewall-cmd" else None,
        ),
        patch("setup.subprocess.run") as mock_run,
    ):
        mock_run.return_value.returncode = 0
        result = setup.configure_firewall([8000, 3002])

    assert result is True
    # Should call firewall-cmd for each port plus reload
    assert mock_run.call_count == 3


def test_configure_firewall_ufw_success():
    """Test configure_firewall with ufw succeeds."""
    setup = _load_setup()
    with (
        patch("setup.platform.system", return_value="Linux"),
        patch(
            "setup.shutil.which", side_effect=lambda cmd: "/usr/sbin/ufw" if cmd == "ufw" else None
        ),
        patch("setup.subprocess.run") as mock_run,
    ):
        mock_run.return_value.returncode = 0
        result = setup.configure_firewall([8000, 3002])

    assert result is True
    # Should call ufw for each port
    assert mock_run.call_count == 2


# Tests for guided mode (Task 11)


def test_run_guided_mode_returns_config():
    """Test guided mode returns complete config dict."""
    setup = _load_setup()
    inputs = [
        "/test/cameras",  # foscam base path
        "n",  # don't create dir
        "/test/models",  # ai models path
        "",  # accept generated postgres password
        "",  # redis password (optional)
        "",  # grafana password (optional)
        "",  # ftp password (accept generated)
        # Ports auto-assign when check_port_available is patched True; the
        # per-port prompts only fire behind "Configure ports manually?".
        "n",  # configure ports manually?
        "n",  # O1.6: expose the UI beyond this machine?
        "y",  # proceed with this configuration
    ]
    with (
        patch("builtins.input", side_effect=inputs),
        patch("setup.check_port_available", return_value=True),
        patch.object(Path, "exists", return_value=False),
    ):
        config = setup.run_guided_mode()

    assert "foscam_base_path" in config
    assert "ai_models_path" in config
    assert "postgres_password" in config
    assert "ftp_password" in config
    assert "ports" in config
    assert config["foscam_base_path"] == "/test/cameras"
    assert config["ai_models_path"] == "/test/models"
