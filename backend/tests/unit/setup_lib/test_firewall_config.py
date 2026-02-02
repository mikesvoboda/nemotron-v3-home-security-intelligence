"""Unit tests for setup_lib.firewall_config module.

Tests firewall detection, port checking, and configuration for firewalld, ufw, and Windows.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch


class TestDetectFirewallType:
    """Tests for detect_firewall_type() function."""

    def test_detect_firewalld(self) -> None:
        """Should detect firewalld when firewall-cmd is available and running."""
        from setup_lib.firewall_config import detect_firewall_type

        with (
            patch("shutil.which") as mock_which,
            patch("subprocess.run") as mock_run,
        ):
            mock_which.side_effect = (
                lambda cmd: "/usr/bin/firewall-cmd" if cmd == "firewall-cmd" else None
            )
            mock_run.return_value = MagicMock(returncode=0, stdout="running\n")

            result = detect_firewall_type()
            assert result == "firewalld"

    def test_detect_firewalld_not_running(self) -> None:
        """Should return None when firewalld is installed but not running."""
        from setup_lib.firewall_config import detect_firewall_type

        with (
            patch("shutil.which") as mock_which,
            patch("subprocess.run") as mock_run,
        ):
            mock_which.side_effect = (
                lambda cmd: "/usr/bin/firewall-cmd" if cmd == "firewall-cmd" else None
            )
            mock_run.return_value = MagicMock(returncode=252, stdout="not running\n")

            result = detect_firewall_type()
            assert result is None

    def test_detect_ufw(self) -> None:
        """Should detect ufw when firewall-cmd not available but ufw is active."""
        from setup_lib.firewall_config import detect_firewall_type

        with (
            patch("shutil.which") as mock_which,
            patch("subprocess.run") as mock_run,
        ):
            mock_which.side_effect = lambda cmd: "/usr/bin/ufw" if cmd == "ufw" else None
            mock_run.return_value = MagicMock(returncode=0, stdout="Status: active\n")

            result = detect_firewall_type()
            assert result == "ufw"

    def test_detect_ufw_inactive(self) -> None:
        """Should return None when ufw is installed but inactive."""
        from setup_lib.firewall_config import detect_firewall_type

        with (
            patch("shutil.which") as mock_which,
            patch("subprocess.run") as mock_run,
        ):
            mock_which.side_effect = lambda cmd: "/usr/bin/ufw" if cmd == "ufw" else None
            mock_run.return_value = MagicMock(returncode=0, stdout="Status: inactive\n")

            result = detect_firewall_type()
            assert result is None

    def test_detect_windows_firewall(self) -> None:
        """Should detect Windows firewall when netsh is available."""
        from setup_lib.firewall_config import detect_firewall_type

        with (
            patch("shutil.which") as mock_which,
            patch("subprocess.run") as mock_run,
            patch("platform.system", return_value="Windows"),
        ):
            mock_which.side_effect = (
                lambda cmd: "C:\\Windows\\netsh.exe" if cmd == "netsh" else None
            )
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Domain Profile Settings:\nState                                 ON\n",
            )

            result = detect_firewall_type()
            assert result == "windows"

    def test_detect_windows_firewall_off(self) -> None:
        """Should return None when Windows firewall is disabled."""
        from setup_lib.firewall_config import detect_firewall_type

        with (
            patch("shutil.which") as mock_which,
            patch("subprocess.run") as mock_run,
            patch("platform.system", return_value="Windows"),
        ):
            mock_which.side_effect = (
                lambda cmd: "C:\\Windows\\netsh.exe" if cmd == "netsh" else None
            )
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Domain Profile Settings:\nState                                 OFF\n"
                "Private Profile Settings:\nState                                 OFF\n"
                "Public Profile Settings:\nState                                 OFF\n",
            )

            result = detect_firewall_type()
            assert result is None

    def test_detect_no_firewall(self) -> None:
        """Should return None when no firewall is detected."""
        from setup_lib.firewall_config import detect_firewall_type

        with (
            patch("shutil.which", return_value=None),
            patch("platform.system", return_value="Linux"),
        ):
            result = detect_firewall_type()
            assert result is None


class TestIsFirewallActive:
    """Tests for is_firewall_active() function."""

    def test_firewalld_active(self) -> None:
        """Should return True when firewalld is running."""
        from setup_lib.firewall_config import is_firewall_active

        with (
            patch("shutil.which") as mock_which,
            patch("subprocess.run") as mock_run,
        ):
            mock_which.side_effect = (
                lambda cmd: "/usr/bin/firewall-cmd" if cmd == "firewall-cmd" else None
            )
            mock_run.return_value = MagicMock(returncode=0, stdout="running\n")

            result = is_firewall_active()
            assert result is True

    def test_ufw_active(self) -> None:
        """Should return True when ufw is active."""
        from setup_lib.firewall_config import is_firewall_active

        with (
            patch("shutil.which") as mock_which,
            patch("subprocess.run") as mock_run,
        ):
            mock_which.side_effect = lambda cmd: "/usr/bin/ufw" if cmd == "ufw" else None
            mock_run.return_value = MagicMock(returncode=0, stdout="Status: active\n")

            result = is_firewall_active()
            assert result is True

    def test_no_firewall_active(self) -> None:
        """Should return False when no firewall is active."""
        from setup_lib.firewall_config import is_firewall_active

        with (
            patch("shutil.which", return_value=None),
            patch("platform.system", return_value="Linux"),
        ):
            result = is_firewall_active()
            assert result is False


class TestIsPortOpen:
    """Tests for is_port_open() function."""

    def test_port_open_firewalld(self) -> None:
        """Should detect open port with firewalld."""
        from setup_lib.firewall_config import is_port_open

        with (
            patch("shutil.which") as mock_which,
            patch("subprocess.run") as mock_run,
        ):
            mock_which.side_effect = (
                lambda cmd: "/usr/bin/firewall-cmd" if cmd == "firewall-cmd" else None
            )
            # First call for detect_firewall_type, second for port check
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="running\n"),  # firewall-cmd --state
                MagicMock(returncode=0, stdout="yes\n"),  # firewall-cmd --query-port
            ]

            result = is_port_open(8443)
            assert result is True

    def test_port_closed_firewalld(self) -> None:
        """Should detect closed port with firewalld."""
        from setup_lib.firewall_config import is_port_open

        with (
            patch("shutil.which") as mock_which,
            patch("subprocess.run") as mock_run,
        ):
            mock_which.side_effect = (
                lambda cmd: "/usr/bin/firewall-cmd" if cmd == "firewall-cmd" else None
            )
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="running\n"),  # firewall-cmd --state
                MagicMock(returncode=1, stdout="no\n"),  # firewall-cmd --query-port
            ]

            result = is_port_open(8443)
            assert result is False

    def test_port_open_ufw(self) -> None:
        """Should detect open port with ufw."""
        from setup_lib.firewall_config import is_port_open

        ufw_status = """Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
