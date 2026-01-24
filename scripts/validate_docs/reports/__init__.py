"""Report generators for documentation validation results.

This package provides different output formats:
- console.py: Rich terminal output with colors
- json_report.py: JSON output for CI integration
"""

from .console import ConsoleReporter
from .json_report import JSONReporter

__all__ = ["ConsoleReporter", "JSONReporter"]
