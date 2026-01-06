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

    system_prompt: str = Field(..., description="Full system prompt template")
    version: int | None = Field(None, description="Version number")


class Florence2Config(BaseModel):
    """Configuration for Florence-2 scene analysis model."""

    queries: list[str] = Field(
        default_factory=list,
        description="List of queries for scene analysis",
    )


class YoloWorldConfig(BaseModel):
    """Configuration for YOLO-World custom object detection."""

    classes: list[str] = Field(
        default_factory=list,
        description="Custom object classes to detect",
    )
    confidence_threshold: float = Field(
        0.35,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for detections",
    )


class XClipConfig(BaseModel):
    """Configuration for X-CLIP action recognition model."""

    action_classes: list[str] = Field(
        default_factory=list,
        description="Action classes to recognize",
    )


class FashionClipConfig(BaseModel):
    """Configuration for Fashion-CLIP clothing analysis model."""

    clothing_categories: list[str] = Field(
        default_factory=list,
        description="Clothing categories to classify",
    )


class ModelPromptConfig(BaseModel):
    """Configuration for a specific AI model."""

    model_config = ConfigDict(from_attributes=True)

    model: AIModelEnum
    config: dict[str, Any] = Field(..., description="Model-specific configuration")
    version: int = Field(..., description="Version number of this configuration")
    created_at: datetime | None = Field(None, description="When this version was created")
    created_by: str | None = Field(None, description="Who created this version")
    change_description: str | None = Field(None, description="Description of changes")


class AllPromptsResponse(BaseModel):
    """Response containing prompts for all configurable models."""

    version: str = Field("1.0", description="Export format version")
    exported_at: datetime = Field(..., description="Export timestamp")
    prompts: dict[str, dict[str, Any]] = Field(..., description="Configuration for each model")


class PromptUpdateRequest(BaseModel):
    """Request to update a model's prompt configuration."""

    config: dict[str, Any] = Field(..., description="New configuration for the model")
    change_description: str | None = Field(None, description="Optional description of what changed")

    @field_validator("config")
    @classmethod
    def validate_config_not_empty(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Ensure config is not empty."""
        if not v:
            raise ValueError("Configuration cannot be empty")
        return v


class PromptTestRequest(BaseModel):
    """Request to test a prompt with modified configuration."""

    model: AIModelEnum = Field(..., description="Model to test")
    config: dict[str, Any] = Field(..., description="Configuration to test")
    event_id: int | None = Field(None, description="Optional event ID to test against")
    image_path: str | None = Field(None, description="Optional image path to test with")


class PromptTestResult(BaseModel):
    """Result of a prompt test."""

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

    model_config = ConfigDict(from_attributes=True)

    id: int
    model: AIModelEnum
    version: int
    created_at: datetime
    created_by: str | None
    change_description: str | None
    is_active: bool


class PromptHistoryResponse(BaseModel):
    """Response containing version history for prompts."""

    versions: list[PromptVersionInfo]
    total_count: int


class PromptRestoreRequest(BaseModel):
    """Request to restore a specific version."""

    pass


class PromptRestoreResponse(BaseModel):
    """Response after restoring a prompt version."""

    restored_version: int
    model: AIModelEnum
    new_version: int = Field(..., description="The new active version number")
    message: str


class PromptsExportResponse(BaseModel):
    """Export of all prompt configurations."""

    version: str = Field("1.0", description="Export format version")
    exported_at: datetime
    prompts: dict[str, dict[str, Any]] = Field(..., description="All model configurations")


class PromptsImportRequest(BaseModel):
    """Request to import prompt configurations."""

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

    imported_models: list[str]
    skipped_models: list[str] = Field(default_factory=list)
    new_versions: dict[str, int] = Field(
        ..., description="New version numbers for each imported model"
    )
    message: str


class PromptDiffEntry(BaseModel):
    """Diff entry for a single model's configuration."""

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
