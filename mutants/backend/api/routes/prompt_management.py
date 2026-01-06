"""API routes for prompt management.

This module provides endpoints for managing AI model prompt configurations,
including CRUD operations, version history, testing, and import/export.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.middleware.rate_limit import RateLimiter, RateLimitTier
from backend.api.schemas.prompt_management import (
    AIModelEnum,
    AllPromptsResponse,
    ModelPromptConfig,
    PromptDiffEntry,
    PromptHistoryResponse,
    PromptRestoreResponse,
    PromptsExportResponse,
    PromptsImportPreviewRequest,
    PromptsImportPreviewResponse,
    PromptsImportRequest,
    PromptsImportResponse,
    PromptTestRequest,
    PromptTestResult,
    PromptUpdateRequest,
    PromptVersionInfo,
)
from backend.core.database import get_db
from backend.services.prompt_service import get_prompt_service

router = APIRouter(prefix="/api/ai-audit/prompts", tags=["prompt-management"])


@router.get("", response_model=AllPromptsResponse)
async def get_all_prompts(
    db: AsyncSession = Depends(get_db),
) -> AllPromptsResponse:
    """Fetch current prompt configurations for all AI models.

    Returns the active prompt/configuration for each supported model:
    - nemotron: System prompt for risk analysis
    - florence2: Scene analysis queries
    - yolo_world: Custom object classes and confidence threshold
    - xclip: Action recognition classes
    - fashion_clip: Clothing categories
    """
    service = get_prompt_service()
    prompts = await service.get_all_prompts(db)

    return AllPromptsResponse(
        version="1.0",
        exported_at=datetime.now(UTC),
        prompts=prompts,
    )


@router.get("/export", response_model=PromptsExportResponse)
async def export_prompts(
    db: AsyncSession = Depends(get_db),
) -> PromptsExportResponse:
    """Export all prompt configurations as JSON.

    Returns a complete export of all model configurations suitable for
    backup, sharing, or importing into another instance.
    """
    service = get_prompt_service()
    export_data = await service.export_all_prompts(db)

    exported_at = export_data["exported_at"]
    if isinstance(exported_at, str):
        exported_at = datetime.fromisoformat(exported_at.replace("Z", "+00:00"))

    return PromptsExportResponse(
        version=export_data["version"],
        exported_at=exported_at,
        prompts=export_data["prompts"],
    )


@router.get("/history", response_model=PromptHistoryResponse)
async def get_prompt_history(
    model: AIModelEnum | None = Query(None, description="Filter by specific model"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
) -> PromptHistoryResponse:
    """Get version history for prompt configurations.

    Returns a list of all prompt versions, optionally filtered by model.
    """
    service = get_prompt_service()

    model_value = model.value if model else None
    versions, total_count = await service.get_version_history(
        session=db,
        model=model_value,
        limit=limit,
        offset=offset,
    )

    return PromptHistoryResponse(
        versions=[
            PromptVersionInfo(
                id=v.id,
                model=AIModelEnum(v.model),
                version=v.version,
                created_at=v.created_at,
                created_by=v.created_by,
                change_description=v.change_description,
                is_active=v.is_active,
            )
            for v in versions
        ],
        total_count=total_count,
    )


# Rate limiter for prompt test endpoint (AI inference is computationally expensive)
# Limit: 10 requests per minute per client with burst of 3 to prevent AI service abuse
prompt_test_rate_limiter = RateLimiter(tier=RateLimitTier.AI_INFERENCE)


@router.post("/test", response_model=PromptTestResult)
async def test_prompt(
    request: PromptTestRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(prompt_test_rate_limiter),
) -> PromptTestResult:
    """Test a modified prompt configuration against an event or image.

    Runs inference with the modified configuration and compares results
    with the original configuration.

    Rate Limited:
        This endpoint is rate limited to 10 requests per minute per client
        with a burst allowance of 3. This protects the AI services from abuse
        since prompt testing runs LLM inference which is computationally expensive.

    Returns 429 Too Many Requests if rate limit is exceeded.
    """
    service = get_prompt_service()

    result = await service.test_prompt(
        session=db,
        model=request.model.value,
        config=request.config,
        event_id=request.event_id,
        image_path=request.image_path,
    )

    return PromptTestResult(
        model=request.model,
        before_score=result.get("before_score"),
        after_score=result.get("after_score"),
        before_response=result.get("before_response"),
        after_response=result.get("after_response"),
        improved=result.get("improved"),
        test_duration_ms=result.get("test_duration_ms", 0),
        error=result.get("error"),
    )


@router.post("/import", response_model=PromptsImportResponse)
async def import_prompts(
    request: PromptsImportRequest,
    db: AsyncSession = Depends(get_db),
) -> PromptsImportResponse:
    """Import prompt configurations from JSON.

    Validates and imports configurations for each model, creating new
    versions for each imported configuration.
    """
    service = get_prompt_service()

    result = await service.import_prompts(
        session=db,
        import_data=request.prompts,
    )

    return PromptsImportResponse(
        imported_models=result["imported_models"],
        skipped_models=result["skipped_models"],
        new_versions=result["new_versions"],
        message=result["message"],
    )


def _compute_config_diff(
    current_config: dict[str, Any] | None,
    imported_config: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Compute diff between current and imported configurations."""
    changes: list[str] = []

    if current_config is None:
        return True, ["New configuration (no existing version)"]

    current = {k: v for k, v in current_config.items() if k != "version"}
    imported = {k: v for k, v in imported_config.items() if k != "version"}

    for key in imported:
        if key not in current:
            changes.append(f"Added: {key}")

    for key in current:
        if key not in imported:
            changes.append(f"Removed: {key}")

    for key in imported:  # noqa: PLC0206 - need to check against current dict
        if key in current and current[key] != imported[key]:
            if isinstance(current[key], list) and isinstance(imported[key], list):
                added = set(imported[key]) - set(current[key])
                removed = set(current[key]) - set(imported[key])
                if added:
                    changes.append(f"{key}: Added {list(added)}")
                if removed:
                    changes.append(f"{key}: Removed {list(removed)}")
            else:
                changes.append(f"Changed: {key}")

    return len(changes) > 0, changes


