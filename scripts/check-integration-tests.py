#!/usr/bin/env python3
"""Pre-commit hook to remind developers to add integration tests.

This script detects when API routes or services are added/modified without
corresponding integration tests and provides helpful guidance.

Integration tests are critical because they verify:
- Database interactions work correctly
- Service dependencies are properly wired
- External APIs are called with correct parameters
- Error handling works end-to-end

Usage:
    ./scripts/check-integration-tests.py [file1.py file2.py ...]
"""

import sys
from pathlib import Path

# Files that MUST have integration tests
INTEGRATION_TEST_REQUIRED = {
    "api/routes": "API route - must verify database and service interactions",
    "services": "Service - must verify external dependencies and error handling",
}

# File types that strongly benefit from integration tests (warning)
INTEGRATION_TEST_RECOMMENDED = {
    "core": "Core utilities - integration tests help verify impact across system",
}


def check_files_for_integration_tests(file_paths: list[str]) -> tuple[bool, list[str]]:
    """Check if files have integration tests.

    Args:
        file_paths: List of file paths to check

    Returns:
        Tuple of (all_have_tests, list_of_warnings)
    """
    project_root = Path(__file__).parent.parent
    warnings = []
    all_have_tests = True

    for file_path in file_paths:
        path = Path(file_path)

        # Resolve to absolute path if relative
        if not path.is_absolute():
            path = project_root / path

        # Only check Python files
        if path.suffix != ".py" or path.name.startswith("test_"):
            continue

        # Check if file requires integration tests
        requires_integration = False
        recommendation = None

        for pattern, reason in INTEGRATION_TEST_REQUIRED.items():
            if pattern in str(path):
                requires_integration = True
                recommendation = reason
                break

        if not requires_integration:
            for pattern, reason in INTEGRATION_TEST_RECOMMENDED.items():
                if pattern in str(path):
                    recommendation = reason
                    break

        if not recommendation:
            continue

        # Look for corresponding integration test
        relative_path = path.relative_to(project_root)
        test_paths = [
            project_root / "backend/tests/integration" / f"test_{path.name}",
            project_root
            / "backend/tests/integration"
            / relative_path.with_name(f"test_{path.name}"),
            project_root / "backend/tests/unit" / f"test_{path.name}",
            project_root / "backend/tests/unit" / relative_path.with_name(f"test_{path.name}"),
        ]

        has_test = any(test_path.exists() for test_path in test_paths)

        if not has_test:
            if requires_integration:
                all_have_tests = False
                warnings.append(f"ERROR: {relative_path} requires integration tests")
                warnings.append(f"  Reason: {recommendation}")
            else:
                warnings.append(f"HINT: Consider adding integration tests for {relative_path}")
                warnings.append(f"  Reason: {recommendation}")

    return all_have_tests, warnings


def print_integration_test_guide():
    """Print helpful guide for writing integration tests."""
    print("\n" + "=" * 80)
    print("INTEGRATION TEST GUIDE")
    print("=" * 80)

    print("""
Integration tests verify that components work together correctly, including:
  - Database queries and mutations
  - Service dependencies and their interactions
  - Error handling across multiple components
  - Real-world usage patterns

Key differences from unit tests:
  - Unit tests: Mock all external dependencies
  - Integration tests: Use real database (test database), mock only remote APIs
  - Integration tests: Verify data persistence and querying
  - Integration tests: Check service-to-service communication

Example structure for API route integration test:

    @pytest.mark.integration
    class TestCamerasIntegration:
        '''Integration tests for cameras API.'''

        @pytest.mark.asyncio
        async def test_create_camera_persists_to_database(
            self, async_client: AsyncClient, db_session: Session
        ):
            '''Verify creating camera through API saves to database.'''
            # Call API endpoint
            response = await async_client.post(
                "/api/cameras",
                json={"name": "front_door", "rtsp_url": "rtsp://..."}
            )

            # Verify API response
            assert response.status_code == 201
            camera_data = response.json()

            # Verify data was persisted (this is what makes it "integration")
            persisted = db_session.query(Camera).filter_by(
                id=camera_data["id"]
            ).first()
            assert persisted is not None
            assert persisted.name == "front_door"

Test file structure:
  - backend/tests/integration/test_<module_name>.py
  - Use @pytest.mark.integration decorator
  - Use async_client fixture for API tests
  - Use db_session fixture for database verification
  - Keep test database clean with pytest fixtures

Running integration tests locally:
  uv run pytest backend/tests/integration/ -v

Fixtures available (from conftest.py):
  - async_client: FastAPI TestClient for API calls
  - db_session: SQLAlchemy session for database access
  - redis: Redis connection
  - Any other project-specific fixtures

Required mocks for integration tests:
  - External APIs (Slack, email, etc.)
  - Third-party services
  - Rate-limited services
  - Do NOT mock database or core services
""")
    print("=" * 80)


def main() -> int:
    """Main entry point.

    Returns:
        0 if no errors, 1 if integration tests are required but missing
    """
    # Get files from pre-commit
    files = sys.argv[1:] if len(sys.argv) > 1 else []

    if not files:
        # No files provided, skip
        return 0

    passed, warnings = check_files_for_integration_tests(files)

    if warnings:
        print("\n" + "=" * 80)
        print("INTEGRATION TEST REMINDER")
        print("=" * 80)
        for warning in warnings:
            print(f"  {warning}")

        has_errors = not passed
        if has_errors:
            print("\n⚠️  FAILED: Some files require integration tests but don't have them")
            print_integration_test_guide()
            print("\nTo skip this check (emergency only):")
            print("  SKIP=check-integration-tests git commit")
            return 1
        else:
            print("\n💡 HINT: These files would benefit from integration tests")
            print("   (This is a warning, not an error)")
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
