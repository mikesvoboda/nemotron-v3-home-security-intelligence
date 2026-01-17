"""Pydantic schemas for prompt management API endpoints."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AIModelEnum(str, Enum):
    """Supported AI models for prompt configuration."""

    NEMOTRON = "nemotron"
    FLORENCE2 = "florence2"
    YOLO_WORLD = "yolo_world"
    XCLIP = "xclip"
    FASHION_CLIP = "fashion_clip"


class NemotronConfig(BaseModel):
    """Configuration for Nemotron risk analysis model."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "system_prompt": "You are a home security AI assistant analyzing camera detections for potential risks...",
                "temperature": 0.7,
                "max_tokens": 2048,
                "version": 3,
            }
        }
    )

    system_prompt: str = Field(..., min_length=1, description="Full system prompt template")
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM generation (0-2)",
    )
    max_tokens: int = Field(
        default=2048,
        ge=1,
        le=16384,
        description="Maximum tokens for LLM response",
    )
    version: int | None = Field(None, description="Version number")

    @field_validator("system_prompt")
    @classmethod
    def validate_system_prompt_not_whitespace(cls, v: str) -> str:
        """Ensure system_prompt is not just whitespace."""
        if not v.strip():
            raise ValueError("system_prompt cannot be empty or whitespace only")
        return v


class Florence2Config(BaseModel):
    """Configuration for Florence-2 scene analysis model."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "vqa_queries": [
                    "What is this person wearing?",
                    "Is this person carrying anything?",
                    "What color is the vehicle?",
                ]
            }
        }
    )

    vqa_queries: list[str] = Field(
        ...,
        min_length=1,
        description="List of VQA queries for scene analysis",
    )

    @field_validator("vqa_queries")
    @classmethod
    def validate_queries_not_empty_strings(cls, v: list[str]) -> list[str]:
        """Ensure queries list doesn't contain empty strings."""
        if any(not q.strip() for q in v):
            raise ValueError("vqa_queries cannot contain empty or whitespace-only strings")
        return v


class YoloWorldConfig(BaseModel):
    """Configuration for YOLO-World custom object detection."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "object_classes": ["person", "car", "truck", "bicycle", "dog", "cat"],
                "confidence_threshold": 0.35,
            }
        }
    )

    object_classes: list[str] = Field(
        ...,
        min_length=1,
        description="Custom object classes to detect",
    )
    confidence_threshold: float = Field(
        0.35,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for detections",
    )

    @field_validator("object_classes")
    @classmethod
    def validate_classes_not_empty_strings(cls, v: list[str]) -> list[str]:
        """Ensure classes list doesn't contain empty strings."""
        if any(not c.strip() for c in v):
            raise ValueError("object_classes cannot contain empty or whitespace-only strings")
        return v


class XClipConfig(BaseModel):
    """Configuration for X-CLIP action recognition model."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action_classes": [
                    "walking",
                    "running",
                    "standing",
                    "sitting",
                    "driving",
                    "entering",
                ]
            }
        }
    )

    action_classes: list[str] = Field(
        ...,
        min_length=1,
        description="Action classes to recognize",
    )

    @field_validator("action_classes")
    @classmethod
    def validate_action_classes_not_empty_strings(cls, v: list[str]) -> list[str]:
        """Ensure action_classes list doesn't contain empty strings."""
        if any(not a.strip() for a in v):
            raise ValueError("action_classes cannot contain empty or whitespace-only strings")
        return v


class FashionClipConfig(BaseModel):
    """Configuration for Fashion-CLIP clothing analysis model."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "clothing_categories": ["jacket", "shirt", "pants", "shorts", "dress", "hat"],
                "suspicious_indicators": [
                    "all black",
                    "face mask",
                    "hoodie up",
                    "gloves at night",
                ],
            }
        }
    )

    clothing_categories: list[str] = Field(
        ...,
        min_length=1,
        description="Clothing categories to classify",
    )
    suspicious_indicators: list[str] = Field(
        default_factory=list,
        description="Suspicious clothing indicators to look for",
    )

    @field_validator("clothing_categories")
    @classmethod
    def validate_categories_not_empty_strings(cls, v: list[str]) -> list[str]:
        """Ensure clothing_categories list doesn't contain empty strings."""
        if any(not c.strip() for c in v):
            raise ValueError("clothing_categories cannot contain empty or whitespace-only strings")
        return v


