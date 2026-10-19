"""Pytest configuration for the ai/ tier (WP6.1/WP6.2, O3.1)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# WP6.2: keep bare `import triton` blocked so torch._dynamo's optional compiler
# probe raises ImportError cleanly when pip `triton` is absent.
sys.modules["triton"] = None
