"""Golden paths: unmocked specs run against a live test deployment.

Brought up by ``scripts/feature-check.sh`` (O2.2, #6961). Sibling directories
under ``backend/tests`` each carry an ``__init__.py``; this package follows the
convention so the suite stays import-mode consistent under
``--dist=worksteal`` (``pyproject.toml`` ``addopts``).
"""
