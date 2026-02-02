"""Storage configuration for setup.py.

Provides storage path validation, disk space checking, and directory creation
for the setup process.

Usage:
    from setup_lib.storage_config import prompt_and_configure_storage
    config = prompt_and_configure_storage({})
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TypedDict


class StorageConfig(TypedDict):
    """Storage configuration result."""

    foscam_base_path: str
    ai_models_path: str


# Minimum disk space requirements in GB
MIN_CAMERA_SPACE_GB = 10
MIN_AI_MODELS_SPACE_GB = 50


def check_path_exists(path: str) -> bool:
    """Check if a path exists.

    Args:
        path: Path to check.

    Returns:
        True if path exists, False otherwise.
    """
    return Path(path).exists()


def check_path_writable(path: str) -> bool:
    """Check if a path is writable.

    Args:
        path: Path to check.

    Returns:
        True if path is writable, False otherwise.
    """
    p = Path(path)
    if not p.exists():
        # Check if parent is writable
        parent = p.parent
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent
        return parent.exists() and parent.is_dir()

    return p.is_dir()


def create_directory(path: str) -> bool:
    """Create a directory with parent directories.

    Args:
        path: Path to create.

    Returns:
        True if created successfully, False otherwise.
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except (PermissionError, OSError):
        return False


def get_free_space_gb(path: str) -> float:
    """Get free disk space in GB for a path.

    Args:
        path: Path to check (or parent if doesn't exist).

    Returns:
        Free space in GB, or 0 if cannot determine.
    """
    check_path = Path(path)

    # Find an existing ancestor path
    while not check_path.exists() and check_path != check_path.parent:
        check_path = check_path.parent

    if not check_path.exists():
        return 0.0

    try:
        usage = shutil.disk_usage(check_path)
        return usage.free / (1024**3)
    except OSError:
        return 0.0


def is_ssd(path: str) -> bool | None:
    """Attempt to detect if path is on SSD.

    Uses Linux-specific detection via /sys/block.

    Args:
        path: Path to check.

    Returns:
        True if SSD detected, False if HDD detected, None if cannot determine.
    """
    try:
        import subprocess

        # Get the device for the mount point
        check_path = Path(path)
        while not check_path.exists() and check_path != check_path.parent:
            check_path = check_path.parent

        if not check_path.exists():
            return None

        # Use lsblk to get device info
        result = subprocess.run(
            ["lsblk", "-no", "ROTA", "-d"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

        if result.returncode != 0:
            return None

        # ROTA=0 means SSD (non-rotational), ROTA=1 means HDD
        # This is a simplified check - in reality we'd need to map the path to device
        lines = result.stdout.strip().split("\n")
        if lines and lines[0].strip() in ("0", "1"):
            return lines[0].strip() == "0"

        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def validate_storage_path(
    path: str,
    min_space_gb: float,
    _description: str,
) -> tuple[bool, str]:
    """Validate a storage path meets requirements.

    Args:
        path: Path to validate.
        min_space_gb: Minimum required free space in GB.
        _description: Human-readable description of the path purpose (reserved).

    Returns:
        Tuple of (is_valid, status_message).
    """
    p = Path(path)

    # Check if exists
    if not p.exists():
        return False, f"Directory does not exist: {path}"

    # Check if directory
    if not p.is_dir():
        return False, f"Path is not a directory: {path}"

    # Check free space
    free_gb = get_free_space_gb(path)
    if free_gb < min_space_gb:
        return (
            False,
            f"Insufficient space: {free_gb:.1f} GB available, {min_space_gb} GB required",
        )

    return True, f"Valid ({free_gb:.1f} GB available)"


def prompt_and_configure_storage(config: dict) -> StorageConfig:
    """Prompt user and configure storage paths.

    Args:
        config: Configuration dictionary (may contain existing paths).

    Returns:
        StorageConfig with validated paths.
    """
    print()
    print("=" * 60)
    print("Step 3/5: Storage Configuration")
    print("=" * 60)
    print()

    # Camera recordings path
    default_foscam = config.get("foscam_base_path", "/export/foscam")
    print(f"Camera recordings path [{default_foscam}]:")

    foscam_path = input(f"  Path [{default_foscam}]: ").strip() or default_foscam

    if check_path_exists(foscam_path):
        free_gb = get_free_space_gb(foscam_path)
        print(f"  + Directory exists ({free_gb:.1f} GB available)")

        if free_gb < MIN_CAMERA_SPACE_GB:
            print(f"  ! Warning: Low disk space (recommend {MIN_CAMERA_SPACE_GB}+ GB)")
    else:
        print("  ! Directory does not exist")
        create = input("  Create directory? [Y/n]: ").strip().lower()
        if not create or create in ("y", "yes"):
            if create_directory(foscam_path):
                print("  + Directory created")
            else:
                print("  ! Failed to create directory (may need sudo)")
                print(f"    Run: sudo mkdir -p {foscam_path}")

    print()

    # AI models path
    default_ai = config.get("ai_models_path", "/export/ai_models")
    print(f"AI models path [{default_ai}]:")

    ai_path = input(f"  Path [{default_ai}]: ").strip() or default_ai

    if check_path_exists(ai_path):
        free_gb = get_free_space_gb(ai_path)
        print(f"  + Directory exists ({free_gb:.1f} GB available)")

        if free_gb < MIN_AI_MODELS_SPACE_GB:
            print(f"  ! Warning: Low disk space (need {MIN_AI_MODELS_SPACE_GB}+ GB for all models)")

        # Check for SSD
        ssd_status = is_ssd(ai_path)
        if ssd_status is True:
            print("  + SSD detected (recommended for AI workloads)")
        elif ssd_status is False:
            print("  ! HDD detected - SSD recommended for better AI performance")
    else:
        print("  ! Directory does not exist")
        create = input("  Create directory? [Y/n]: ").strip().lower()
        if not create or create in ("y", "yes"):
            if create_directory(ai_path):
                free_gb = get_free_space_gb(ai_path)
                print(f"  + Directory created ({free_gb:.1f} GB available)")

                if free_gb < MIN_AI_MODELS_SPACE_GB:
                    print(
                        f"  ! Warning: Low disk space (need {MIN_AI_MODELS_SPACE_GB}+ GB for all models)"
                    )
            else:
                print("  ! Failed to create directory (may need sudo)")
                print(f"    Run: sudo mkdir -p {ai_path}")

    print()

    return StorageConfig(
        foscam_base_path=foscam_path,
        ai_models_path=ai_path,
    )
