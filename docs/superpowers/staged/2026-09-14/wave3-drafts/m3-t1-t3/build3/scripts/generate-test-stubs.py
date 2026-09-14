#!/usr/bin/env python3
"""Auto-generate test stub files for new source files.

This script generates skeleton test files with proper structure and patterns
for new backend and frontend files. The generated stubs follow project conventions
and include docstrings and example test cases.

Usage:
    ./scripts/generate-test-stubs.py path/to/new_file.py
    ./scripts/generate-test-stubs.py path/to/component.tsx --frontend
"""

import sys
from pathlib import Path


def generate_backend_test_stub(source_file: Path) -> str:
    """Generate a pytest test stub for a backend Python file.

    Args:
        source_file: Path to the source file (relative to project root)

    Returns:
        Generated test file content
    """
    # Extract module name
    module_name = source_file.stem
    module_path = ".".join(source_file.with_suffix("").parts)

    # Determine file type based on location
    if "api/routes" in str(source_file):
        return generate_api_route_test(module_name, module_path)
    elif "services" in str(source_file):
        return generate_service_test(module_name, module_path)
    elif "models" in str(source_file):
        return generate_model_test(module_name, module_path)
    else:
        return generate_generic_backend_test(module_name, module_path)


def generate_api_route_test(module_name: str, _module_path: str) -> str:
    """Generate test stub for an API route module."""
    return f'''"""Tests for {module_name} API routes.

This module contains unit and integration tests for the {module_name} endpoints.
Tests follow the pattern:
- Unit tests: mock external dependencies (DB, external APIs)
- Integration tests: use test database and services
- Coverage requirement: 95% (API routes are critical)
"""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

from backend.main import app


class Test{module_name.title()}Routes:
    """Test cases for {module_name} routes."""

    @pytest.mark.asyncio
    async def test_route_returns_success(self, async_client: AsyncClient):
        """Test that [route_name] returns successful response.

        RED: Write this test first to define the expected behavior.
        """
        # TODO: Replace with actual endpoint and assertion
        response = await async_client.get("/api/{module_name}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_route_handles_error_gracefully(self, async_client: AsyncClient):
        """Test that [route_name] handles errors appropriately.

        GREEN: Make this test pass with proper error handling.
        """
        # TODO: Test error cases (404, 400, 500)
        response = await async_client.get("/api/{module_name}/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data or "error" in data


@pytest.mark.integration
class Test{module_name.title()}Integration:
    """Integration tests for {module_name} - requires database."""

    @pytest.mark.asyncio
    async def test_create_resource(self, async_client: AsyncClient, db_session):
        """Integration test: create and retrieve resource."""
        # TODO: Test full flow with real database
        pass

    @pytest.mark.asyncio
    async def test_update_resource(self, async_client: AsyncClient, db_session):
        """Integration test: update existing resource."""
        # TODO: Test update operations
        pass

    @pytest.mark.asyncio
    async def test_delete_resource(self, async_client: AsyncClient, db_session):
        """Integration test: delete resource."""
        # TODO: Test deletion
        pass
'''


def generate_service_test(module_name: str, _module_path: str) -> str:
    """Generate test stub for a service module."""
    return f'''"""Tests for {module_name} service.

Service layer tests focus on business logic and external dependencies.
Coverage requirement: 90%
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.{module_name} import {module_name.title().replace("_", "")}


class Test{module_name.title().replace("_", "")}:
    """Unit tests for {module_name} service."""

    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        # TODO: Initialize service with mocked dependencies
        return {module_name.title().replace("_", "")}()

    @pytest.mark.asyncio
    async def test_core_functionality(self, service):
        """Test the primary business logic.

        RED: Write test first to define expected behavior.
        """
        # TODO: Test main functionality
        pass

    @pytest.mark.asyncio
    async def test_handles_external_service_failure(self, service):
        """Test graceful degradation when external service fails."""
        # TODO: Mock external service failure and verify handling
        pass

    @pytest.mark.asyncio
    async def test_validates_input(self, service):
        """Test input validation."""
        # TODO: Test with invalid inputs
        pass


@pytest.mark.integration
class Test{module_name.title().replace("_", "")}Integration:
    """Integration tests for {module_name} service."""

    @pytest.mark.asyncio
    async def test_integration_with_database(self):
        """Test service with real database."""
        # TODO: Integration test with actual DB
        pass
'''


