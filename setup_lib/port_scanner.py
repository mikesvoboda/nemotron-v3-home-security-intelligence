"""Network port scanner for setup.py.

This module provides utilities to scan for port conflicts before starting
the application. It detects which required ports are already in use and
can identify the process using them, suggesting alternative ports.

Usage:
    from setup_lib.port_scanner import scan_required_ports, print_conflict_report

    result = scan_required_ports()
    if result.has_conflicts:
        print_conflict_report(result)
"""

from __future__ import annotations

import shutil
import socket
import subprocess
from dataclasses import dataclass, field

# Required application ports with descriptions
REQUIRED_PORTS: dict[int, str] = {
    8080: "Frontend",
    8000: "Backend API",
    5432: "PostgreSQL",
    6379: "Redis",
    1883: "MQTT",
    8883: "MQTT TLS",
    5000: "YOLO service",
    5001: "Nemotron service",
}


@dataclass
class ProcessInfo:
    """Information about a process using a port.

    Attributes:
        pid: Process ID.
        name: Process name.
        user: User running the process.
    """

    pid: int | None = None
    name: str | None = None
    user: str | None = None


@dataclass
class PortConflict:
    """Represents a port conflict with process info and alternatives.

    Attributes:
        port: The conflicting port number.
        service: Description of the expected service on this port.
        process: Information about the process using the port.
        alternatives: List of available alternative ports.
    """

    port: int
    service: str
    process: ProcessInfo = field(default_factory=ProcessInfo)
    alternatives: list[int] = field(default_factory=list)


@dataclass
class PortScanResult:
    """Contains scan results with conflict information.

    Attributes:
        scanned_ports: Ports that were scanned.
        conflicts: List of port conflicts found.
    """

    scanned_ports: dict[int, str] = field(default_factory=dict)
    conflicts: list[PortConflict] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        """Check if any port conflicts were found.

        Returns:
            True if there are conflicts, False otherwise.
        """
        return len(self.conflicts) > 0

    @property
    def conflicting_ports(self) -> list[int]:
        """Get list of ports that have conflicts.

        Returns:
            List of port numbers with conflicts.
        """
        return [c.port for c in self.conflicts]


def check_port_available(port: int) -> bool:
    """Check if a port is available for binding.

    Checks both IPv4 and IPv6 localhost to detect processes bound to either.

    Args:
        port: Port number to check.

    Returns:
        True if port is available on both IPv4 and IPv6, False if in use.
    """
    # Check IPv4
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return False
    except OSError:
        pass  # Socket error, assume available for IPv4

    # Check IPv6
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex(("::1", port)) == 0:
                return False
    except OSError:
        pass  # IPv6 not available or error

    return True


