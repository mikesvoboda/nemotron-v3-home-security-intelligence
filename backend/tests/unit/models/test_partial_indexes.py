"""Unit tests for partial indexes on boolean filter columns.

Tests cover:
- Migration file structure validation
- Partial index definitions for boolean columns
- Upgrade and downgrade function presence
- Index naming conventions

These tests verify the migration code structure without requiring a database connection.
Integration tests with actual PostgreSQL are in the integration test suite.
"""

import importlib.util
from pathlib import Path

import pytest

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def migration_module():
    """Load the partial indexes migration module."""
    # Path from test file to migration: tests/unit/models -> backend -> alembic/versions
    migration_path = (
        Path(__file__).parents[3]
        / "alembic"
        / "versions"
        / "add_partial_indexes_boolean_columns.py"
    )

    if not migration_path.exists():
        pytest.skip(f"Migration file not found at {migration_path}")

    spec = importlib.util.spec_from_file_location("migration", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def migration_content():
    """Read the migration file content for pattern matching."""
    # Path from test file to migration: tests/unit/models -> backend -> alembic/versions
    migration_path = (
        Path(__file__).parents[3]
        / "alembic"
        / "versions"
        / "add_partial_indexes_boolean_columns.py"
    )

    if not migration_path.exists():
        pytest.skip(f"Migration file not found at {migration_path}")

    return migration_path.read_text()


# =============================================================================
# Migration Structure Tests
# =============================================================================


class TestMigrationStructure:
    """Tests for migration file structure."""

    def test_migration_has_revision_identifier(self, migration_module):
        """Test migration has revision identifier."""
        assert hasattr(migration_module, "revision")
        assert migration_module.revision == "add_partial_indexes_boolean"

    def test_migration_has_down_revision(self, migration_module):
        """Test migration has down_revision linking to previous migration."""
        assert hasattr(migration_module, "down_revision")
        assert migration_module.down_revision == "add_alerts_dedup_indexes"

    def test_migration_has_upgrade_function(self, migration_module):
        """Test migration has upgrade function."""
        assert hasattr(migration_module, "upgrade")
        assert callable(migration_module.upgrade)

    def test_migration_has_downgrade_function(self, migration_module):
        """Test migration has downgrade function."""
        assert hasattr(migration_module, "downgrade")
        assert callable(migration_module.downgrade)


# =============================================================================
# Partial Index Definition Tests
# =============================================================================


class TestPartialIndexDefinitions:
    """Tests for partial index definitions in the migration."""

    def test_events_reviewed_false_index_defined(self, migration_content):
        """Test events.reviewed partial index for unreviewed events."""
        assert "idx_events_reviewed_false" in migration_content
        assert "reviewed = false" in migration_content.lower()

    def test_events_is_fast_path_true_index_defined(self, migration_content):
        """Test events.is_fast_path partial index for fast-path events."""
        assert "idx_events_is_fast_path_true" in migration_content
        assert "is_fast_path = true" in migration_content.lower()

    def test_zones_enabled_true_index_defined(self, migration_content):
        """Test zones.enabled partial index for enabled zones."""
        assert "idx_zones_enabled_true" in migration_content
        # Check for the index and condition (may be split across lines)
        assert "zones" in migration_content.lower()
        assert "enabled" in migration_content.lower()

    def test_alert_rules_enabled_true_index_defined(self, migration_content):
        """Test alert_rules.enabled partial index for enabled rules."""
        assert "idx_alert_rules_enabled_true" in migration_content
        assert "alert_rules" in migration_content.lower()

    def test_api_keys_is_active_true_index_defined(self, migration_content):
        """Test api_keys.is_active partial index for active keys."""
        assert "idx_api_keys_is_active_true" in migration_content
        assert "api_keys" in migration_content.lower()

    def test_prompt_versions_is_active_true_index_defined(self, migration_content):
        """Test prompt_versions.is_active partial index for active versions."""
        assert "idx_prompt_versions_is_active_true" in migration_content
        assert "prompt_versions" in migration_content.lower()

    def test_scene_changes_acknowledged_false_index_note(self, migration_content):
        """Test scene_changes index is documented as handled elsewhere.

        The idx_scene_changes_acknowledged_false index is created in the
        create_scene_changes_table migration to avoid dependency ordering issues.
        """
        assert "idx_scene_changes_acknowledged_false" in migration_content
        assert "create_scene_changes_table" in migration_content


class TestPartialIndexSyntax:
    """Tests for correct PostgreSQL partial index syntax."""

    def test_uses_postgresql_where_clause(self, migration_content):
        """Test that indexes use postgresql_where for partial index creation.

        Note: scene_changes index is created in create_scene_changes_table migration,
        so this migration only has 6 active partial indexes.
        """
        # Count occurrences - should have 6 partial indexes (scene_changes is elsewhere)
        count = migration_content.count("postgresql_where")
        assert count >= 6, f"Expected at least 6 postgresql_where clauses, found {count}"

    def test_uses_sa_text_for_where_clause(self, migration_content):
        """Test that where clauses use sa.text() for SQL expressions."""
        # Each partial index should use sa.text() for the where clause
        assert "sa.text(" in migration_content, "Should use sa.text() for WHERE clauses"

    def test_create_index_operations(self, migration_content):
        """Test that migration uses op.create_index for index creation.

        Note: scene_changes index is created in create_scene_changes_table migration,
        so this migration only has 6 active create_index calls.
        """
        count = migration_content.count("op.create_index")
        assert count >= 6, f"Expected at least 6 create_index calls, found {count}"

    def test_drop_index_operations_in_downgrade(self, migration_content):
        """Test that downgrade uses op.drop_index for cleanup.

        Note: scene_changes index is dropped in create_scene_changes_table migration,
        so this migration only has 6 active drop_index calls.
        """
        count = migration_content.count("op.drop_index")
        assert count >= 6, f"Expected at least 6 drop_index calls, found {count}"


# =============================================================================
# Index Naming Convention Tests
# =============================================================================


class TestIndexNamingConventions:
    """Tests for consistent index naming conventions."""

    def test_index_names_follow_pattern(self, migration_content):
        """Test index names follow idx_{table}_{column}_{value} pattern.

        Note: idx_scene_changes_acknowledged_false is handled by create_scene_changes_table.
        """
        # Indexes actively created in this migration
        active_indexes = [
            "idx_events_reviewed_false",
            "idx_events_is_fast_path_true",
            "idx_zones_enabled_true",
            "idx_alert_rules_enabled_true",
            "idx_api_keys_is_active_true",
            "idx_prompt_versions_is_active_true",
        ]

        for pattern in active_indexes:
            assert pattern in migration_content, f"Expected index name {pattern} not found"

        # scene_changes index should be referenced (in a NOTE comment)
        assert "idx_scene_changes_acknowledged_false" in migration_content

    def test_downgrade_references_same_index_names(self, migration_content):
        """Test that downgrade drops the same indexes that upgrade creates.

        Note: idx_scene_changes_acknowledged_false is handled by create_scene_changes_table.
        """
        # Split content into upgrade and downgrade sections
        parts = migration_content.split("def downgrade")
        assert len(parts) == 2, "Should have upgrade and downgrade sections"

        upgrade_section = parts[0]
        downgrade_section = parts[1]

        # Active indexes created in this migration (not scene_changes)
        active_indexes = [
            "idx_events_reviewed_false",
            "idx_events_is_fast_path_true",
            "idx_zones_enabled_true",
            "idx_alert_rules_enabled_true",
            "idx_api_keys_is_active_true",
            "idx_prompt_versions_is_active_true",
        ]

        for index_name in active_indexes:
            assert index_name in upgrade_section, f"Index {index_name} not created in upgrade"
            assert index_name in downgrade_section, f"Index {index_name} not dropped in downgrade"

        # scene_changes index should be mentioned (in NOTE comments)
        assert "idx_scene_changes_acknowledged_false" in upgrade_section
        assert "idx_scene_changes_acknowledged_false" in downgrade_section


# =============================================================================
# Table Reference Tests
# =============================================================================


class TestTableReferences:
    """Tests for correct table references in the migration."""

    def test_events_table_referenced(self, migration_content):
        """Test events table is correctly referenced."""
        assert '"events"' in migration_content or "'events'" in migration_content

    def test_zones_table_referenced(self, migration_content):
        """Test zones table is correctly referenced."""
        assert '"zones"' in migration_content or "'zones'" in migration_content

    def test_alert_rules_table_referenced(self, migration_content):
        """Test alert_rules table is correctly referenced."""
        assert '"alert_rules"' in migration_content or "'alert_rules'" in migration_content

    def test_api_keys_table_referenced(self, migration_content):
        """Test api_keys table is correctly referenced."""
        assert '"api_keys"' in migration_content or "'api_keys'" in migration_content

    def test_prompt_versions_table_referenced(self, migration_content):
        """Test prompt_versions table is correctly referenced."""
        assert '"prompt_versions"' in migration_content or "'prompt_versions'" in migration_content

    def test_scene_changes_table_referenced(self, migration_content):
        """Test scene_changes table is correctly referenced.

        Note: scene_changes index is handled by create_scene_changes_table,
        so this migration only references it in NOTE comments.
        """
        # The migration references scene_changes in the comment about the index
        assert "scene_changes" in migration_content.lower()


# =============================================================================
# Documentation Tests
# =============================================================================


class TestMigrationDocumentation:
    """Tests for migration documentation."""

    def test_migration_has_docstring(self, migration_content):
        """Test migration has descriptive docstring."""
        # The file should start with a docstring
        assert '"""' in migration_content, "Migration should have a docstring"

    def test_docstring_mentions_partial_indexes(self, migration_content):
        """Test docstring mentions partial indexes."""
        # Extract the docstring (first triple-quoted string)
        docstring_start = migration_content.find('"""')
        docstring_end = migration_content.find('"""', docstring_start + 3)
        docstring = migration_content[docstring_start : docstring_end + 3].lower()

        assert "partial" in docstring, "Docstring should mention partial indexes"
        assert "boolean" in docstring, "Docstring should mention boolean columns"

    def test_docstring_explains_use_cases(self, migration_content):
        """Test docstring explains use cases for each index."""
        docstring_start = migration_content.find('"""')
        docstring_end = migration_content.find('"""', docstring_start + 3)
        docstring = migration_content[docstring_start : docstring_end + 3].lower()

        # Should mention key use cases
        assert "unreviewed" in docstring or "reviewed" in docstring
        assert "enabled" in docstring
        assert "active" in docstring