8443/tcp                   ALLOW       Anywhere
"""
        with (
            patch("shutil.which") as mock_which,
            patch("subprocess.run") as mock_run,
        ):
            mock_which.side_effect = lambda cmd: "/usr/bin/ufw" if cmd == "ufw" else None
            mock_run.return_value = MagicMock(returncode=0, stdout=ufw_status)

            result = is_port_open(8443)
            assert result is True

    def test_port_closed_ufw(self) -> None:
        """Should detect closed port with ufw."""
        from setup_lib.firewall_config import is_port_open

        ufw_status = """Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
"""
        with (
            patch("shutil.which") as mock_which,
            patch("subprocess.run") as mock_run,
        ):
            mock_which.side_effect = lambda cmd: "/usr/bin/ufw" if cmd == "ufw" else None
            mock_run.return_value = MagicMock(returncode=0, stdout=ufw_status)

            result = is_port_open(8443)
            assert result is False

    def test_port_open_windows(self) -> None:
        """Should detect open port with Windows firewall."""
        from setup_lib.firewall_config import is_port_open

        netsh_output = """Rule Name:                            Home Security Dashboard
Enabled:                              Yes
Direction:                            In
Profiles:                             Domain,Private,Public
LocalPort:                            8443
Protocol:                             TCP
"""
        with (
            patch("shutil.which") as mock_which,
            patch("subprocess.run") as mock_run,
            patch("platform.system", return_value="Windows"),
        ):
            mock_which.side_effect = (
                lambda cmd: "C:\\Windows\\netsh.exe" if cmd == "netsh" else None
            )
            mock_run.side_effect = [
                MagicMock(
                    returncode=0, stdout="State                                 ON\n"
                ),  # state check
                MagicMock(returncode=0, stdout=netsh_output),  # rule query
            ]

            result = is_port_open(8443)
            assert result is True

    def test_port_closed_windows(self) -> None:
        """Should detect closed port with Windows firewall."""
        from setup_lib.firewall_config import is_port_open

        with (
            patch("shutil.which") as mock_which,
            patch("subprocess.run") as mock_run,
            patch("platform.system", return_value="Windows"),
        ):
            mock_which.side_effect = (
                lambda cmd: "C:\\Windows\\netsh.exe" if cmd == "netsh" else None
            )
            mock_run.side_effect = [
                MagicMock(
                    returncode=0, stdout="State                                 ON\n"
                ),  # state check
                MagicMock(
                    returncode=1, stdout="No rules match the specified criteria.\n"
                ),  # no rule found
            ]

            result = is_port_open(8443)
            assert result is False

    def test_port_no_firewall(self) -> None:
        """Should return True when no firewall is active (port not blocked)."""
        from setup_lib.firewall_config import is_port_open

        with (
            patch("shutil.which", return_value=None),
            patch("platform.system", return_value="Linux"),
        ):
            result = is_port_open(8443)
            assert result is True


class TestGetOpenPortCommands:
    """Tests for get_open_port_commands() function."""

    def test_firewalld_commands(self) -> None:
        """Should generate correct firewalld commands."""
        from setup_lib.firewall_config import get_open_port_commands

        ports = [8443, 8555]
        commands = get_open_port_commands(ports, "firewalld")

        assert len(commands) == 3  # 2 port commands + 1 reload
        assert "firewall-cmd --permanent --add-port=8443/tcp" in commands[0]
        assert "firewall-cmd --permanent --add-port=8555/tcp" in commands[1]
        assert "firewall-cmd --reload" in commands[2]

    def test_ufw_commands(self) -> None:
        """Should generate correct ufw commands."""
        from setup_lib.firewall_config import get_open_port_commands

        ports = [8443, 8555]
        commands = get_open_port_commands(ports, "ufw")

        assert len(commands) == 2
        assert "ufw allow 8443/tcp" in commands[0]
        assert "ufw allow 8555/tcp" in commands[1]

    def test_windows_commands(self) -> None:
        """Should generate correct Windows firewall commands."""
        from setup_lib.firewall_config import get_open_port_commands

        ports = [8443, 8555]
        commands = get_open_port_commands(ports, "windows")

        assert len(commands) == 2
        assert "netsh advfirewall firewall add rule" in commands[0]
        assert 'name="Home Security 8443"' in commands[0]
        assert "localport=8443" in commands[0]
        assert "netsh advfirewall firewall add rule" in commands[1]
        assert 'name="Home Security 8555"' in commands[1]
        assert "localport=8555" in commands[1]

    def test_no_firewall_returns_empty(self) -> None:
        """Should return empty list when no firewall type."""
        from setup_lib.firewall_config import get_open_port_commands

        commands = get_open_port_commands([8443], None)
        assert commands == []

    def test_empty_ports_returns_empty(self) -> None:
        """Should return empty list when no ports specified."""
        from setup_lib.firewall_config import get_open_port_commands

        commands = get_open_port_commands([], "firewalld")
        assert commands == []


class TestOpenFirewallPorts:
    """Tests for open_firewall_ports() function."""

    def test_open_ports_firewalld_success(self) -> None:
        """Should execute firewalld commands successfully."""
        from setup_lib.firewall_config import open_firewall_ports

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="success\n", stderr="")

            result = open_firewall_ports([8443, 8555], "firewalld")

            assert result is True
            # Should have called 3 commands (2 ports + reload)
            assert mock_run.call_count == 3

    def test_open_ports_ufw_success(self) -> None:
        """Should execute ufw commands successfully."""
        from setup_lib.firewall_config import open_firewall_ports

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Rule added\n", stderr="")

            result = open_firewall_ports([8443], "ufw")

            assert result is True
            assert mock_run.call_count == 1

    def test_open_ports_windows_success(self) -> None:
        """Should execute Windows firewall commands successfully."""
        from setup_lib.firewall_config import open_firewall_ports

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Ok.\n", stderr="")

            result = open_firewall_ports([8443], "windows")

            assert result is True
            assert mock_run.call_count == 1

    def test_open_ports_failure(self) -> None:
        """Should return False on command failure."""
        from setup_lib.firewall_config import open_firewall_ports

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="Error: Permission denied\n"
            )

            result = open_firewall_ports([8443], "firewalld")

            assert result is False

    def test_open_ports_no_firewall(self) -> None:
        """Should return True when no firewall type (nothing to configure)."""
        from setup_lib.firewall_config import open_firewall_ports

        result = open_firewall_ports([8443], None)
        assert result is True

    def test_open_ports_subprocess_exception(self) -> None:
        """Should handle subprocess exceptions gracefully."""
        from setup_lib.firewall_config import open_firewall_ports

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.SubprocessError("Command failed")

            result = open_firewall_ports([8443], "firewalld")

            assert result is False


class TestDefaultPorts:
    """Tests for DEFAULT_PORTS constant."""

    def test_default_ports_defined(self) -> None:
        """Should have default ports defined."""
        from setup_lib.firewall_config import DEFAULT_PORTS

        assert 8443 in DEFAULT_PORTS  # HTTPS dashboard
        assert 8555 in DEFAULT_PORTS  # WebRTC streaming
        assert 5432 in DEFAULT_PORTS  # PostgreSQL
        assert 6379 in DEFAULT_PORTS  # Redis


class TestGetPortsToOpen:
    """Tests for get_ports_to_open() function."""

    def test_filters_already_open_ports(self) -> None:
        """Should only return ports that are not already open."""
        from setup_lib.firewall_config import get_ports_to_open

        with (
            patch("setup_lib.firewall_config.is_port_open") as mock_is_open,
            patch("setup_lib.firewall_config.detect_firewall_type", return_value="firewalld"),
        ):
            # 8443 is open, 8555 is closed
            mock_is_open.side_effect = lambda p: p == 8443

            result = get_ports_to_open([8443, 8555])

            assert 8443 not in result
            assert 8555 in result

    def test_returns_all_when_firewall_inactive(self) -> None:
        """Should return empty list when no firewall is active."""
        from setup_lib.firewall_config import get_ports_to_open

        with patch("setup_lib.firewall_config.detect_firewall_type", return_value=None):
            result = get_ports_to_open([8443, 8555])
            assert result == []


class TestPromptAndConfigureFirewall:
    """Tests for prompt_and_configure_firewall() function."""

    def test_prompt_when_firewall_active(self) -> None:
        """Should prompt user when firewall is active and ports need opening."""
        from setup_lib.firewall_config import prompt_and_configure_firewall

        with (
            patch("setup_lib.firewall_config.detect_firewall_type", return_value="firewalld"),
            patch("setup_lib.firewall_config.get_ports_to_open", return_value=[8443, 8555]),
            patch(
                "setup_lib.firewall_config.get_open_port_commands", return_value=["cmd1", "cmd2"]
            ),
            patch("setup_lib.firewall_config.open_firewall_ports", return_value=True) as mock_open,
            patch("builtins.input", return_value="y"),
            patch("builtins.print"),
        ):
            prompt_and_configure_firewall({})

            mock_open.assert_called_once_with([8443, 8555], "firewalld")

    def test_skip_when_user_declines(self) -> None:
        """Should not open ports when user declines."""
        from setup_lib.firewall_config import prompt_and_configure_firewall

        with (
            patch("setup_lib.firewall_config.detect_firewall_type", return_value="firewalld"),
            patch("setup_lib.firewall_config.get_ports_to_open", return_value=[8443]),
            patch("setup_lib.firewall_config.get_open_port_commands", return_value=["cmd"]),
            patch("setup_lib.firewall_config.open_firewall_ports") as mock_open,
            patch("builtins.input", return_value="n"),
            patch("builtins.print"),
        ):
            prompt_and_configure_firewall({})

            mock_open.assert_not_called()

    def test_skip_when_no_firewall(self) -> None:
        """Should skip configuration when no firewall is detected."""
        from setup_lib.firewall_config import prompt_and_configure_firewall

        with (
            patch("setup_lib.firewall_config.detect_firewall_type", return_value=None),
            patch("setup_lib.firewall_config.open_firewall_ports") as mock_open,
            patch("builtins.print"),
        ):
            prompt_and_configure_firewall({})

            mock_open.assert_not_called()

    def test_skip_when_all_ports_open(self) -> None:
        """Should skip when all ports are already open."""
        from setup_lib.firewall_config import prompt_and_configure_firewall

        with (
            patch("setup_lib.firewall_config.detect_firewall_type", return_value="firewalld"),
            patch("setup_lib.firewall_config.get_ports_to_open", return_value=[]),
            patch("setup_lib.firewall_config.open_firewall_ports") as mock_open,
            patch("builtins.print"),
        ):
            prompt_and_configure_firewall({})

            mock_open.assert_not_called()

    def test_custom_ports_from_config(self) -> None:
        """Should use custom ports from config when provided."""
        from setup_lib.firewall_config import prompt_and_configure_firewall

        custom_ports = [9000, 9001]
        config = {"firewall_ports": custom_ports}

        with (
            patch("setup_lib.firewall_config.detect_firewall_type", return_value="ufw"),
            patch(
                "setup_lib.firewall_config.get_ports_to_open", return_value=custom_ports
            ) as mock_get,
            patch("setup_lib.firewall_config.get_open_port_commands", return_value=["cmd"]),
            patch("setup_lib.firewall_config.open_firewall_ports", return_value=True),
            patch("builtins.input", return_value="y"),
            patch("builtins.print"),
        ):
            prompt_and_configure_firewall(config)

            mock_get.assert_called_once_with(custom_ports)


class TestFirewallTypeEnum:
    """Tests for FirewallType literal type."""

    def test_valid_firewall_types(self) -> None:
        """Should accept valid firewall type strings."""
        from typing import get_args

        from setup_lib.firewall_config import FirewallType

        # Verify the FirewallType includes expected values
        valid_types = get_args(FirewallType)
        assert "firewalld" in valid_types
        assert "ufw" in valid_types
        assert "windows" in valid_types
        assert len(valid_types) == 3
