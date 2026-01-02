# tests/test_setup.py
import socket
import sys
from pathlib import Path

# Add project root to path for setup.py import
sys.path.insert(0, str(Path(__file__).parent.parent))

from setup import check_port_available, find_available_port, generate_password


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
