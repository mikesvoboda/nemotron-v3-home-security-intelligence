"""Prompt Management Service.

Handles CRUD operations for AI model prompt configurations,
version history, import/export, and testing.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.prompt_management import AIModelEnum
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.models.prompt_version import PromptVersion
from backend.services.prompts import MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT

logger = get_logger(__name__)

# Default configurations for each model
DEFAULT_CONFIGS: dict[str, dict[str, Any]] = {
    AIModelEnum.NEMOTRON.value: {
        "system_prompt": MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
        "version": 1,
    },
    AIModelEnum.FLORENCE2.value: {
        "queries": [
            "What is the person doing?",
            "What objects are they carrying?",
            "Describe the environment",
            "Is there anything unusual in this scene?",
        ],
    },
    AIModelEnum.YOLO_WORLD.value: {
        "classes": [
            "knife",
            "gun",
            "package",
            "crowbar",
            "spray paint",
            "Amazon box",
            "FedEx package",
            "suspicious bag",
        ],
        "confidence_threshold": 0.35,
    },
    AIModelEnum.XCLIP.value: {
        "action_classes": [
            "loitering",
            "running away",
            "fighting",
            "breaking in",
            "climbing fence",
            "hiding",
            "normal walking",
        ],
    },
    AIModelEnum.FASHION_CLIP.value: {
        "clothing_categories": [
            "dark hoodie",
            "face mask",
            "gloves",
            "all black",
            "delivery uniform",
            "high-vis vest",
            "business attire",
        ],
    },
}


class PromptService:
    """Service for managing AI model prompt configurations."""

    def __init__(self) -> None:
        """Initialize the prompt service."""
        settings = get_settings()
        self._llm_url = settings.nemotron_url
        self._timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)

    async def get_all_prompts(
        self,
        session: AsyncSession,
    ) -> dict[str, dict[str, Any]]:
        """Get current active prompt configurations for all models.

        Args:
            session: Database session

        Returns:
            Dict mapping model names to their active configurations
        """
        prompts: dict[str, dict[str, Any]] = {}

        for model_enum in AIModelEnum:
            model_name = model_enum.value
            config = await self.get_prompt_for_model(session, model_name)
            prompts[model_name] = config

        return prompts

    async def get_prompt_for_model(
        self,
        session: AsyncSession,
        model: str,
    ) -> dict[str, Any]:
        """Get the active prompt configuration for a specific model.

        Args:
            session: Database session
            model: Model name (e.g., 'nemotron', 'florence2')

        Returns:
            Configuration dict for the model
        """
        # Query for active version
        result = await session.execute(
            select(PromptVersion)
            .where(
                and_(
                    PromptVersion.model == model,
                    PromptVersion.is_active == True,  # noqa: E712
                )
            )
            .order_by(PromptVersion.version.desc())
            .limit(1)
        )
        version = result.scalar_one_or_none()

        if version:
            config = version.config.copy()
            config["version"] = version.version
            return config

        # Return default config if no version exists
        return DEFAULT_CONFIGS.get(model, {}).copy()

    async def update_prompt_for_model(
        self,
        session: AsyncSession,
        model: str,
        config: dict[str, Any],
        change_description: str | None = None,
        created_by: str | None = None,
        expected_version: int | None = None,
    ) -> PromptVersion:
        """Update prompt configuration for a model, creating a new version.

        Args:
            session: Database session
            model: Model name
            config: New configuration
            change_description: Optional description of changes
            created_by: Optional user identifier
            expected_version: If provided, used for optimistic locking. The update
                will fail if the current version doesn't match.

        Returns:
            The new PromptVersion record

        Raises:
            PromptVersionConflictError: If expected_version is provided and doesn't
                match the current version (concurrent modification detected)
        """
        from backend.api.schemas.prompt_management import PromptVersionConflictError

        # Get current max version for this model
        result = await session.execute(
            select(func.max(PromptVersion.version)).where(PromptVersion.model == model)
        )
        max_version = result.scalar() or 0
        new_version = max_version + 1

        # Optimistic locking check: verify expected_version matches current version
        if expected_version is not None and max_version > 0 and expected_version != max_version:
            logger.warning(
                f"Concurrent modification detected for model {model}: "
                f"expected version {expected_version}, actual version {max_version}",
                extra={
                    "model": model,
                    "expected_version": expected_version,
                    "actual_version": max_version,
                },
            )
            raise PromptVersionConflictError(
                model=model,
                expected_version=expected_version,
                actual_version=max_version,
            )

        # Deactivate all existing versions for this model
        await session.execute(
            update(PromptVersion).where(PromptVersion.model == model).values(is_active=False)
        )

        # Create new version
        new_prompt = PromptVersion(
            model=model,
            version=new_version,
            config_json=json.dumps(config),
            change_description=change_description,
            created_by=created_by,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        session.add(new_prompt)
        await session.commit()
        await session.refresh(new_prompt)

        logger.info(
            f"Created new prompt version {new_version} for model {model}",
            extra={"model": model, "version": new_version},
        )

        return new_prompt

    async def test_prompt(
        self,
        session: AsyncSession,
        model: str,
        config: dict[str, Any],
        event_id: int | None = None,
        image_path: str | None = None,
    ) -> dict[str, Any]:
        """Test a prompt configuration against an event or image.

        Args:
            session: Database session
            model: Model name to test
            config: Configuration to test
            event_id: Optional event ID to test against
            image_path: Optional image path to test with

        Returns:
            Test results including before/after comparison
        """
        start_time = time.monotonic()
        result: dict[str, Any] = {
            "model": model,
            "before_score": None,
            "after_score": None,
            "before_response": None,
            "after_response": None,
            "improved": None,
            "test_duration_ms": 0,
            "error": None,
        }

        try:
            # For now, only support Nemotron testing
            if model != AIModelEnum.NEMOTRON.value:
                result["error"] = f"Testing for model '{model}' not yet implemented"
                result["test_duration_ms"] = int((time.monotonic() - start_time) * 1000)
                return result

            if not event_id and not image_path:
                result["error"] = "Either event_id or image_path must be provided"
                result["test_duration_ms"] = int((time.monotonic() - start_time) * 1000)
                return result

            # Get the event if provided
            if event_id:
                from backend.models.event import Event

                event_result = await session.execute(select(Event).where(Event.id == event_id))
                event = event_result.scalar_one_or_none()

                if not event:
                    result["error"] = f"Event {event_id} not found"
                    result["test_duration_ms"] = int((time.monotonic() - start_time) * 1000)
                    return result

                # Store original score
                result["before_score"] = event.risk_score

                # Get the new prompt from config
                new_prompt = config.get("system_prompt", "")
                if not new_prompt:
                    result["error"] = "system_prompt not found in config"
                    result["test_duration_ms"] = int((time.monotonic() - start_time) * 1000)
                    return result

                # Test with new prompt
                test_response = await self._run_llm_test(new_prompt, event.llm_prompt)
                result["after_response"] = test_response
                result["after_score"] = test_response.get("risk_score")

                if result["before_score"] is not None and result["after_score"] is not None:
                    # Lower score is generally better (less false positives)
                    # But this depends on context - for now just show the difference
                    result["improved"] = abs(result["after_score"] - result["before_score"]) <= 10

        except httpx.TimeoutException as e:
            logger.warning(f"Prompt test timed out for model {model}: {e}")
            result["error"] = f"Request timed out: {e}"
        except httpx.HTTPStatusError as e:
            logger.warning(f"Prompt test HTTP error for model {model}: {e}")
            result["error"] = f"HTTP error: {e}"
        except httpx.RequestError as e:
            logger.warning(f"Prompt test request failed for model {model}: {e}")
            result["error"] = f"Request failed: {e}"
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"Prompt test data error for model {model}: {e}")
            result["error"] = f"Data error: {e}"

        result["test_duration_ms"] = int((time.monotonic() - start_time) * 1000)
        return result

    async def _run_llm_test(
        self,
        system_prompt: str,
        context: str | None,
    ) -> dict[str, Any]:
        """Run LLM test with the given prompt.

        Args:
            system_prompt: The system prompt to test
            context: The context/user message

        Returns:
            LLM response as dict
        """
        if not context:
            return {"error": "No context available for testing"}

        payload = {
            "prompt": system_prompt + context,
            "temperature": 0.3,
            "top_p": 0.9,
            "max_tokens": 1024,
            "stop": ["<|im_end|>", "<|im_start|>"],
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._llm_url}/completion",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()

            content: str = result.get("content", "")

            # Try to parse JSON from response
            from backend.core.json_utils import extract_json_from_llm_response

            try:
                return extract_json_from_llm_response(content)
            except ValueError:
                return {"raw_response": content}
        except httpx.TimeoutException as e:
            return {"error": f"Request timed out: {e}"}
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error {e.response.status_code}: {e}"}
        except httpx.RequestError as e:
            return {"error": f"Request failed: {e}"}

    async def get_version_history(
        self,
        session: AsyncSession,
        model: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PromptVersion], int]:
        """Get version history for prompts.

        Args:
            session: Database session
            model: Optional model to filter by
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            Tuple of (list of versions, total count)
        """
        # Build base query
        query = select(PromptVersion)
        count_query = select(func.count(PromptVersion.id))

        if model:
            query = query.where(PromptVersion.model == model)
            count_query = count_query.where(PromptVersion.model == model)

        # Get total count
        count_result = await session.execute(count_query)
        total_count = count_result.scalar() or 0

        # Get paginated results
        query = query.order_by(PromptVersion.created_at.desc()).offset(offset).limit(limit)

        result = await session.execute(query)
        versions = list(result.scalars().all())

        return versions, total_count

    async def restore_version(
        self,
        session: AsyncSession,
        version_id: int,
    ) -> PromptVersion:
        """Restore a specific version by creating a new version with the same config.

        Args:
            session: Database session
            version_id: ID of the version to restore

        Returns:
            The new active PromptVersion

        Raises:
            ValueError: If version not found
        """
        # Get the version to restore
        result = await session.execute(select(PromptVersion).where(PromptVersion.id == version_id))
        old_version = result.scalar_one_or_none()

        if not old_version:
            raise ValueError(f"Version {version_id} not found")

        # Create a new version with the same config
        return await self.update_prompt_for_model(
            session=session,
            model=old_version.model,
            config=old_version.config,
            change_description=f"Restored from version {old_version.version}",
        )

    async def export_all_prompts(
        self,
        session: AsyncSession,
    ) -> dict[str, Any]:
        """Export all prompt configurations.

        Args:
            session: Database session

        Returns:
            Export data structure
        """
        prompts = await self.get_all_prompts(session)

        return {
            "version": "1.0",
            "exported_at": datetime.now(UTC).isoformat(),
            "prompts": prompts,
        }

    async def import_prompts(
        self,
        session: AsyncSession,
        import_data: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Import prompt configurations.

        Args:
            session: Database session
            import_data: Prompts data to import

        Returns:
            Import result with counts and new versions
        """
        imported_models: list[str] = []
        skipped_models: list[str] = []
        new_versions: dict[str, int] = {}

        valid_models = {m.value for m in AIModelEnum}

        for model_name, config in import_data.items():
            if model_name not in valid_models:
                skipped_models.append(model_name)
                logger.warning(f"Skipping unknown model: {model_name}")
                continue

            try:
                new_version = await self.update_prompt_for_model(
                    session=session,
                    model=model_name,
                    config=config,
                    change_description="Imported from JSON",
                )
                imported_models.append(model_name)
                new_versions[model_name] = new_version.version
            except Exception as e:
                logger.error(f"Failed to import config for {model_name}: {e}")
                skipped_models.append(model_name)

        return {
            "imported_models": imported_models,
            "skipped_models": skipped_models,
            "new_versions": new_versions,
            "message": f"Imported {len(imported_models)} model configurations",
        }


# Singleton instance
_prompt_service: PromptService | None = None


def get_prompt_service() -> PromptService:
    """Get or create the prompt service singleton."""
    global _prompt_service  # noqa: PLW0603
    if _prompt_service is None:
        _prompt_service = PromptService()
    return _prompt_service


def reset_prompt_service() -> None:
    """Reset the prompt service singleton (for testing)."""
    global _prompt_service  # noqa: PLW0603
    _prompt_service = None