def get_process_using_port(port: int) -> ProcessInfo:
    """Get information about the process using a port.

    Uses ss (preferred) or netstat to identify the process.

    Args:
        port: Port number to check.

    Returns:
        ProcessInfo with process details, or empty ProcessInfo if not found.
    """
    # Try ss first (modern Linux)
    ss_path = shutil.which("ss")
    if ss_path:
        try:
            result = subprocess.run(
                [ss_path, "-tlnp", f"sport = :{port}"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and result.stdout:
                return _parse_ss_output(result.stdout)
        except (subprocess.SubprocessError, OSError):
            pass

    # Fall back to netstat
    netstat_path = shutil.which("netstat")
    if netstat_path:
        try:
            result = subprocess.run(
                [netstat_path, "-tlnp"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and result.stdout:
                return _parse_netstat_output(result.stdout, port)
        except (subprocess.SubprocessError, OSError):
            pass

    return ProcessInfo()


def _parse_ss_output(output: str) -> ProcessInfo:
    """Parse ss command output to extract process info.

    Args:
        output: Raw output from ss command.

    Returns:
        ProcessInfo extracted from output.
    """
    info = ProcessInfo()

    for line in output.splitlines():
        # Look for users:(("process",pid=12345,fd=3))
        if "users:((" in line:
            try:
                users_part = line.split("users:((")[1]
                # Extract process name
                if '"' in users_part:
                    name_start = users_part.index('"') + 1
                    name_end = users_part.index('"', name_start)
                    info.name = users_part[name_start:name_end]

                # Extract PID
                if "pid=" in users_part:
                    pid_start = users_part.index("pid=") + 4
                    pid_end = pid_start
                    while pid_end < len(users_part) and users_part[pid_end].isdigit():
                        pid_end += 1
                    if pid_end > pid_start:
                        info.pid = int(users_part[pid_start:pid_end])
                break
            except (ValueError, IndexError):
                continue

    return info


def _parse_netstat_output(output: str, port: int) -> ProcessInfo:
    """Parse netstat command output to extract process info.

    Args:
        output: Raw output from netstat command.
        port: Port number to find.

    Returns:
        ProcessInfo extracted from output.
    """
    info = ProcessInfo()
    port_str = f":{port}"

    for line in output.splitlines():
        if port_str in line and "LISTEN" in line:
            parts = line.split()
            if len(parts) >= 7:
                # Last column is usually PID/Program
                pid_prog = parts[-1]
                if "/" in pid_prog:
                    pid_str, name = pid_prog.split("/", 1)
                    try:
                        info.pid = int(pid_str)
                        info.name = name
                    except ValueError:
                        pass
                break

    return info


def find_alternative_port(port: int, exclude: set[int] | None = None) -> int:
    """Find an available alternative port.

    Searches for the next available port starting from the given port + 1.

    Args:
        port: Starting port to find alternative for.
        exclude: Set of ports to exclude from consideration.

    Returns:
        First available port number.

    Raises:
        RuntimeError: If no available port found up to 65535.
    """
    if exclude is None:
        exclude = set()

    # Start searching from port + 1
    candidate = port + 1
    while candidate <= 65535:
        if candidate not in exclude and check_port_available(candidate):
            return candidate
        candidate += 1

    raise RuntimeError(f"No available port found starting from {port + 1}")


def find_alternative_ports(port: int, count: int = 3, exclude: set[int] | None = None) -> list[int]:
    """Find multiple available alternative ports.

    Args:
        port: Starting port to find alternatives for.
        count: Number of alternatives to find.
        exclude: Set of ports to exclude from consideration.

    Returns:
        List of available port numbers.
    """
    if exclude is None:
        exclude = set()

    alternatives: list[int] = []
    exclude_copy = exclude.copy()

    for _ in range(count):
        try:
            alt = find_alternative_port(port, exclude_copy)
            alternatives.append(alt)
            exclude_copy.add(alt)
            port = alt  # Search from the new port
        except RuntimeError:
            break

    return alternatives


def scan_ports(ports: dict[int, str]) -> PortScanResult:
    """Scan specified ports for conflicts.

    Args:
        ports: Dictionary of port numbers to service descriptions.

    Returns:
        PortScanResult containing scan results and any conflicts.
    """
    result = PortScanResult(scanned_ports=ports.copy())
    assigned_ports: set[int] = set(ports.keys())

    for port, service in ports.items():
        if not check_port_available(port):
            process_info = get_process_using_port(port)
            alternatives = find_alternative_ports(port, count=3, exclude=assigned_ports)

            conflict = PortConflict(
                port=port,
                service=service,
                process=process_info,
                alternatives=alternatives,
            )
            result.conflicts.append(conflict)

            # Add suggested alternatives to exclude set for next iteration
            for alt in alternatives:
                assigned_ports.add(alt)

    return result


def scan_required_ports() -> PortScanResult:
    """Scan all required application ports for conflicts.

    Scans the ports defined in REQUIRED_PORTS.

    Returns:
        PortScanResult containing scan results and any conflicts.
    """
    return scan_ports(REQUIRED_PORTS)


def format_conflict_report(result: PortScanResult) -> str:
    """Format scan results as a human-readable report.

    Args:
        result: PortScanResult from a port scan.

    Returns:
        Formatted string report.
    """
    if not result.has_conflicts:
        return "All required ports are available."

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("PORT CONFLICT REPORT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Found {len(result.conflicts)} port conflict(s):")
    lines.append("")

    for conflict in result.conflicts:
        lines.append(f"  Port {conflict.port} ({conflict.service}):")

        if conflict.process.name or conflict.process.pid:
            proc_info = []
            if conflict.process.name:
                proc_info.append(f"process={conflict.process.name}")
            if conflict.process.pid:
                proc_info.append(f"pid={conflict.process.pid}")
            if conflict.process.user:
                proc_info.append(f"user={conflict.process.user}")
            lines.append(f"    In use by: {', '.join(proc_info)}")
        else:
            lines.append("    In use by: unknown process")

        if conflict.alternatives:
            alt_str = ", ".join(str(p) for p in conflict.alternatives)
            lines.append(f"    Alternatives: {alt_str}")
        else:
            lines.append("    Alternatives: none found")

        lines.append("")

    lines.append("-" * 60)
    lines.append("To resolve conflicts, either:")
    lines.append("  1. Stop the processes using these ports")
    lines.append("  2. Configure the application to use alternative ports")
    lines.append("-" * 60)

    return "\n".join(lines)


def print_conflict_report(result: PortScanResult) -> None:
    """Print scan results to stdout.

    Args:
        result: PortScanResult from a port scan.
    """
    print(format_conflict_report(result))


def prompt_and_scan_ports() -> PortScanResult:
    """Interactive port scanning for setup scripts.

    Scans required ports and displays results. If conflicts are found,
    prompts the user to acknowledge before continuing.

    Returns:
        PortScanResult from the scan.
    """
    print("\nScanning required ports...")
    result = scan_required_ports()

    if result.has_conflicts:
        print_conflict_report(result)
        print("")
        try:
            response = input("Continue with port conflicts? (y/n): ").strip().lower()
            if response not in ("y", "yes"):
                print("Setup cancelled due to port conflicts.")
                raise SystemExit(1)
        except (EOFError, KeyboardInterrupt) as exc:
            print("\nSetup cancelled.")
            raise SystemExit(1) from exc
    else:
        print("All required ports are available.")

    return result


if __name__ == "__main__":
    result = prompt_and_scan_ports()
    if not result.has_conflicts:
        print("\nReady to proceed with setup.")
