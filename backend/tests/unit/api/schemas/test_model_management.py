"""Unit tests for Model Management API schemas.

Tests for the Pydantic schemas defined in backend/api/schemas/model_management.py.
These schemas support the Model Zoo Management API endpoints.

Related Issues:
    - NEM-4780: Model Zoo Management Epic
    - NEM-4782: Backend API endpoint unit tests (TDD RED phase)

Design Document:
    See docs/plans/2025-01-31-model-zoo-management-design.md
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.model_management import (
    LoadModelResponse,
    ModelCategory,
    ModelDetailResponse,
    ModelListResponse,
    ModelRuntimeInfo,
    ModelStatus,
    ServiceName,
    ServiceStatus,
    UnloadAllResponse,
    UnloadModelResponse,
    VramGpuInfo,
    VramSummaryResponse,
    VramTotals,
)

# =============================================================================
# ModelRuntimeInfo Tests
# =============================================================================


class TestModelRuntimeInfo:
    """Tests for ModelRuntimeInfo schema."""

    def test_model_runtime_info_loaded(self) -> None:
        """ModelRuntimeInfo should accept valid loaded state."""
        runtime = ModelRuntimeInfo(
            loaded=True,
            actual_vram_mb=287,
            last_used=datetime(2025, 1, 31, 10, 30, 0, tzinfo=UTC),
            load_count=5,
        )
        assert runtime.loaded is True
        assert runtime.actual_vram_mb == 287
        assert runtime.load_count == 5
        assert runtime.last_used is not None

    def test_model_runtime_info_not_loaded(self) -> None:
        """ModelRuntimeInfo should accept valid unloaded state."""
        runtime = ModelRuntimeInfo(
            loaded=False,
            actual_vram_mb=None,
            last_used=None,
            load_count=0,
        )
        assert runtime.loaded is False
        assert runtime.actual_vram_mb is None
        assert runtime.last_used is None
        assert runtime.load_count == 0

    def test_model_runtime_info_default_load_count(self) -> None:
        """ModelRuntimeInfo should default load_count to 0."""
        runtime = ModelRuntimeInfo(loaded=False)
        assert runtime.load_count == 0

    def test_model_runtime_info_rejects_negative_vram(self) -> None:
        """ModelRuntimeInfo should reject negative VRAM values."""
        with pytest.raises(ValidationError):
            ModelRuntimeInfo(loaded=True, actual_vram_mb=-100)

    def test_model_runtime_info_rejects_negative_load_count(self) -> None:
        """ModelRuntimeInfo should reject negative load count."""
        with pytest.raises(ValidationError):
            ModelRuntimeInfo(loaded=True, load_count=-1)

    def test_model_runtime_info_serialization(self) -> None:
        """ModelRuntimeInfo should serialize to expected JSON format."""
        timestamp = datetime(2025, 1, 31, 10, 30, 0, tzinfo=UTC)
        runtime = ModelRuntimeInfo(
            loaded=True,
            actual_vram_mb=287,
            last_used=timestamp,
            load_count=5,
        )
        data = runtime.model_dump()
        assert data["loaded"] is True
        assert data["actual_vram_mb"] == 287
        assert data["load_count"] == 5
        assert "last_used" in data

    def test_model_runtime_info_json_schema_example(self) -> None:
        """ModelRuntimeInfo should have a valid JSON schema example."""
        schema = ModelRuntimeInfo.model_json_schema()
        assert "example" in schema
        assert schema["example"]["loaded"] is True


# =============================================================================
# ModelStatus Tests
# =============================================================================


class TestModelStatus:
    """Tests for ModelStatus schema."""

    def test_model_status_schema_validation(self) -> None:
        """ModelStatus should validate all required fields correctly."""
        runtime = ModelRuntimeInfo(loaded=True, actual_vram_mb=287, load_count=5)
        status = ModelStatus(
            name="threat-detection-yolov8n",
            category="detection",
            estimated_vram_mb=300,
            enabled=True,
            service="ai-enrichment-light",
            gpu_id=1,
            runtime=runtime,
        )
        assert status.name == "threat-detection-yolov8n"
        assert status.category == "detection"
        assert status.estimated_vram_mb == 300
        assert status.enabled is True
        assert status.service == "ai-enrichment-light"
        assert status.gpu_id == 1
        assert status.runtime.loaded is True

    def test_model_status_rejects_empty_name(self) -> None:
        """ModelStatus should reject empty model name."""
        runtime = ModelRuntimeInfo(loaded=False)
        with pytest.raises(ValidationError):
            ModelStatus(
                name="",
                category="detection",
                estimated_vram_mb=300,
                enabled=True,
                service="ai-enrichment",
                gpu_id=0,
                runtime=runtime,
            )

    def test_model_status_rejects_negative_vram(self) -> None:
        """ModelStatus should reject negative VRAM estimates."""
        runtime = ModelRuntimeInfo(loaded=False)
        with pytest.raises(ValidationError):
            ModelStatus(
                name="test-model",
                category="detection",
                estimated_vram_mb=-100,
                enabled=True,
                service="ai-enrichment",
                gpu_id=0,
                runtime=runtime,
            )

    def test_model_status_rejects_negative_gpu_id(self) -> None:
        """ModelStatus should reject negative GPU ID."""
        runtime = ModelRuntimeInfo(loaded=False)
        with pytest.raises(ValidationError):
            ModelStatus(
                name="test-model",
                category="detection",
                estimated_vram_mb=300,
                enabled=True,
                service="ai-enrichment",
                gpu_id=-1,
                runtime=runtime,
            )

    def test_model_status_serialization(self) -> None:
        """ModelStatus should serialize to expected JSON format."""
        runtime = ModelRuntimeInfo(loaded=False, load_count=0)
        status = ModelStatus(
            name="vehicle-segment-classification",
            category="classification",
            estimated_vram_mb=1500,
            enabled=True,
            service="ai-enrichment",
            gpu_id=0,
            runtime=runtime,
        )
        data = status.model_dump()
        assert data["name"] == "vehicle-segment-classification"
        assert data["category"] == "classification"
        assert data["estimated_vram_mb"] == 1500
        assert data["enabled"] is True
        assert data["service"] == "ai-enrichment"
        assert data["gpu_id"] == 0
        assert data["runtime"]["loaded"] is False

    def test_model_status_json_schema_example(self) -> None:
        """ModelStatus should have a valid JSON schema example."""
        schema = ModelStatus.model_json_schema()
        assert "example" in schema
        assert schema["example"]["name"] == "threat-detection-yolov8n"


# =============================================================================
# ModelListResponse Tests
# =============================================================================


class TestModelListResponse:
    """Tests for ModelListResponse schema."""

    def test_model_list_response_with_models(self) -> None:
        """ModelListResponse should accept list of models with service status."""
        runtime1 = ModelRuntimeInfo(loaded=True, actual_vram_mb=287, load_count=5)
        runtime2 = ModelRuntimeInfo(loaded=False, load_count=0)

        model1 = ModelStatus(
            name="threat-detection-yolov8n",
            category="detection",
            estimated_vram_mb=300,
            enabled=True,
            service="ai-enrichment-light",
            gpu_id=1,
            runtime=runtime1,
        )
        model2 = ModelStatus(
            name="vehicle-segment-classification",
            category="classification",
            estimated_vram_mb=1500,
            enabled=True,
            service="ai-enrichment",
            gpu_id=0,
            runtime=runtime2,
        )

        response = ModelListResponse(
            models=[model1, model2],
            service_status={
                "ai-enrichment": "healthy",
                "ai-enrichment-light": "healthy",
            },
        )
        assert len(response.models) == 2
        assert response.models[0].name == "threat-detection-yolov8n"
        assert response.models[1].name == "vehicle-segment-classification"
        assert response.service_status["ai-enrichment"] == "healthy"
        assert response.service_status["ai-enrichment-light"] == "healthy"

    def test_model_list_response_empty_models(self) -> None:
        """ModelListResponse should accept empty model list."""
        response = ModelListResponse(
            models=[],
            service_status={
                "ai-enrichment": "unknown",
                "ai-enrichment-light": "unknown",
            },
        )
        assert len(response.models) == 0

    def test_model_list_response_serialization(self) -> None:
        """ModelListResponse should serialize to expected JSON format."""
        runtime = ModelRuntimeInfo(loaded=True, actual_vram_mb=287, load_count=1)
        model = ModelStatus(
            name="test-model",
            category="detection",
            estimated_vram_mb=300,
            enabled=True,
            service="ai-enrichment",
            gpu_id=0,
            runtime=runtime,
        )
        response = ModelListResponse(
            models=[model],
            service_status={"ai-enrichment": "healthy"},
        )
        data = response.model_dump()
        assert "models" in data
        assert "service_status" in data
        assert len(data["models"]) == 1

    def test_model_list_response_json_schema_example(self) -> None:
        """ModelListResponse should have a valid JSON schema example."""
        schema = ModelListResponse.model_json_schema()
        assert "example" in schema
        assert "models" in schema["example"]
        assert "service_status" in schema["example"]


# =============================================================================
# VramGpuInfo Tests
# =============================================================================


class TestVramGpuInfo:
    """Tests for VramGpuInfo schema."""

    def test_vram_gpu_info_validation(self) -> None:
        """VramGpuInfo should validate all fields correctly."""
        gpu_info = VramGpuInfo(
            gpu_id=0,
            service="ai-enrichment",
            budget_mb=6800,
            used_mb=2100,
            available_mb=4700,
            utilization_percent=30.9,
            loaded_models=["fashion-clip", "vehicle-segment-classification"],
        )
        assert gpu_info.gpu_id == 0
        assert gpu_info.service == "ai-enrichment"
        assert gpu_info.budget_mb == 6800
        assert gpu_info.used_mb == 2100
        assert gpu_info.available_mb == 4700
        assert gpu_info.utilization_percent == 30.9
        assert len(gpu_info.loaded_models) == 2

    def test_vram_gpu_info_default_empty_models(self) -> None:
        """VramGpuInfo should default to empty loaded_models list."""
        gpu_info = VramGpuInfo(
            gpu_id=1,
            service="ai-enrichment-light",
            budget_mb=1200,
            used_mb=0,
            available_mb=1200,
            utilization_percent=0.0,
        )
        assert gpu_info.loaded_models == []

    def test_vram_gpu_info_rejects_negative_values(self) -> None:
        """VramGpuInfo should reject negative VRAM values."""
        with pytest.raises(ValidationError):
            VramGpuInfo(
                gpu_id=0,
                service="ai-enrichment",
                budget_mb=-100,
                used_mb=0,
                available_mb=0,
                utilization_percent=0.0,
            )

    def test_vram_gpu_info_rejects_utilization_over_100(self) -> None:
        """VramGpuInfo should reject utilization over 100%."""
        with pytest.raises(ValidationError):
            VramGpuInfo(
                gpu_id=0,
                service="ai-enrichment",
                budget_mb=6800,
                used_mb=6800,
                available_mb=0,
                utilization_percent=150.0,
            )

    def test_vram_gpu_info_serialization(self) -> None:
        """VramGpuInfo should serialize to expected JSON format."""
        gpu_info = VramGpuInfo(
            gpu_id=0,
            service="ai-enrichment",
            budget_mb=6800,
            used_mb=2100,
            available_mb=4700,
            utilization_percent=30.9,
            loaded_models=["test-model"],
        )
        data = gpu_info.model_dump()
        assert data["gpu_id"] == 0
        assert data["budget_mb"] == 6800
        assert data["utilization_percent"] == 30.9

    def test_vram_gpu_info_json_schema_example(self) -> None:
        """VramGpuInfo should have a valid JSON schema example."""
        schema = VramGpuInfo.model_json_schema()
        assert "example" in schema
        assert schema["example"]["gpu_id"] == 0


# =============================================================================
# VramSummaryResponse Tests
# =============================================================================


class TestVramSummaryResponse:
    """Tests for VramSummaryResponse schema."""

    def test_vram_summary_schema_validation(self) -> None:
        """VramSummaryResponse should validate all fields correctly."""
        gpu0 = VramGpuInfo(
            gpu_id=0,
            service="ai-enrichment",
            budget_mb=6800,
            used_mb=2100,
            available_mb=4700,
            utilization_percent=30.9,
            loaded_models=["fashion-clip"],
        )
        gpu1 = VramGpuInfo(
            gpu_id=1,
            service="ai-enrichment-light",
            budget_mb=1200,
            used_mb=450,
            available_mb=750,
            utilization_percent=37.5,
            loaded_models=["threat-detection-yolov8n"],
        )
        totals = VramTotals(
            budget_mb=8000,
            used_mb=2550,
            available_mb=5450,
            model_count=2,
        )

        response = VramSummaryResponse(
            gpus=[gpu0, gpu1],
            totals=totals,
        )
        assert len(response.gpus) == 2
        assert response.gpus[0].gpu_id == 0
        assert response.gpus[1].gpu_id == 1
        assert response.totals.budget_mb == 8000
        assert response.totals.model_count == 2

    def test_vram_summary_empty_gpus(self) -> None:
        """VramSummaryResponse should accept empty GPU list."""
        totals = VramTotals(
            budget_mb=0,
            used_mb=0,
            available_mb=0,
            model_count=0,
        )
        response = VramSummaryResponse(gpus=[], totals=totals)
        assert len(response.gpus) == 0
        assert response.totals.model_count == 0

    def test_vram_summary_serialization(self) -> None:
        """VramSummaryResponse should serialize to expected JSON format."""
        gpu = VramGpuInfo(
            gpu_id=0,
            service="ai-enrichment",
            budget_mb=6800,
            used_mb=1000,
            available_mb=5800,
            utilization_percent=14.7,
        )
        totals = VramTotals(
            budget_mb=6800,
            used_mb=1000,
            available_mb=5800,
            model_count=1,
        )
        response = VramSummaryResponse(gpus=[gpu], totals=totals)
        data = response.model_dump()
        assert "gpus" in data
        assert "totals" in data
        assert len(data["gpus"]) == 1
        assert data["totals"]["model_count"] == 1

    def test_vram_summary_json_schema_example(self) -> None:
        """VramSummaryResponse should have a valid JSON schema example."""
        schema = VramSummaryResponse.model_json_schema()
        assert "example" in schema
        assert "gpus" in schema["example"]
        assert "totals" in schema["example"]


# =============================================================================
# LoadModelResponse Tests
# =============================================================================


class TestLoadModelResponse:
    """Tests for LoadModelResponse schema."""

    def test_load_response_schema_validation(self) -> None:
        """LoadModelResponse should validate all fields correctly."""
        response = LoadModelResponse(
            success=True,
            model_name="threat-detection-yolov8n",
            service="ai-enrichment-light",
            gpu_id=1,
            load_time_ms=1250.0,
            vram_mb=287,
        )
        assert response.success is True
        assert response.model_name == "threat-detection-yolov8n"
        assert response.service == "ai-enrichment-light"
        assert response.gpu_id == 1
        assert response.load_time_ms == 1250.0
        assert response.vram_mb == 287

    def test_load_response_rejects_negative_load_time(self) -> None:
        """LoadModelResponse should reject negative load time."""
        with pytest.raises(ValidationError):
            LoadModelResponse(
                success=True,
                model_name="test-model",
                service="ai-enrichment",
                gpu_id=0,
                load_time_ms=-100.0,
                vram_mb=300,
            )

    def test_load_response_rejects_negative_vram(self) -> None:
        """LoadModelResponse should reject negative VRAM."""
        with pytest.raises(ValidationError):
            LoadModelResponse(
                success=True,
                model_name="test-model",
                service="ai-enrichment",
                gpu_id=0,
                load_time_ms=1000.0,
                vram_mb=-100,
            )

    def test_load_response_serialization(self) -> None:
        """LoadModelResponse should serialize to expected JSON format."""
        response = LoadModelResponse(
            success=True,
            model_name="vehicle-segment-classification",
            service="ai-enrichment",
            gpu_id=0,
            load_time_ms=2500.5,
            vram_mb=1500,
        )
        data = response.model_dump()
        assert data["success"] is True
        assert data["model_name"] == "vehicle-segment-classification"
        assert data["load_time_ms"] == 2500.5

    def test_load_response_json_schema_example(self) -> None:
        """LoadModelResponse should have a valid JSON schema example."""
        schema = LoadModelResponse.model_json_schema()
        assert "example" in schema
        assert schema["example"]["success"] is True


# =============================================================================
# UnloadModelResponse Tests
# =============================================================================


class TestUnloadModelResponse:
    """Tests for UnloadModelResponse schema."""

    def test_unload_response_validation(self) -> None:
        """UnloadModelResponse should validate all fields correctly."""
        response = UnloadModelResponse(
            success=True,
            model_name="threat-detection-yolov8n",
            freed_vram_mb=287,
        )
        assert response.success is True
        assert response.model_name == "threat-detection-yolov8n"
        assert response.freed_vram_mb == 287

    def test_unload_response_rejects_negative_freed_vram(self) -> None:
        """UnloadModelResponse should reject negative freed VRAM."""
        with pytest.raises(ValidationError):
            UnloadModelResponse(
                success=True,
                model_name="test-model",
                freed_vram_mb=-100,
            )

    def test_unload_response_serialization(self) -> None:
        """UnloadModelResponse should serialize to expected JSON format."""
        response = UnloadModelResponse(
            success=True,
            model_name="vehicle-segment-classification",
            freed_vram_mb=1500,
        )
        data = response.model_dump()
        assert data["success"] is True
        assert data["model_name"] == "vehicle-segment-classification"
        assert data["freed_vram_mb"] == 1500

    def test_unload_response_json_schema_example(self) -> None:
        """UnloadModelResponse should have a valid JSON schema example."""
        schema = UnloadModelResponse.model_json_schema()
        assert "example" in schema
        assert schema["example"]["success"] is True


# =============================================================================
# UnloadAllResponse Tests
# =============================================================================


class TestUnloadAllResponse:
    """Tests for UnloadAllResponse schema."""

    def test_unload_all_response_validation(self) -> None:
        """UnloadAllResponse should validate all fields correctly."""
        response = UnloadAllResponse(
            success=True,
            unloaded_count=4,
            freed_vram_mb=2550,
            services={
                "ai-enrichment": 2,
                "ai-enrichment-light": 2,
            },
        )
        assert response.success is True
        assert response.unloaded_count == 4
        assert response.freed_vram_mb == 2550
        assert response.services["ai-enrichment"] == 2
        assert response.services["ai-enrichment-light"] == 2

    def test_unload_all_response_empty_services(self) -> None:
        """UnloadAllResponse should accept empty services dict when nothing loaded."""
        response = UnloadAllResponse(
            success=True,
            unloaded_count=0,
            freed_vram_mb=0,
            services={},
        )
        assert response.unloaded_count == 0
        assert response.services == {}

    def test_unload_all_response_rejects_negative_count(self) -> None:
        """UnloadAllResponse should reject negative unloaded count."""
        with pytest.raises(ValidationError):
            UnloadAllResponse(
                success=True,
                unloaded_count=-1,
                freed_vram_mb=0,
                services={},
            )

    def test_unload_all_response_serialization(self) -> None:
        """UnloadAllResponse should serialize to expected JSON format."""
        response = UnloadAllResponse(
            success=True,
            unloaded_count=3,
            freed_vram_mb=1800,
            services={"ai-enrichment": 3},
        )
        data = response.model_dump()
        assert data["success"] is True
        assert data["unloaded_count"] == 3
        assert "services" in data

    def test_unload_all_response_json_schema_example(self) -> None:
        """UnloadAllResponse should have a valid JSON schema example."""
        schema = UnloadAllResponse.model_json_schema()
        assert "example" in schema
        assert schema["example"]["success"] is True


# =============================================================================
# ModelDetailResponse Tests
# =============================================================================


class TestModelDetailResponse:
    """Tests for ModelDetailResponse schema."""

    def test_model_detail_response_validation(self) -> None:
        """ModelDetailResponse should validate all fields correctly."""
        runtime = ModelRuntimeInfo(
            loaded=True,
            actual_vram_mb=287,
            last_used=datetime(2025, 1, 31, 10, 30, 0, tzinfo=UTC),
            load_count=5,
        )
        response = ModelDetailResponse(
            name="threat-detection-yolov8n",
            category="detection",
            path="/models/model-zoo/threat-detection-yolov8n",
            estimated_vram_mb=300,
            enabled=True,
            available=True,
            service="ai-enrichment-light",
            gpu_id=1,
            runtime=runtime,
        )
        assert response.name == "threat-detection-yolov8n"
        assert response.category == "detection"
        assert response.path == "/models/model-zoo/threat-detection-yolov8n"
        assert response.enabled is True
        assert response.available is True
        assert response.runtime.loaded is True

    def test_model_detail_response_not_available(self) -> None:
        """ModelDetailResponse should accept unavailable model state."""
        runtime = ModelRuntimeInfo(loaded=False, load_count=0)
        response = ModelDetailResponse(
            name="florence-2-large",
            category="vision-language",
            path="/models/model-zoo/florence-2-large",
            estimated_vram_mb=1200,
            enabled=False,
            available=False,
            service="ai-enrichment",
            gpu_id=0,
            runtime=runtime,
        )
        assert response.enabled is False
        assert response.available is False

    def test_model_detail_response_serialization(self) -> None:
        """ModelDetailResponse should serialize to expected JSON format."""
        runtime = ModelRuntimeInfo(loaded=True, actual_vram_mb=300, load_count=1)
        response = ModelDetailResponse(
            name="test-model",
            category="detection",
            path="/models/test-model",
            estimated_vram_mb=300,
            enabled=True,
            available=True,
            service="ai-enrichment",
            gpu_id=0,
            runtime=runtime,
        )
        data = response.model_dump()
        assert data["name"] == "test-model"
        assert data["path"] == "/models/test-model"
        assert data["runtime"]["loaded"] is True

    def test_model_detail_response_json_schema_example(self) -> None:
        """ModelDetailResponse should have a valid JSON schema example."""
        schema = ModelDetailResponse.model_json_schema()
        assert "example" in schema
        assert schema["example"]["name"] == "threat-detection-yolov8n"


# =============================================================================
# Enum Tests
# =============================================================================


class TestModelCategory:
    """Tests for ModelCategory enum."""

    def test_model_category_values(self) -> None:
        """ModelCategory should have all expected values."""
        assert ModelCategory.DETECTION.value == "detection"
        assert ModelCategory.CLASSIFICATION.value == "classification"
        assert ModelCategory.EMBEDDING.value == "embedding"
        assert ModelCategory.POSE.value == "pose"
        assert ModelCategory.OCR.value == "ocr"
        assert ModelCategory.SEGMENTATION.value == "segmentation"
        assert ModelCategory.DEPTH_ESTIMATION.value == "depth_estimation"
        assert ModelCategory.ACTION_RECOGNITION.value == "action_recognition"
        assert ModelCategory.VISION_LANGUAGE.value == "vision_language"
        assert ModelCategory.QUALITY_ASSESSMENT.value == "quality_assessment"


class TestServiceName:
    """Tests for ServiceName enum."""

    def test_service_name_values(self) -> None:
        """ServiceName should have expected service values."""
        assert ServiceName.AI_ENRICHMENT.value == "ai-enrichment"
        assert ServiceName.AI_ENRICHMENT_LIGHT.value == "ai-enrichment-light"


class TestServiceStatus:
    """Tests for ServiceStatus enum."""

    def test_service_status_values(self) -> None:
        """ServiceStatus should have expected status values."""
        assert ServiceStatus.HEALTHY.value == "healthy"
        assert ServiceStatus.UNHEALTHY.value == "unhealthy"
        assert ServiceStatus.UNKNOWN.value == "unknown"


# =============================================================================
# Schema Consistency Tests
# =============================================================================


class TestSchemaConsistency:
    """Tests for consistency across Model Management schemas."""

    def test_model_status_has_required_fields(self) -> None:
        """ModelStatus should have all required fields for API response."""
        fields = set(ModelStatus.model_fields.keys())
        required_fields = {
            "name",
            "category",
            "estimated_vram_mb",
            "enabled",
            "service",
            "gpu_id",
            "runtime",
        }
        assert required_fields.issubset(fields)

    def test_vram_summary_totals_fields(self) -> None:
        """VramTotals should have standard aggregation fields."""
        fields = set(VramTotals.model_fields.keys())
        assert fields == {"budget_mb", "used_mb", "available_mb", "model_count"}

    def test_load_response_has_timing_info(self) -> None:
        """LoadModelResponse should include timing information."""
        fields = set(LoadModelResponse.model_fields.keys())
        assert "load_time_ms" in fields

    def test_unload_response_has_freed_vram(self) -> None:
        """UnloadModelResponse should include freed VRAM info."""
        fields = set(UnloadModelResponse.model_fields.keys())
        assert "freed_vram_mb" in fields

    def test_model_detail_includes_path(self) -> None:
        """ModelDetailResponse should include model path for debugging."""
        fields = set(ModelDetailResponse.model_fields.keys())
        assert "path" in fields
        assert "available" in fields
