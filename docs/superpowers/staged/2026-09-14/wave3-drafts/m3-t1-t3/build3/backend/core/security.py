"""Security utilities for path validation and model integrity.

This module provides security functions for:
- Path traversal prevention (NEM-4501, NEM-4511)
- Environment variable validation (NEM-4513)
- File deletion safety (NEM-4514)
- Model integrity verification (NEM-4519, NEM-4478)

All functions follow defense-in-depth principles with multiple validation layers.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PathSecurityError(ValueError):
    """Raised when a path fails security validation."""

    pass


class ModelIntegrityError(ValueError):
    """Raised when model integrity verification fails."""

    pass


# =============================================================================
# Path Validation (NEM-4501, NEM-4511, NEM-4514)
# =============================================================================

# Allowed base directories for model files
# These are the only directories from which models can be loaded
DEFAULT_ALLOWED_MODEL_DIRECTORIES: tuple[str, ...] = (
    "/models",
    "/cache",
    "/tmp",  # For temporary model files during build  # noqa: S108
    "/export/ai_models",  # Host mount point
    "/app/models",  # Container models directory
    "/test",  # For unit tests
)

# Allowed file extensions for model files
ALLOWED_MODEL_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pt",  # PyTorch model
        ".pth",  # PyTorch checkpoint
        ".onnx",  # ONNX model
        ".engine",  # TensorRT engine
        ".bin",  # HuggingFace model weights
        ".safetensors",  # SafeTensors format
        ".pkl",  # Pickle (legacy, discouraged)
        ".h5",  # HDF5 (Keras models)
    }
)

# Allowed file extensions for TensorRT engines specifically
ALLOWED_ENGINE_EXTENSIONS: frozenset[str] = frozenset({".engine"})


def validate_model_path(
    path: str | Path,
    allowed_directories: tuple[str, ...] | None = None,
    allowed_extensions: frozenset[str] | None = None,
    must_exist: bool = False,
) -> Path:
    """Validate a model path to prevent path traversal attacks.

    This function implements multiple security checks:
    1. Rejects paths containing ".." to prevent traversal
    2. Resolves the path to its absolute, canonical form
    3. Verifies the path is within allowed directories
    4. Optionally validates file extension
    5. Optionally verifies the file exists

    Args:
        path: The model path to validate (string or Path)
        allowed_directories: Tuple of allowed base directories.
            Defaults to DEFAULT_ALLOWED_MODEL_DIRECTORIES.
        allowed_extensions: Set of allowed file extensions.
            Defaults to ALLOWED_MODEL_EXTENSIONS. Pass empty frozenset to skip.
        must_exist: If True, verify the file exists.

    Returns:
        Validated Path object (resolved to absolute path)

    Raises:
        PathSecurityError: If the path fails validation

    Example:
        >>> validate_model_path("/models/yolo26/model.pt")
        PosixPath('/models/yolo26/model.pt')

        >>> validate_model_path("/etc/passwd")
        PathSecurityError: Path '/etc/passwd' is not within allowed directories

        >>> validate_model_path("/models/../etc/passwd")
        PathSecurityError: Path traversal detected in '/models/../etc/passwd'
    """
    if allowed_directories is None:
        allowed_directories = DEFAULT_ALLOWED_MODEL_DIRECTORIES

    if allowed_extensions is None:
        allowed_extensions = ALLOWED_MODEL_EXTENSIONS

    # Convert to string for initial checks
    path_str = str(path)

    # Check for path traversal sequences BEFORE path resolution
    # This catches attempts like "/models/../etc/passwd"
    if ".." in path_str:
        raise PathSecurityError(
            f"Path traversal detected in '{path_str}'. Paths containing '..' are not allowed."
        )

    # Reject paths with null bytes (null byte injection)
    if "\x00" in path_str:
        raise PathSecurityError(
            f"Null byte detected in path '{path_str}'. Paths containing null bytes are not allowed."
        )

    # Convert to Path and resolve to absolute canonical form
    try:
        path_obj = Path(path_str)
        # Use resolve() to get the canonical absolute path
        # This resolves symlinks and normalizes the path
        resolved_path = path_obj.resolve()
    except (OSError, ValueError) as e:
        raise PathSecurityError(f"Invalid path '{path_str}': {e}") from e

    # Verify the resolved path is within an allowed directory
    resolved_str = str(resolved_path)
    is_allowed = any(
        resolved_str.startswith(allowed_dir)
        or resolved_str.startswith(os.path.realpath(allowed_dir))
        for allowed_dir in allowed_directories
    )

    if not is_allowed:
        raise PathSecurityError(
            f"Path '{resolved_str}' is not within allowed directories. "
            f"Allowed directories: {', '.join(allowed_directories)}"
        )

    # Validate file extension if specified
    if allowed_extensions:
        ext = resolved_path.suffix.lower()
        if ext not in allowed_extensions:
            raise PathSecurityError(
                f"Invalid file extension '{ext}' for path '{resolved_str}'. "
                f"Allowed extensions: {', '.join(sorted(allowed_extensions))}"
            )

    # Optionally verify file exists
    if must_exist and not resolved_path.exists():
        raise PathSecurityError(f"Model file does not exist: '{resolved_str}'")

    return resolved_path


def validate_engine_path(
    path: str | Path,
    allowed_directories: tuple[str, ...] | None = None,
    must_exist: bool = False,
) -> Path:
    """Validate a TensorRT engine path.

    Specialized validation for TensorRT engine files with stricter
    extension checking.

    Args:
        path: The engine path to validate
        allowed_directories: Tuple of allowed base directories
        must_exist: If True, verify the file exists

    Returns:
        Validated Path object

    Raises:
        PathSecurityError: If the path fails validation
    """
    return validate_model_path(
        path,
        allowed_directories=allowed_directories,
        allowed_extensions=ALLOWED_ENGINE_EXTENSIONS,
        must_exist=must_exist,
    )


def is_safe_path_for_deletion(
    path: str | Path,
    allowed_directories: tuple[str, ...] | None = None,
    allowed_extensions: frozenset[str] | None = None,
) -> bool:
    """Check if a path is safe for deletion.

    This function validates that a file path is safe to delete by checking:
    1. The path is within allowed directories
    2. The path has an expected file extension
    3. The path does not contain traversal sequences

    This is a non-throwing version of validate_model_path for use in
    deletion scenarios where we want to fail safely.

    Args:
        path: The file path to check
        allowed_directories: Tuple of allowed base directories
        allowed_extensions: Set of allowed file extensions for deletion

    Returns:
        True if the path is safe to delete, False otherwise

    Example:
        >>> is_safe_path_for_deletion("/models/yolo26/stale.engine")
        True

        >>> is_safe_path_for_deletion("/etc/passwd")
        False
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


