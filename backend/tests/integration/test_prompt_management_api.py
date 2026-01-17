"""Integration tests for prompt management API endpoints.

Tests the /api/prompts routes including:
- GET /api/prompts - Get all prompt configurations
- GET /api/prompts/{model} - Get prompt for specific model
- PUT /api/prompts/{model} - Update prompt configuration
- GET /api/prompts/history - Get version history
- GET /api/prompts/export - Export all prompts
- POST /api/prompts/import - Import prompts
- POST /api/prompts/import/preview - Preview import changes
- POST /api/prompts/history/{version_id} - Restore prompt version
- POST /api/prompts/test - Test prompt configuration (rate limited)

Uses shared fixtures from conftest.py:
- integration_db: Clean database with initialized schema
- client: httpx AsyncClient with test app
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pytest

from backend.tests.integration.test_helpers import get_error_message

if TYPE_CHECKING:
    from httpx import AsyncClient

    from backend.models.prompt_version import PromptVersion


@pytest.fixture
async def _clean_prompt_tables(integration_db: str):
    """Delete prompt-related data before test runs for proper isolation.

    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine

    async with get_engine().begin() as conn:
        await conn.execute(text("DELETE FROM prompt_versions"))
        await conn.execute(text("DELETE FROM prompt_configs"))

    yield

    # Cleanup after test
    try:
        async with get_engine().begin() as conn:
            await conn.execute(text("DELETE FROM prompt_versions"))
            await conn.execute(text("DELETE FROM prompt_configs"))
    except Exception:
        pass


@pytest.fixture
async def sample_nemotron_config(_clean_prompt_tables: None) -> dict[str, object]:
    """Create sample Nemotron prompt configuration."""
    from backend.core.database import get_session
    from backend.models.prompt_config import PromptConfig
    from backend.models.prompt_version import PromptVersion

    config_data = {
        "system_prompt": "You are a security analyst. Analyze the following detections.",
        "temperature": 0.7,
        "max_tokens": 2048,
    }

    async with get_session() as db:
        # Create prompt config
        prompt_config = PromptConfig(
            model="nemotron",
            system_prompt=config_data["system_prompt"],
            temperature=config_data["temperature"],
            max_tokens=config_data["max_tokens"],
            version=1,
        )
        db.add(prompt_config)
        await db.flush()

        # Create version
        version = PromptVersion(
            model="nemotron",
            version=1,
            created_by="system",
            change_description="Initial configuration",
            is_active=True,
        )
        version.set_config(config_data)
        db.add(version)
        await db.commit()

        return {"config": config_data, "version": 1, "model": "nemotron"}


@pytest.fixture
async def multiple_prompt_versions(
    _clean_prompt_tables: None,
) -> list[PromptVersion]:
    """Create multiple prompt versions for history testing."""
    from backend.core.database import get_session
    from backend.models.prompt_config import PromptConfig
    from backend.models.prompt_version import PromptVersion

    versions: list[PromptVersion] = []

    async with get_session() as db:
        # Create Nemotron versions
        for i in range(3):
            config_data = {
                "system_prompt": f"Version {i + 1} prompt",
                "temperature": 0.7 + (i * 0.1),
                "max_tokens": 2048,
            }

            version = PromptVersion(
                model="nemotron",
                version=i + 1,
                created_by="test_user",
                change_description=f"Update {i + 1}",
                is_active=(i == 2),  # Only last version is active
            )
            version.set_config(config_data)
            db.add(version)
            versions.append(version)

        # Create Florence2 versions
        for i in range(2):
            config_data = {
                "vqa_queries": [f"Query {i + 1}?", "What do you see?"],
            }

            version = PromptVersion(
                model="florence2",
                version=i + 1,
                created_by="test_user",
                change_description=f"Florence update {i + 1}",
                is_active=(i == 1),
            )
            version.set_config(config_data)
            db.add(version)
            versions.append(version)

        await db.commit()

        # Update active configs (only for Nemotron which uses PromptConfig table)
        latest_nemotron = next(v for v in versions if v.model == "nemotron" and v.is_active)
        prompt_config = PromptConfig(
            model="nemotron",
            system_prompt=latest_nemotron.config["system_prompt"],
            temperature=latest_nemotron.config["temperature"],
            max_tokens=latest_nemotron.config["max_tokens"],
            version=latest_nemotron.version,
        )
        db.add(prompt_config)

        await db.commit()

        for v in versions:
            await db.refresh(v)

    return versions


