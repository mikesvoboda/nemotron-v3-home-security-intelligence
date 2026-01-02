# tests/test_setup.py
import socket
import sys
from pathlib import Path

# Add project root to path for setup.py import
sys.path.insert(0, str(Path(__file__).parent.parent))

from setup import (
    check_port_available,
    find_available_port,
    generate_docker_override_content,
    generate_env_content,
    generate_password,
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