def validate_config_for_model(model: AIModelEnum, config: dict[str, Any]) -> list[str]:
    """Validate configuration dictionary for a specific model.

    Args:
        model: The AI model type
        config: Configuration dictionary to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors: list[str] = []

    # Map models to their config schemas and required fields
    validators: dict[AIModelEnum, tuple[type[BaseModel], dict[str, str]]] = {
        AIModelEnum.NEMOTRON: (NemotronConfig, {"system_prompt": "system_prompt"}),
        AIModelEnum.FLORENCE2: (Florence2Config, {"vqa_queries": "vqa_queries"}),
        AIModelEnum.YOLO_WORLD: (YoloWorldConfig, {"object_classes": "object_classes"}),
        AIModelEnum.XCLIP: (XClipConfig, {"action_classes": "action_classes"}),
        AIModelEnum.FASHION_CLIP: (
            FashionClipConfig,
            {"clothing_categories": "clothing_categories"},
        ),
    }

    if model not in validators:
        errors.append(f"Unknown model: {model}")
        return errors

    schema_class, required_fields = validators[model]

    # Check required fields first
    for _field_name, config_key in required_fields.items():
        if config_key not in config:
            errors.append(f"Missing required field: {config_key}")

    # If required fields are present, try full validation
    if not errors:
        try:
            schema_class(**config)
        except Exception as e:
            error_msg = str(e)
            # Extract just the error message from Pydantic's verbose output
            if "validation error" in error_msg.lower():
                # Parse Pydantic v2 error format
                for line in error_msg.split("\n"):
                    if (
                        line.strip()
                        and not line.startswith(" ")
                        and "validation error" not in line.lower()
                    ):
                        errors.append(line.strip())
                if not errors:
                    errors.append(error_msg)
            else:
                errors.append(error_msg)

    return errors


class ModelPromptConfig(BaseModel):
    """Configuration for a specific AI model."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "model": "nemotron",
                "config": {
                    "system_prompt": "You are a home security AI assistant...",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
                "version": 3,
                "created_at": "2026-01-03T10:30:00Z",
                "created_by": "admin",
                "change_description": "Added weather context to prompt",
            }
        },
    )

    model: AIModelEnum
    config: dict[str, Any] = Field(..., description="Model-specific configuration")
    version: int = Field(..., description="Version number of this configuration")
    created_at: datetime | None = Field(None, description="When this version was created")
    created_by: str | None = Field(None, description="Who created this version")
    change_description: str | None = Field(None, description="Description of changes")


