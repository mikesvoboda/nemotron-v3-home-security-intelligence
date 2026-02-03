"""Unit tests for setup_lib.port_scanner module.

Tests network port scanning, process detection, conflict identification,
and alternative port suggestions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestRequiredPorts:
    """Tests for REQUIRED_PORTS constant."""

    def test_required_ports_defined(self) -> None:
        """Should have required ports defined."""
        from setup_lib.port_scanner import REQUIRED_PORTS

        assert 8080 in REQUIRED_PORTS
        assert 8000 in REQUIRED_PORTS
        assert 5432 in REQUIRED_PORTS
        assert 6379 in REQUIRED_PORTS
        assert 1883 in REQUIRED_PORTS
        assert 8883 in REQUIRED_PORTS
        assert 5000 in REQUIRED_PORTS
        assert 5001 in REQUIRED_PORTS

    def test_required_ports_have_descriptions(self) -> None:
        """Should have descriptions for all ports."""
        from setup_lib.port_scanner import REQUIRED_PORTS

        assert REQUIRED_PORTS[8080] == "Frontend"
        assert REQUIRED_PORTS[8000] == "Backend API"
        assert REQUIRED_PORTS[5432] == "PostgreSQL"
        assert REQUIRED_PORTS[6379] == "Redis"
        assert REQUIRED_PORTS[1883] == "MQTT"
        assert REQUIRED_PORTS[8883] == "MQTT TLS"
        assert REQUIRED_PORTS[5000] == "YOLO service"
        assert REQUIRED_PORTS[5001] == "Nemotron service"

    def test_required_ports_count(self) -> None:
        """Should have expected number of required ports."""
        from setup_lib.port_scanner import REQUIRED_PORTS

        assert len(REQUIRED_PORTS) == 8


class TestProcessInfo:
    """Tests for ProcessInfo dataclass."""

    def test_default_values(self) -> None:
        """Should have None as default for all fields."""
        from setup_lib.port_scanner import ProcessInfo

        info = ProcessInfo()
        assert info.pid is None
        assert info.name is None
        assert info.user is None

    def test_with_values(self) -> None:
        """Should store provided values."""
        from setup_lib.port_scanner import ProcessInfo

        info = ProcessInfo(pid=1234, name="nginx", user="www-data")
        assert info.pid == 1234
        assert info.name == "nginx"
        assert info.user == "www-data"


class TestPortConflict:
    """Tests for PortConflict dataclass."""

    def test_default_values(self) -> None:
        """Should have default empty process and alternatives."""
        from setup_lib.port_scanner import PortConflict, ProcessInfo

        conflict = PortConflict(port=8080, service="Frontend")
        assert conflict.port == 8080
        assert conflict.service == "Frontend"
        assert isinstance(conflict.process, ProcessInfo)
        assert conflict.alternatives == []

    def test_with_process_info(self) -> None:
        """Should store process information."""
        from setup_lib.port_scanner import PortConflict, ProcessInfo

        proc = ProcessInfo(pid=1234, name="nginx")
        conflict = PortConflict(port=8080, service="Frontend", process=proc)
        assert conflict.process.pid == 1234
        assert conflict.process.name == "nginx"

    def test_with_alternatives(self) -> None:
        """Should store alternative ports."""
        from setup_lib.port_scanner import PortConflict

        conflict = PortConflict(port=8080, service="Frontend", alternatives=[8081, 8082, 8083])
        assert conflict.alternatives == [8081, 8082, 8083]


class TestPortScanResult:
    """Tests for PortScanResult dataclass."""

    def test_default_values(self) -> None:
        """Should have empty defaults."""
        from setup_lib.port_scanner import PortScanResult

        result = PortScanResult()
        assert result.scanned_ports == {}
        assert result.conflicts == []

    def test_has_conflicts_false(self) -> None:
        """Should return False when no conflicts."""
        from setup_lib.port_scanner import PortScanResult

        result = PortScanResult()
        assert result.has_conflicts is False

    def test_has_conflicts_true(self) -> None:
        """Should return True when conflicts exist."""
        from setup_lib.port_scanner import PortConflict, PortScanResult

        conflict = PortConflict(port=8080, service="Frontend")
        result = PortScanResult(conflicts=[conflict])
        assert result.has_conflicts is True

    def test_conflicting_ports_empty(self) -> None:
        """Should return empty list when no conflicts."""
        from setup_lib.port_scanner import PortScanResult

        result = PortScanResult()
        assert result.conflicting_ports == []

    def test_conflicting_ports_list(self) -> None:
        """Should return list of conflicting port numbers."""
        from setup_lib.port_scanner import PortConflict, PortScanResult

        conflicts = [
            PortConflict(port=8080, service="Frontend"),
            PortConflict(port=8000, service="Backend"),
        ]
        result = PortScanResult(conflicts=conflicts)
        assert result.conflicting_ports == [8080, 8000]


class TestCheckPortAvailable:
    """Tests for check_port_available() function."""

    def test_port_available_ipv4(self) -> None:
        """Should return True when port is available on IPv4."""
        from setup_lib.port_scanner import check_port_available

        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 111  # Connection refused (port free)
            mock_socket.return_value.__enter__.return_value = mock_sock

            result = check_port_available(8080)
            assert result is True

    def test_port_in_use_ipv4(self) -> None:
        """Should return False when port is in use on IPv4."""
        from setup_lib.port_scanner import check_port_available

        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0  # Connection successful (port in use)
            mock_socket.return_value.__enter__.return_value = mock_sock

            result = check_port_available(8080)
            assert result is False

    def test_port_in_use_ipv6(self) -> None:
        """Should return False when port is in use on IPv6 only."""
        from setup_lib.port_scanner import check_port_available

        with patch("socket.socket") as mock_socket:
            mock_sock_v4 = MagicMock()
            mock_sock_v4.connect_ex.return_value = 111  # IPv4 available

            mock_sock_v6 = MagicMock()
            mock_sock_v6.connect_ex.return_value = 0  # IPv6 in use

            # First call IPv4, second call IPv6
            mock_socket.return_value.__enter__.side_effect = [mock_sock_v4, mock_sock_v6]

            result = check_port_available(8080)
            assert result is False

    def test_port_available_ipv6_not_supported(self) -> None:
        """Should return True when IPv4 available and IPv6 raises error."""
        from setup_lib.port_scanner import check_port_available

        with patch("socket.socket") as mock_socket:
            mock_sock_v4 = MagicMock()
            mock_sock_v4.connect_ex.return_value = 111

            # IPv6 raises OSError
            def side_effect(*args, **kwargs):
                ctx = MagicMock()
                if args and args[0] == 10:  # AF_INET6
                    ctx.__enter__.side_effect = OSError("IPv6 not supported")
                else:
                    ctx.__enter__.return_value = mock_sock_v4
                return ctx

            mock_socket.side_effect = side_effect

            result = check_port_available(8080)
            assert result is True


class TestGetProcessUsingPort:
    """Tests for get_process_using_port() function."""

    def test_process_found_ss(self) -> None:
        """Should find process using ss command."""
        from setup_lib.port_scanner import get_process_using_port

        ss_output = 'LISTEN 0 128 *:8080 *:* users:(("nginx",pid=1234,fd=6))'

        with (
            patch("shutil.which", return_value="/usr/bin/ss"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout=ss_output)

            result = get_process_using_port(8080)
            assert result.pid == 1234
            assert result.name == "nginx"

    def test_process_found_netstat(self) -> None:
        """Should find process using netstat when ss unavailable."""
        from setup_lib.port_scanner import get_process_using_port

        netstat_output = """Active Internet connections (only servers)
Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name
tcp        0      0 0.0.0.0:8080            0.0.0.0:*               LISTEN      5678/python"""

        with (
            patch("shutil.which") as mock_which,
            patch("subprocess.run") as mock_run,
        ):
            mock_which.side_effect = lambda cmd: "/usr/bin/netstat" if cmd == "netstat" else None
            mock_run.return_value = MagicMock(returncode=0, stdout=netstat_output)

            result = get_process_using_port(8080)
            assert result.pid == 5678
            assert result.name == "python"

    def test_process_not_found(self) -> None:
        """Should return empty ProcessInfo when no process found."""
        from setup_lib.port_scanner import get_process_using_port

        with patch("shutil.which", return_value=None):
            result = get_process_using_port(8080)
            assert result.pid is None
            assert result.name is None

    def test_ss_command_fails(self) -> None:
        """Should handle ss command failure gracefully."""
        from setup_lib.port_scanner import get_process_using_port

        with (
            patch("shutil.which", return_value="/usr/bin/ss"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=1, stdout="")

            result = get_process_using_port(8080)
            assert result.pid is None


class TestParseSsOutput:
    """Tests for _parse_ss_output() function."""

    def test_parse_valid_output(self) -> None:
        """Should parse valid ss output."""
        from setup_lib.port_scanner import _parse_ss_output

        output = 'LISTEN 0 128 *:8080 *:* users:(("nginx",pid=1234,fd=6))'
        result = _parse_ss_output(output)
        assert result.pid == 1234
        assert result.name == "nginx"

    def test_parse_multiple_processes(self) -> None:
        """Should parse first process from output."""
        from setup_lib.port_scanner import _parse_ss_output

        output = """LISTEN 0 128 *:8080 *:* users:(("nginx",pid=1234,fd=6))
