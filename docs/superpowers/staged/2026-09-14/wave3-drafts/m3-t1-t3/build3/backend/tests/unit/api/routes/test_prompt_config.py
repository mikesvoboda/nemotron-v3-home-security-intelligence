"""Unit tests for prompt configuration schemas.

NOTE: The database-backed /api/ai-audit/prompt-config/{model} endpoints have been
consolidated into the /api/prompts/* endpoints in prompt_management.py (NEM-2695).

This file now only contains schema validation tests.
Route tests for prompt configuration are in test_prompt_management.py.
"""

import os
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

# Set DATABASE_URL for tests before importing any backend modules
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
)

from backend.api.schemas.ai_audit import PromptConfigRequest, PromptConfigResponse


class TestPromptConfigRequestSchema:
    """Tests for PromptConfigRequest Pydantic schema."""

    def test_valid_request(self) -> None:
        """Test PromptConfigRequest with valid data."""
        request = PromptConfigRequest(
            system_prompt="Test prompt",
            temperature=0.8,
            max_tokens=4096,
        )
        assert request.system_prompt == "Test prompt"
        assert request.temperature == 0.8
        assert request.max_tokens == 4096

    def test_camel_case_alias(self) -> None:
        """Test that camelCase aliases work."""
        # Should work with camelCase (from frontend)
        request = PromptConfigRequest.model_validate(
            {
                "systemPrompt": "Test prompt",
                "temperature": 0.8,
                "maxTokens": 4096,
            }
        )
        assert request.system_prompt == "Test prompt"
        assert request.max_tokens == 4096

    def test_snake_case_also_works(self) -> None:
        """Test that snake_case also works (populate_by_name=True)."""
        request = PromptConfigRequest.model_validate(
            {
                "system_prompt": "Test prompt",
                "temperature": 0.8,
                "max_tokens": 4096,
            }
        )
        assert request.system_prompt == "Test prompt"
        assert request.max_tokens == 4096

    def test_empty_system_prompt_rejected(self) -> None:
        """Test that empty system_prompt is rejected."""
        with pytest.raises(ValidationError):
            PromptConfigRequest(
                system_prompt="",
                temperature=0.7,
                max_tokens=2048,
            )

    def test_temperature_range_validation(self) -> None:
        """Test temperature must be between 0 and 2."""
        with pytest.raises(ValidationError):
            PromptConfigRequest(
                system_prompt="Test",
                temperature=3.0,
                max_tokens=2048,
            )

    def test_max_tokens_range_validation(self) -> None:
        """Test max_tokens must be between 100 and 8192."""
        with pytest.raises(ValidationError):
            PromptConfigRequest(
                system_prompt="Test",
                temperature=0.7,
                max_tokens=50,
            )


class TestPromptConfigResponseSchema:
    """Tests for PromptConfigResponse Pydantic schema."""

    def test_valid_response(self) -> None:
        """Test PromptConfigResponse with valid data."""
        response = PromptConfigResponse(
            model="nemotron",
            system_prompt="Test prompt",
            temperature=0.8,
            max_tokens=4096,
            version=1,
            updated_at=datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC),
        )
        assert response.model == "nemotron"
        assert response.system_prompt == "Test prompt"
        assert response.version == 1

    def test_json_serialization_uses_camel_case(self) -> None:
        """Test that JSON serialization uses camelCase aliases."""
        response = PromptConfigResponse(
            model="nemotron",
            system_prompt="Test prompt",
            temperature=0.8,
            max_tokens=4096,
            version=1,
            updated_at=datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC),
        )
        data = response.model_dump(by_alias=True)
        assert "systemPrompt" in data
        assert "maxTokens" in data
        assert "updatedAt" in data
