"""Entry point for running validate_docs as a module.

Usage:
    python -m validate_docs docs/architecture/
    python -m validate_docs docs/architecture/ai-pipeline.md --format json
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