@router.post("/import/preview", response_model=PromptsImportPreviewResponse)
async def preview_import_prompts(
    request: PromptsImportPreviewRequest,
    db: AsyncSession = Depends(get_db),
) -> PromptsImportPreviewResponse:
    """Preview import changes without applying them.

    Validates the import data and computes diffs against current configurations.
    """
    service = get_prompt_service()
    valid_models = {m.value for m in AIModelEnum}
    validation_errors: list[str] = []
    unknown_models: list[str] = []
    diffs: list[PromptDiffEntry] = []
    total_changes = 0

    if request.version != "1.0":
        validation_errors.append(f"Unsupported version: {request.version}. Expected: 1.0")

    for model_name, imported_config in request.prompts.items():
        if model_name not in valid_models:
            unknown_models.append(model_name)
            continue

        current_config = await service.get_prompt_for_model(db, model_name)
        current_version = current_config.get("version") if current_config else None

        has_changes, change_list = _compute_config_diff(current_config, imported_config)

        if has_changes:
            total_changes += 1

        diffs.append(
            PromptDiffEntry(
                model=model_name,
                has_changes=has_changes,
                current_version=current_version,
                current_config=current_config,
                imported_config=imported_config,
                changes=change_list,
            )
        )

    return PromptsImportPreviewResponse(
        version=request.version,
        valid=len(validation_errors) == 0,
        validation_errors=validation_errors,
        diffs=diffs,
        total_changes=total_changes,
        unknown_models=unknown_models,
    )


@router.post("/history/{version_id}", response_model=PromptRestoreResponse)
async def restore_prompt_version(
    version_id: int,
    db: AsyncSession = Depends(get_db),
) -> PromptRestoreResponse:
    """Restore a specific prompt version.

    Creates a new version with the configuration from the specified version,
    making it the active configuration.
    """
    service = get_prompt_service()

    try:
        new_version = await service.restore_version(
            session=db,
            version_id=version_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    from backend.models.prompt_version import PromptVersion

    result = await db.execute(select(PromptVersion).where(PromptVersion.id == version_id))
    original = result.scalar_one_or_none()
    original_version = original.version if original else 0

    return PromptRestoreResponse(
        restored_version=original_version,
        model=AIModelEnum(new_version.model),
        new_version=new_version.version,
        message=f"Successfully restored version {original_version} as new version {new_version.version}",
    )


# Dynamic route comes AFTER all static routes to prevent path conflicts
@router.get("/{model}", response_model=ModelPromptConfig)
async def get_prompt_for_model(
    model: AIModelEnum,
    db: AsyncSession = Depends(get_db),
) -> ModelPromptConfig:
    """Fetch prompt configuration for a specific AI model."""
    service = get_prompt_service()
    config = await service.get_prompt_for_model(db, model.value)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No configuration found for model {model.value}",
        )

    version = config.pop("version", 1)

    return ModelPromptConfig(
        model=model,
        config=config,
        version=version,
        created_at=None,
        created_by=None,
        change_description=None,
    )


@router.put("/{model}", response_model=ModelPromptConfig)
async def update_prompt_for_model(
    model: AIModelEnum,
    request: PromptUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> ModelPromptConfig:
    """Update prompt configuration for a specific AI model.

    Creates a new version of the configuration while preserving history.
    """
    service = get_prompt_service()

    new_version = await service.update_prompt_for_model(
        session=db,
        model=model.value,
        config=request.config,
        change_description=request.change_description,
    )

    return ModelPromptConfig(
        model=model,
        config=new_version.config,
        version=new_version.version,
        created_at=new_version.created_at,
        created_by=new_version.created_by,
        change_description=new_version.change_description,
    )
