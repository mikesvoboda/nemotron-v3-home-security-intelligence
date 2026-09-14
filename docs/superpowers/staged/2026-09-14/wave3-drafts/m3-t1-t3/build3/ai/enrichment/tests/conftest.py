"""Pytest configuration for ai/enrichment tests.

Adds the ai directory to the Python path so that imports like
`from ai.enrichment.model_manager import ...` work correctly.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add the project root to the Python path so ai.enrichment imports work
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
