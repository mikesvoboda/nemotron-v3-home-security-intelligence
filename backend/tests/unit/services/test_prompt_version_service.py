"""Tests for PromptVersionService.

Tests version history management, restore functionality, and cleanup behavior.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.prompt_version import AIModel, PromptVersion
from backend.services.prompt_version_service import (
    MAX_VERSIONS_PER_MODEL,
    PromptVersionService,
    get_prompt_version_service,
    reset_prompt_version_service,
)


@pytest.fixture
def service() -> PromptVersionService:
    """Create a fresh service instance for each test."""
    reset_prompt_version_service()
    return get_prompt_version_service()


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def sample_version() -> PromptVersion:
    """Create a sample PromptVersion for testing."""
    version = PromptVersion(
        id=1,
        model=AIModel.NEMOTRON,
        version=1,
        config_json=json.dumps({"system_prompt": "Test prompt"}),
        created_at=datetime.now(UTC),
        created_by="test_user",
        change_description="Initial version",
        is_active=True,
    )
    return version


class TestPromptVersionServiceSingleton:
    """Tests for singleton behavior."""

    def test_get_prompt_version_service_returns_same_instance(self) -> None:
        """Test that get_prompt_version_service returns the same singleton."""
        reset_prompt_version_service()
        service1 = get_prompt_version_service()
        service2 = get_prompt_version_service()
        assert service1 is service2

    def test_reset_clears_singleton(self) -> None:
        """Test that reset clears the singleton instance."""
        reset_prompt_version_service()
        service1 = get_prompt_version_service()
        reset_prompt_version_service()
        service2 = get_prompt_version_service()
        assert service1 is not service2


class TestGetActiveVersion:
    """Tests for get_active_version method."""

    @pytest.mark.asyncio
    async def test_returns_active_version(
        self, service: PromptVersionService, mock_session: AsyncMock, sample_version: PromptVersion
    ) -> None:
        """Test that active version is returned correctly."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_version
        mock_session.execute.return_value = mock_result

        result = await service.get_active_version(mock_session, AIModel.NEMOTRON)

        assert result is sample_version
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_no_active_version(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Test that None is returned when no active version exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.get_active_version(mock_session, AIModel.NEMOTRON)

        assert result is None


class TestGetVersionById:
    """Tests for get_version_by_id method."""

    @pytest.mark.asyncio
    async def test_returns_version_by_id(
        self, service: PromptVersionService, mock_session: AsyncMock, sample_version: PromptVersion
    ) -> None:
        """Test that version is returned by ID."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_version
        mock_session.execute.return_value = mock_result

        result = await service.get_version_by_id(mock_session, 1)

        assert result is sample_version

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_id(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Test that None is returned for nonexistent ID."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.get_version_by_id(mock_session, 999)

        assert result is None


class TestGetVersionHistory:
    """Tests for get_version_history method."""

    @pytest.mark.asyncio
    async def test_returns_versions_and_count(
        self, service: PromptVersionService, mock_session: AsyncMock, sample_version: PromptVersion
    ) -> None:
        """Test that version history returns versions and total count."""
        # Mock count query
        count_result = MagicMock()
        count_result.scalar.return_value = 5

        # Mock versions query
        versions_result = MagicMock()
        versions_result.scalars.return_value.all.return_value = [sample_version]

        mock_session.execute.side_effect = [count_result, versions_result]

        versions, total = await service.get_version_history(mock_session)

        assert len(versions) == 1
        assert versions[0] is sample_version
        assert total == 5

    @pytest.mark.asyncio
    async def test_filters_by_model(
        self, service: PromptVersionService, mock_session: AsyncMock, sample_version: PromptVersion
    ) -> None:
        """Test that history can be filtered by model."""
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        versions_result = MagicMock()
        versions_result.scalars.return_value.all.return_value = [sample_version]

        mock_session.execute.side_effect = [count_result, versions_result]

        versions, total = await service.get_version_history(mock_session, model=AIModel.NEMOTRON)

        assert len(versions) == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_respects_limit_and_offset(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Test that limit and offset are applied."""
        count_result = MagicMock()
        count_result.scalar.return_value = 100

        versions_result = MagicMock()
        versions_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [count_result, versions_result]

        _versions, total = await service.get_version_history(mock_session, limit=10, offset=20)

        assert total == 100
        # The actual query would have limit and offset applied


class TestGetNextVersionNumber:
    """Tests for get_next_version_number method."""

    @pytest.mark.asyncio
    async def test_returns_1_for_new_model(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Test that 1 is returned for a model with no versions."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.get_next_version_number(mock_session, AIModel.NEMOTRON)

        assert result == 1

    @pytest.mark.asyncio
    async def test_returns_incremented_version(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Test that max version + 1 is returned."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_session.execute.return_value = mock_result

        result = await service.get_next_version_number(mock_session, AIModel.NEMOTRON)

        assert result == 6


class TestCreateVersion:
    """Tests for create_version method."""

    @pytest.mark.asyncio
    async def test_creates_new_version(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Test that a new version is created correctly."""
        # Mock get_next_version_number
        version_result = MagicMock()
        version_result.scalar.return_value = 2
        mock_session.execute.return_value = version_result

        # Mock get_active_version (returns None, no deactivation needed)
        with (
            patch.object(
                service, "_deactivate_current_version", new_callable=AsyncMock
            ) as mock_deactivate,
            patch.object(service, "_cleanup_old_versions", new_callable=AsyncMock) as mock_cleanup,
        ):
            config = {"system_prompt": "Test prompt"}

            _result = await service.create_version(
                mock_session,
                model=AIModel.NEMOTRON,
                config=config,
                created_by="test_user",
                change_description="Test change",
                make_active=True,
            )

            # Verify session.add was called
            mock_session.add.assert_called_once()
            mock_session.flush.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

            # Verify deactivation was called when make_active=True
            mock_deactivate.assert_called_once()

            # Verify cleanup was called
            mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_deactivation_when_not_active(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Test that deactivation is skipped when make_active=False."""
        version_result = MagicMock()
        version_result.scalar.return_value = 1
        mock_session.execute.return_value = version_result

        with (
            patch.object(
                service, "_deactivate_current_version", new_callable=AsyncMock
            ) as mock_deactivate,
            patch.object(service, "_cleanup_old_versions", new_callable=AsyncMock),
        ):
            await service.create_version(
                mock_session,
                model=AIModel.NEMOTRON,
                config={"test": "config"},
                make_active=False,
            )

            mock_deactivate.assert_not_called()


class TestRestoreVersion:
    """Tests for restore_version method."""

    @pytest.mark.asyncio
    async def test_restore_creates_new_version(
        self,
        service: PromptVersionService,
        mock_session: AsyncMock,
        sample_version: PromptVersion,
    ) -> None:
        """Test that restoring creates a new version with the same config."""
        # Mock get_version_by_id
        with patch.object(service, "get_version_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_version

            with patch.object(service, "create_version", new_callable=AsyncMock) as mock_create:
                new_version = MagicMock()
                new_version.version = 2
                mock_create.return_value = new_version

                _result = await service.restore_version(
                    mock_session, version_id=1, created_by="restore_user"
                )

                mock_get.assert_called_once_with(mock_session, 1)
                mock_create.assert_called_once()

                # Check that create_version was called with the old config
                call_kwargs = mock_create.call_args.kwargs
                # Model should be converted to AIModel enum
                assert call_kwargs["model"] == AIModel.NEMOTRON
                assert call_kwargs["config"] == sample_version.config
                assert call_kwargs["created_by"] == "restore_user"
                assert "Restored from version 1" in call_kwargs["change_description"]

    @pytest.mark.asyncio
    async def test_restore_raises_for_nonexistent_version(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Test that restoring a nonexistent version raises ValueError."""
        with patch.object(service, "get_version_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with pytest.raises(ValueError, match="Version 999 not found"):
                await service.restore_version(mock_session, version_id=999)


class TestGetVersionDiff:
    """Tests for get_version_diff method."""

    @pytest.mark.asyncio
    async def test_calculates_diff_between_versions(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Test that diff is calculated correctly between two versions."""
        version_a = PromptVersion(
            id=1,
            model=AIModel.NEMOTRON,
            version=1,
            config_json=json.dumps({"prompt": "old", "threshold": 0.5}),
            created_at=datetime.now(UTC),
            is_active=False,
        )
        version_b = PromptVersion(
            id=2,
            model=AIModel.NEMOTRON,
            version=2,
            config_json=json.dumps({"prompt": "new", "new_field": True}),
            created_at=datetime.now(UTC),
            is_active=True,
        )

        with patch.object(service, "get_version_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [version_a, version_b]

            result = await service.get_version_diff(mock_session, 1, 2)

            assert result["version_a"]["id"] == 1
            assert result["version_b"]["id"] == 2
            assert result["diff"]["has_changes"] is True
            assert "threshold" in result["diff"]["removed"]
            assert "new_field" in result["diff"]["added"]
            assert "prompt" in result["diff"]["changed"]

    @pytest.mark.asyncio
    async def test_diff_raises_for_nonexistent_versions(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Test that diff raises ValueError for nonexistent versions."""
        with patch.object(service, "get_version_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with pytest.raises(ValueError, match="Version 1 not found"):
                await service.get_version_diff(mock_session, 1, 2)


class TestCalculateDiff:
    """Tests for _calculate_diff helper method."""

    def test_identifies_added_keys(self, service: PromptVersionService) -> None:
        """Test that added keys are identified."""
        config_a: dict[str, Any] = {"existing": "value"}
        config_b: dict[str, Any] = {"existing": "value", "new": "added"}

        diff = service._calculate_diff(config_a, config_b)

        assert "new" in diff["added"]
        assert diff["added"]["new"] == "added"
        assert diff["has_changes"] is True

    def test_identifies_removed_keys(self, service: PromptVersionService) -> None:
        """Test that removed keys are identified."""
        config_a: dict[str, Any] = {"existing": "value", "removed": "gone"}
        config_b: dict[str, Any] = {"existing": "value"}

        diff = service._calculate_diff(config_a, config_b)

        assert "removed" in diff["removed"]
        assert diff["removed"]["removed"] == "gone"

    def test_identifies_changed_values(self, service: PromptVersionService) -> None:
        """Test that changed values are identified."""
        config_a: dict[str, Any] = {"key": "old_value"}
        config_b: dict[str, Any] = {"key": "new_value"}

        diff = service._calculate_diff(config_a, config_b)

        assert "key" in diff["changed"]
        assert diff["changed"]["key"]["from"] == "old_value"
        assert diff["changed"]["key"]["to"] == "new_value"

    def test_no_changes_detected(self, service: PromptVersionService) -> None:
        """Test that identical configs show no changes."""
        config: dict[str, Any] = {"key": "value", "number": 42}

        diff = service._calculate_diff(config, config.copy())

        assert diff["has_changes"] is False
        assert len(diff["added"]) == 0
        assert len(diff["removed"]) == 0
        assert len(diff["changed"]) == 0


class TestCleanupOldVersions:
    """Tests for _cleanup_old_versions method."""

    @pytest.mark.asyncio
    async def test_no_cleanup_when_under_limit(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Test that no cleanup occurs when under the version limit."""
        count_result = MagicMock()
        count_result.scalar.return_value = MAX_VERSIONS_PER_MODEL - 1
        mock_session.execute.return_value = count_result

        await service._cleanup_old_versions(mock_session, AIModel.NEMOTRON)

        # Only the count query should be executed
        assert mock_session.execute.call_count == 1
        mock_session.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_removes_oldest_versions(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Test that oldest versions are removed when over limit."""
        # First call: count query (over limit)
        count_result = MagicMock()
        count_result.scalar.return_value = MAX_VERSIONS_PER_MODEL + 5

        # Second call: get IDs to keep
        keep_result = MagicMock()
        keep_result.fetchall.return_value = [(i,) for i in range(MAX_VERSIONS_PER_MODEL)]

        # Third call: get versions to delete
        old_version = MagicMock(spec=PromptVersion)
        delete_result = MagicMock()
        delete_result.scalars.return_value.all.return_value = [old_version]

        mock_session.execute.side_effect = [count_result, keep_result, delete_result]

        await service._cleanup_old_versions(mock_session, AIModel.NEMOTRON)

        # Verify delete was called for old versions
        mock_session.delete.assert_called_once_with(old_version)


class TestDeactivateCurrentVersion:
    """Tests for _deactivate_current_version method."""

    @pytest.mark.asyncio
    async def test_deactivates_active_version(
        self,
        service: PromptVersionService,
        mock_session: AsyncMock,
        sample_version: PromptVersion,
    ) -> None:
        """Test that the current active version is deactivated."""
        with patch.object(service, "get_active_version", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_version

            await service._deactivate_current_version(mock_session, AIModel.NEMOTRON)

            assert sample_version.is_active is False
            mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_action_when_no_active_version(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Test that no action is taken when no active version exists."""
        with patch.object(service, "get_active_version", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            await service._deactivate_current_version(mock_session, AIModel.NEMOTRON)

            mock_session.flush.assert_not_called()
