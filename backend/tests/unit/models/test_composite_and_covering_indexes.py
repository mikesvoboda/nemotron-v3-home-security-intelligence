"""Unit tests for composite and covering indexes migrations.

Tests cover:
- Migration file structure validation for composite indexes (NEM-1491)
- Migration file structure validation for covering indexes (NEM-1497)
- Index definitions and naming conventions
- Upgrade and downgrade function presence
- PostgreSQL-specific INCLUDE clause usage for covering indexes

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
def composite_indexes_migration_module():
    """Load the composite indexes migration module."""
    # Path from test file to migration: tests/unit/models -> backend -> alembic/versions
    migration_path = (
        Path(__file__).parents[3] / "alembic" / "versions" / "add_composite_indexes_for_filters.py"
    )

    if not migration_path.exists():
        pytest.skip(f"Migration file not found at {migration_path}")

    spec = importlib.util.spec_from_file_location("migration", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def composite_indexes_migration_content():
    """Read the composite indexes migration file content for pattern matching."""
    # Path from test file to migration: tests/unit/models -> backend -> alembic/versions
    migration_path = (
        Path(__file__).parents[3] / "alembic" / "versions" / "add_composite_indexes_for_filters.py"
    )

    if not migration_path.exists():
        pytest.skip(f"Migration file not found at {migration_path}")

    return migration_path.read_text()


@pytest.fixture
def covering_indexes_migration_module():
    """Load the covering indexes migration module."""
    # Path from test file to migration: tests/unit/models -> backend -> alembic/versions
    migration_path = (
        Path(__file__).parents[3]
        / "alembic"
        / "versions"
        / "add_covering_indexes_for_pagination.py"
    )

    if not migration_path.exists():
        pytest.skip(f"Migration file not found at {migration_path}")

    spec = importlib.util.spec_from_file_location("migration", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def covering_indexes_migration_content():
    """Read the covering indexes migration file content for pattern matching."""
    # Path from test file to migration: tests/unit/models -> backend -> alembic/versions
    migration_path = (
        Path(__file__).parents[3]
        / "alembic"
        / "versions"
        / "add_covering_indexes_for_pagination.py"
    )

    if not migration_path.exists():
        pytest.skip(f"Migration file not found at {migration_path}")

    return migration_path.read_text()


# =============================================================================
# Composite Indexes Migration Structure Tests (NEM-1491)
# =============================================================================


class TestCompositeIndexesMigrationStructure:
    """Tests for composite indexes migration file structure."""

    def test_migration_has_revision_identifier(self, composite_indexes_migration_module):
        """Test migration has revision identifier."""
        assert hasattr(composite_indexes_migration_module, "revision")
        assert composite_indexes_migration_module.revision == "add_composite_indexes_filters"

    def test_migration_has_down_revision(self, composite_indexes_migration_module):
        """Test migration has down_revision linking to previous migration."""
        assert hasattr(composite_indexes_migration_module, "down_revision")
        assert (
            composite_indexes_migration_module.down_revision == "add_detections_camera_object_idx"
        )

    def test_migration_has_upgrade_function(self, composite_indexes_migration_module):
        """Test migration has upgrade function."""
        assert hasattr(composite_indexes_migration_module, "upgrade")
        assert callable(composite_indexes_migration_module.upgrade)

    def test_migration_has_downgrade_function(self, composite_indexes_migration_module):
        """Test migration has downgrade function."""
        assert hasattr(composite_indexes_migration_module, "downgrade")
        assert callable(composite_indexes_migration_module.downgrade)


class TestCompositeIndexDefinitions:
    """Tests for composite index definitions in the migration."""

    def test_events_camera_started_index_defined(self, composite_indexes_migration_content):
        """Test events camera + started_at composite index."""
        assert "idx_events_camera_started" in composite_indexes_migration_content
        assert '"camera_id"' in composite_indexes_migration_content
        assert '"started_at"' in composite_indexes_migration_content

    def test_events_camera_time_reviewed_index_defined(self, composite_indexes_migration_content):
        """Test events camera + time + reviewed composite index."""
        assert "idx_events_camera_time_reviewed" in composite_indexes_migration_content
        assert '"reviewed"' in composite_indexes_migration_content

    def test_detections_camera_time_type_index_defined(self, composite_indexes_migration_content):
        """Test detections camera + time + type composite index."""
        assert "idx_detections_camera_time_type" in composite_indexes_migration_content
        assert '"detected_at"' in composite_indexes_migration_content
        assert '"object_type"' in composite_indexes_migration_content

    def test_alerts_status_created_index_defined(self, composite_indexes_migration_content):
        """Test alerts status + created_at composite index."""
        assert "idx_alerts_status_created" in composite_indexes_migration_content
        assert '"status"' in composite_indexes_migration_content
        assert '"created_at"' in composite_indexes_migration_content

    def test_alerts_severity_created_index_defined(self, composite_indexes_migration_content):
        """Test alerts severity + created_at composite index."""
        assert "idx_alerts_severity_created" in composite_indexes_migration_content
        assert '"severity"' in composite_indexes_migration_content

    def test_logs_time_level_component_index_defined(self, composite_indexes_migration_content):
        """Test logs timestamp + level + component composite index."""
        assert "idx_logs_time_level_component" in composite_indexes_migration_content
        assert '"timestamp"' in composite_indexes_migration_content
        assert '"level"' in composite_indexes_migration_content
        assert '"component"' in composite_indexes_migration_content

    def test_logs_time_level_index_defined(self, composite_indexes_migration_content):
        """Test logs timestamp + level composite index."""
        assert "idx_logs_time_level" in composite_indexes_migration_content


class TestCompositeIndexOperations:
    """Tests for correct Alembic operations in composite indexes migration."""

    def test_create_index_operations(self, composite_indexes_migration_content):
        """Test that migration uses op.create_index for index creation."""
        count = composite_indexes_migration_content.count("op.create_index")
        assert count >= 7, f"Expected at least 7 create_index calls, found {count}"

    def test_drop_index_operations_in_downgrade(self, composite_indexes_migration_content):
        """Test that downgrade uses op.drop_index for cleanup."""
        count = composite_indexes_migration_content.count("op.drop_index")
        assert count >= 7, f"Expected at least 7 drop_index calls, found {count}"

    def test_downgrade_drops_same_indexes(self, composite_indexes_migration_content):
        """Test that downgrade drops the same indexes that upgrade creates."""
        expected_indexes = [
            "idx_events_camera_started",
            "idx_events_camera_time_reviewed",
            "idx_detections_camera_time_type",
            "idx_alerts_status_created",
            "idx_alerts_severity_created",
            "idx_logs_time_level_component",
            "idx_logs_time_level",
        ]

        # Split content into upgrade and downgrade sections
        parts = composite_indexes_migration_content.split("def downgrade")
        assert len(parts) == 2, "Should have upgrade and downgrade sections"

        upgrade_section = parts[0]
        downgrade_section = parts[1]

        for index_name in expected_indexes:
            assert index_name in upgrade_section, f"Index {index_name} not created in upgrade"
            assert index_name in downgrade_section, f"Index {index_name} not dropped in downgrade"


# =============================================================================
# Covering Indexes Migration Structure Tests (NEM-1497)
# =============================================================================


class TestCoveringIndexesMigrationStructure:
    """Tests for covering indexes migration file structure."""

    def test_migration_has_revision_identifier(self, covering_indexes_migration_module):
        """Test migration has revision identifier."""
        assert hasattr(covering_indexes_migration_module, "revision")
        assert covering_indexes_migration_module.revision == "add_covering_indexes_pagination"

    def test_migration_has_down_revision(self, covering_indexes_migration_module):
        """Test migration has down_revision linking to composite indexes migration."""
        assert hasattr(covering_indexes_migration_module, "down_revision")
        assert covering_indexes_migration_module.down_revision == "add_composite_indexes_filters"

    def test_migration_has_upgrade_function(self, covering_indexes_migration_module):
        """Test migration has upgrade function."""
        assert hasattr(covering_indexes_migration_module, "upgrade")
        assert callable(covering_indexes_migration_module.upgrade)

    def test_migration_has_downgrade_function(self, covering_indexes_migration_module):
        """Test migration has downgrade function."""
        assert hasattr(covering_indexes_migration_module, "downgrade")
        assert callable(covering_indexes_migration_module.downgrade)


class TestCoveringIndexDefinitions:
    """Tests for covering index definitions using PostgreSQL INCLUDE clause."""

    def test_events_pagination_covering_index_defined(self, covering_indexes_migration_content):
        """Test events pagination covering index with INCLUDE columns."""
        assert "idx_events_pagination_covering" in covering_indexes_migration_content
        # Check for postgresql_include usage
        assert "postgresql_include" in covering_indexes_migration_content
        # Check included columns for events
        assert '"risk_score"' in covering_indexes_migration_content
        assert '"risk_level"' in covering_indexes_migration_content
        assert '"summary"' in covering_indexes_migration_content
        assert '"reviewed"' in covering_indexes_migration_content

    def test_detections_pagination_covering_index_defined(self, covering_indexes_migration_content):
        """Test detections pagination covering index with INCLUDE columns."""
        assert "idx_detections_pagination_covering" in covering_indexes_migration_content
        # Check included columns for detections
        assert '"confidence"' in covering_indexes_migration_content

    def test_alerts_pagination_covering_index_defined(self, covering_indexes_migration_content):
        """Test alerts pagination covering index with INCLUDE columns."""
        assert "idx_alerts_pagination_covering" in covering_indexes_migration_content
        # Check included columns for alerts
        assert '"event_id"' in covering_indexes_migration_content

    def test_logs_pagination_covering_index_defined(self, covering_indexes_migration_content):
        """Test logs pagination covering index with INCLUDE columns."""
        assert "idx_logs_pagination_covering" in covering_indexes_migration_content


class TestCoveringIndexPostgresqlInclude:
    """Tests for correct PostgreSQL INCLUDE clause usage."""

    def test_uses_postgresql_include_parameter(self, covering_indexes_migration_content):
        """Test that indexes use postgresql_include for covering columns."""
        count = covering_indexes_migration_content.count("postgresql_include")
        assert count >= 4, f"Expected at least 4 postgresql_include usages, found {count}"

    def test_create_index_operations(self, covering_indexes_migration_content):
        """Test that migration uses op.create_index for index creation."""
        count = covering_indexes_migration_content.count("op.create_index")
        assert count >= 4, f"Expected at least 4 create_index calls, found {count}"

    def test_drop_index_operations_in_downgrade(self, covering_indexes_migration_content):
        """Test that downgrade uses op.drop_index for cleanup."""
        count = covering_indexes_migration_content.count("op.drop_index")
        assert count >= 4, f"Expected at least 4 drop_index calls, found {count}"


class TestCoveringIndexOperations:
    """Tests for correct Alembic operations in covering indexes migration."""

    def test_downgrade_drops_same_indexes(self, covering_indexes_migration_content):
        """Test that downgrade drops the same indexes that upgrade creates."""
        expected_indexes = [
            "idx_events_pagination_covering",
            "idx_detections_pagination_covering",
            "idx_alerts_pagination_covering",
            "idx_logs_pagination_covering",
        ]

        # Split content into upgrade and downgrade sections
        parts = covering_indexes_migration_content.split("def downgrade")
        assert len(parts) == 2, "Should have upgrade and downgrade sections"

        upgrade_section = parts[0]
        downgrade_section = parts[1]

        for index_name in expected_indexes:
            assert index_name in upgrade_section, f"Index {index_name} not created in upgrade"
            assert index_name in downgrade_section, f"Index {index_name} not dropped in downgrade"


# =============================================================================
# Documentation Tests
# =============================================================================


class TestCompositeIndexesMigrationDocumentation:
    """Tests for composite indexes migration documentation."""

    def test_migration_has_docstring(self, composite_indexes_migration_content):
        """Test migration has descriptive docstring."""
        assert '"""' in composite_indexes_migration_content, "Migration should have a docstring"

    def test_docstring_mentions_composite_indexes(self, composite_indexes_migration_content):
        """Test docstring mentions composite indexes."""
        docstring_start = composite_indexes_migration_content.find('"""')
        docstring_end = composite_indexes_migration_content.find('"""', docstring_start + 3)
        docstring = composite_indexes_migration_content[docstring_start : docstring_end + 3].lower()

        assert "composite" in docstring, "Docstring should mention composite indexes"

    def test_docstring_mentions_nem_1491(self, composite_indexes_migration_content):
        """Test docstring references the Linear issue."""
        assert "NEM-1491" in composite_indexes_migration_content