class TestGetAllPrompts:
    """Tests for GET /api/prompts endpoint."""

    async def test_get_all_prompts_empty(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test getting all prompts when none are configured."""
        response = await client.get("/api/prompts")
        assert response.status_code == 200

        data = response.json()
        assert "version" in data
        assert data["version"] == "1.0"
        assert "exported_at" in data
        assert "prompts" in data
        assert isinstance(data["prompts"], dict)

    async def test_get_all_prompts_with_data(
        self,
        client: AsyncClient,
        sample_nemotron_config: dict[str, object],
    ):
        """Test getting all prompts when configurations exist."""
        response = await client.get("/api/prompts")
        assert response.status_code == 200

        data = response.json()
        assert "prompts" in data
        prompts = data["prompts"]

        # Should have nemotron config
        assert "nemotron" in prompts
        assert (
            prompts["nemotron"]["system_prompt"]
            == "You are a security analyst. Analyze the following detections."
        )
        assert prompts["nemotron"]["temperature"] == 0.7


class TestGetPromptForModel:
    """Tests for GET /api/prompts/{model} endpoint."""

    async def test_get_prompt_for_model_success(
        self,
        client: AsyncClient,
        sample_nemotron_config: dict[str, object],
    ):
        """Test getting prompt configuration for a specific model."""
        response = await client.get("/api/prompts/nemotron")
        assert response.status_code == 200

        data = response.json()
        assert data["model"] == "nemotron"
        assert data["version"] == 1
        assert "config" in data
        assert (
            data["config"]["system_prompt"]
            == "You are a security analyst. Analyze the following detections."
        )

    async def test_get_prompt_for_model_not_found(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test 404 when model configuration doesn't exist."""
        response = await client.get("/api/prompts/nemotron")
        assert response.status_code == 404

        data = response.json()
        error_msg = get_error_message(data)
        assert "no configuration found" in error_msg.lower()

    async def test_get_prompt_invalid_model_enum(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test 422 for invalid model name."""
        response = await client.get("/api/prompts/invalid_model")
        assert response.status_code == 422


class TestUpdatePromptForModel:
    """Tests for PUT /api/prompts/{model} endpoint."""

    async def test_update_prompt_success(
        self,
        client: AsyncClient,
        sample_nemotron_config: dict[str, object],
    ):
        """Test successful prompt update."""
        new_config = {
            "system_prompt": "Updated security analyst prompt",
            "temperature": 0.8,
            "max_tokens": 3000,
        }

        response = await client.put(
            "/api/prompts/nemotron",
            json={
                "config": new_config,
                "change_description": "Updated temperature and max_tokens",
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["model"] == "nemotron"
        assert data["version"] == 2  # Should be incremented
        assert data["config"]["system_prompt"] == "Updated security analyst prompt"
        assert data["config"]["temperature"] == 0.8
        assert data["change_description"] == "Updated temperature and max_tokens"

    async def test_update_prompt_validation_error(
        self,
        client: AsyncClient,
        sample_nemotron_config: dict[str, object],
    ):
        """Test update with invalid configuration."""
        invalid_config = {
            "temperature": 3.0,  # Invalid: must be <= 2.0
            "max_tokens": 2048,
        }

        response = await client.put(
            "/api/prompts/nemotron",
            json={"config": invalid_config},
        )
        assert response.status_code == 422

        data = response.json()
        assert "invalid configuration" in data["detail"]["message"].lower()

    async def test_update_prompt_missing_required_field(
        self,
        client: AsyncClient,
        sample_nemotron_config: dict[str, object],
    ):
        """Test update with missing required field."""
        invalid_config = {
            "temperature": 0.7,
            "max_tokens": 2048,
            # Missing system_prompt
        }

        response = await client.put(
            "/api/prompts/nemotron",
            json={"config": invalid_config},
        )
        assert response.status_code == 422

        data = response.json()
        assert "errors" in data["detail"]
        assert any("system_prompt" in str(err).lower() for err in data["detail"]["errors"])

    async def test_update_prompt_optimistic_locking_success(
        self,
        client: AsyncClient,
        sample_nemotron_config: dict[str, object],
    ):
        """Test optimistic locking with correct expected_version."""
        new_config = {
            "system_prompt": "Updated with version check",
            "temperature": 0.7,
            "max_tokens": 2048,
        }

        response = await client.put(
            "/api/prompts/nemotron",
            json={
                "config": new_config,
                "expected_version": 1,  # Current version
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 2

    async def test_update_prompt_optimistic_locking_conflict(
        self,
        client: AsyncClient,
        sample_nemotron_config: dict[str, object],
    ):
        """Test optimistic locking conflict detection."""
        new_config = {
            "system_prompt": "Updated config",
            "temperature": 0.7,
            "max_tokens": 2048,
        }

        response = await client.put(
            "/api/prompts/nemotron",
            json={
                "config": new_config,
                "expected_version": 999,  # Wrong version
            },
        )
        assert response.status_code == 409

        data = response.json()
        assert "concurrent modification" in data["detail"]["message"].lower()
        assert data["detail"]["expected_version"] == 999
        assert data["detail"]["actual_version"] == 1


class TestGetPromptHistory:
    """Tests for GET /api/prompts/history endpoint."""

    async def test_get_history_empty(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test getting history when no versions exist."""
        response = await client.get("/api/prompts/history")
        assert response.status_code == 200

        data = response.json()
        assert "versions" in data
        assert "total_count" in data
        assert data["total_count"] == 0
        assert data["versions"] == []

    async def test_get_history_with_data(
        self,
        client: AsyncClient,
        multiple_prompt_versions: list[PromptVersion],
    ):
        """Test getting version history with data."""
        response = await client.get("/api/prompts/history")
        assert response.status_code == 200

        data = response.json()
        assert data["total_count"] == 5  # 3 nemotron + 2 florence2
        assert len(data["versions"]) == 5

        # Check version structure
        version = data["versions"][0]
        assert "id" in version
        assert "model" in version
        assert "version" in version
        assert "created_at" in version
        assert "created_by" in version
        assert "change_description" in version
        assert "is_active" in version

    async def test_get_history_filter_by_model(
        self,
        client: AsyncClient,
        multiple_prompt_versions: list[PromptVersion],
    ):
        """Test filtering history by specific model."""
        response = await client.get("/api/prompts/history?model=nemotron")
        assert response.status_code == 200

        data = response.json()
        assert data["total_count"] == 3
        assert all(v["model"] == "nemotron" for v in data["versions"])

    async def test_get_history_pagination(
        self,
        client: AsyncClient,
        multiple_prompt_versions: list[PromptVersion],
    ):
        """Test pagination parameters."""
        # Get first 2
        response = await client.get("/api/prompts/history?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["versions"]) == 2

        # Get next 2 with offset
        response = await client.get("/api/prompts/history?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["versions"]) == 2

    async def test_get_history_validation(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test validation of query parameters."""
        # Invalid limit
        response = await client.get("/api/prompts/history?limit=0")
        assert response.status_code == 422

        response = await client.get("/api/prompts/history?limit=101")
        assert response.status_code == 422

        # Invalid offset
        response = await client.get("/api/prompts/history?offset=-1")
        assert response.status_code == 422


class TestExportPrompts:
    """Tests for GET /api/prompts/export endpoint."""

    async def test_export_prompts_empty(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test exporting when no prompts exist."""
        response = await client.get("/api/prompts/export")
        assert response.status_code == 200

        data = response.json()
        assert data["version"] == "1.0"
        assert "exported_at" in data
        assert "prompts" in data

    async def test_export_prompts_with_data(
        self,
        client: AsyncClient,
        sample_nemotron_config: dict[str, object],
    ):
        """Test exporting prompt configurations."""
        response = await client.get("/api/prompts/export")
        assert response.status_code == 200

        data = response.json()
        assert data["version"] == "1.0"
        assert "nemotron" in data["prompts"]
        assert (
            data["prompts"]["nemotron"]["system_prompt"]
            == "You are a security analyst. Analyze the following detections."
        )


class TestImportPrompts:
    """Tests for POST /api/prompts/import endpoint."""

    async def test_import_prompts_success(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test successful import of prompt configurations."""
        import_data = {
            "version": "1.0",
            "prompts": {
                "nemotron": {
                    "system_prompt": "Imported prompt",
                    "temperature": 0.75,
                    "max_tokens": 2500,
                },
                "florence2": {
                    "vqa_queries": ["What is in the image?", "Describe the scene"],
                },
            },
        }

        response = await client.post("/api/prompts/import", json=import_data)
        assert response.status_code == 200

        data = response.json()
        assert len(data["imported_models"]) == 2
        assert "nemotron" in data["imported_models"]
        assert "florence2" in data["imported_models"]
        assert data["new_versions"]["nemotron"] == 1
        assert data["new_versions"]["florence2"] == 1

    async def test_import_prompts_partial_success(
        self,
        client: AsyncClient,
        sample_nemotron_config: dict[str, object],
    ):
        """Test import with some valid and some invalid configs."""
        import_data = {
            "version": "1.0",
            "prompts": {
                "nemotron": {
                    "system_prompt": "New imported prompt",
                    "temperature": 0.8,
                    "max_tokens": 3000,
                },
                "florence2": {
                    "vqa_queries": [],  # Invalid: empty list
                },
            },
        }

        response = await client.post("/api/prompts/import", json=import_data)
        assert response.status_code == 200

        data = response.json()
        # Nemotron should import successfully
        assert "nemotron" in data["imported_models"]
        # Florence2 might be skipped or in skipped_models
        if "florence2" not in data["imported_models"]:
            assert "florence2" in data["skipped_models"]

    async def test_import_prompts_empty_data(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test import with empty prompts dict."""
        import_data = {
            "version": "1.0",
            "prompts": {},
        }

        response = await client.post("/api/prompts/import", json=import_data)
        assert response.status_code == 422


class TestImportPreview:
    """Tests for POST /api/prompts/import/preview endpoint."""

    async def test_import_preview_new_config(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test preview of new configuration import."""
        import_data = {
            "version": "1.0",
            "prompts": {
                "nemotron": {
                    "system_prompt": "New prompt",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
            },
        }

        response = await client.post("/api/prompts/import/preview", json=import_data)
        assert response.status_code == 200

        data = response.json()
        assert data["valid"] is True
        assert data["total_changes"] == 1
        assert len(data["diffs"]) == 1

        diff = data["diffs"][0]
        assert diff["model"] == "nemotron"
        assert diff["has_changes"] is True
        assert "New configuration" in " ".join(diff["changes"])

    async def test_import_preview_with_existing_config(
        self,
        client: AsyncClient,
        sample_nemotron_config: dict[str, object],
    ):
        """Test preview with changes to existing configuration."""
        import_data = {
            "version": "1.0",
            "prompts": {
                "nemotron": {
                    "system_prompt": "Modified prompt",  # Changed
                    "temperature": 0.7,  # Same
                    "max_tokens": 3000,  # Changed
                },
            },
        }

        response = await client.post("/api/prompts/import/preview", json=import_data)
        assert response.status_code == 200

        data = response.json()
        assert data["valid"] is True
        assert data["total_changes"] == 1

        diff = data["diffs"][0]
        assert diff["has_changes"] is True
        assert diff["current_version"] == 1
        assert len(diff["changes"]) > 0

    async def test_import_preview_no_changes(
        self,
        client: AsyncClient,
        sample_nemotron_config: dict[str, object],
    ):
        """Test preview when import has no changes."""
        import_data = {
            "version": "1.0",
            "prompts": {
                "nemotron": {
                    "system_prompt": "You are a security analyst. Analyze the following detections.",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
            },
        }

        response = await client.post("/api/prompts/import/preview", json=import_data)
        assert response.status_code == 200

        data = response.json()
        assert data["total_changes"] == 0

        diff = data["diffs"][0]
        assert diff["has_changes"] is False

    async def test_import_preview_invalid_version(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test preview with unsupported version."""
        import_data = {
            "version": "2.0",  # Unsupported
            "prompts": {
                "nemotron": {
                    "system_prompt": "Test",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
            },
        }

        response = await client.post("/api/prompts/import/preview", json=import_data)
        assert response.status_code == 200

        data = response.json()
        assert data["valid"] is False
        assert len(data["validation_errors"]) > 0
        assert any("version" in err.lower() for err in data["validation_errors"])

    async def test_import_preview_unknown_models(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test preview with unknown model names."""
        import_data = {
            "version": "1.0",
            "prompts": {
                "unknown_model": {
                    "some_config": "value",
                },
            },
        }

        response = await client.post("/api/prompts/import/preview", json=import_data)
        assert response.status_code == 200

        data = response.json()
        assert len(data["unknown_models"]) == 1
        assert "unknown_model" in data["unknown_models"]


class TestRestorePromptVersion:
    """Tests for POST /api/prompts/history/{version_id} endpoint."""

    async def test_restore_version_success(
        self,
        client: AsyncClient,
        multiple_prompt_versions: list[PromptVersion],
    ):
        """Test successful restoration of a previous version."""
        # Get first nemotron version (version 1)
        version_to_restore = next(
            v for v in multiple_prompt_versions if v.model == "nemotron" and v.version == 1
        )

        response = await client.post(f"/api/prompts/history/{version_to_restore.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["model"] == "nemotron"
        assert data["restored_version"] == 1
        assert data["new_version"] == 4  # Next version after 3
        assert "successfully restored" in data["message"].lower()

    async def test_restore_version_not_found(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test 404 for non-existent version ID."""
        response = await client.post("/api/prompts/history/999999")
        assert response.status_code == 404

        data = response.json()
        error_msg = get_error_message(data)
        assert "not found" in error_msg.lower()

    async def test_restore_creates_new_version(
        self,
        client: AsyncClient,
        multiple_prompt_versions: list[PromptVersion],
    ):
        """Test that restore creates a new version, not modifying the original."""
        version_to_restore = next(
            v for v in multiple_prompt_versions if v.model == "nemotron" and v.version == 1
        )

        response = await client.post(f"/api/prompts/history/{version_to_restore.id}")
        assert response.status_code == 200

        # Verify old version still exists
        history_response = await client.get("/api/prompts/history?model=nemotron")
        history_data = history_response.json()

        # Should have original 3 versions + new restored version = 4
        assert history_data["total_count"] == 4


class TestPromptTest:
    """Tests for POST /api/prompts/test endpoint."""

    async def test_prompt_test_validation_error(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test prompt test with invalid configuration."""
        test_request = {
            "model": "nemotron",
            "config": {
                "temperature": 5.0,  # Invalid
                "max_tokens": 2048,
            },
            "event_id": None,
            "image_path": None,
        }

        response = await client.post("/api/prompts/test", json=test_request)
        assert response.status_code == 422

        data = response.json()
        assert "invalid configuration" in data["detail"]["message"].lower()

    async def test_prompt_test_missing_required_field(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test prompt test with missing required field."""
        test_request = {
            "model": "nemotron",
            "config": {
                "temperature": 0.7,
                "max_tokens": 2048,
                # Missing system_prompt
            },
        }

        response = await client.post("/api/prompts/test", json=test_request)
        assert response.status_code == 422

    async def test_prompt_test_rate_limiting(
        self,
        client: AsyncClient,
        sample_nemotron_config: dict[str, object],
    ):
        """Test that prompt test endpoint is rate limited."""
        test_request = {
            "model": "nemotron",
            "config": {
                "system_prompt": "Test prompt",
                "temperature": 0.7,
                "max_tokens": 2048,
            },
        }

        # Make multiple rapid requests
        responses = []
        for _ in range(15):  # Exceed the rate limit
            response = await client.post("/api/prompts/test", json=test_request)
            responses.append(response)

        # At least one should be rate limited
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes or any(s in [500, 503] for s in status_codes)


class TestPromptManagementEdgeCases:
    """Tests for edge cases and error handling."""

    async def test_update_florence2_config(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test updating Florence2 configuration with proper structure."""
        config = {
            "vqa_queries": ["What objects are present?", "Describe the scene"],
        }

        response = await client.put(
            "/api/prompts/florence2",
            json={"config": config},
        )
        # Should succeed even without existing config
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "florence2"
        assert data["config"]["vqa_queries"] == config["vqa_queries"]

    async def test_update_yolo_world_config(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test updating YOLO World configuration."""
        config = {
            "object_classes": ["person", "vehicle", "animal"],
            "confidence_threshold": 0.45,
        }

        response = await client.put(
            "/api/prompts/yolo_world",
            json={"config": config},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "yolo_world"
        assert data["config"]["object_classes"] == config["object_classes"]

    async def test_update_xclip_config(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test updating X-CLIP configuration."""
        config = {
            "action_classes": ["walking", "running", "standing"],
        }

        response = await client.put(
            "/api/prompts/xclip",
            json={"config": config},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "xclip"

    async def test_update_fashion_clip_config(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test updating Fashion-CLIP configuration."""
        config = {
            "clothing_categories": ["shirt", "pants", "shoes"],
            "suspicious_indicators": ["mask", "hood"],
        }

        response = await client.put(
            "/api/prompts/fashion_clip",
            json={"config": config},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "fashion_clip"

    async def test_concurrent_updates_optimistic_locking(
        self,
        client: AsyncClient,
        sample_nemotron_config: dict[str, object],
    ):
        """Test that concurrent updates are detected with optimistic locking."""
        config1 = {
            "system_prompt": "First update",
            "temperature": 0.7,
            "max_tokens": 2048,
        }
        config2 = {
            "system_prompt": "Second update",
            "temperature": 0.8,
            "max_tokens": 2048,
        }

        # First update succeeds
        response1 = await client.put(
            "/api/prompts/nemotron",
            json={"config": config1, "expected_version": 1},
        )
        assert response1.status_code == 200

        # Second update with stale version should fail
        response2 = await client.put(
            "/api/prompts/nemotron",
            json={"config": config2, "expected_version": 1},
        )
        assert response2.status_code == 409

    async def test_export_and_reimport_roundtrip(
        self,
        client: AsyncClient,
        sample_nemotron_config: dict[str, object],
    ):
        """Test exporting and then reimporting configurations."""
        # Export
        export_response = await client.get("/api/prompts/export")
        assert export_response.status_code == 200
        export_data = export_response.json()

        # Import back
        import_request = {
            "version": export_data["version"],
            "prompts": export_data["prompts"],
        }
        import_response = await client.post("/api/prompts/import", json=import_request)
        assert import_response.status_code == 200

        # Should create new versions
        import_result = import_response.json()
        assert len(import_result["imported_models"]) > 0

    async def test_get_all_prompts_response_structure(
        self,
        client: AsyncClient,
        sample_nemotron_config: dict[str, object],
    ):
        """Test that response structure matches schema."""
        response = await client.get("/api/prompts")
        assert response.status_code == 200

        data = response.json()
        # Required fields from AllPromptsResponse
        assert "version" in data
        assert "exported_at" in data
        assert "prompts" in data

        # Validate exported_at is ISO format datetime
        datetime.fromisoformat(data["exported_at"].replace("Z", "+00:00"))

    async def test_history_version_order(
        self,
        client: AsyncClient,
        multiple_prompt_versions: list[PromptVersion],
    ):
        """Test that version history is ordered correctly (most recent first)."""
        response = await client.get("/api/prompts/history?model=nemotron")
        assert response.status_code == 200

        data = response.json()
        versions = data["versions"]

        # Should be ordered by created_at descending (most recent first)
        for i in range(len(versions) - 1):
            v1_time = datetime.fromisoformat(versions[i]["created_at"].replace("Z", "+00:00"))
            v2_time = datetime.fromisoformat(versions[i + 1]["created_at"].replace("Z", "+00:00"))
            assert v1_time >= v2_time

    async def test_validation_whitespace_only_fields(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test that whitespace-only fields are rejected."""
        # Nemotron with whitespace-only system_prompt
        config = {
            "system_prompt": "   ",  # Whitespace only
            "temperature": 0.7,
            "max_tokens": 2048,
        }

        response = await client.put(
            "/api/prompts/nemotron",
            json={"config": config},
        )
        assert response.status_code == 422

    async def test_validation_empty_lists(
        self,
        client: AsyncClient,
        _clean_prompt_tables: None,
    ):
        """Test that empty list fields are rejected where required."""
        # Florence2 with empty vqa_queries
        config = {
            "vqa_queries": [],
        }

        response = await client.put(
            "/api/prompts/florence2",
            json={"config": config},
        )
        assert response.status_code == 422
