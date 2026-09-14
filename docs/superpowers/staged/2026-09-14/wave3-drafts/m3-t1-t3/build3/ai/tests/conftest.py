"""Pytest configuration for AI tests.

This conftest.py file adds the ai directory to sys.path to enable
importing AI modules like compile_utils and batch_utils.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add ai directory to sys.path for imports
ai_dir = Path(__file__).parent.parent
if str(ai_dir) not in sys.path:
    sys.path.insert(0, str(ai_dir))