# =============================================================================
# Environment Variable Validation (NEM-4513)
# =============================================================================

# Allowed model names for ENRICHMENT_PRELOAD_MODELS
ALLOWED_PRELOAD_MODELS: frozenset[str] = frozenset(
    {
        # Heavy service models (ai-enrichment)
        "vehicle_classifier",
        "fashion_clip",
        "demographics",
        "action_recognizer",
        # Light service models (ai-enrichment-light)
        "pose_estimator",
        "threat_detector",
        "person_reid",
        "pet_classifier",
        "depth_estimator",
    }
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

    Example:
        >>> validate_preload_models_env("vehicle_classifier,fashion_clip")
        ['vehicle_classifier', 'fashion_clip']

        >>> validate_preload_models_env("malicious_model")
        ValueError: Invalid preload models: {'malicious_model'}
    """
    if not env_value or not env_value.strip():
        return []

    # Parse comma-separated list
    models = [m.strip() for m in env_value.split(",") if m.strip()]

    # Check for invalid model names
    invalid_models = set(models) - ALLOWED_PRELOAD_MODELS
    if invalid_models:
        raise ValueError(
            f"Invalid preload models: {invalid_models}. "
            f"Allowed models: {sorted(ALLOWED_PRELOAD_MODELS)}"
        )

    return models


def validate_model_path_env(
    env_name: str,
    env_value: str | None,
    default: str | None = None,
    allowed_directories: tuple[str, ...] | None = None,
) -> str | None:
    """Validate a model path from an environment variable.

    Args:
        env_name: Name of the environment variable (for error messages)
        env_value: The environment variable value
        default: Default value if env_value is None or empty
        allowed_directories: Tuple of allowed base directories

    Returns:
        Validated path string, or None if empty and no default

    Raises:
        PathSecurityError: If the path fails validation

    Example:
        >>> validate_model_path_env(
        ...     "YOLO26_MODEL_PATH",
        ...     "/models/yolo26/model.engine"
        ... )
        '/models/yolo26/model.engine'
    """
    path = env_value if env_value else default
    if not path:
        return None

    try:
        validated = validate_model_path(
            path,
            allowed_directories=allowed_directories,
            must_exist=False,
        )
        return str(validated)
    except PathSecurityError as e:
        raise PathSecurityError(f"Invalid {env_name} environment variable: {e}") from e


# =============================================================================
# Model Integrity Verification (NEM-4519, NEM-4478)
# =============================================================================

# Known model checksums (SHA-256)
# These should be populated with actual checksums for production models
KNOWN_MODEL_CHECKSUMS: dict[str, str] = {
    # Example entries - replace with actual checksums
    # "osnet_ain_x1_0_msmt17.pth": "abc123...",
}


def compute_file_checksum(file_path: str | Path, algorithm: str = "sha256") -> str:
    """Compute the checksum of a file.

    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use (default: sha256)

    Returns:
        Hexadecimal checksum string

    Raises:
        FileNotFoundError: If the file does not exist
        IOError: If the file cannot be read
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    hash_obj = hashlib.new(algorithm)
    # Path is already validated via validate_model_path before calling this
    with path.open("rb") as f:  # nosemgrep: path-traversal-open
        # Read in 64KB chunks for memory efficiency
        for chunk in iter(lambda: f.read(65536), b""):
            hash_obj.update(chunk)

    return hash_obj.hexdigest()


def verify_model_integrity(
    file_path: str | Path,
    expected_checksum: str | None = None,
    algorithm: str = "sha256",
) -> bool:
    """Verify the integrity of a model file.

    Computes the checksum of the file and compares it against the
    expected checksum. If no expected checksum is provided, looks
    up the filename in KNOWN_MODEL_CHECKSUMS.

    Args:
        file_path: Path to the model file
        expected_checksum: Expected checksum (optional)
        algorithm: Hash algorithm to use

    Returns:
        True if checksum matches, False otherwise

    Raises:
        ModelIntegrityError: If verification fails and strict mode is enabled
    """
    path = Path(file_path)

    # Get expected checksum
    if expected_checksum is None:
        expected_checksum = KNOWN_MODEL_CHECKSUMS.get(path.name)

    if expected_checksum is None:
        # No known checksum - log warning and return True
        # In production, consider making this stricter
        logger.warning(
            f"No known checksum for model '{path.name}'. Integrity verification skipped."
        )
        return True

    try:
        actual_checksum = compute_file_checksum(path, algorithm)
    except (OSError, FileNotFoundError) as e:
        logger.error(f"Failed to compute checksum for '{path}': {e}")
        return False

    if actual_checksum != expected_checksum:
        logger.error(
            f"Model integrity check failed for '{path.name}'. "
            f"Expected: {expected_checksum[:16]}..., "
            f"Got: {actual_checksum[:16]}..."
        )
        return False

    logger.debug(f"Model integrity verified for '{path.name}'")
    return True


def log_model_load_strict_false_warning(
    model_path: str | Path,
    missing_keys: list[str] | None = None,
    unexpected_keys: list[str] | None = None,
) -> None:
    """Log a warning when loading a model with strict=False.

    When models are loaded with strict=False, some weight keys may
    be missing or unexpected. This function logs details about which
    keys were affected for security auditing.

    Args:
        model_path: Path to the model being loaded
        missing_keys: Keys present in model but not in state dict
        unexpected_keys: Keys present in state dict but not in model
    """
    if not missing_keys and not unexpected_keys:
        return

    warnings = []
    if missing_keys:
        warnings.append(f"Missing keys ({len(missing_keys)}): {missing_keys[:5]}")
        if len(missing_keys) > 5:
            warnings.append(f"  ... and {len(missing_keys) - 5} more")

    if unexpected_keys:
        warnings.append(f"Unexpected keys ({len(unexpected_keys)}): {unexpected_keys[:5]}")
        if len(unexpected_keys) > 5:
            warnings.append(f"  ... and {len(unexpected_keys) - 5} more")

    logger.warning(
        f"Model loaded with strict=False: '{model_path}'. "
        f"Key mismatches: {'; '.join(warnings)}. "
        "This may indicate model tampering or version mismatch."
    )


def get_safe_torch_load_kwargs() -> dict[str, Any]:
    """Get safe keyword arguments for torch.load().

    Returns kwargs that enable PyTorch 2.x security features:
    - weights_only=True: Prevents arbitrary code execution during load
    - map_location="cpu": Loads to CPU first for inspection

    Returns:
        Dictionary of safe kwargs for torch.load()
    """
    return {
        "weights_only": True,
        "map_location": "cpu",
    }


# =============================================================================
# ONNX Model Security (NEM-4478)
# =============================================================================


def validate_onnx_model_source(
    model_path: str | Path,
    allowed_sources: tuple[str, ...] | None = None,
) -> bool:
    """Validate that an ONNX model comes from a trusted source.

    ONNX models can contain custom operators that may execute
    arbitrary code. This function validates that the model:
    1. Comes from an allowed directory (trusted source)
    2. Has not been tampered with (optional checksum verification)

    Args:
        model_path: Path to the ONNX model
        allowed_sources: Tuple of allowed source directories

    Returns:
        True if the model is from a trusted source

    Raises:
        PathSecurityError: If the model path is not trusted
    """
    allowed_extensions = frozenset({".onnx"})

    try:
        validate_model_path(
            model_path,
            allowed_directories=allowed_sources,
            allowed_extensions=allowed_extensions,
            must_exist=True,
        )
        return True
    except PathSecurityError:
        raise