class TestCoveringIndexesMigrationDocumentation:
    """Tests for covering indexes migration documentation."""

    def test_migration_has_docstring(self, covering_indexes_migration_content):
        """Test migration has descriptive docstring."""
        assert '"""' in covering_indexes_migration_content, "Migration should have a docstring"

    def test_docstring_mentions_covering_indexes(self, covering_indexes_migration_content):
        """Test docstring mentions covering indexes."""
        docstring_start = covering_indexes_migration_content.find('"""')
        docstring_end = covering_indexes_migration_content.find('"""', docstring_start + 3)
        docstring = covering_indexes_migration_content[docstring_start : docstring_end + 3].lower()

        assert "covering" in docstring, "Docstring should mention covering indexes"

    def test_docstring_mentions_postgresql_include(self, covering_indexes_migration_content):
        """Test docstring mentions PostgreSQL INCLUDE clause."""
        docstring_start = covering_indexes_migration_content.find('"""')
        docstring_end = covering_indexes_migration_content.find('"""', docstring_start + 3)
        docstring = covering_indexes_migration_content[docstring_start : docstring_end + 3].lower()

        assert "include" in docstring, "Docstring should mention INCLUDE clause"

    def test_docstring_mentions_nem_1497(self, covering_indexes_migration_content):
        """Test docstring references the Linear issue."""
        assert "NEM-1497" in covering_indexes_migration_content


