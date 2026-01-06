"""Prompt version history service.

Manages version tracking, history retrieval, and version restoration
for AI model prompt configurations.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging import get_logger
from backend.core.time_utils import utc_now
from backend.models.prompt_version import AIModel, PromptVersion

logger = get_logger(__name__)

# Maximum versions to keep per model
MAX_VERSIONS_PER_MODEL = 50


class PromptVersionService:
    """Service for managing prompt version history."""

    async def get_active_version(
        self,
        session: AsyncSession,
        model: AIModel,
    ) -> PromptVersion | None:
        """Get the currently active version for a model.

        Args:
            session: Database session
            model: The AI model to get active version for

        Returns:
            The active PromptVersion or None if no active version exists
        """
        result = await session.execute(
            select(PromptVersion).where(
                PromptVersion.model == model,
                PromptVersion.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_version_by_id(
        self,
        session: AsyncSession,
        version_id: int,
    ) -> PromptVersion | None:
        """Get a specific version by ID.

        Args:
            session: Database session
            version_id: The version ID to retrieve

        Returns:
            The PromptVersion or None if not found
        """
        result = await session.execute(select(PromptVersion).where(PromptVersion.id == version_id))
        return result.scalar_one_or_none()

    async def get_version_history(
        self,
        session: AsyncSession,
        model: AIModel | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PromptVersion], int]:
        """Get version history for one or all models.

        Args:
            session: Database session
            model: Optional model to filter by (None = all models)
            limit: Maximum versions to return
            offset: Number of versions to skip

        Returns:
            Tuple of (list of versions, total count)
        """
        # Build base query
        query = select(PromptVersion)
        count_query = select(func.count()).select_from(PromptVersion)

        if model is not None:
            query = query.where(PromptVersion.model == model)
            count_query = count_query.where(PromptVersion.model == model)

        # Get total count
        count_result = await session.execute(count_query)
        total_count = count_result.scalar() or 0

        # Get versions with ordering and pagination
        query = query.order_by(desc(PromptVersion.created_at)).limit(limit).offset(offset)
        result = await session.execute(query)
        versions = list(result.scalars().all())

        return versions, total_count

    async def get_next_version_number(
        self,
        session: AsyncSession,
        model: AIModel,
    ) -> int:
        """Get the next version number for a model.

        Args:
            session: Database session
            model: The AI model

        Returns:
            The next version number (1 if no versions exist)
        """
        result = await session.execute(
            select(func.max(PromptVersion.version)).where(PromptVersion.model == model)
        )
        max_version = result.scalar()
        return (max_version or 0) + 1

    async def create_version(
        self,
        session: AsyncSession,
        model: AIModel,
        config: dict[str, Any],
        created_by: str | None = None,
        change_description: str | None = None,
        make_active: bool = True,
    ) -> PromptVersion:
        """Create a new version for a model.

        Args:
            session: Database session
            model: The AI model
            config: The configuration to store
            created_by: Optional user/system that created this version
            change_description: Optional description of what changed
            make_active: Whether to make this the active version

        Returns:
            The created PromptVersion
        """
        # Get next version number
        next_version = await self.get_next_version_number(session, model)

        # If making active, deactivate current active version
        if make_active:
            await self._deactivate_current_version(session, model)

        # Create new version
        version = PromptVersion(
            model=model,
            version=next_version,
            config_json=json.dumps(config, indent=2),
            created_at=utc_now(),
            created_by=created_by,
            change_description=change_description,
            is_active=make_active,
        )
        session.add(version)
        await session.flush()

        # Cleanup old versions if needed
        await self._cleanup_old_versions(session, model)

        await session.commit()
        await session.refresh(version)

        logger.info(f"Created version {next_version} for model {model.value}, active={make_active}")

        return version

    async def restore_version(
        self,
        session: AsyncSession,
        version_id: int,
        created_by: str | None = None,
    ) -> PromptVersion:
        """Restore a historical version by creating a new version with its config.

        This creates a new version with the same config as the target version,
        rather than modifying the historical record.

        Args:
            session: Database session
            version_id: The version ID to restore
            created_by: Optional user/system performing the restore

        Returns:
            The newly created PromptVersion (copy of the restored version)

        Raises:
            ValueError: If the version_id is not found
        """
        # Get the version to restore
        old_version = await self.get_version_by_id(session, version_id)
        if old_version is None:
            raise ValueError(f"Version {version_id} not found")

        # Create a new version with the same config
        change_desc = f"Restored from version {old_version.version}"
        if old_version.change_description:
            change_desc += f" ({old_version.change_description})"

        # Convert string model to AIModel enum
        model_enum = (
            old_version.model
            if isinstance(old_version.model, AIModel)
            else AIModel(old_version.model)
        )

        new_version = await self.create_version(
            session=session,
            model=model_enum,
            config=old_version.config,
            created_by=created_by,
            change_description=change_desc,
            make_active=True,
        )

        # Get model value for logging
        model_value = model_enum.value if isinstance(model_enum, AIModel) else str(model_enum)
        logger.info(
            f"Restored version {old_version.version} to new version "
            f"{new_version.version} for model {model_value}"
        )

        return new_version

    async def get_version_diff(
        self,
        session: AsyncSession,
        version_id_a: int,
        version_id_b: int,
    ) -> dict[str, Any]:
        """Get differences between two versions.

        Args:
            session: Database session
            version_id_a: First version ID
            version_id_b: Second version ID

        Returns:
            Dict with diff information

        Raises:
            ValueError: If either version is not found
        """
        version_a = await self.get_version_by_id(session, version_id_a)
        version_b = await self.get_version_by_id(session, version_id_b)

        if version_a is None:
            raise ValueError(f"Version {version_id_a} not found")
        if version_b is None:
            raise ValueError(f"Version {version_id_b} not found")

        config_a = version_a.config
        config_b = version_b.config

        # Calculate simple diff
        diff = self._calculate_diff(config_a, config_b)

        # Get model values (handle both AIModel enum and string)
        model_a = version_a.model.value if isinstance(version_a.model, AIModel) else version_a.model
        model_b = version_b.model.value if isinstance(version_b.model, AIModel) else version_b.model

        return {
            "version_a": {
                "id": version_a.id,
                "version": version_a.version,
                "model": model_a,
                "created_at": version_a.created_at.isoformat(),
            },
            "version_b": {
                "id": version_b.id,
                "version": version_b.version,
                "model": model_b,
                "created_at": version_b.created_at.isoformat(),
            },
            "diff": diff,
        }

    def _calculate_diff(
        self,
        config_a: dict[str, Any],
        config_b: dict[str, Any],
    ) -> dict[str, Any]:
        """Calculate differences between two configurations.

        Args:
            config_a: First configuration
            config_b: Second configuration

        Returns:
            Dict describing the differences
        """
        all_keys = set(config_a.keys()) | set(config_b.keys())

        added: dict[str, Any] = {}
        removed: dict[str, Any] = {}
        changed: dict[str, dict[str, Any]] = {}

        for key in all_keys:
            in_a = key in config_a
            in_b = key in config_b

            if in_a and not in_b:
                removed[key] = config_a[key]
            elif in_b and not in_a:
                added[key] = config_b[key]
            elif config_a[key] != config_b[key]:
                changed[key] = {
                    "from": config_a[key],
                    "to": config_b[key],
                }

        return {
            "added": added,
            "removed": removed,
            "changed": changed,
            "has_changes": bool(added or removed or changed),
        }

    async def _deactivate_current_version(
        self,
        session: AsyncSession,
        model: AIModel,
    ) -> None:
        """Deactivate the currently active version for a model.

        Args:
            session: Database session
            model: The AI model
        """
        current = await self.get_active_version(session, model)
        if current is not None:
            current.is_active = False
            await session.flush()

    async def _cleanup_old_versions(
        self,
        session: AsyncSession,
        model: AIModel,
    ) -> None:
        """Remove old versions beyond the maximum limit.

        Keeps the most recent MAX_VERSIONS_PER_MODEL versions.

        Args:
            session: Database session
            model: The AI model
        """
        # Get count of versions
        count_result = await session.execute(
            select(func.count()).select_from(PromptVersion).where(PromptVersion.model == model)
        )
        total = count_result.scalar() or 0

        if total <= MAX_VERSIONS_PER_MODEL:
            return

        # Get IDs of versions to keep (most recent ones)
        keep_query = (
            select(PromptVersion.id)
            .where(PromptVersion.model == model)
            .order_by(desc(PromptVersion.created_at))
            .limit(MAX_VERSIONS_PER_MODEL)
        )
        keep_result = await session.execute(keep_query)
        keep_ids = {row[0] for row in keep_result.fetchall()}

        # Delete old versions
        delete_query = select(PromptVersion).where(
            PromptVersion.model == model,
            ~PromptVersion.id.in_(keep_ids),
        )
        delete_result = await session.execute(delete_query)
        old_versions = list(delete_result.scalars().all())

        for old_version in old_versions:
            await session.delete(old_version)

        if old_versions:
            logger.info(f"Cleaned up {len(old_versions)} old versions for model {model.value}")


# Singleton
_prompt_version_service: PromptVersionService | None = None


def get_prompt_version_service() -> PromptVersionService:
    """Get or create prompt version service singleton."""
    global _prompt_version_service  # noqa: PLW0603
    if _prompt_version_service is None:
        _prompt_version_service = PromptVersionService()
    return _prompt_version_service


def reset_prompt_version_service() -> None:
    """Reset the prompt version service singleton (for testing)."""
    global _prompt_version_service  # noqa: PLW0603
    _prompt_version_service = None