LISTEN 0 128 *:8081 *:* users:(("apache",pid=5678,fd=7))"""
        result = _parse_ss_output(output)
        assert result.pid == 1234
        assert result.name == "nginx"

    def test_parse_empty_output(self) -> None:
        """Should handle empty output."""
        from setup_lib.port_scanner import _parse_ss_output

        result = _parse_ss_output("")
        assert result.pid is None
        assert result.name is None

    def test_parse_malformed_output(self) -> None:
        """Should handle malformed output gracefully."""
        from setup_lib.port_scanner import _parse_ss_output

        result = _parse_ss_output("not valid ss output")
        assert result.pid is None
        assert result.name is None


class TestParseNetstatOutput:
    """Tests for _parse_netstat_output() function."""

    def test_parse_valid_output(self) -> None:
        """Should parse valid netstat output."""
        from setup_lib.port_scanner import _parse_netstat_output

        output = """Active Internet connections (only servers)
Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name
tcp        0      0 0.0.0.0:8080            0.0.0.0:*               LISTEN      1234/nginx"""
        result = _parse_netstat_output(output, 8080)
        assert result.pid == 1234
        assert result.name == "nginx"

    def test_parse_port_not_found(self) -> None:
        """Should return empty ProcessInfo when port not in output."""
        from setup_lib.port_scanner import _parse_netstat_output

        output = """Active Internet connections (only servers)
Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name
tcp        0      0 0.0.0.0:8081            0.0.0.0:*               LISTEN      1234/nginx"""
        result = _parse_netstat_output(output, 8080)
        assert result.pid is None

    def test_parse_empty_output(self) -> None:
        """Should handle empty output."""
        from setup_lib.port_scanner import _parse_netstat_output

        result = _parse_netstat_output("", 8080)
        assert result.pid is None


class TestFindAlternativePort:
    """Tests for find_alternative_port() function."""

    def test_find_next_available(self) -> None:
        """Should find next available port."""
        from setup_lib.port_scanner import find_alternative_port

        with patch("setup_lib.port_scanner.check_port_available") as mock_check:
            mock_check.return_value = True
            result = find_alternative_port(8080)
            assert result == 8081

    def test_skip_unavailable_ports(self) -> None:
        """Should skip unavailable ports."""
        from setup_lib.port_scanner import find_alternative_port

        with patch("setup_lib.port_scanner.check_port_available") as mock_check:
            # 8081 and 8082 unavailable, 8083 available
            mock_check.side_effect = lambda p: p >= 8083
            result = find_alternative_port(8080)
            assert result == 8083

    def test_skip_excluded_ports(self) -> None:
        """Should skip excluded ports."""
        from setup_lib.port_scanner import find_alternative_port

        with patch("setup_lib.port_scanner.check_port_available", return_value=True):
            result = find_alternative_port(8080, exclude={8081, 8082})
            assert result == 8083

    def test_no_available_port_raises(self) -> None:
        """Should raise RuntimeError when no port available."""
        from setup_lib.port_scanner import find_alternative_port

        with patch("setup_lib.port_scanner.check_port_available", return_value=False):
            with pytest.raises(RuntimeError, match="No available port found"):
                find_alternative_port(65530)


class TestFindAlternativePorts:
    """Tests for find_alternative_ports() function."""

    def test_find_multiple_alternatives(self) -> None:
        """Should find multiple alternative ports."""
        from setup_lib.port_scanner import find_alternative_ports

        with patch("setup_lib.port_scanner.check_port_available", return_value=True):
            result = find_alternative_ports(8080, count=3)
            assert result == [8081, 8082, 8083]

    def test_find_fewer_than_requested(self) -> None:
        """Should return fewer alternatives if not enough available."""
        from setup_lib.port_scanner import find_alternative_ports

        with patch("setup_lib.port_scanner.check_port_available") as mock_check:
            # Only 8081 available, then no more
            mock_check.side_effect = lambda p: p == 8081
            result = find_alternative_ports(8080, count=3)
            assert len(result) == 1
            assert result[0] == 8081

    def test_empty_result_when_none_available(self) -> None:
        """Should return empty list when no alternatives available."""
        from setup_lib.port_scanner import find_alternative_ports

        with patch("setup_lib.port_scanner.check_port_available", return_value=False):
            result = find_alternative_ports(65530, count=3)
            assert result == []

    def test_respect_exclude_set(self) -> None:
        """Should respect exclude set."""
        from setup_lib.port_scanner import find_alternative_ports

        with patch("setup_lib.port_scanner.check_port_available", return_value=True):
            result = find_alternative_ports(8080, count=2, exclude={8081})
            assert 8081 not in result
            assert result == [8082, 8083]


class TestScanPorts:
    """Tests for scan_ports() function."""

    def test_all_ports_available(self) -> None:
        """Should return no conflicts when all ports available."""
        from setup_lib.port_scanner import scan_ports

        ports = {8080: "Frontend", 8000: "Backend"}

        with patch("setup_lib.port_scanner.check_port_available", return_value=True):
            result = scan_ports(ports)
            assert result.has_conflicts is False
            assert result.conflicts == []
            assert result.scanned_ports == ports

    def test_port_in_use(self) -> None:
        """Should detect port in use."""
        from setup_lib.port_scanner import scan_ports

        ports = {8080: "Frontend"}

        with (
            patch("setup_lib.port_scanner.check_port_available", return_value=False),
            patch("setup_lib.port_scanner.get_process_using_port") as mock_get_proc,
            patch("setup_lib.port_scanner.find_alternative_ports", return_value=[8081, 8082]),
        ):
            from setup_lib.port_scanner import ProcessInfo

            mock_get_proc.return_value = ProcessInfo(pid=1234, name="nginx")

            result = scan_ports(ports)

            assert result.has_conflicts is True
            assert len(result.conflicts) == 1
            assert result.conflicts[0].port == 8080
            assert result.conflicts[0].service == "Frontend"
            assert result.conflicts[0].process.pid == 1234

    def test_multiple_conflicts(self) -> None:
        """Should detect multiple port conflicts."""
        from setup_lib.port_scanner import scan_ports

        ports = {8080: "Frontend", 8000: "Backend"}

        with (
            patch("setup_lib.port_scanner.check_port_available", return_value=False),
            patch("setup_lib.port_scanner.get_process_using_port") as mock_get_proc,
            patch("setup_lib.port_scanner.find_alternative_ports", return_value=[]),
        ):
            from setup_lib.port_scanner import ProcessInfo

            mock_get_proc.return_value = ProcessInfo()

            result = scan_ports(ports)

            assert len(result.conflicts) == 2
            assert result.conflicting_ports == [8080, 8000]


class TestScanRequiredPorts:
    """Tests for scan_required_ports() function."""

    def test_scans_all_required_ports(self) -> None:
        """Should scan all ports in REQUIRED_PORTS."""
        from setup_lib.port_scanner import REQUIRED_PORTS, scan_required_ports

        with patch("setup_lib.port_scanner.check_port_available", return_value=True):
            result = scan_required_ports()
            assert result.scanned_ports == REQUIRED_PORTS


class TestFormatConflictReport:
    """Tests for format_conflict_report() function."""

    def test_no_conflicts_message(self) -> None:
        """Should return simple message when no conflicts."""
        from setup_lib.port_scanner import PortScanResult, format_conflict_report

        result = PortScanResult()
        report = format_conflict_report(result)
        assert "All required ports are available" in report

    def test_conflict_report_header(self) -> None:
        """Should include report header."""
        from setup_lib.port_scanner import PortConflict, PortScanResult, format_conflict_report

        conflict = PortConflict(port=8080, service="Frontend")
        result = PortScanResult(conflicts=[conflict])
        report = format_conflict_report(result)
        assert "PORT CONFLICT REPORT" in report

    def test_conflict_details_in_report(self) -> None:
        """Should include conflict details."""
        from setup_lib.port_scanner import (
            PortConflict,
            PortScanResult,
            ProcessInfo,
            format_conflict_report,
        )

        proc = ProcessInfo(pid=1234, name="nginx")
        conflict = PortConflict(port=8080, service="Frontend", process=proc, alternatives=[8081])
        result = PortScanResult(conflicts=[conflict])
        report = format_conflict_report(result)

        assert "Port 8080" in report
        assert "Frontend" in report
        assert "nginx" in report
        assert "1234" in report
        assert "8081" in report

    def test_unknown_process_in_report(self) -> None:
        """Should handle unknown process gracefully."""
        from setup_lib.port_scanner import PortConflict, PortScanResult, format_conflict_report

        conflict = PortConflict(port=8080, service="Frontend")
        result = PortScanResult(conflicts=[conflict])
        report = format_conflict_report(result)

        assert "unknown process" in report

    def test_no_alternatives_in_report(self) -> None:
        """Should handle no alternatives gracefully."""
        from setup_lib.port_scanner import PortConflict, PortScanResult, format_conflict_report

        conflict = PortConflict(port=8080, service="Frontend", alternatives=[])
        result = PortScanResult(conflicts=[conflict])
        report = format_conflict_report(result)

        assert "none found" in report


class TestPrintConflictReport:
    """Tests for print_conflict_report() function."""

    def test_prints_report(self) -> None:
        """Should print report to stdout."""
        from setup_lib.port_scanner import PortScanResult, print_conflict_report

        result = PortScanResult()

        with patch("builtins.print") as mock_print:
            print_conflict_report(result)
            mock_print.assert_called_once()
            assert "All required ports are available" in mock_print.call_args[0][0]


class TestPromptAndScanPorts:
    """Tests for prompt_and_scan_ports() function."""

    def test_no_conflicts_no_prompt(self) -> None:
        """Should not prompt when no conflicts."""
        from setup_lib.port_scanner import prompt_and_scan_ports

        with (
            patch("setup_lib.port_scanner.scan_required_ports") as mock_scan,
            patch("builtins.print"),
            patch("builtins.input") as mock_input,
        ):
            from setup_lib.port_scanner import PortScanResult

            mock_scan.return_value = PortScanResult()

            result = prompt_and_scan_ports()

            mock_input.assert_not_called()
            assert result.has_conflicts is False

    def test_prompt_on_conflicts(self) -> None:
        """Should prompt user when conflicts exist."""
        from setup_lib.port_scanner import prompt_and_scan_ports

        with (
            patch("setup_lib.port_scanner.scan_required_ports") as mock_scan,
            patch("setup_lib.port_scanner.print_conflict_report"),
            patch("builtins.print"),
            patch("builtins.input", return_value="y") as mock_input,
        ):
            from setup_lib.port_scanner import PortConflict, PortScanResult

            conflict = PortConflict(port=8080, service="Frontend")
            mock_scan.return_value = PortScanResult(conflicts=[conflict])

            result = prompt_and_scan_ports()

            mock_input.assert_called_once()
            assert result.has_conflicts is True

    def test_exit_on_decline(self) -> None:
        """Should exit when user declines to continue."""
        from setup_lib.port_scanner import prompt_and_scan_ports

        with (
            patch("setup_lib.port_scanner.scan_required_ports") as mock_scan,
            patch("setup_lib.port_scanner.print_conflict_report"),
            patch("builtins.print"),
            patch("builtins.input", return_value="n"),
        ):
            from setup_lib.port_scanner import PortConflict, PortScanResult

            conflict = PortConflict(port=8080, service="Frontend")
            mock_scan.return_value = PortScanResult(conflicts=[conflict])

            with pytest.raises(SystemExit) as exc_info:
                prompt_and_scan_ports()

            assert exc_info.value.code == 1

    def test_exit_on_eof(self) -> None:
        """Should exit on EOF (Ctrl+D)."""
        from setup_lib.port_scanner import prompt_and_scan_ports

        with (
            patch("setup_lib.port_scanner.scan_required_ports") as mock_scan,
            patch("setup_lib.port_scanner.print_conflict_report"),
            patch("builtins.print"),
            patch("builtins.input", side_effect=EOFError),
        ):
            from setup_lib.port_scanner import PortConflict, PortScanResult

            conflict = PortConflict(port=8080, service="Frontend")
            mock_scan.return_value = PortScanResult(conflicts=[conflict])

            with pytest.raises(SystemExit) as exc_info:
                prompt_and_scan_ports()

            assert exc_info.value.code == 1

    def test_exit_on_keyboard_interrupt(self) -> None:
        """Should exit on Ctrl+C."""
        from setup_lib.port_scanner import prompt_and_scan_ports

        with (
            patch("setup_lib.port_scanner.scan_required_ports") as mock_scan,
            patch("setup_lib.port_scanner.print_conflict_report"),
            patch("builtins.print"),
            patch("builtins.input", side_effect=KeyboardInterrupt),
        ):
            from setup_lib.port_scanner import PortConflict, PortScanResult

            conflict = PortConflict(port=8080, service="Frontend")
            mock_scan.return_value = PortScanResult(conflicts=[conflict])

            with pytest.raises(SystemExit) as exc_info:
                prompt_and_scan_ports()

            assert exc_info.value.code == 1
