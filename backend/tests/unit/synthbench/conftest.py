"""Import the backend modules the inherited autouse fixtures import, at collection.

These tests never import backend, but they inherit two autouse fixtures that do, lazily:
enable_api_key_auth_for_unit_tests (backend.core.config, at the first setup on a worker)
and reset_settings_cache (backend.services.severity, at every teardown). pytest-timeout
times setup and teardown too (timeout_func_only = false), so the first test on each
worker paid a ~2.3 s import inside its 5 s budget. Under load (-n auto on a busy host)
SIGALRM landed mid-import and left half-initialized modules behind, which then failed
later tests with circular-import and "Table already defined" errors. Every other unit
module imports backend at collection, where nothing is timed; so do these.
"""

import importlib

for _module in ("backend.core.config", "backend.services.severity"):
    importlib.import_module(_module)
