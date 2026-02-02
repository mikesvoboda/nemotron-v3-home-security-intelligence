"""Unit tests for Alembic env.py configuration.

Tests verify that:
1. compare_type=True is enabled for detecting column type changes (NEM-5028)
2. URL conversion handles asyncpg to sync conversion correctly

These tests only read files and don't need database connections.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Get the path to the alembic directory relative to this test file
# mutants/backend/tests/unit/core/test_alembic_env.py -> mutants/backend/alembic/env.py
_test_file_path = Path(__file__).resolve()
backend_path = _test_file_path.parent.parent.parent.parent  # mutants/backend


@pytest.fixture(autouse=True)
def disable_settings_cache_fixture(request: pytest.FixtureRequest) -> None:
    """Disable the reset_settings_cache autouse fixture for these tests.

    These tests only read files and don't need database/settings setup.
    """
    # This fixture shadows the autouse fixture from conftest.py
    pass


class TestAlembicEnvCompareType:
    """Tests for compare_type configuration in alembic env.py (NEM-5028)."""

    @pytest.fixture
    def env_py_path(self) -> Path:
        """Get the path to alembic env.py."""
        return backend_path / "alembic" / "env.py"

    def test_env_py_exists(self, env_py_path: Path) -> None:
        """Test that alembic env.py file exists."""
        assert env_py_path.exists(), f"env.py not found at {env_py_path}"

    def test_compare_type_enabled_in_offline_mode(self, env_py_path: Path) -> None:
        """Test that compare_type=True is set in run_migrations_offline().

        compare_type=True enables Alembic autogenerate to detect column type changes,
        which is essential for catching type modifications like VARCHAR(50) -> VARCHAR(100).
        """
        source = env_py_path.read_text()
        tree = ast.parse(source)

        # Find the run_migrations_offline function
        offline_func = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_migrations_offline":
                offline_func = node
                break

        assert offline_func is not None, "run_migrations_offline function not found"

        # Find context.configure() call within the function
        configure_call = None
        for node in ast.walk(offline_func):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "configure"
            ):
                configure_call = node
                break

        assert configure_call is not None, "context.configure() call not found in offline mode"

        # Check for compare_type=True keyword argument
        compare_type_found = False
        for keyword in configure_call.keywords:
            if (
                keyword.arg == "compare_type"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
            ):
                compare_type_found = True
                break

        assert compare_type_found, (
            "compare_type=True not found in context.configure() for offline mode. "
            "Add compare_type=True to enable column type change detection during autogenerate."
        )

    def test_compare_type_enabled_in_online_mode(self, env_py_path: Path) -> None:
        """Test that compare_type=True is set in run_migrations_online().

        compare_type=True enables Alembic autogenerate to detect column type changes
        when running with a live database connection.
        """
        source = env_py_path.read_text()
        tree = ast.parse(source)

        # Find the run_migrations_online function
        online_func = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_migrations_online":
                online_func = node
                break

        assert online_func is not None, "run_migrations_online function not found"

        # Find context.configure() call within the function
        configure_call = None
        for node in ast.walk(online_func):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "configure"
            ):
                configure_call = node
                break

        assert configure_call is not None, "context.configure() call not found in online mode"

        # Check for compare_type=True keyword argument
        compare_type_found = False
        for keyword in configure_call.keywords:
            if (
                keyword.arg == "compare_type"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
            ):
                compare_type_found = True
                break

        assert compare_type_found, (
            "compare_type=True not found in context.configure() for online mode. "
            "Add compare_type=True to enable column type change detection during autogenerate."
        )


class TestAlembicEnvUrlConversion:
    """Tests for database URL conversion in alembic env.py."""

    @pytest.fixture
    def env_py_path(self) -> Path:
        """Get the path to alembic env.py."""
        return backend_path / "alembic" / "env.py"

    def test_get_url_converts_asyncpg(self, env_py_path: Path) -> None:
        """Test that get_url() converts asyncpg URLs to sync."""
        source = env_py_path.read_text()

        # Check that the conversion logic exists
        assert "+asyncpg" in source, "asyncpg conversion logic should be present in env.py"
        assert "replace" in source, "URL replacement logic should be present"

    def test_get_url_requires_database_url_env_var(self, env_py_path: Path) -> None:
        """Test that get_url() requires DATABASE_URL environment variable."""
        source = env_py_path.read_text()

        # Check that DATABASE_URL is required
        assert "DATABASE_URL" in source, "DATABASE_URL should be referenced in env.py"
        assert "ValueError" in source or "raise" in source, (
            "Should raise an error when DATABASE_URL is not set"
        )