def generate_model_test(module_name: str, _module_path: str) -> str:
    """Generate test stub for a SQLAlchemy model module."""
    return f'''"""Tests for {module_name} ORM models.

Model tests verify:
- Relationships and constraints
- Cascading operations
- Database integrity
Coverage requirement: 85%
"""

import pytest
from sqlalchemy.orm import Session

from backend.models.{module_name} import *  # noqa: F401, F403


class Test{module_name.title().replace("_", "")}Model:
    """Unit tests for {module_name} ORM models."""

    def test_model_initialization(self):
        """Test creating model instance."""
        # TODO: Test model initialization with required fields
        pass

    def test_model_relationships(self, db_session: Session):
        """Test foreign key relationships."""
        # TODO: Test model relationships (one-to-many, many-to-many, etc.)
        pass

    def test_model_constraints(self, db_session: Session):
        """Test database constraints."""
        # TODO: Test NOT NULL, UNIQUE, FOREIGN KEY constraints
        pass

    def test_model_cascade_delete(self, db_session: Session):
        """Test cascading deletes work correctly."""
        # TODO: Verify cascade behavior
        pass


@pytest.mark.integration
class Test{module_name.title().replace("_", "")}Integration:
    """Integration tests for {module_name} models with database."""

    def test_persist_and_retrieve(self, db_session: Session):
        """Test persisting model to database and retrieving it."""
        # TODO: Create, save, and retrieve model
        pass

    def test_query_filtering(self, db_session: Session):
        """Test filtering queries."""
        # TODO: Test various filter conditions
        pass
'''


def generate_generic_backend_test(module_name: str, module_path: str) -> str:
    """Generate generic test stub for backend module."""
    return f'''"""Tests for {module_name} module.

This module contains tests for {module_path}.
"""

import pytest
from unittest.mock import patch, MagicMock

# TODO: Import the module under test
# from {module_path} import ...


class Test{module_name.title().replace("_", "")}:
    """Test cases for {module_name}."""

    def test_basic_functionality(self):
        """Test basic module functionality.

        RED: Write this test first to define behavior.
        """
        # TODO: Implement test
        pass

    def test_error_handling(self):
        """Test error handling."""
        # TODO: Test error cases
        pass

    @pytest.mark.asyncio
    async def test_async_functionality(self):
        """Test async functions if applicable."""
        # TODO: Test async behavior
        pass
'''


def generate_frontend_test_stub(source_file: Path) -> str:
    """Generate a Vitest test stub for a frontend file.

    Args:
        source_file: Path to the source file (relative to project root)

    Returns:
        Generated test file content
    """
    module_name = source_file.stem
    module_type = "component" if source_file.suffix == ".tsx" else "utility"

    if "components" in str(source_file):
        return generate_component_test(module_name)
    elif "hooks" in str(source_file):
        return generate_hook_test(module_name)
    else:
        return generate_generic_frontend_test(module_name, module_type)


def generate_component_test(component_name: str) -> str:
    """Generate test stub for a React component."""
    return f'''"""Tests for {component_name} component.

Component tests verify:
- Rendering with various props
- User interactions
- State changes
- Accessibility
Coverage requirement: 80%+ (statements/branches/functions/lines)
"""

import {{'  render, screen, fireEvent }} from '@testing-library/react';
import {{ describe, it, expect, beforeEach, vi }} from 'vitest';
import {{ {component_name} }} from './{component_name}';


describe('{component_name}', () => {{
  let mockProps: any;

  beforeEach(() => {{
    // TODO: Set up default props
    mockProps = {{
      // TODO: Add required props
    }};
  }});

  it('renders without crashing', () => {{
    render(<{component_name} {{...mockProps}} />);
    // TODO: Add specific assertions
  }});

  it('renders with custom props', () => {{
    render(<{component_name} {{...mockProps}} />);
    // TODO: Verify prop values are used
  }});

  it('handles user interactions', async () => {{
    render(<{component_name} {{...mockProps}} />);
    // TODO: Simulate user interactions (click, input, etc.)
  }});

  it('updates state on prop changes', () => {{
    const {{ rerender }} = render(<{component_name} {{...mockProps}} />);
    // TODO: Change props and verify re-render
    rerender(<{component_name} {{...mockProps}} />);
  }});

  it('is accessible', () => {{
    render(<{component_name} {{...mockProps}} />);
    // TODO: Check ARIA attributes and semantic HTML
    const element = screen.getByRole('button'); // or appropriate role
    expect(element).toBeInTheDocument();
  }});

  it('handles error states', () => {{
    // TODO: Test with error props
    render(<{component_name} {{...mockProps, error: true}} />);
  }});
}});
'''


