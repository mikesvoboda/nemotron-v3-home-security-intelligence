# Setup Library Directory - Agent Guide

## Purpose

This directory contains reusable Python utilities for the main `setup.py` script. These functions are extracted to enable better testing and reusability.

## Directory Contents

```
setup_lib/
  AGENTS.md     # This file
  __init__.py   # Package exports
  core.py       # Core utility functions
```

## Key Files

### **init**.py

**Purpose:** Package initialization and public API exports.

**Exports:**

- `WEAK_PASSWORDS` - Set of known weak/default passwords
- `check_port_available(port)` - Check if a port is available
- `find_available_port(start)` - Find next available port
- `generate_password(length)` - Generate secure random password
- `is_weak_password(password)` - Check if password is weak

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

## Usage

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

## Related Files

- `/setup.py` - Main setup script that uses these utilities
- `/setup.sh` - Shell wrapper for setup.py
- `/.env.example` - Template for environment configuration
