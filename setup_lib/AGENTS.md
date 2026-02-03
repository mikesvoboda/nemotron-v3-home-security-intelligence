# Setup Library Directory - Agent Guide

## Purpose

This directory contains reusable Python utilities for the main `setup.py` script. These functions are extracted to enable better testing and reusability.

## Directory Contents

```
setup_lib/
  AGENTS.md       # This file
  __init__.py     # Package exports
  core.py         # Core utility functions
  port_scanner.py # Network port scanning
```

## Key Files

### **init**.py

**Purpose:** Package initialization and public API exports.

**Exports:**

Core utilities:

- `WEAK_PASSWORDS` - Set of known weak/default passwords
- `check_port_available(port)` - Check if a port is available
- `find_available_port(start)` - Find next available port
- `generate_password(length)` - Generate secure random password
- `is_weak_password(password)` - Check if password is weak

Port scanner:

- `REQUIRED_PORTS` - Dict of required application ports
- `PortConflict` - Dataclass for port conflict information
- `PortScanResult` - Dataclass for scan results
- `ProcessInfo` - Dataclass for process information
- `scan_ports(ports)` - Scan specified ports for conflicts
- `scan_required_ports()` - Scan all required application ports
- `find_alternative_port(port)` - Find available alternative port
- `find_alternative_ports(port, count)` - Find multiple alternatives
- `get_process_using_port(port)` - Get process info for port
- `format_conflict_report(result)` - Format scan results as string
- `print_conflict_report(result)` - Print scan results to stdout
- `prompt_and_scan_ports()` - Interactive port scanning

### core.py

**Purpose:** Core utility implementations for the setup script.

**Functions:**

| Function               | Purpose                                           |
| ---------------------- | ------------------------------------------------- |
| `check_port_available` | Check if a port is available for binding          |
| `find_available_port`  | Find the next available port starting from a port |
| `generate_password`    | Generate a secure URL-safe random password        |
| `is_weak_password`     | Check if password is in weak list or < 16 chars   |

**Constants:**

- `WEAK_PASSWORDS` - Set containing common weak passwords to warn about:
  - `security_dev_password`, `password`, `postgres`, `admin`, `root`, `123456`, `changeme`, `secret`

### port_scanner.py

**Purpose:** Network port scanning to detect conflicts before starting services.

**Dataclasses:**

| Class            | Purpose                                          |
| ---------------- | ------------------------------------------------ |
| `ProcessInfo`    | Information about a process (pid, name, user)    |
| `PortConflict`   | Port conflict with process info and alternatives |
| `PortScanResult` | Scan results with `has_conflicts` property       |

**Functions:**

| Function                 | Purpose                                        |
| ------------------------ | ---------------------------------------------- |
| `check_port_available`   | Check if port is available (IPv4/IPv6)         |
| `get_process_using_port` | Get process info using ss/netstat              |
| `find_alternative_port`  | Find single available alternative port         |
| `find_alternative_ports` | Find multiple available alternative ports      |
| `scan_ports`             | Scan specified ports for conflicts             |
| `scan_required_ports`    | Scan all REQUIRED_PORTS for conflicts          |
| `format_conflict_report` | Format PortScanResult as human-readable string |
| `print_conflict_report`  | Print formatted report to stdout               |
| `prompt_and_scan_ports`  | Interactive scanning with user prompts         |

**Constants:**

- `REQUIRED_PORTS` - Dict mapping port numbers to service descriptions:
  - `8080`: Frontend
  - `8000`: Backend API
  - `5432`: PostgreSQL
  - `6379`: Redis
  - `1883`: MQTT
  - `8883`: MQTT TLS
  - `5000`: YOLO service
  - `5001`: Nemotron service

## Usage

### Core Utilities

```python
from setup_lib import (
    check_port_available,
    find_available_port,
    generate_password,
    is_weak_password,
)

# Check if port 8000 is available
if check_port_available(8000):
    print("Port 8000 is free")

# Find next available port starting from 8000
port = find_available_port(8000)

# Generate a 32-character secure password
password = generate_password(32)

# Check if a password is weak
if is_weak_password("changeme"):
    print("Warning: weak password")
```

### Port Scanner

```python
from setup_lib import (
    REQUIRED_PORTS,
    scan_required_ports,
    print_conflict_report,
    prompt_and_scan_ports,
)

# Scan all required ports
result = scan_required_ports()

if result.has_conflicts:
    print_conflict_report(result)
    for conflict in result.conflicts:
        print(f"Port {conflict.port} ({conflict.service}) in use")
        print(f"  Process: {conflict.process.name} (PID {conflict.process.pid})")
        print(f"  Alternatives: {conflict.alternatives}")

# Interactive scanning for setup scripts
result = prompt_and_scan_ports()  # Prompts user if conflicts found
```

## Related Files

- `/setup.py` - Main setup script that uses these utilities
- `/setup.sh` - Shell wrapper for setup.py
- `/.env.example` - Template for environment configuration
- `/backend/tests/unit/setup_lib/` - Unit tests for this package
