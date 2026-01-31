"""Security utilities for enrichment-light service.

This module provides security functions for validating environment variables
and model paths to prevent security vulnerabilities.

Security issues addressed:
- NEM-4513: Validate environment variables for model paths
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class PathSecurityError(ValueError):
    """Raised when a path fails security validation."""

    pass


# Allowed model names for ENRICHMENT_PRELOAD_MODELS on light service
ALLOWED_LIGHT_PRELOAD_MODELS: frozenset[str] = frozenset(
    {
        "pose_estimator",
        "threat_detector",
        "person_reid",
        "pet_classifier",
        "depth_estimator",
    }
)

# Allowed base directories for model files
ALLOWED_MODEL_DIRECTORIES: tuple[str, ...] = (
    "/models",
    "/cache",
    "/tmp",  # noqa: S108 - intentional for temp model files during build
    "/export/ai_models",
    "/app/models",
)


def validate_preload_models_env(env_value: str) -> list[str]:
    """Validate ENRICHMENT_PRELOAD_MODELS environment variable.

    Parses and validates the comma-separated list of model names
    to ensure only allowed models are preloaded.

    Args:
        env_value: Raw environment variable value

    Returns:
        List of validated model names

    Raises:
        ValueError: If invalid model names are found
    """
    if not env_value or not env_value.strip():
        return []

    # Parse comma-separated list
    models = [m.strip() for m in env_value.split(",") if m.strip()]

    # Check for invalid model names
    invalid_models = set(models) - ALLOWED_LIGHT_PRELOAD_MODELS
    if invalid_models:
        raise ValueError(
            f"Invalid preload models: {invalid_models}. "
            f"Allowed models for light service: {sorted(ALLOWED_LIGHT_PRELOAD_MODELS)}"
        )

    return models


def validate_model_path(
    path: str | Path,
    allowed_directories: tuple[str, ...] | None = None,
    must_exist: bool = False,
) -> Path:
    """Validate a model path to prevent path traversal attacks.

    Args:
        path: The model path to validate
        allowed_directories: Tuple of allowed base directories
        must_exist: If True, verify the file exists

    Returns:
        Validated Path object

    Raises:
        PathSecurityError: If the path fails validation
    """
    if allowed_directories is None:
        allowed_directories = ALLOWED_MODEL_DIRECTORIES

    path_str = str(path)

    # Check for path traversal sequences
    if ".." in path_str:
        raise PathSecurityError(
            f"Path traversal detected in '{path_str}'. Paths containing '..' are not allowed."
        )

    # Reject paths with null bytes
    if "\x00" in path_str:
        raise PathSecurityError(f"Null byte detected in path '{path_str}'.")

    # Convert to Path and resolve
    try:
        path_obj = Path(path_str)
        resolved_path = path_obj.resolve()
    except (OSError, ValueError) as e:
        raise PathSecurityError(f"Invalid path '{path_str}': {e}") from e

    # Verify within allowed directories
    resolved_str = str(resolved_path)
    is_allowed = any(
        resolved_str.startswith(allowed_dir)
        or resolved_str.startswith(os.path.realpath(allowed_dir))
        for allowed_dir in allowed_directories
    )

    if not is_allowed:
        raise PathSecurityError(
            f"Path '{resolved_str}' is not within allowed directories: "
            f"{', '.join(allowed_directories)}"
        )

    # Verify file exists
    if must_exist and not resolved_path.exists():
        raise PathSecurityError(f"Model file does not exist: '{resolved_str}'")

    return resolved_path


def validate_model_path_env(
    env_name: str,
    env_value: str | None,
    default: str | None = None,
) -> str | None:
    """Validate a model path from an environment variable.

    Args:
        env_name: Name of the environment variable (for error messages)
        env_value: The environment variable value
        default: Default value if env_value is None or empty

    Returns:
        Validated path string, or None if empty and no default

    Raises:
        PathSecurityError: If the path fails validation
    """
    path = env_value if env_value else default
    if not path:
        return None

    try:
        validated = validate_model_path(path, must_exist=False)
        return str(validated)
    except PathSecurityError as e:
        raise PathSecurityError(f"Invalid {env_name} environment variable: {e}") from e
