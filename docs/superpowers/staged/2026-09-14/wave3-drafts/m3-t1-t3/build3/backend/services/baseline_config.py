"""Baseline configuration service for per-camera anomaly detection settings.

This service manages per-camera baseline configuration overrides, allowing
individual cameras to have custom threshold and minimum sample settings
that differ from the global defaults.

NEM-4921: Baseline Tuning UI for per-camera configuration.

Usage:
    from backend.services.baseline_config_service import baseline_config_service

    # Get configuration for a camera (includes global defaults)
    config = await baseline_config_service.get_camera_config(camera_id, session)

    # Update per-camera configuration
    await baseline_config_service.set_camera_config(
        camera_id,
        threshold_stdev=3.0,
        min_samples=15,
        override_global_config=True,
        session=session
    )

    # Reset all baseline data for a camera
    result = await baseline_config_service.reset_camera_baseline(camera_id, session)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import delete

from backend.core.logging import get_logger
from backend.models.baseline import ActivityBaseline, ClassBaseline
from backend.services.baseline import get_baseline_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# In-memory storage for per-camera configuration overrides
# In a production system, this would be stored in the database
# For now, we use a dictionary keyed by camera_id
_camera_configs: dict[str, dict[str, Any]] = {}


class BaselineConfigService:
    """Service for managing per-camera baseline configuration.

    This service wraps the global BaselineService and provides per-camera
    configuration overrides. Each camera can have custom settings for:
    - threshold_stdev: Anomaly detection threshold in standard deviations
    - min_samples: Minimum samples required for reliable detection

    If no per-camera override exists, the global defaults from BaselineService
    are used.
    """

    def __init__(self) -> None:
        """Initialize the baseline config service."""
        self._baseline_service = get_baseline_service()

    @property
    def global_config(self) -> dict[str, Any]:
        """Get the global baseline configuration defaults.

        Returns:
            Dictionary with global configuration values.
        """
        return {
            "threshold_stdev": self._baseline_service.anomaly_threshold_std,
            "min_samples": self._baseline_service.min_samples,
            "decay_factor": self._baseline_service.decay_factor,
            "window_days": self._baseline_service.window_days,
        }

    async def get_camera_config(
        self,
        camera_id: str,
        session: AsyncSession | None = None,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Get baseline configuration for a camera.

        Returns the active configuration for the camera, which may be either
        per-camera overrides or global defaults based on override_global_config.

        Args:
            camera_id: ID of the camera.
            session: Database session (unused, for future DB storage).

        Returns:
            Dictionary containing:
            - threshold_stdev: Active threshold value
            - min_samples: Active minimum samples value
            - override_global_config: Whether per-camera overrides are active
            - global_config: Dictionary of global defaults
        """
        global_conf = self.global_config
        camera_override = _camera_configs.get(camera_id, {})
        override_active = camera_override.get("override_global_config", False)

        # Use per-camera values only when override is active, otherwise use global
        threshold = (
            camera_override.get("threshold_stdev", global_conf["threshold_stdev"])
            if override_active
            else global_conf["threshold_stdev"]
        )
        min_samples = (
            camera_override.get("min_samples", global_conf["min_samples"])
            if override_active
            else global_conf["min_samples"]
        )

        return {
            "threshold_stdev": threshold,
            "min_samples": min_samples,
            "override_global_config": override_active,
            "global_config": global_conf,
        }

    async def set_camera_config(
        self,
        camera_id: str,
        *,
        threshold_stdev: float | None = None,
        min_samples: int | None = None,
        override_global_config: bool | None = None,
        session: AsyncSession | None = None,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Set baseline configuration for a camera.

        Updates per-camera configuration overrides. If override_global_config
        is set to False, per-camera values are ignored in favor of global defaults.

        Args:
            camera_id: ID of the camera.
            threshold_stdev: New anomaly threshold (None to keep existing).
            min_samples: New minimum samples (None to keep existing).
            override_global_config: Whether to enable per-camera overrides.
            session: Database session (unused, for future DB storage).

        Returns:
            Updated configuration dictionary.

        Raises:
            ValueError: If invalid values are provided.
        """
        # Validate inputs
        if threshold_stdev is not None and threshold_stdev < 0.5:
            raise ValueError("threshold_stdev must be at least 0.5")
        if min_samples is not None and min_samples < 1:
            raise ValueError("min_samples must be at least 1")

        # Get existing config or create new
        if camera_id not in _camera_configs:
            _camera_configs[camera_id] = {}

        camera_config = _camera_configs[camera_id]

        # Update values if provided
        if threshold_stdev is not None:
            camera_config["threshold_stdev"] = threshold_stdev
        if min_samples is not None:
            camera_config["min_samples"] = min_samples
        if override_global_config is not None:
            camera_config["override_global_config"] = override_global_config

        logger.info(
            f"Updated baseline config for camera {camera_id}: "
            f"threshold={camera_config.get('threshold_stdev')}, "
            f"min_samples={camera_config.get('min_samples')}, "
            f"override={camera_config.get('override_global_config')}"
        )

        # Return the full config
        return await self.get_camera_config(camera_id)

    async def reset_camera_baseline(
        self,
        *,
        camera_id: str,
        session: AsyncSession,
    ) -> dict[str, int]:
        """Reset all baseline data for a camera.

        Deletes all ActivityBaseline and ClassBaseline records for the camera.
        This forces the baseline to be re-learned from new detections.

        Args:
            camera_id: ID of the camera.
            session: Database session for deletion queries.

        Returns:
            Dictionary with counts of deleted records:
            - activity_baselines_deleted: Number of ActivityBaseline records deleted
            - class_baselines_deleted: Number of ClassBaseline records deleted
        """
        # Delete activity baselines
        activity_result = await session.execute(
            delete(ActivityBaseline).where(ActivityBaseline.camera_id == camera_id)
        )
        activity_count: int = activity_result.rowcount or 0  # type: ignore[attr-defined]

        # Delete class baselines
        class_result = await session.execute(
            delete(ClassBaseline).where(ClassBaseline.camera_id == camera_id)
        )
        class_count: int = class_result.rowcount or 0  # type: ignore[attr-defined]

        await session.commit()

        logger.info(
            f"Reset baseline for camera {camera_id}: "
            f"deleted {activity_count} activity baselines, {class_count} class baselines"
        )

        return {
            "activity_baselines_deleted": activity_count,
            "class_baselines_deleted": class_count,
        }

    def clear_camera_config(self, camera_id: str) -> None:
        """Clear per-camera configuration (revert to global defaults).

        Args:
            camera_id: ID of the camera.
        """
        if camera_id in _camera_configs:
            del _camera_configs[camera_id]
            logger.info(f"Cleared per-camera config for {camera_id}")


# Global singleton instance
baseline_config_service = BaselineConfigService()