class AllPromptsResponse(BaseModel):
    """Response containing prompts for all configurable models."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": "1.0",
                "exported_at": "2026-01-03T10:30:00Z",
                "prompts": {
                    "nemotron": {
                        "system_prompt": "You are a home security AI assistant...",
                        "temperature": 0.7,
                        "max_tokens": 2048,
                    },
                    "florence2": {
                        "vqa_queries": [
                            "What is this person wearing?",
                            "Is this person carrying anything?",
                        ],
                    },
                },
            }
        }
    )

    version: str = Field("1.0", description="Export format version")
    exported_at: datetime = Field(..., description="Export timestamp")
    prompts: dict[str, dict[str, Any]] = Field(..., description="Configuration for each model")


class PromptUpdateRequest(BaseModel):
    """Request to update a model's prompt configuration.

    Supports optimistic locking via expected_version field to prevent
    race conditions when multiple clients update simultaneously.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "config": {
                    "system_prompt": "You are a home security AI assistant with enhanced context awareness...",
                    "temperature": 0.8,
                    "max_tokens": 2048,
                },
                "change_description": "Increased temperature for more creative responses",
                "expected_version": 3,
            }
        }
    )

    config: dict[str, Any] = Field(..., description="New configuration for the model")
    change_description: str | None = Field(None, description="Optional description of what changed")
    expected_version: int | None = Field(
        None,
        description=(
            "Expected current version for optimistic locking. "
            "If provided, the update will fail with 409 Conflict if the current version "
            "doesn't match, indicating someone else updated the config concurrently."
        ),
        ge=1,
    )

    @field_validator("config")
    @classmethod
    def validate_config_not_empty(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Ensure config is not empty."""
        if not v:
            raise ValueError("Configuration cannot be empty")
        return v


class PromptVersionConflictError(Exception):
    """Exception raised when a concurrent modification is detected.

    This occurs when using optimistic locking and the expected_version
    doesn't match the current version in the database.
    """

    def __init__(self, model: str, expected_version: int, actual_version: int):
        self.model = model
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Concurrent modification detected for model '{model}': "
            f"expected version {expected_version}, but current version is {actual_version}. "
            f"Please refresh and retry your update."
        )


class PromptTestRequest(BaseModel):
    """Request to test a prompt with modified configuration."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model": "nemotron",
                "config": {
                    "system_prompt": "You are a home security AI assistant...",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
                "event_id": 12345,
                "image_path": None,
            }
        }
    )

    model: AIModelEnum = Field(..., description="Model to test")
    config: dict[str, Any] = Field(..., description="Configuration to test")
    event_id: int | None = Field(None, description="Optional event ID to test against")
    image_path: str | None = Field(None, description="Optional image path to test with")


class PromptTestResult(BaseModel):
    """Result of a prompt test."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model": "nemotron",
                "before_score": 65,
                "after_score": 45,
                "before_response": {
                    "risk_score": 65,
                    "risk_level": "medium",
                    "summary": "Person detected at front door during evening hours",
                },
                "after_response": {
                    "risk_score": 45,
                    "risk_level": "low",
                    "summary": "Regular visitor detected - matches known delivery pattern",
                },
                "improved": True,
                "test_duration_ms": 1250,
                "error": None,
            }
        }
    )

    model: AIModelEnum
    before_score: int | None = Field(None, description="Risk score before changes")
    after_score: int | None = Field(None, description="Risk score after changes")
    before_response: dict[str, Any] | None = Field(None, description="Full response before changes")
    after_response: dict[str, Any] | None = Field(None, description="Full response after changes")
    improved: bool | None = Field(None, description="Whether the change improved results")
    test_duration_ms: int = Field(..., description="Test duration in milliseconds")
    error: str | None = Field(None, description="Error message if test failed")


class PromptVersionInfo(BaseModel):
    """Information about a single prompt version."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 15,
                "model": "nemotron",
                "version": 3,
                "created_at": "2026-01-03T10:30:00Z",
                "created_by": "admin",
                "change_description": "Added weather context to prompt",
                "is_active": True,
            }
        },
    )

    id: int
    model: AIModelEnum
    version: int
    created_at: datetime
    created_by: str | None
    change_description: str | None
    is_active: bool


class PromptHistoryResponse(BaseModel):
    """Response containing version history for prompts."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "versions": [
                    {
                        "id": 15,
                        "model": "nemotron",
                        "version": 3,
                        "created_at": "2026-01-03T10:30:00Z",
                        "created_by": "admin",
                        "change_description": "Added weather context to prompt",
                        "is_active": True,
                    },
                    {
                        "id": 12,
                        "model": "nemotron",
                        "version": 2,
                        "created_at": "2026-01-02T14:00:00Z",
                        "created_by": "system",
                        "change_description": "Initial configuration",
                        "is_active": False,
                    },
                ],
                "total_count": 3,
            }
        }
    )

    versions: list[PromptVersionInfo]
    total_count: int


class PromptRestoreRequest(BaseModel):
    """Request to restore a specific version."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "description": "Restoring to version 2 due to regression in analysis quality",
            }
        }
    )

    description: str | None = Field(
        None,
        description="Optional description for the restore action",
    )


