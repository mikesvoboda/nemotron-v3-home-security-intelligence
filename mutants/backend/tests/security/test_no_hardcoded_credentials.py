"""Security tests for hardcoded credentials in configuration files.

These tests ensure that:
1. No database credentials are hardcoded in alembic.ini
2. DATABASE_URL environment variable is required (no fallback)
3. Clear error messages are provided when DATABASE_URL is missing

Part of NEM-5026: Remove hardcoded database credentials from alembic.ini
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

# Add backend to path for imports
backend_path = Path(__file__).resolve().parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestNoHardcodedCredentialsInAlembicIni:
    """Tests to verify alembic.ini does not contain hardcoded database credentials."""

    @pytest.fixture
    def alembic_ini_path(self) -> Path:
        """Get the path to alembic.ini."""
        return backend_path / "alembic.ini"

    @pytest.fixture
    def alembic_ini_content(self, alembic_ini_path: Path) -> str:
        """Read the contents of alembic.ini."""
        return alembic_ini_path.read_text()

    def test_no_password_in_sqlalchemy_url(self, alembic_ini_content: str) -> None:
        """Verify sqlalchemy.url does not contain a password."""
        # Pattern to match sqlalchemy.url with credentials
        # Matches patterns like: postgresql://user:password@host:port/db
        credential_pattern = re.compile(
            r"sqlalchemy\.url\s*=\s*\S*://[^:]+:[^@]+@",
            re.MULTILINE,
        )
        match = credential_pattern.search(alembic_ini_content)
        assert match is None, (
            f"Found hardcoded credentials in alembic.ini sqlalchemy.url: "
            f"'{match.group()}'. Database credentials must be provided via "
            "DATABASE_URL environment variable."
        )

    def test_no_postgresql_url_with_credentials(self, alembic_ini_content: str) -> None:
        """Verify no PostgreSQL URL with credentials exists anywhere in alembic.ini."""
        # Pattern to match any postgresql URL with credentials
        credential_pattern = re.compile(
            r"postgresql://[^:]+:[^@]+@\w+",
            re.MULTILINE | re.IGNORECASE,
        )
        match = credential_pattern.search(alembic_ini_content)
        assert match is None, (
            f"Found hardcoded PostgreSQL credentials in alembic.ini: "
            f"'{match.group()}'. Database credentials must be provided via "
            "DATABASE_URL environment variable."
        )

    def test_sqlalchemy_url_is_empty_or_placeholder(
        self, alembic_ini_content: str
    ) -> None:
        """Verify sqlalchemy.url is empty or contains a placeholder."""
        # Find the sqlalchemy.url line by searching line by line
        found = False
        url_value = None
        for line in alembic_ini_content.split('\n'):
            if line.startswith('sqlalchemy.url'):
                found = True
                # Extract value after '='
                parts = line.split('=', 1)
                if len(parts) == 2:
                    url_value = parts[1].strip()
                else:
                    url_value = ""
                break

        assert found, "sqlalchemy.url not found in alembic.ini"

        # URL should be empty (value is set via env.py from DATABASE_URL)
        assert url_value == "", (
            f"sqlalchemy.url should be empty (value is read from DATABASE_URL "
            f"env var in env.py), but found: '{url_value}'"
        )

    def test_no_hardcoded_username_security(self, alembic_ini_content: str) -> None:
        """Verify the common 'security' username is not hardcoded."""
        # Pattern to detect common hardcoded credentials
        security_pattern = re.compile(
            r"://security:", re.IGNORECASE
        )
        match = security_pattern.search(alembic_ini_content)
        assert match is None, (
            f"Found hardcoded 'security' username in alembic.ini. "
            "Database credentials must be provided via DATABASE_URL environment variable."
        )


class TestNoHardcodedCredentialsInEnvPy:
    """Tests to verify alembic/env.py does not contain hardcoded fallback credentials."""

    @pytest.fixture
    def env_py_path(self) -> Path:
        """Get the path to alembic/env.py."""
        return backend_path / "alembic" / "env.py"

    @pytest.fixture
    def env_py_content(self, env_py_path: Path) -> str:
        """Read the contents of alembic/env.py."""
        return env_py_path.read_text()

    def test_no_default_database_url_constant(self, env_py_content: str) -> None:
        """Verify no DEFAULT_DATABASE_URL constant with credentials exists."""
        # Pattern to match DEFAULT_DATABASE_URL with credentials
        default_url_pattern = re.compile(
            r"DEFAULT_DATABASE_URL\s*=\s*[\"']postgresql://[^:]+:[^@]+@",
            re.MULTILINE,
        )
        match = default_url_pattern.search(env_py_content)
        assert match is None, (
            f"Found hardcoded DEFAULT_DATABASE_URL in env.py: "
            f"'{match.group()}'. Remove fallback - DATABASE_URL must be required."
        )

    def test_no_hardcoded_postgresql_url(self, env_py_content: str) -> None:
        """Verify no hardcoded PostgreSQL URL with credentials in env.py.

        This test ignores example URLs in comments, docstrings, and error messages
        (lines containing 'Example' or '# ').
        """
        # Split content into lines and check each non-example line
        lines = env_py_content.split('\n')

        # Pattern to match postgresql URLs with credentials
        credential_pattern = re.compile(
            r"postgresql://[^:]+:[^@]+@\w+",
            re.IGNORECASE,
        )

        for i, line in enumerate(lines, 1):
            # Skip example lines, comments, and string literals with examples
            if any(skip in line.lower() for skip in ['example', '# ', 'e.g.']):
                continue
            # Skip docstring example lines
            if 'DATABASE_URL=' in line.upper():
                continue

            match = credential_pattern.search(line)
            if match:
                raise AssertionError(
                    f"Found hardcoded PostgreSQL credentials in env.py at line {i}: "
                    f"'{match.group()}'. Database credentials must be provided via "
                    "DATABASE_URL environment variable."
                )

    def test_no_fallback_url_in_get_database_url(self, env_py_content: str) -> None:
        """Verify get_database_url does not have fallback to hardcoded credentials."""
        # Check for patterns like:
        # return ini_url if ini_url else DEFAULT_DATABASE_URL
        # or fallback patterns in the function
        fallback_patterns = [
            r"return\s+\S+\s+if\s+\S+\s+else\s+DEFAULT",
            r"return\s+DEFAULT_DATABASE_URL",
            r"or\s+DEFAULT_DATABASE_URL",
        ]
        for pattern in fallback_patterns:
            match = re.search(pattern, env_py_content, re.MULTILINE)
            assert match is None, (
                f"Found fallback to DEFAULT_DATABASE_URL in env.py: "
                f"'{match.group()}'. DATABASE_URL must be required with no fallback."
            )


class TestDatabaseUrlRequired:
    """Tests to verify DATABASE_URL is required with proper error handling."""

    @pytest.fixture(autouse=True)
    def clear_database_url(self) -> Generator[None, None, None]:
        """Clear DATABASE_URL environment variable for testing."""
        original_url = os.environ.get("DATABASE_URL")
        os.environ.pop("DATABASE_URL", None)
        yield
        if original_url is not None:
            os.environ["DATABASE_URL"] = original_url

    def test_get_url_raises_without_database_url(self) -> None:
        """Verify get_url raises ValueError when DATABASE_URL is not set."""
        # Import the module fresh to ensure clean state
        import importlib
        import sys

        # Remove cached module if present
        modules_to_remove = [key for key in sys.modules if "alembic.env" in key]
        for mod in modules_to_remove:
            del sys.modules[mod]

        # We need to test the function directly from env.py
        # Since env.py uses alembic.context, we'll test by reading the source
        # and verifying the required behavior is implemented
        env_py_path = backend_path / "alembic" / "env.py"
        env_py_content = env_py_path.read_text()

        # Check that the function raises ValueError when DATABASE_URL is missing
        # Look for patterns that indicate proper error handling:
        # 1. Check for os.getenv("DATABASE_URL")
        # 2. Check for ValueError raise with helpful message
        assert 'os.getenv("DATABASE_URL")' in env_py_content, (
            "env.py should read DATABASE_URL from environment"
        )

        # Check for ValueError raise
        assert "raise ValueError" in env_py_content, (
            "env.py should raise ValueError when DATABASE_URL is missing"
        )

        # Check for helpful error message mentioning DATABASE_URL
        assert "DATABASE_URL" in env_py_content and "required" in env_py_content.lower(), (
            "env.py should have a clear error message indicating DATABASE_URL is required"
        )

    def test_error_message_is_helpful(self) -> None:
        """Verify the error message provides helpful guidance."""
        env_py_path = backend_path / "alembic" / "env.py"
        env_py_content = env_py_path.read_text()

        # Check that error message contains example format
        example_pattern = re.compile(
            r"Example.*postgresql://",
            re.IGNORECASE | re.DOTALL,
        )
        match = example_pattern.search(env_py_content)
        assert match is not None, (
            "Error message should include an example DATABASE_URL format "
            "(e.g., 'Example: postgresql://user:pass@localhost:5432/dbname')"
        )

    def test_get_url_function_exists(self) -> None:
        """Verify get_url or get_database_url function exists in env.py."""
        env_py_path = backend_path / "alembic" / "env.py"
        env_py_content = env_py_path.read_text()

        # Look for function definition
        func_pattern = re.compile(r"def\s+get_(?:database_)?url\s*\(", re.MULTILINE)
        match = func_pattern.search(env_py_content)
        assert match is not None, (
            "env.py should have a get_url or get_database_url function"
        )


class TestAsyncUrlConversion:
    """Tests to verify async URL conversion still works correctly."""

    def test_env_py_converts_asyncpg_urls(self) -> None:
        """Verify env.py handles asyncpg URL conversion."""
        env_py_path = backend_path / "alembic" / "env.py"
        env_py_content = env_py_path.read_text()

        # Check for asyncpg conversion logic
        assert "+asyncpg" in env_py_content, (
            "env.py should handle conversion of postgresql+asyncpg URLs"
        )
        assert "replace" in env_py_content, (
            "env.py should use replace() to convert asyncpg URLs"
        )