def generate_hook_test(hook_name: str) -> str:
    """Generate test stub for a React hook."""
    return f'''"""Tests for {hook_name} hook.

Custom hook tests verify:
- Hook behavior with various inputs
- State and side-effect management
- Dependency array correctness
Coverage requirement: 80%+
"""

import {{ renderHook, act, waitFor }} from '@testing-library/react';
import {{ describe, it, expect, beforeEach, vi }} from 'vitest';
import {{ {hook_name} }} from './{hook_name}';


describe('{hook_name}', () => {{
  beforeEach(() => {{
    vi.clearAllMocks();
  }});

  it('initializes with default value', () => {{
    const {{ result }} = renderHook(() => {hook_name}());
    // TODO: Assert initial state
    expect(result.current).toBeDefined();
  }});

  it('updates state correctly', () => {{
    const {{ result }} = renderHook(() => {hook_name}());

    act(() => {{
      // TODO: Trigger state update
    }});

    // TODO: Assert state changed
  }});

  it('calls dependencies in useEffect', async () => {{
    const mockFn = vi.fn();
    const {{ result }} = renderHook(() => {hook_name}(mockFn));

    await waitFor(() => {{
      // TODO: Verify side effects
      expect(mockFn).toHaveBeenCalled();
    }});
  }});

  it('cleans up on unmount', () => {{
    const mockCleanup = vi.fn();
    const {{ unmount }} = renderHook(() => {hook_name}());

    unmount();

    // TODO: Verify cleanup was called
    expect(mockCleanup).toHaveBeenCalled();
  }});
}});
'''


def generate_generic_frontend_test(module_name: str, module_type: str) -> str:
    """Generate generic test stub for frontend module."""
    return f'''"""Tests for {module_name} {module_type}.

This module contains tests for {module_name}.
Coverage requirement: 80%+
"""

import {{ describe, it, expect, beforeEach, vi }} from 'vitest';
// TODO: Import module under test
// import {{ {module_name} }} from './{module_name}';


describe('{module_name}', () => {{
  beforeEach(() => {{
    vi.clearAllMocks();
  }});

  it('basic functionality', () => {{
    // TODO: Implement test
    expect(true).toBe(true);
  }});

  it('error handling', () => {{
    // TODO: Test error cases
  }});

  it('edge cases', () => {{
    // TODO: Test boundary conditions
  }});
}});
'''


def main() -> int:
    """Main entry point.

    Returns:
        0 on success, 1 on failure
    """
    if len(sys.argv) < 2:
        print("Usage: generate-test-stubs.py <source_file> [--frontend]")
        print("\nExamples:")
        print("  ./scripts/generate-test-stubs.py backend/services/detector.py")
        print("  ./scripts/generate-test-stubs.py frontend/src/components/Card.tsx")
        return 1

    source_path = sys.argv[1]
    is_frontend = "--frontend" in sys.argv

    # Convert to Path
    project_root = Path(__file__).parent.parent
    source_file = Path(source_path)

    if not source_file.is_absolute():
        source_file = project_root / source_file

    # Validate source file exists
    if not source_file.exists():
        print(f"Error: Source file not found: {source_path}")
        return 1

    # Determine test file path
    if is_frontend or source_file.suffix in [".tsx", ".ts"]:
        test_file = source_file.with_name(
            source_file.stem + ".test" + "".join(source_file.suffixes)
        )
        stub_content = generate_frontend_test_stub(source_file)
    else:
        # Backend file
        if "api/routes" in str(source_file):
            test_dir = source_file.parent.parent / "tests" / "integration"
        else:
            test_dir = source_file.parent.parent / "tests" / "unit"

        test_file = test_dir / f"test_{source_file.name}"
        stub_content = generate_backend_test_stub(source_file.relative_to(project_root))

    # Check if test file already exists
    if test_file.exists():
        print(f"Test file already exists: {test_file.relative_to(project_root)}")
        return 0

    # Create test directory if needed
    test_file.parent.mkdir(parents=True, exist_ok=True)

    # Write test stub
    test_file.write_text(stub_content)

    print(f"Generated test stub: {test_file.relative_to(project_root)}")
    print(f"TODO: Implement tests in {test_file.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