class PromptRestoreResponse(BaseModel):
    """Response after restoring a prompt version."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "restored_version": 2,
                "model": "nemotron",
                "new_version": 4,
                "message": "Successfully restored version 2 as new version 4",
            }
        }
    )

    restored_version: int
    model: AIModelEnum
    new_version: int = Field(..., description="The new active version number")
    message: str


class PromptsExportResponse(BaseModel):
    """Export of all prompt configurations."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": "1.0",
                "exported_at": "2026-01-03T10:30:00Z",
                "prompts": {
                    "nemotron": {
                        "system_prompt": "You are a home security AI assistant...",
                        "temperature": 0.7,
                        "max_tokens": 2048,
                    },
                    "florence2": {
                        "vqa_queries": ["What is this person wearing?"],
                    },
                    "yolo_world": {
                        "object_classes": ["person", "car", "truck"],
                        "confidence_threshold": 0.35,
                    },
                },
            }
        }
    )

    version: str = Field("1.0", description="Export format version")
    exported_at: datetime
    prompts: dict[str, dict[str, Any]] = Field(..., description="All model configurations")


class PromptsImportRequest(BaseModel):
    """Request to import prompt configurations."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": "1.0",
                "prompts": {
                    "nemotron": {
                        "system_prompt": "You are a home security AI assistant...",
                        "temperature": 0.7,
                        "max_tokens": 2048,
                    },
                    "florence2": {
                        "vqa_queries": ["What is this person wearing?"],
                    },
                },
            }
        }
    )

    version: str = Field("1.0", description="Import format version")
    prompts: dict[str, dict[str, Any]] = Field(..., description="Model configurations to import")

    @field_validator("prompts")
    @classmethod
    def validate_prompts_not_empty(cls, v: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Ensure prompts dict is not empty."""
        if not v:
            raise ValueError("Prompts configuration cannot be empty")
        return v


class PromptsImportResponse(BaseModel):
    """Response after importing prompt configurations."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "imported_models": ["nemotron", "florence2"],
                "skipped_models": ["yolo_world"],
                "new_versions": {
                    "nemotron": 4,
                    "florence2": 2,
                },
                "message": "Successfully imported 2 prompt configurations, skipped 1",
            }
        }
    )

    imported_models: list[str]
    skipped_models: list[str] = Field(default_factory=list)
    new_versions: dict[str, int] = Field(
        ..., description="New version numbers for each imported model"
    )
    message: str


class PromptDiffEntry(BaseModel):
    """Diff entry for a single model's configuration."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model": "nemotron",
                "has_changes": True,
                "current_version": 3,
                "current_config": {
                    "system_prompt": "You are a home security AI...",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
                "imported_config": {
                    "system_prompt": "You are a home security AI with enhanced context...",
                    "temperature": 0.8,
                    "max_tokens": 2048,
                },
                "changes": [
                    "temperature: 0.7 -> 0.8",
                    "system_prompt: modified (length: 40 -> 55 chars)",
                ],
            }
        }
    )

    model: str = Field(..., description="Model name")
    has_changes: bool = Field(..., description="Whether there are changes")
    current_version: int | None = Field(None, description="Current version number")
    current_config: dict[str, Any] | None = Field(None, description="Current configuration")
    imported_config: dict[str, Any] = Field(..., description="Configuration to import")
    changes: list[str] = Field(
        default_factory=list,
        description="List of human-readable change descriptions",
    )


