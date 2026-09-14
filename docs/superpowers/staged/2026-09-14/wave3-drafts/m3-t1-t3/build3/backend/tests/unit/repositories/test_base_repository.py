"""Unit tests for Repository base class.

Tests for the generic Repository class, focusing on pagination limit enforcement
to prevent memory exhaustion attacks.

Related to NEM-2559: Enforce upper bound on pagination limit.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models import Entity
from backend.models.enums import EntityType
from backend.repositories.base import MAX_LIMIT


class TestRepositoryPaginationLimits:
    """Test pagination limit enforcement in Repository base class."""

    @pytest.mark.asyncio
    async def test_max_limit_constant_is_1000(self):
        """Test that MAX_LIMIT is set to 1000."""
        assert MAX_LIMIT == 1000

    @pytest.mark.asyncio
    async def test_list_paginated_respects_limit_within_max(self, mock_db_session: AsyncMock):
        """Test list_paginated uses provided limit when within MAX_LIMIT."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        entities = [Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value) for _ in range(5)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = entities
        mock_db_session.execute.return_value = mock_result

        result = await repo.list_paginated(limit=50)

        assert len(result) == 5
        mock_db_session.execute.assert_called_once()

        # Verify the query was built with LIMIT clause
        call_args = mock_db_session.execute.call_args
        stmt = call_args[0][0]
        # The query should contain LIMIT (exact format may vary with SQLAlchemy version)
        assert "LIMIT" in str(stmt)

    @pytest.mark.asyncio
    async def test_list_paginated_caps_limit_exceeding_max(self, mock_db_session: AsyncMock):
        """Test list_paginated silently caps limit when exceeding MAX_LIMIT."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        entities = [Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value) for _ in range(10)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = entities
        mock_db_session.execute.return_value = mock_result

        # Request limit of 5000, should be capped to MAX_LIMIT (1000)
        result = await repo.list_paginated(limit=5000)

        assert len(result) == 10
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_paginated_at_exact_max_limit(self, mock_db_session: AsyncMock):
        """Test list_paginated accepts exactly MAX_LIMIT without capping."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        entities = [Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value) for _ in range(10)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = entities
        mock_db_session.execute.return_value = mock_result

        # Request exactly MAX_LIMIT
        result = await repo.list_paginated(limit=MAX_LIMIT)

        assert len(result) == 10
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_paginated_at_max_limit_plus_one(self, mock_db_session: AsyncMock):
        """Test list_paginated caps limit at MAX_LIMIT + 1."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        entities = [Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value) for _ in range(10)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = entities
        mock_db_session.execute.return_value = mock_result

        # Request MAX_LIMIT + 1, should be capped to MAX_LIMIT
        result = await repo.list_paginated(limit=MAX_LIMIT + 1)

        assert len(result) == 10
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_paginated_with_very_large_limit(self, mock_db_session: AsyncMock):
        """Test list_paginated handles extremely large limit values safely."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        entities = []

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = entities
        mock_db_session.execute.return_value = mock_result

        # Request an absurdly large limit (potential memory attack)
        result = await repo.list_paginated(limit=10_000_000)

        # Should not raise, should return empty result (capped query)
        assert result == []
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_paginated_with_zero_limit(self, mock_db_session: AsyncMock):
        """Test list_paginated handles zero limit."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        result = await repo.list_paginated(limit=0)

        # Zero limit should return empty results
        assert result == []
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_paginated_with_negative_limit(self, mock_db_session: AsyncMock):
        """Test list_paginated handles negative limit (edge case)."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        # Negative limit - min() will use the negative value
        # This is an edge case that the database will handle
        result = await repo.list_paginated(limit=-1)

        assert result == []
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_paginated_preserves_skip_parameter(self, mock_db_session: AsyncMock):
        """Test list_paginated preserves skip/offset parameter when capping limit."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        entities = [Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value) for _ in range(5)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = entities
        mock_db_session.execute.return_value = mock_result

        # Request with large limit and skip
        result = await repo.list_paginated(skip=100, limit=5000)

        assert len(result) == 5
        mock_db_session.execute.assert_called_once()

        # Verify query includes offset
        call_args = mock_db_session.execute.call_args
        stmt = call_args[0][0]
        stmt_str = str(stmt)
        assert "OFFSET" in stmt_str


class TestMaxLimitConstant:
    """Test MAX_LIMIT constant is properly exported and accessible."""

    def test_max_limit_exported_from_base_module(self):
        """Test MAX_LIMIT can be imported from base module."""
        from backend.repositories.base import MAX_LIMIT

        assert MAX_LIMIT == 1000

    def test_max_limit_is_integer(self):
        """Test MAX_LIMIT is an integer type."""
        assert isinstance(MAX_LIMIT, int)

    def test_max_limit_is_positive(self):
        """Test MAX_LIMIT is a positive number."""
        assert MAX_LIMIT > 0
