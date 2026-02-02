"""Unit tests for Alembic migration idempotency.

Tests verify that:
1. ENUM type creations use IF NOT EXISTS or equivalent (NEM-5029)
2. Migrations can be run multiple times without errors

These tests only read files and don't need database connections.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Get the path to the alembic directory relative to this test file
# mutants/backend/tests/unit/core/test_alembic_migrations.py -> mutants/backend/alembic/
_test_file_path = Path(__file__).resolve()
backend_path = _test_file_path.parent.parent.parent.parent  # mutants/backend


@pytest.fixture(autouse=True)
def disable_settings_cache_fixture(request: pytest.FixtureRequest) -> None:
    """Disable the reset_settings_cache autouse fixture for these tests.

    These tests only read files and don't need database/settings setup.
    """
    # This fixture shadows the autouse fixture from conftest.py
    pass


class TestEnumTypeIdempotency:
    """Tests for idempotent ENUM type creation in migrations (NEM-5029)."""

    @pytest.fixture
    def migrations_dir(self) -> Path:
        """Get the path to alembic migrations directory."""
        return backend_path / "alembic" / "versions"

    @pytest.fixture
    def migration_files(self, migrations_dir: Path) -> list[Path]:
        """Get all migration files."""
        return list(migrations_dir.glob("*.py"))

    def test_migrations_directory_exists(self, migrations_dir: Path) -> None:
        """Test that migrations directory exists."""
        assert migrations_dir.exists(), f"Migrations directory not found at {migrations_dir}"

    def test_no_raw_create_type_enum_statements(  # noqa: PLR0912
        self, migrations_dir: Path, migration_files: list[Path]
    ) -> None:
        """Test that migrations don't use raw CREATE TYPE ... AS ENUM without idempotency.

        Raw CREATE TYPE statements will fail if the type already exists.
        Migrations should use one of:
        1. DO $$ BEGIN ... EXCEPTION WHEN duplicate_object THEN null; END $$;
        2. CREATE TYPE IF NOT EXISTS (PostgreSQL 9.1+)
        3. SQLAlchemy ENUM with create_type=True and checkfirst=True
        """
        # Pattern to find raw CREATE TYPE ... AS ENUM without exception handling
        raw_create_pattern = re.compile(
            r'op\.execute\s*\(\s*["\']CREATE TYPE\s+\w+\s+AS\s+ENUM',
            re.IGNORECASE,
        )

        # Pattern for idempotent version with exception handling
        idempotent_pattern = re.compile(
            r"DO\s+\$\$\s+BEGIN\s+CREATE TYPE.*EXCEPTION\s+WHEN\s+duplicate_object",
            re.IGNORECASE | re.DOTALL,
        )

        violations: list[tuple[str, int, str]] = []

        for migration_file in migration_files:
            if migration_file.name == "__init__.py" or migration_file.suffix != ".py":
                continue

            # Skip AGENTS.md and other non-migration files
            if not migration_file.name.endswith(".py"):
                continue

            content = migration_file.read_text()

            # Find all CREATE TYPE statements
            for match in raw_create_pattern.finditer(content):
                line_start = content.rfind("\n", 0, match.start()) + 1
                line_num = content[: match.start()].count("\n") + 1
                line = content[line_start : content.find("\n", match.end())]

                # Check if this is actually within an idempotent DO block
                # Look for the full statement context
                stmt_start = content.rfind("op.execute", 0, match.start())
                if stmt_start == -1:
                    stmt_start = match.start()

                # Find the end of the statement (closing parenthesis)
                paren_count = 0
                stmt_end = stmt_start
                in_string = False
                string_char = None

                for i, char in enumerate(content[stmt_start:], start=stmt_start):
                    if char in "\"'":
                        if not in_string:
                            in_string = True
                            string_char = char
                        elif char == string_char:
                            in_string = False
                    elif not in_string:
                        if char == "(":
                            paren_count += 1
                        elif char == ")":
                            paren_count -= 1
                            if paren_count == 0:
                                stmt_end = i + 1
                                break

                full_stmt = content[stmt_start:stmt_end]

                # Check if the statement includes idempotent handling
                if not idempotent_pattern.search(full_stmt):
                    violations.append((migration_file.name, line_num, line.strip()))

        if violations:
            msg_parts = [
                "Found non-idempotent CREATE TYPE ENUM statements in migrations:",
                "",
                "These statements will fail if run twice. Fix by wrapping in exception handler:",
                "",
                '  op.execute("DO $$ BEGIN CREATE TYPE my_enum AS ENUM (...); '
                'EXCEPTION WHEN duplicate_object THEN null; END $$;")',
                "",
                "Violations found:",
            ]
            for filename, line_num, line in violations:
                msg_parts.append(f"  - {filename}:{line_num}: {line[:80]}...")

            pytest.fail("\n".join(msg_parts))

    def test_alerts_migration_enum_types_are_idempotent(self, migrations_dir: Path) -> None:
        """Test specifically that add_alerts_and_alert_rules migration has idempotent ENUMs.

        This migration creates alert_severity and alert_status enum types and must
        handle the case where these types already exist.
        """
        alerts_migration = migrations_dir / "add_alerts_and_alert_rules.py"
        if not alerts_migration.exists():
            pytest.skip("add_alerts_and_alert_rules.py migration not found")

        content = alerts_migration.read_text()

        # Check for alert_severity enum
        if "alert_severity" in content.lower():
            # Must use idempotent creation
            assert ("DO $$" in content and "EXCEPTION WHEN duplicate_object" in content) or (
                "IF NOT EXISTS" in content.upper()
            ), (
                "alert_severity enum creation must be idempotent. "
                "Use DO $$ BEGIN ... EXCEPTION WHEN duplicate_object THEN null; END $$;"
            )

        # Check for alert_status enum
        if "alert_status" in content.lower():
            assert ("DO $$" in content and "EXCEPTION WHEN duplicate_object" in content) or (
                "IF NOT EXISTS" in content.upper()
            ), (
                "alert_status enum creation must be idempotent. "
                "Use DO $$ BEGIN ... EXCEPTION WHEN duplicate_object THEN null; END $$;"
            )


class TestMigrationDowngradeIdempotency:
    """Tests for idempotent ENUM type drops in migration downgrades."""

    @pytest.fixture
    def migrations_dir(self) -> Path:
        """Get the path to alembic migrations directory."""
        return backend_path / "alembic" / "versions"

    def test_downgrade_uses_if_exists_for_enum_drops(self, migrations_dir: Path) -> None:
        """Test that downgrade functions use DROP TYPE IF EXISTS.

        This ensures downgrades are idempotent and won't fail if the type
        was already dropped.
        """
        # Pattern for DROP TYPE without IF EXISTS
        raw_drop_pattern = re.compile(
            r'op\.execute\s*\(\s*["\']DROP TYPE\s+(?!IF EXISTS)',
            re.IGNORECASE,
        )

        violations: list[tuple[str, int, str]] = []

        for migration_file in migrations_dir.glob("*.py"):
            if migration_file.name == "__init__.py":
                continue

            content = migration_file.read_text()

            # Only check downgrade functions
            downgrade_match = re.search(
                r"def downgrade\(\).*?(?=\ndef |\Z)",
                content,
                re.DOTALL,
            )

            if not downgrade_match:
                continue

            downgrade_content = downgrade_match.group()

            for match in raw_drop_pattern.finditer(downgrade_content):
                line_start = downgrade_content.rfind("\n", 0, match.start()) + 1
                line_num = (
                    content[: content.find(downgrade_content) + match.start()].count("\n") + 1
                )
                line = downgrade_content[line_start : downgrade_content.find("\n", match.end())]

                # Skip if it's already using IF EXISTS
                if "IF EXISTS" in line.upper():
                    continue

                violations.append((migration_file.name, line_num, line.strip()))

        # This is informational - existing migrations already use IF EXISTS in downgrade
        # But we want to ensure new migrations follow this pattern
        if violations:
            msg_parts = [
                "Found DROP TYPE statements without IF EXISTS in downgrade functions:",
                "",
                "These should use: DROP TYPE IF EXISTS to be idempotent.",
                "",
                "Violations found:",
            ]
            for filename, line_num, line in violations:
                msg_parts.append(f"  - {filename}:{line_num}: {line[:80]}...")

            pytest.fail("\n".join(msg_parts))
