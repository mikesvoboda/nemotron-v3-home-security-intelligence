#!/usr/bin/env bash
# setup.sh - Linux/macOS wrapper for setup.py
# Usage: ./setup.sh [--guided]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/setup.py" "$@"
