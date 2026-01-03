# tests/test_setup_core.py
"""Tests for the setup_lib.core module.

This module tests the core utility functions extracted from setup.py.
"""

import socket
import sys
from pathlib import Path

# Add project root to path for setup_lib package import
sys.path.insert(0, str(Path(__file__).parent.parent))

from setup_lib.core import (
    WEAK_PASSWORDS,
    check_port_available,
    find_available_port,
    generate_password,
    is_weak_password,
)


class TestCheckPortAvailable:
    """Tests for check_port_available function."""

    def test_open_port_is_available(self):
        """Test that an unbound port is detected as available."""
        # Find a port that's likely free by binding and immediately releasing
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]
        # Port is now closed and should be available
        assert check_port_available(port) is True

    def test_used_port_is_not_available(self):
        """Test that a bound port is detected as in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]
            s.listen(1)
            # Port is still bound, should not be available
            assert check_port_available(port) is False

    def test_invalid_port_behavior(self):
        """Test behavior with edge case port numbers."""
        # Port 0 should be available (it's a special port for OS assignment)
        # This may vary by OS, so we just test it doesn't crash
        result = check_port_available(0)
        assert isinstance(result, bool)


class TestFindAvailablePort:
    """Tests for find_available_port function."""

    def test_finds_port_from_start(self):
        """Test finding an available port starting from a given number."""
        port = find_available_port(49000)
        assert port >= 49000
        assert check_port_available(port)

    def test_skips_used_ports(self):
        """Test that function skips ports that are in use."""
        # Bind a port to simulate it being in use
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            used_port = s.getsockname()[1]
            s.listen(1)
            # Find a port starting from the used one
            available = find_available_port(used_port)
            # Should find a different port
            assert available > used_port

    def test_returns_start_if_available(self):
        """Test that function returns start port if it's available."""
        # Find a free port to use as start
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            free_port = s.getsockname()[1]
        # The port should be returned as-is since it's free
        result = find_available_port(free_port)
        assert result == free_port


class TestGeneratePassword:
    """Tests for generate_password function."""

    def test_default_length(self):
        """Test that default length is 32 characters."""
        password = generate_password()
        assert len(password) == 32

    def test_custom_length(self):
        """Test generating password with custom length."""
        password = generate_password(16)
        assert len(password) == 16

    def test_short_length(self):
        """Test generating short password."""
        password = generate_password(8)
        assert len(password) == 8

    def test_passwords_are_unique(self):
        """Test that generated passwords are unique."""
        p1 = generate_password(16)
        p2 = generate_password(16)
        assert p1 != p2

    def test_password_is_url_safe(self):
        """Test that password contains only URL-safe characters."""
        password = generate_password(64)
        # URL-safe base64 uses A-Za-z0-9-_
        valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        assert all(c in valid_chars for c in password)


class TestIsWeakPassword:
    """Tests for is_weak_password function."""

    def test_short_password_is_weak(self):
        """Test that short passwords are considered weak."""
        assert is_weak_password("short") is True
        assert is_weak_password("fifteenchars!!") is True  # 14 chars

    def test_minimum_length_not_weak(self):
        """Test that 16+ char passwords are not automatically weak."""
        # 16 characters, but not in weak list
        assert is_weak_password("sixteencharacter") is False

    def test_known_weak_passwords(self):
        """Test that known weak passwords are detected."""
        # Weak passwords are detected by exact match (case-insensitive)
        # Since they're short (<16 chars), they're weak by length
        assert is_weak_password("password") is True
        assert is_weak_password("admin") is True
        assert is_weak_password("changeme") is True
        assert is_weak_password("security_dev_password") is True  # This is >= 16 but in weak list

    def test_weak_passwords_case_insensitive(self):
        """Test that weak password detection is case-insensitive."""
        # The function converts to lowercase before checking
        assert is_weak_password("PASSWORD") is True
        assert is_weak_password("ADMIN") is True
        assert is_weak_password("SECURITY_DEV_PASSWORD") is True  # Exact match, case-insensitive

    def test_strong_password_not_weak(self):
        """Test that strong passwords are not flagged."""
        strong = generate_password(32)
        assert is_weak_password(strong) is False


class TestWeakPasswordsConstant:
    """Tests for WEAK_PASSWORDS constant."""

    def test_weak_passwords_is_set(self):
        """Test that WEAK_PASSWORDS is a set."""
        assert isinstance(WEAK_PASSWORDS, set)

    def test_contains_common_weak_passwords(self):
        """Test that common weak passwords are in the set."""
        expected = {"password", "admin", "root", "123456", "changeme", "secret"}
        assert expected.issubset(WEAK_PASSWORDS)

    def test_contains_project_specific_weak_password(self):
        """Test that the project's old default password is flagged."""
        assert "security_dev_password" in WEAK_PASSWORDS


class TestImportFromPackage:
    """Tests for importing from the setup_lib package."""

    def test_import_from_setup_lib_package(self):
        """Test that functions can be imported from setup_lib package."""
        from setup_lib import (
            WEAK_PASSWORDS as pkg_weak,
        )
        from setup_lib import (
            check_port_available as pkg_check,
        )
        from setup_lib import (
            find_available_port as pkg_find,
        )
        from setup_lib import (
            generate_password as pkg_gen,
        )
        from setup_lib import (
            is_weak_password as pkg_weak_check,
        )

        # Verify they're the same functions
        assert pkg_check is check_port_available
        assert pkg_find is find_available_port
        assert pkg_gen is generate_password
        assert pkg_weak_check is is_weak_password
        assert pkg_weak is WEAK_PASSWORDS


class TestBackwardCompatibility:
    """Tests for backward compatibility with setup.py."""

    def test_import_from_setup_py(self):
        """Test that functions can still be imported from setup.py (the module)."""
        import importlib.util

        # Load setup.py directly as a module to avoid package import
        spec = importlib.util.spec_from_file_location(
            "setup_module",
            str(Path(__file__).parent.parent / "setup.py"),
        )
        setup_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup_module)

        # Verify the functions are exported
        assert hasattr(setup_module, "check_port_available")
        assert hasattr(setup_module, "find_available_port")
        assert hasattr(setup_module, "generate_password")
        assert hasattr(setup_module, "is_weak_password")
        assert hasattr(setup_module, "WEAK_PASSWORDS")

        # Verify they work correctly
        assert setup_module.is_weak_password("short") is True
        assert len(setup_module.generate_password(16)) == 16
