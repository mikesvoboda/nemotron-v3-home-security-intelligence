"""Security utilities for YOLO26 model path validation.

This module provides security functions for:
- Path traversal prevention (NEM-4501, NEM-4511)
- Environment variable validation (NEM-4513)
- Safe file deletion (NEM-4514)

These functions are duplicated from backend.core.security to avoid
cross-package dependencies between ai/ and backend/.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class PathSecurityError(ValueError):
    """Raised when a path fails security validation."""

    pass


# Allowed base directories for YOLO26 model files
ALLOWED_MODEL_DIRECTORIES: tuple[str, ...] = (
    "/models",
    "/cache",
    "/tmp",  # noqa: S108 - intentional for temp model files during build
    "/export/ai_models",
    "/app/models",
)

# Allowed file extensions for model files
ALLOWED_MODEL_EXTENSIONS: frozenset[str] = frozenset({".pt", ".pth", ".onnx", ".engine"})

# Allowed extensions for TensorRT engines
ALLOWED_ENGINE_EXTENSIONS: frozenset[str] = frozenset({".engine"})


def validate_model_path(
    path: str | Path,
    allowed_directories: tuple[str, ...] | None = None,
    allowed_extensions: frozenset[str] | None = None,
    must_exist: bool = False,
) -> Path:
    """Validate a model path to prevent path traversal attacks.

    Security checks performed:
    1. Rejects paths containing ".." (path traversal)
    2. Rejects paths containing null bytes
    3. Resolves the path to its canonical absolute form
    4. Verifies the path is within allowed directories
    5. Validates file extension
    6. Optionally verifies the file exists

    Args:
        path: The model path to validate
        allowed_directories: Tuple of allowed base directories
        allowed_extensions: Set of allowed file extensions
        must_exist: If True, verify the file exists

    Returns:
        Validated Path object

    Raises:
        PathSecurityError: If the path fails validation
    """
    if allowed_directories is None:
        allowed_directories = ALLOWED_MODEL_DIRECTORIES

    if allowed_extensions is None:
        allowed_extensions = ALLOWED_MODEL_EXTENSIONS

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

    # Validate file extension
    if allowed_extensions:
        ext = resolved_path.suffix.lower()
        if ext not in allowed_extensions:
            raise PathSecurityError(
                f"Invalid file extension '{ext}' for path '{resolved_str}'. "
                f"Allowed: {', '.join(sorted(allowed_extensions))}"
            )

    # Verify file exists
    if must_exist and not resolved_path.exists():
        raise PathSecurityError(f"Model file does not exist: '{resolved_str}'")

    return resolved_path


def is_safe_path_for_deletion(
    path: str | Path,
    allowed_directories: tuple[str, ...] | None = None,
    allowed_extensions: frozenset[str] | None = None,
) -> bool:
    """Check if a path is safe for deletion.

    Non-throwing version of validate_model_path for deletion scenarios.

    Args:
        path: The file path to check
        allowed_directories: Tuple of allowed base directories
        allowed_extensions: Set of allowed file extensions

    Returns:
        True if the path is safe to delete, False otherwise
    """
    try:
        validate_model_path(
            path,
            allowed_directories=allowed_directories,
            allowed_extensions=allowed_extensions,
            must_exist=False,
        )
        return True
    except PathSecurityError as e:
        logger.warning(f"Path failed deletion safety check: {e}")
        return False


def validate_model_path_env(
    env_name: str,
    env_value: str | None,
    default: str | None = None,
    allowed_directories: tuple[str, ...] | None = None,
    allowed_extensions: frozenset[str] | None = None,
) -> str | None:
    """Validate a model path from an environment variable.

    Args:
        env_name: Name of the environment variable (for error messages)
        env_value: The environment variable value
        default: Default value if env_value is None or empty
        allowed_directories: Tuple of allowed base directories
        allowed_extensions: Set of allowed file extensions

    Returns:
        Validated path string, or None if empty and no default

    Raises:
        PathSecurityError: If the path fails validation
    """
    path = env_value if env_value else default
    if not path:
        return None

    try:
        validated = validate_model_path(
            path,
            allowed_directories=allowed_directories,
            allowed_extensions=allowed_extensions,
            must_exist=False,
        )
        return str(validated)
    except PathSecurityError as e:
        raise PathSecurityError(f"Invalid {env_name} environment variable: {e}") from e