# =============================================================================
# Table Reference Tests
# =============================================================================


class TestTableReferences:
    """Tests for correct table references in both migrations."""

    def test_composite_events_table_referenced(self, composite_indexes_migration_content):
        """Test events table is correctly referenced in composite indexes."""
        assert '"events"' in composite_indexes_migration_content

    def test_composite_detections_table_referenced(self, composite_indexes_migration_content):
        """Test detections table is correctly referenced in composite indexes."""
        assert '"detections"' in composite_indexes_migration_content

    def test_composite_alerts_table_referenced(self, composite_indexes_migration_content):
        """Test alerts table is correctly referenced in composite indexes."""
        assert '"alerts"' in composite_indexes_migration_content

    def test_composite_logs_table_referenced(self, composite_indexes_migration_content):
        """Test logs table is correctly referenced in composite indexes."""
        assert '"logs"' in composite_indexes_migration_content

    def test_covering_events_table_referenced(self, covering_indexes_migration_content):
        """Test events table is correctly referenced in covering indexes."""
        assert '"events"' in covering_indexes_migration_content

    def test_covering_detections_table_referenced(self, covering_indexes_migration_content):
        """Test detections table is correctly referenced in covering indexes."""
        assert '"detections"' in covering_indexes_migration_content

    def test_covering_alerts_table_referenced(self, covering_indexes_migration_content):
        """Test alerts table is correctly referenced in covering indexes."""
        assert '"alerts"' in covering_indexes_migration_content

    def test_covering_logs_table_referenced(self, covering_indexes_migration_content):
        """Test logs table is correctly referenced in covering indexes."""
        assert '"logs"' in covering_indexes_migration_content
