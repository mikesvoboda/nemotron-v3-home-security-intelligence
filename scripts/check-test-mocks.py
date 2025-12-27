#!/usr/bin/env python3
"""Pre-commit hook to detect integration tests that don't mock slow background services.

Background:
WebSocket integration tests were taking 5+ seconds each because they didn't mock:
- SystemBroadcaster / get_system_broadcaster
- GPUMonitor
- CleanupService

This script ensures all integration tests using TestClient(app) properly mock these services.
"""

import ast
import sys
from pathlib import Path

# Services that must be mocked when using TestClient with the FastAPI app
# These services start background tasks during app lifespan and cause slow tests
REQUIRED_MOCK_PATTERNS = {
    # Patterns that indicate proper mocking (any ONE of these per service category)
    "system_broadcaster": [
        "backend.main.get_system_broadcaster",
        "backend.services.system_broadcaster.get_system_broadcaster",
        "backend.services.system_broadcaster.SystemBroadcaster",
    ],
    "gpu_monitor": [
        "backend.main.GPUMonitor",
        "backend.services.gpu_monitor.GPUMonitor",
    ],
    "cleanup_service": [
        "backend.main.CleanupService",
        "backend.services.cleanup_service.CleanupService",
    ],
}

# Patterns that indicate a test uses TestClient with the main app
TESTCLIENT_PATTERNS = [
    "TestClient(app)",
    "TestClient(app,",
    "TestClient( app)",
    "TestClient( app,",
]

# Import patterns that indicate TestClient usage
TESTCLIENT_IMPORT_PATTERNS = [
    "from starlette.testclient import TestClient",
    "from fastapi.testclient import TestClient",
]

# Import patterns that indicate backend.main app usage
APP_IMPORT_PATTERNS = [
    "from backend.main import app",
    "import backend.main",
]


def extract_string_literals(node: ast.AST) -> list[str]:
    """Extract all string literals from an AST node."""
    strings = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            strings.append(child.value)
    return strings


def check_file_for_mocks(file_path: Path) -> tuple[bool, list[str]]:
    """Check if a file properly mocks slow services when using TestClient.

    Returns:
        Tuple of (passes_check, list_of_issues)
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return False, [f"Could not read file: {e}"]

    # Quick text-based check: does file use TestClient?
    uses_testclient = any(pattern in content for pattern in TESTCLIENT_IMPORT_PATTERNS)
    imports_app = any(pattern in content for pattern in APP_IMPORT_PATTERNS)

    if not uses_testclient or not imports_app:
        # File doesn't use TestClient with backend.main.app, skip
        return True, []

    # Check if TestClient(app) is actually instantiated (not just imported)
    uses_testclient_with_app = any(pattern in content for pattern in TESTCLIENT_PATTERNS)

    if not uses_testclient_with_app:
        # TestClient imported but not used with app directly
        return True, []

    # Parse file as AST for more reliable string extraction
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return False, [f"Syntax error in file: {e}"]

    # Extract all string literals from the file (these include patch targets)
    all_strings = extract_string_literals(tree)

    # Also check raw content for patch patterns (handles multi-line strings better)
    patch_targets = set(all_strings)

    # Check which service categories are properly mocked
    missing_mocks = []

    for service_name, patterns in REQUIRED_MOCK_PATTERNS.items():
        service_mocked = False
        for pattern in patterns:
            # Check if pattern appears in any string literal or in raw content
            if pattern in patch_targets or f'"{pattern}"' in content or f"'{pattern}'" in content:
                service_mocked = True
                break
        if not service_mocked:
            missing_mocks.append(service_name)

    if missing_mocks:
        return False, missing_mocks

    return True, []


def main() -> int:
    """Main entry point for pre-commit hook.

    Returns:
        0 on success, 1 on failure
    """
    # Get files to check from command line arguments
    if len(sys.argv) < 2:
        # No files provided, check all integration test files
        integration_dir = Path(__file__).parent.parent / "backend" / "tests" / "integration"
        if not integration_dir.exists():
            print("No integration test directory found.")
            return 0
        files_to_check = list(integration_dir.glob("*.py"))
    else:
        files_to_check = [Path(f) for f in sys.argv[1:]]

    # Filter to only Python files in integration directory
    files_to_check = [
        f
        for f in files_to_check
        if f.suffix == ".py" and "integration" in str(f) and f.name != "__init__.py"
    ]

    if not files_to_check:
        return 0

    failed_files = []

    for file_path in files_to_check:
        passes, issues = check_file_for_mocks(file_path)
        if not passes:
            failed_files.append((file_path, issues))

    if failed_files:
        print("\nERROR: Integration tests using TestClient must mock slow background services.\n")

        for file_path, issues in failed_files:
            print(f"  {file_path}")
            if issues and (
                issues[0].startswith("Could not read") or issues[0].startswith("Syntax error")
            ):
                print(f"    Error: {issues[0]}")
            else:
                print(f"    Missing mocks for: {', '.join(issues)}")

        print("\n" + "=" * 80)
        print("Integration tests using TestClient(app) must mock these services to avoid")
        print("5+ second delays from background tasks starting during app lifespan:\n")
        print("  - backend.main.get_system_broadcaster (or SystemBroadcaster)")
        print("  - backend.main.GPUMonitor")
        print("  - backend.main.CleanupService")
        print("\nExample fix - add patches to your fixture or test:\n")
        print(
            """  from unittest.mock import MagicMock, AsyncMock, patch

  @pytest.fixture
  def client():
      mock_broadcaster = MagicMock()
      mock_broadcaster.start_broadcasting = AsyncMock()
      mock_broadcaster.stop_broadcasting = AsyncMock()

      mock_gpu_monitor = MagicMock()
      mock_gpu_monitor.start = AsyncMock()
      mock_gpu_monitor.stop = AsyncMock()

      mock_cleanup_service = MagicMock()
      mock_cleanup_service.start = AsyncMock()
      mock_cleanup_service.stop = AsyncMock()

      with (
          patch('backend.main.get_system_broadcaster', return_value=mock_broadcaster),
          patch('backend.main.GPUMonitor', return_value=mock_gpu_monitor),
          patch('backend.main.CleanupService', return_value=mock_cleanup_service),
      ):
          with TestClient(app) as client:
              yield client"""
        )
        print("\n" + "=" * 80)
        return 1

    # Success - only print if running standalone (not in pre-commit)
    if len(sys.argv) < 2:
        print("All integration tests properly mock background services.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
