"""HuggingFace Hub Cache Configuration (NEM-3812).

This module configures persistent HuggingFace Hub cache to avoid re-downloading
models on container restart. It should be imported early in the application
startup to ensure environment variables are set before any HuggingFace imports.

Configuration:
    The cache is configured via environment variables:
    - HF_HOME: Root directory for HuggingFace cache (default: /cache/huggingface)
    - HF_HUB_CACHE: Directory for Hub downloads (default: $HF_HOME/hub)
    - TRANSFORMERS_CACHE: Legacy transformers cache (default: $HF_HOME)
    - HF_DATASETS_CACHE: Datasets cache directory (default: $HF_HOME/datasets)
    - HF_HUB_OFFLINE: Enable offline mode for production (default: 0)
    - HF_HUB_DISABLE_TELEMETRY: Disable telemetry (default: 1)

Docker Volume:
    Add to docker-compose.yml:
    ```yaml
    volumes:
      - hf_cache:/cache/huggingface
    ```

Usage:
    Import this module at the top of your AI service entry point:

    ```python
    # At the very top of model.py, before other imports
    import hub_cache_config  # noqa: F401  # Configure HF cache

    from transformers import AutoModel  # Now uses configured cache
    ```

    Or call configure_hub_cache() explicitly:

    ```python
    from hub_cache_config import configure_hub_cache
    configure_hub_cache(offline_mode=True)
    ```

References:
    - NEM-3812: Configure Persistent Hub Cache
    - https://huggingface.co/docs/huggingface_hub/guides/manage-cache
    - https://huggingface.co/docs/transformers/installation#offline-mode
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Default cache directory - should be a persistent volume mount
DEFAULT_HF_HOME = "/cache/huggingface"

# Environment variable names
ENV_HF_HOME = "HF_HOME"
ENV_HF_HUB_CACHE = "HF_HUB_CACHE"
ENV_TRANSFORMERS_CACHE = "TRANSFORMERS_CACHE"
ENV_HF_DATASETS_CACHE = "HF_DATASETS_CACHE"
ENV_HF_HUB_OFFLINE = "HF_HUB_OFFLINE"
ENV_HF_HUB_DISABLE_TELEMETRY = "HF_HUB_DISABLE_TELEMETRY"


@dataclass
class HubCacheConfig:
    """HuggingFace Hub cache configuration.

    Attributes:
        hf_home: Root directory for HuggingFace cache.
        hub_cache: Directory for Hub model downloads.
        transformers_cache: Legacy transformers cache directory.
        datasets_cache: Datasets cache directory.
        offline_mode: Whether to enable offline mode (fail if not cached).
        disable_telemetry: Whether to disable HuggingFace telemetry.
    """

    hf_home: str = DEFAULT_HF_HOME
    hub_cache: str | None = None  # Defaults to $HF_HOME/hub
    transformers_cache: str | None = None  # Defaults to $HF_HOME
    datasets_cache: str | None = None  # Defaults to $HF_HOME/datasets
    offline_mode: bool = False
    disable_telemetry: bool = True


def get_current_config() -> HubCacheConfig:
    """Get current HuggingFace cache configuration from environment.

    Returns:
        HubCacheConfig with current environment settings.
    """
    hf_home = os.environ.get(ENV_HF_HOME, DEFAULT_HF_HOME)
    return HubCacheConfig(
        hf_home=hf_home,
        hub_cache=os.environ.get(ENV_HF_HUB_CACHE),
        transformers_cache=os.environ.get(ENV_TRANSFORMERS_CACHE),
        datasets_cache=os.environ.get(ENV_HF_DATASETS_CACHE),
        offline_mode=os.environ.get(ENV_HF_HUB_OFFLINE, "0").lower() in ("1", "true", "yes"),
        disable_telemetry=os.environ.get(ENV_HF_HUB_DISABLE_TELEMETRY, "1").lower()
        in ("1", "true", "yes"),
    )


def configure_hub_cache(
    config: HubCacheConfig | None = None,
    hf_home: str | None = None,
    offline_mode: bool | None = None,
    create_dirs: bool = True,
) -> HubCacheConfig:
    """Configure HuggingFace Hub cache environment variables (NEM-3812).

    This function sets environment variables for HuggingFace Hub caching.
    It should be called early in application startup, before importing
    transformers, diffusers, or other HuggingFace libraries.

    Args:
        config: Full configuration object. If provided, other args are ignored.
        hf_home: Root cache directory. Defaults to /cache/huggingface.
        offline_mode: Enable offline mode. Defaults to False.
        create_dirs: Create cache directories if they don't exist.

    Returns:
        HubCacheConfig with applied configuration.

    Example:
        >>> configure_hub_cache(hf_home="/app/models/huggingface", offline_mode=True)
        >>> from transformers import AutoModel  # Uses configured cache
    """
    if config is None:
        config = HubCacheConfig(
            hf_home=hf_home or os.environ.get(ENV_HF_HOME, DEFAULT_HF_HOME),
            offline_mode=offline_mode
            if offline_mode is not None
            else os.environ.get(ENV_HF_HUB_OFFLINE, "0").lower() in ("1", "true", "yes"),
        )

    # Set HF_HOME (root directory)
    os.environ[ENV_HF_HOME] = config.hf_home
    logger.info(f"HuggingFace cache configured: {ENV_HF_HOME}={config.hf_home}")

    # Set derived cache directories
    hub_cache = config.hub_cache or str(Path(config.hf_home) / "hub")
    os.environ[ENV_HF_HUB_CACHE] = hub_cache

    transformers_cache = config.transformers_cache or config.hf_home
    os.environ[ENV_TRANSFORMERS_CACHE] = transformers_cache

    datasets_cache = config.datasets_cache or str(Path(config.hf_home) / "datasets")
    os.environ[ENV_HF_DATASETS_CACHE] = datasets_cache

    # Set offline mode
    if config.offline_mode:
        os.environ[ENV_HF_HUB_OFFLINE] = "1"
        logger.info("HuggingFace Hub offline mode enabled")
    elif ENV_HF_HUB_OFFLINE not in os.environ:
        # Don't override if already set
        os.environ[ENV_HF_HUB_OFFLINE] = "0"

    # Disable telemetry
    if config.disable_telemetry:
        os.environ[ENV_HF_HUB_DISABLE_TELEMETRY] = "1"

    # Create directories if requested
    if create_dirs:
        _create_cache_dirs(config)

    logger.debug(
        f"HuggingFace cache configuration applied: "
        f"HF_HOME={config.hf_home}, "
        f"HF_HUB_CACHE={hub_cache}, "
        f"TRANSFORMERS_CACHE={transformers_cache}, "
        f"offline_mode={config.offline_mode}"
    )

    return config


def _create_cache_dirs(config: HubCacheConfig) -> None:
    """Create cache directories if they don't exist.

    Args:
        config: Cache configuration with directory paths.
    """
    dirs_to_create = [
        config.hf_home,
        config.hub_cache or str(Path(config.hf_home) / "hub"),
        config.datasets_cache or str(Path(config.hf_home) / "datasets"),
    ]

    for dir_path in dirs_to_create:
        try:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            logger.debug(f"Cache directory ensured: {dir_path}")
        except PermissionError:
            logger.warning(f"Cannot create cache directory (permission denied): {dir_path}")
        except OSError as e:
            logger.warning(f"Cannot create cache directory: {dir_path}: {e}")


def validate_cache_config() -> dict[str, bool]:
    """Validate that cache configuration is correct.

    Returns:
        Dict with validation results:
        - hf_home_exists: Whether HF_HOME directory exists
        - hf_home_writable: Whether HF_HOME directory is writable
        - hub_cache_exists: Whether hub cache directory exists
        - offline_mode_enabled: Whether offline mode is enabled
    """
    config = get_current_config()

    hf_home_path = Path(config.hf_home)
    hub_cache_path = Path(config.hub_cache) if config.hub_cache else hf_home_path / "hub"

    results = {
        "hf_home_exists": hf_home_path.exists(),
        "hf_home_writable": os.access(config.hf_home, os.W_OK) if hf_home_path.exists() else False,
        "hub_cache_exists": hub_cache_path.exists(),
        "offline_mode_enabled": config.offline_mode,
    }

    return results


def get_cache_stats() -> dict[str, int | str]:
    """Get statistics about the HuggingFace cache.

    Returns:
        Dict with cache statistics:
        - hf_home: Path to HF_HOME
        - total_size_mb: Total cache size in MB
        - num_models: Number of cached models (approximate)
        - offline_mode: Whether offline mode is enabled
    """
    config = get_current_config()
    hf_home_path = Path(config.hf_home)

    stats: dict[str, int | str] = {
        "hf_home": config.hf_home,
        "total_size_mb": 0,
        "num_models": 0,
        "offline_mode": "enabled" if config.offline_mode else "disabled",
    }

    if hf_home_path.exists():
        # Calculate total size
        total_size = sum(f.stat().st_size for f in hf_home_path.rglob("*") if f.is_file())
        stats["total_size_mb"] = total_size // (1024 * 1024)

        # Count models (approximate by counting model directories)
        hub_path = hf_home_path / "hub"
        if hub_path.exists():
            model_dirs = [
                d for d in hub_path.iterdir() if d.is_dir() and d.name.startswith("models--")
            ]
            stats["num_models"] = len(model_dirs)

    return stats


# Auto-configure on module import
# This ensures cache is configured before any HuggingFace imports
_auto_configured = False


def _auto_configure() -> None:
    """Auto-configure cache on first import."""
    global _auto_configured
    if not _auto_configured:
        # Only configure if HF_HOME is already set (Docker containers)
        # or create default config
        hf_home = os.environ.get(ENV_HF_HOME)
        if hf_home:
            configure_hub_cache(hf_home=hf_home, create_dirs=True)
        _auto_configured = True


# Run auto-configuration on import
_auto_configure()
