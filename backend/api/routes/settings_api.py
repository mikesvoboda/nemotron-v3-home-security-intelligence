"""Settings API endpoints for exposing user-configurable settings.

This module provides REST API endpoints for reading and updating system settings
that are configurable by the user. Settings are grouped by category for easy
consumption by the frontend Settings UI.

Phase 2.1: GET endpoint (NEM-3119)
Phase 2.2: PATCH endpoint (NEM-3120)

Part of the Orphaned Infrastructure Integration epic (NEM-3113).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status

from backend.api.schemas.settings_api import (
    BatchSettings,
    DetectionSettings,
    FeatureSettings,
    QueueSettings,
    RateLimitingSettings,
    RetentionSettings,
    SettingsResponse,
    SettingsUpdate,
    SeveritySettings,
)
from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Mapping from schema field names to environment variable names
# Schema field -> env var name
SETTINGS_ENV_MAP: dict[str, dict[str, str]] = {
    "detection": {
        "confidence_threshold": "DETECTION_CONFIDENCE_THRESHOLD",
        "fast_path_threshold": "FAST_PATH_CONFIDENCE_THRESHOLD",
    },
    "batch": {
        "window_seconds": "BATCH_WINDOW_SECONDS",
        "idle_timeout_seconds": "BATCH_IDLE_TIMEOUT_SECONDS",
    },
    "severity": {
        "low_max": "SEVERITY_LOW_MAX",
        "medium_max": "SEVERITY_MEDIUM_MAX",
        "high_max": "SEVERITY_HIGH_MAX",
    },
    "features": {
        "vision_extraction_enabled": "VISION_EXTRACTION_ENABLED",
        "reid_enabled": "REID_ENABLED",
        "scene_change_enabled": "SCENE_CHANGE_ENABLED",
        "clip_generation_enabled": "CLIP_GENERATION_ENABLED",
        "image_quality_enabled": "IMAGE_QUALITY_ENABLED",
        "background_eval_enabled": "BACKGROUND_EVALUATION_ENABLED",
    },
    "rate_limiting": {
        "enabled": "RATE_LIMIT_ENABLED",
        "requests_per_minute": "RATE_LIMIT_REQUESTS_PER_MINUTE",
        "burst_size": "RATE_LIMIT_BURST",
    },
    "queue": {
        "max_size": "QUEUE_MAX_SIZE",
        "backpressure_threshold": "QUEUE_BACKPRESSURE_THRESHOLD",
    },
    "retention": {
        "days": "RETENTION_DAYS",
        "log_days": "LOG_RETENTION_DAYS",
    },
}

router = APIRouter(
    prefix="/api/v1/settings",
    tags=["settings"],
)


@router.get(
    "",
    response_model=SettingsResponse,
    summary="Get current system settings",
    description="Returns user-configurable settings grouped by category. "
    "These settings control detection thresholds, batch processing, "
    "severity levels, feature toggles, rate limiting, queue management, "
    "and data retention policies.",
)
async def get_user_settings() -> SettingsResponse:
    """Get current system settings (user-configurable subset).

    Returns all user-configurable settings organized into logical groups:
    - detection: Confidence thresholds for object detection
    - batch: Batch processing time windows
    - severity: Risk score thresholds for severity levels
    - features: Feature toggles for AI pipeline components
    - rate_limiting: API rate limiting configuration
    - queue: Queue size and backpressure settings
    - retention: Data retention periods

    Returns:
        SettingsResponse with all configurable settings grouped by category.
    """
    settings = get_settings()

    return SettingsResponse(
        detection=DetectionSettings(
            confidence_threshold=settings.detection_confidence_threshold,
            fast_path_threshold=settings.fast_path_confidence_threshold,
        ),
        batch=BatchSettings(
            window_seconds=settings.batch_window_seconds,
            idle_timeout_seconds=settings.batch_idle_timeout_seconds,
        ),
        severity=SeveritySettings(
            low_max=settings.severity_low_max,
            medium_max=settings.severity_medium_max,
            high_max=settings.severity_high_max,
        ),
        features=FeatureSettings(
            vision_extraction_enabled=settings.vision_extraction_enabled,
            reid_enabled=settings.reid_enabled,
            scene_change_enabled=settings.scene_change_enabled,
            clip_generation_enabled=settings.clip_generation_enabled,
            image_quality_enabled=settings.image_quality_enabled,
            background_eval_enabled=settings.background_evaluation_enabled,
        ),
        rate_limiting=RateLimitingSettings(
            enabled=settings.rate_limit_enabled,
            requests_per_minute=settings.rate_limit_requests_per_minute,
            burst_size=settings.rate_limit_burst,
        ),
        queue=QueueSettings(
            max_size=settings.queue_max_size,
            backpressure_threshold=settings.queue_backpressure_threshold,
        ),
        retention=RetentionSettings(
            days=settings.retention_days,
            log_days=settings.log_retention_days,
        ),
    )


def _get_runtime_env_path() -> Path:
    """Get the path to the runtime.env file.

    Returns:
        Path to data/runtime.env, creating the data directory if needed.
    """
    runtime_env_path = os.getenv("HSI_RUNTIME_ENV_PATH", "./data/runtime.env")
    path = Path(runtime_env_path)
    # Ensure the directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_runtime_env(path: Path) -> dict[str, str]:
    """Read existing runtime.env file into a dictionary.

    Args:
        path: Path to the runtime.env file

    Returns:
        Dictionary of environment variable name -> value pairs
    """
    env_vars: dict[str, str] = {}
    if path.exists():
        with path.open("r") as f:
            for raw_line in f:
                stripped_line = raw_line.strip()
                # Skip empty lines and comments
                if not stripped_line or stripped_line.startswith("#"):
                    continue
                # Parse KEY=value format
                if "=" in stripped_line:
                    key, _, value = stripped_line.partition("=")
                    env_vars[key.strip()] = value.strip()
    return env_vars


def _write_runtime_env(path: Path, env_vars: dict[str, str]) -> None:
    """Write environment variables to runtime.env file.

    Args:
        path: Path to the runtime.env file
        env_vars: Dictionary of environment variable name -> value pairs
    """
    with path.open("w") as f:
        f.write("# Runtime settings - auto-generated by Settings API\n")
        f.write("# Do not edit manually while the server is running\n\n")
        for key, value in sorted(env_vars.items()):
            f.write(f"{key}={value}\n")


def _validate_severity_with_current(
    update: SettingsUpdate,
    current_settings: Any,
) -> None:
    """Validate that severity thresholds maintain proper ordering with current values.

    When only some severity thresholds are being updated, we need to validate
    against the current values to ensure the final state is valid.

    Args:
        update: The SettingsUpdate being applied
        current_settings: Current Settings instance

    Raises:
        HTTPException: If severity thresholds would be invalid after update
    """
    if update.severity is None:
        return

    # Get current values
    low_max = current_settings.severity_low_max
    medium_max = current_settings.severity_medium_max
    high_max = current_settings.severity_high_max

    # Apply updates
    if update.severity.low_max is not None:
        low_max = update.severity.low_max
    if update.severity.medium_max is not None:
        medium_max = update.severity.medium_max
    if update.severity.high_max is not None:
        high_max = update.severity.high_max

    # Validate final ordering
    if low_max >= medium_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"low_max ({low_max}) must be less than medium_max ({medium_max})",
        )
    if medium_max >= high_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"medium_max ({medium_max}) must be less than high_max ({high_max})",
        )


def _extract_env_updates(update: SettingsUpdate) -> dict[str, str]:
    """Extract environment variable updates from SettingsUpdate schema.

    Args:
        update: The SettingsUpdate containing partial updates

    Returns:
        Dictionary of environment variable name -> value pairs to update
    """
    env_updates: dict[str, str] = {}

    # Process each category
    for category, field_map in SETTINGS_ENV_MAP.items():
        category_update = getattr(update, category, None)
        if category_update is None:
            continue

        # Process each field in the category
        for field_name, env_var_name in field_map.items():
            value = getattr(category_update, field_name, None)
            if value is not None:
                # Convert bool to string format expected by pydantic-settings
                if isinstance(value, bool):
                    env_updates[env_var_name] = str(value).lower()
                else:
                    env_updates[env_var_name] = str(value)

    return env_updates


@router.patch(
    "",
    response_model=SettingsResponse,
    summary="Update runtime settings",
    description="Update system settings at runtime without server restart. "
    "Changes are written to data/runtime.env and take effect immediately. "
    "All fields are optional - only provided fields will be updated.",
    responses={
        200: {"description": "Settings updated successfully"},
        422: {"description": "Validation error (e.g., invalid severity ordering)"},
        500: {"description": "Failed to write settings to runtime.env"},
    },
)
async def update_settings(update: SettingsUpdate) -> SettingsResponse:
    """Update runtime settings (writes to runtime.env, triggers reload).

    This endpoint allows partial updates to system settings. Changes are:
    1. Validated against current values (e.g., severity threshold ordering)
    2. Written to data/runtime.env file
    3. Settings cache is cleared to reload with new values

    Args:
        update: SettingsUpdate with fields to update (all fields optional)

    Returns:
        SettingsResponse with the updated settings

    Raises:
        HTTPException: 422 if validation fails (e.g., invalid severity ordering)
        HTTPException: 500 if unable to write to runtime.env
    """
    # Get current settings for validation
    current_settings = get_settings()

    # Validate severity thresholds against current values
    _validate_severity_with_current(update, current_settings)

    # Extract environment variable updates
    env_updates = _extract_env_updates(update)

    if not env_updates:
        # No updates provided, just return current settings
        logger.debug("No settings updates provided, returning current settings")
        return await get_user_settings()

    # Get runtime.env path and read existing values
    runtime_env_path = _get_runtime_env_path()

    try:
        existing_vars = _read_runtime_env(runtime_env_path)
        # Merge updates with existing values
        existing_vars.update(env_updates)
        # Write back to file
        _write_runtime_env(runtime_env_path, existing_vars)
        logger.info(
            "Updated runtime settings",
            extra={"updated_vars": list(env_updates.keys())},
        )
    except OSError as e:
        logger.error(
            "Failed to write runtime.env",
            extra={"error": str(e), "path": str(runtime_env_path)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write settings: {e}",
        ) from e

    # Clear settings cache to reload with new values
    get_settings.cache_clear()

    # Return updated settings
    return await get_user_settings()