class PromptsImportPreviewRequest(BaseModel):
    """Request to preview prompt configuration import without applying."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": "1.0",
                "prompts": {
                    "nemotron": {
                        "system_prompt": "You are a home security AI assistant...",
                        "temperature": 0.8,
                        "max_tokens": 2048,
                    },
                },
            }
        }
    )

    version: str = Field("1.0", description="Import format version")
    prompts: dict[str, dict[str, Any]] = Field(..., description="Model configurations to preview")

    @field_validator("prompts")
    @classmethod
    def validate_prompts_not_empty(cls, v: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Ensure prompts dict is not empty."""
        if not v:
            raise ValueError("Prompts configuration cannot be empty")
        return v


class PromptsImportPreviewResponse(BaseModel):
    """Response with preview of import changes."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": "1.0",
                "valid": True,
                "validation_errors": [],
                "diffs": [
                    {
                        "model": "nemotron",
                        "has_changes": True,
                        "current_version": 3,
                        "current_config": {
                            "system_prompt": "You are a home security AI...",
                            "temperature": 0.7,
                        },
                        "imported_config": {
                            "system_prompt": "You are a home security AI...",
                            "temperature": 0.8,
                        },
                        "changes": ["temperature: 0.7 -> 0.8"],
                    }
                ],
                "total_changes": 1,
                "unknown_models": [],
            }
        }
    )

    version: str = Field(..., description="Import format version")
    valid: bool = Field(..., description="Whether the import data is valid")
    validation_errors: list[str] = Field(
        default_factory=list, description="List of validation errors"
    )
    diffs: list[PromptDiffEntry] = Field(
        default_factory=list, description="Diff entries for each model"
    )
    total_changes: int = Field(0, description="Total number of models with changes")
    unknown_models: list[str] = Field(default_factory=list, description="Models not recognized")


# =============================================================================
# Custom Prompt A/B Testing Schemas (migrated from ai_audit.py)
# =============================================================================


class CustomTestPromptRequest(BaseModel):
    """Request to test a custom prompt against an existing event.

    This is used for A/B testing in the Prompt Playground - testing a
    modified prompt without persisting results to the database.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": 12345,
                "custom_prompt": "You are a home security AI with enhanced context...",
                "temperature": 0.7,
                "max_tokens": 2048,
                "model": "nemotron",
            }
        }
    )

    event_id: int = Field(..., ge=1, description="Event ID to test the prompt against")
    custom_prompt: str = Field(..., min_length=1, description="Custom prompt text to test")
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM generation (0-2)",
    )
    max_tokens: int = Field(
        default=2048,
        ge=100,
        le=8192,
        description="Maximum tokens for LLM response (100-8192)",
    )
    model: str = Field(
        default="nemotron",
        description="Model to use for testing (default: nemotron)",
    )


class CustomTestPromptResponse(BaseModel):
    """Response from testing a custom prompt against an event.

    Results are NOT persisted - this is for A/B testing only.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "risk_score": 45,
                "risk_level": "low",
                "reasoning": "The detected person matches the expected delivery pattern based on time and approach direction.",
                "summary": "Delivery person detected at front door during expected hours",
                "entities": [{"type": "person", "confidence": 0.95}],
                "flags": [],
                "recommended_action": "No action required",
                "processing_time_ms": 1250,
                "tokens_used": 512,
            }
        }
    )

    risk_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Risk score from 0 (no risk) to 100 (critical)",
    )
    risk_level: str = Field(
        ...,
        description="Risk level: low, medium, high, or critical",
    )
    reasoning: str = Field(
        ...,
        description="Detailed reasoning for the risk assessment",
    )
    summary: str = Field(
        ...,
        description="Brief summary of the analysis",
    )
    entities: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Entities detected in the analysis",
    )
    flags: list[str] = Field(
        default_factory=list,
        description="Any flags raised during analysis",
    )
    recommended_action: str = Field(
        ...,
        description="Recommended action based on risk level",
    )
    processing_time_ms: int = Field(
        ...,
        ge=0,
        description="Processing time in milliseconds",
    )
    tokens_used: int = Field(
        ...,
        ge=0,
        description="Estimated tokens used for the analysis",
    )
