"""Integration tests for QueryExplainLogger with actual database queries.

Tests cover:
- EXPLAIN logging with real database queries
- EXPLAIN output on actual table queries
- Query execution timing and logging integration

These tests require database access to validate EXPLAIN ANALYZE functionality.
"""

import pytest
from sqlalchemy import text

from backend.core.database import get_engine
from backend.core.query_explain import QueryExplainLogger, setup_explain_logging

# Mark as integration tests
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_explain_logging_with_real_query(session):
    """Test EXPLAIN logging with a real database query.

    This validates that the QueryExplainLogger integrates properly with
    SQLAlchemy's event system and can execute queries without errors.
    """
    engine = get_engine()
    setup_explain_logging(engine.sync_engine)

    # Execute a query that should trigger timing
    result = await session.execute(text("SELECT 1"))
    result.fetchall()

    # Test passes if no exceptions were raised
    # In production, slow queries would be logged


@pytest.mark.asyncio
async def test_explain_on_actual_table_query(session):
    """Test EXPLAIN output on actual table query.

    This validates that EXPLAIN ANALYZE works correctly on real tables
    and produces expected output structure.
    """
    _logger = QueryExplainLogger()

    # Create a simple query on the cameras table
    result = await session.execute(text("SELECT * FROM cameras LIMIT 10"))
    result.fetchall()

    # Manually run EXPLAIN to verify it works
    explain_result = await session.execute(text("EXPLAIN ANALYZE SELECT * FROM cameras LIMIT 10"))
    explain_rows = explain_result.fetchall()

    # Verify EXPLAIN output has expected structure
    assert len(explain_rows) > 0
    explain_text = " ".join(row[0] for row in explain_rows)
    assert "Scan" in explain_text or "Planning" in explain_text
