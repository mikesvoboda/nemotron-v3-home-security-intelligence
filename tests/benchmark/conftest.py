"""
Pytest configuration for benchmark tests.

Adds the project root to sys.path to allow imports from scripts/ directory.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
