"""Prompt storage service for AI model configuration management.

This module provides file-based storage for AI model prompt configurations
with version history tracking. Each model's configuration is stored as JSON
with automatic versioning.

Storage Structure:
    backend/data/prompts/
        nemotron/
            current.json       - Current configuration
            history/
                v1.json        - Version 1
                v2.json        - Version 2
                ...
        florence2/
            current.json
            history/
                v1.json
                ...
        ...
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.core.logging import get_logger, sanitize_log_value
from backend.services.prompts import MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT

logger = get_logger(__name__)


def safe_parse_datetime(value: str | None, fallback: datetime | None = None) -> datetime:
    """Safely parse an ISO format datetime string.

    Handles malformed timestamps gracefully by returning a fallback value
    and logging a warning.

    Args:
        value: ISO format datetime string to parse
        fallback: Datetime to return if parsing fails (defaults to now UTC)

    Returns:
        Parsed datetime or fallback value
    """
    if fallback is None:
        fallback = datetime.now(UTC)
    if not value:
        return fallback
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        logger.warning(f"Invalid datetime format: {sanitize_log_value(value)}, using fallback")
        return fallback


# Default storage path relative to backend directory
DEFAULT_PROMPT_STORAGE_PATH = Path(__file__).parent.parent / "data" / "prompts"

# Supported model names
SUPPORTED_MODELS = frozenset({"nemotron", "florence2", "yolo_world", "xclip", "fashion_clip"})

# Default configurations for each model
DEFAULT_CONFIGS: dict[str, dict[str, Any]] = {
    "nemotron": {
        "system_prompt": MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
        "temperature": 0.7,
        "max_tokens": 2048,
    },
    "florence2": {
        "vqa_queries": [
            "What is this person wearing?",
            "What is this person carrying?",
            "What is this person doing?",
            "Is this person a service worker or delivery person?",
            "What color is this vehicle?",
            "What type of vehicle is this?",
            "Is this a commercial or personal vehicle?",
            "Are there any visible company logos or text on this vehicle?",
        ],
    },
    "yolo_world": {
        "object_classes": [
            "person",
            "car",
            "truck",
            "motorcycle",
            "bicycle",
            "dog",
            "cat",
            "backpack",
            "handbag",
            "suitcase",
            "knife",
            "baseball bat",
            "skateboard",
            "umbrella",
        ],
        "confidence_threshold": 0.5,
    },
    "xclip": {
        "action_classes": [
            "walking",
            "running",
            "standing",
            "sitting",
            "crouching",
            "crawling",
            "loitering",
            "pacing",
            "looking around",
            "photographing",
            "checking car doors",
            "breaking in",
            "climbing",
            "hiding",
            "fighting",
            "throwing",
        ],
    },
    "fashion_clip": {
        "clothing_categories": [
            "casual wear",
            "formal wear",
            "athletic wear",
            "work uniform",
            "delivery uniform",
            "all black clothing",
            "hoodie",
            "face mask",
            "sunglasses",
            "hat or cap",
            "gloves",
            "high visibility vest",
        ],
        "suspicious_indicators": [
            "all black",
            "face mask",
            "hoodie up",
            "gloves at night",
            "balaclava",
            "face covering",
        ],
    },
}


@dataclass(slots=True)
class PromptVersion:
    """A versioned prompt configuration."""

    version: int
    config: dict[str, Any]
    created_at: datetime
    created_by: str
    description: str | None


class PromptStorageService:
    """Service for managing AI model prompt configurations with versioning.

    This service provides:
    - CRUD operations for model configurations
    - Automatic version history tracking
    - Default configuration initialization
    - Import/export functionality

    All data is stored as JSON files for simplicity and portability.
    """

    def __init__(self, storage_path: Path | None = None) -> None:
        """Initialize the prompt storage service.

        Args:
            storage_path: Optional custom path for prompt storage.
                         Defaults to backend/data/prompts/
        """
        self.storage_path = storage_path or DEFAULT_PROMPT_STORAGE_PATH
        self._ensure_storage_structure()

    def _ensure_storage_structure(self) -> None:
        """Create the storage directory structure if it doesn't exist."""
        for model_name in SUPPORTED_MODELS:
            model_dir = self.storage_path / model_name
            history_dir = model_dir / "history"
            history_dir.mkdir(parents=True, exist_ok=True)

    def _get_model_dir(self, model_name: str) -> Path:
        """Get the directory for a model's configurations."""
        if model_name not in SUPPORTED_MODELS:
            logger.warning(f"Invalid model requested: {sanitize_log_value(model_name)}")
            raise ValueError(f"Unsupported model: {model_name}")
        return self.storage_path / model_name

    def _get_current_path(self, model_name: str) -> Path:
        """Get the path to the current configuration file."""
        return self._get_model_dir(model_name) / "current.json"

    def _get_history_dir(self, model_name: str) -> Path:
        """Get the history directory for a model."""
        return self._get_model_dir(model_name) / "history"

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        """Read and parse a JSON file."""
        if not path.exists():
            return None
        try:
            # nosemgrep: path-traversal-open - path is internally generated from config
            with open(path, encoding="utf-8") as f:
                result: dict[str, Any] = json.load(f)
                return result
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read {path}: {e}")
            return None

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        """Write data to a JSON file with pretty formatting."""
        path.parent.mkdir(parents=True, exist_ok=True)
        # nosemgrep: path-traversal-open - path is internally generated from config
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _get_next_version(self, model_name: str) -> int:
        """Get the next version number for a model."""
        history_dir = self._get_history_dir(model_name)
        if not history_dir.exists():
            return 1

        versions = []
        for f in history_dir.glob("v*.json"):
            try:
                version = int(f.stem[1:])  # Extract number from "vN"
                versions.append(version)
            except ValueError:
                continue

        return max(versions, default=0) + 1

    def get_config(self, model_name: str) -> dict[str, Any]:
        """Get the current configuration for a model.

        Args:
            model_name: Name of the model (nemotron, florence2, etc.)

        Returns:
            Current configuration dict, or default if none exists
        """
        current_path = self._get_current_path(model_name)
        data = self._read_json(current_path)

        if data is None:
            # Initialize with default configuration
            return self._initialize_default_config(model_name)

        config = data.get("config", DEFAULT_CONFIGS.get(model_name, {}))
        return config if isinstance(config, dict) else {}

    def get_config_with_metadata(self, model_name: str) -> dict[str, Any]:
        """Get the current configuration with version metadata.

        Args:
            model_name: Name of the model

        Returns:
            Dict containing config, version, and metadata
        """
        current_path = self._get_current_path(model_name)
        data = self._read_json(current_path)

        if data is None:
            # Initialize with default configuration
            self._initialize_default_config(model_name)
            data = self._read_json(current_path)

        return data or {
            "model_name": model_name,
            "config": DEFAULT_CONFIGS.get(model_name, {}),
            "version": 1,
            "updated_at": datetime.now(UTC).isoformat(),
        }

    def _initialize_default_config(self, model_name: str) -> dict[str, Any]:
        """Initialize a model with its default configuration.

        Args:
            model_name: Name of the model

        Returns:
            The default configuration dict
        """
        default_config = DEFAULT_CONFIGS.get(model_name, {})
        self.update_config(
            model_name=model_name,
            config=default_config,
            created_by="system",
            description="Initial default configuration",
        )
        return default_config

    def update_config(
        self,
        model_name: str,
        config: dict[str, Any],
        created_by: str = "user",
        description: str | None = None,
    ) -> PromptVersion:
        """Update a model's configuration, creating a new version.

        Args:
            model_name: Name of the model
            config: New configuration dict
            created_by: Who is making the change
            description: Optional description of the changes

        Returns:
            PromptVersion with the new version info
        """
        # Validate model name
        if model_name not in SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {model_name}")

        # Get next version number
        version = self._get_next_version(model_name)
        now = datetime.now(UTC)

        # Create version data
        version_data = {
            "model_name": model_name,
            "config": config,
            "version": version,
            "created_at": now.isoformat(),
            "created_by": created_by,
            "description": description,
            "updated_at": now.isoformat(),
        }

        # Save to history
        history_path = self._get_history_dir(model_name) / f"v{version}.json"
        self._write_json(history_path, version_data)

        # Update current
        self._write_json(self._get_current_path(model_name), version_data)

        logger.info(
            f"Updated {sanitize_log_value(model_name)} config to version {version}",
            extra={"model_name": model_name, "version": version, "created_by": created_by},
        )

        return PromptVersion(
            version=version,
            config=config,
            created_at=now,
            created_by=created_by,
            description=description,
        )

    def get_history(
        self,
        model_name: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PromptVersion]:
        """Get version history for a model.

        Args:
            model_name: Name of the model
            limit: Maximum number of versions to return
            offset: Number of versions to skip

        Returns:
            List of PromptVersion objects, newest first
        """
        history_dir = self._get_history_dir(model_name)
        if not history_dir.exists():
            return []

        # Get all version files
        version_files: list[tuple[int, Path]] = []
        for f in history_dir.glob("v*.json"):
            try:
                version = int(f.stem[1:])
                version_files.append((version, f))
            except ValueError:
                continue

        # Sort by version descending (newest first)
        version_files.sort(key=lambda x: x[0], reverse=True)

        # Apply pagination
        paginated = version_files[offset : offset + limit]

        # Load version data
        versions = []
        for version_num, path in paginated:
            data = self._read_json(path)
            if data:
                versions.append(
                    PromptVersion(
                        version=data.get("version", version_num),
                        config=data.get("config", {}),
                        created_at=safe_parse_datetime(data.get("created_at")),
                        created_by=data.get("created_by", "unknown"),
                        description=data.get("description"),
                    )
                )

        return versions

    def get_version(self, model_name: str, version: int) -> PromptVersion | None:
        """Get a specific version of a model's configuration.

        Args:
            model_name: Name of the model
            version: Version number to retrieve

        Returns:
            PromptVersion if found, None otherwise
        """
        history_path = self._get_history_dir(model_name) / f"v{version}.json"
        data = self._read_json(history_path)

        if data is None:
            return None

        return PromptVersion(
            version=data.get("version", version),
            config=data.get("config", {}),
            created_at=safe_parse_datetime(data.get("created_at")),
            created_by=data.get("created_by", "unknown"),
            description=data.get("description"),
        )

    def get_total_versions(self, model_name: str) -> int:
        """Get the total number of versions for a model.

        Args:
            model_name: Name of the model

        Returns:
            Total count of versions
        """
        history_dir = self._get_history_dir(model_name)
        if not history_dir.exists():
            return 0

        return len(list(history_dir.glob("v*.json")))

    def restore_version(
        self,
        model_name: str,
        version: int,
        created_by: str = "user",
        description: str | None = None,
    ) -> PromptVersion:
        """Restore a specific version as the current configuration.

        This creates a new version with the old configuration.

        Args:
            model_name: Name of the model
            version: Version number to restore
            created_by: Who is making the restore
            description: Optional description of the restore

        Returns:
            New PromptVersion created from the restore

        Raises:
            ValueError: If the version doesn't exist
        """
        old_version = self.get_version(model_name, version)
        if old_version is None:
            raise ValueError(f"Version {version} not found for model {model_name}")

        restore_description = description or f"Restored from version {version}"

        return self.update_config(
            model_name=model_name,
            config=old_version.config,
            created_by=created_by,
            description=restore_description,
        )

    def get_all_configs(self) -> dict[str, dict[str, Any]]:
        """Get current configurations for all models.

        Returns:
            Dict mapping model names to their current configs with metadata
        """
        configs = {}
        for model_name in SUPPORTED_MODELS:
            configs[model_name] = self.get_config_with_metadata(model_name)
        return configs

    def export_all(self) -> dict[str, Any]:
        """Export all model configurations for backup/transfer.

        Returns:
            Dict containing all configurations with export metadata
        """
        return {
            "exported_at": datetime.now(UTC).isoformat(),
            "version": "1.0",
            "prompts": {model_name: self.get_config(model_name) for model_name in SUPPORTED_MODELS},
        }

    def import_configs(
        self,
        configs: dict[str, dict[str, Any]],
        overwrite: bool = False,
        created_by: str = "import",
    ) -> dict[str, str]:
        """Import model configurations from an export.

        Args:
            configs: Dict mapping model names to their configurations
            overwrite: If True, overwrite existing configurations
            created_by: Who is performing the import

        Returns:
            Dict with import results (imported, skipped, errors)
        """
        results: dict[str, str] = {
            "imported": "",
            "skipped": "",
            "errors": "",
        }
        imported: list[str] = []
        skipped: list[str] = []
        errors: list[str] = []

        for model_name, config in configs.items():
            if model_name not in SUPPORTED_MODELS:
                errors.append(f"{model_name}: Unsupported model")
                continue

            # Check if config exists and we're not overwriting
            current_path = self._get_current_path(model_name)
            if current_path.exists() and not overwrite:
                skipped.append(model_name)
                continue

            try:
                self.update_config(
                    model_name=model_name,
                    config=config,
                    created_by=created_by,
                    description="Imported configuration",
                )
                imported.append(model_name)
            except Exception as e:
                errors.append(f"{model_name}: {e!s}")

        results["imported"] = ", ".join(imported) if imported else "none"
        results["skipped"] = ", ".join(skipped) if skipped else "none"
        results["errors"] = "; ".join(errors) if errors else "none"

        return results

    def _validate_required_string(
        self, config: dict[str, Any], field: str, errors: list[str]
    ) -> None:
        """Validate a required string field."""
        if field not in config:
            errors.append(f"Missing required field: {field}")
        elif not isinstance(config[field], str):
            errors.append(f"{field} must be a string")

    def _validate_required_list(
        self, config: dict[str, Any], field: str, item_name: str, errors: list[str]
    ) -> None:
        """Validate a required non-empty list field."""
        if field not in config:
            errors.append(f"Missing required field: {field}")
        elif not isinstance(config[field], list):
            errors.append(f"{field} must be a list")
        elif len(config[field]) == 0:
            errors.append(f"{field} must have at least one {item_name}")

    def _validate_number_range(
        self,
        config: dict[str, Any],
        field: str,
        min_val: float,
        max_val: float,
        errors: list[str],
    ) -> None:
        """Validate an optional number field is within range."""
        if field in config:
            val = config[field]
            if not isinstance(val, int | float) or val < min_val or val > max_val:
                errors.append(f"{field} must be a number between {min_val} and {max_val}")

    def validate_config(self, model_name: str, config: dict[str, Any]) -> list[str]:
        """Validate a configuration for a model.

        Args:
            model_name: Name of the model
            config: Configuration to validate

        Returns:
            List of validation errors (empty if valid)
        """
        if model_name not in SUPPORTED_MODELS:
            return [f"Unsupported model: {model_name}"]

        errors: list[str] = []

        # Dispatch to model-specific validators
        validators: dict[str, tuple[str, str] | None] = {
            "nemotron": None,  # Special handling
            "florence2": ("vqa_queries", "query"),
            "yolo_world": None,  # Special handling (has threshold)
            "xclip": ("action_classes", "class"),
            "fashion_clip": ("clothing_categories", "category"),
        }

        if model_name == "nemotron":
            self._validate_required_string(config, "system_prompt", errors)
            self._validate_number_range(config, "temperature", 0, 2, errors)
        elif model_name == "yolo_world":
            self._validate_required_list(config, "object_classes", "class", errors)
            self._validate_number_range(config, "confidence_threshold", 0, 1, errors)
        elif model_name in validators:
            validator_config = validators[model_name]
            if validator_config is not None:
                field, item_name = validator_config
                self._validate_required_list(config, field, item_name, errors)

        return errors

    async def run_mock_test(
        self,
        model_name: str,
        config: dict[str, Any],
        event_id: int,
    ) -> dict[str, Any]:
        """Run a mock test of a configuration against an event.

        This simulates running the AI models with the modified config
        and returns mock before/after results for comparison.

        In production, this would call the actual AI services.
        For now, it returns mock data to demonstrate the API.

        Args:
            model_name: Name of the model to test
            config: Modified configuration to test
            event_id: Event ID to test against

        Returns:
            Dict with before/after comparison results
        """
        # Validate the config first
        validation_errors = self.validate_config(model_name, config)
        if validation_errors:
            raise ValueError(f"Invalid configuration: {'; '.join(validation_errors)}")

        # Mock before/after results
        # In production, these would come from actual AI inference
        start_time = time.time()

        # Simulate some processing time using non-blocking asyncio.sleep
        import random

        await asyncio.sleep(random.uniform(0.05, 0.15))  # noqa: S311

        # Generate mock results based on model type
        before_score = random.randint(30, 70)  # noqa: S311  # nosemgrep: insecure-random
        after_score = random.randint(20, 60)  # noqa: S311  # nosemgrep: insecure-random

        def _score_to_level(score: int) -> str:
            if score < 30:
                return "low"
            elif score < 60:
                return "medium"
            elif score < 85:
                return "high"
            return "critical"

        inference_time_ms = int((time.time() - start_time) * 1000)

        return {
            "before": {
                "score": before_score,
                "risk_level": _score_to_level(before_score),
                "summary": f"Mock analysis with original {model_name} config for event {event_id}",
            },
            "after": {
                "score": after_score,
                "risk_level": _score_to_level(after_score),
                "summary": f"Mock analysis with modified {model_name} config for event {event_id}",
            },
            "improved": after_score < before_score,
            "inference_time_ms": inference_time_ms,
        }


# Global singleton instance
_prompt_storage: PromptStorageService | None = None


def get_prompt_storage() -> PromptStorageService:
    """Get the global prompt storage service instance.

    Returns:
        PromptStorageService singleton
    """
    global _prompt_storage  # noqa: PLW0603
    if _prompt_storage is None:
        _prompt_storage = PromptStorageService()
    return _prompt_storage


def reset_prompt_storage() -> None:
    """Reset the global prompt storage service (for testing)."""
    global _prompt_storage  # noqa: PLW0603
    _prompt_storage = None
