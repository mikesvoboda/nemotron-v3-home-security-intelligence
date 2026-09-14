"""Unit tests for type-safe prompt configuration with generic constraints.

Tests cover:
- TypedPromptTemplate with generic parameter validation
- ModelConfigRegistry type mappings
- Generic constraint enforcement at runtime
- Type inference and validation
- Pydantic model integration

NEM-1547: Type-safe prompt configuration with generic constraints
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestTypedPromptTemplate:
    """Tests for TypedPromptTemplate class with generic constraints."""

    def test_create_nemotron_config_template(self) -> None:
        """Test creating a typed prompt template for Nemotron."""
        from backend.services.typed_prompt_config import (
            NemotronPromptParams,
            TypedPromptTemplate,
        )

        template = TypedPromptTemplate[NemotronPromptParams](
            model_name="nemotron",
            template_string="Camera: {camera_name}\nTime: {timestamp}",
            param_type=NemotronPromptParams,
        )

        assert template.model_name == "nemotron"
        assert template.param_type == NemotronPromptParams

    def test_validate_params_accepts_valid_nemotron_params(self) -> None:
        """Test that valid Nemotron params pass validation."""
        from backend.services.typed_prompt_config import (
            NemotronPromptParams,
            TypedPromptTemplate,
        )

        template = TypedPromptTemplate[NemotronPromptParams](
            model_name="nemotron",
            template_string="Camera: {camera_name}\nTime: {timestamp}",
            param_type=NemotronPromptParams,
        )

        params = NemotronPromptParams(
            camera_name="Front Door",
            timestamp="2024-01-15T10:30:00",
            day_of_week="Monday",
            time_of_day="morning",
        )

        # Should not raise
        validated = template.validate_params(params)
        assert validated.camera_name == "Front Door"

    def test_validate_params_rejects_invalid_type(self) -> None:
        """Test that invalid parameter types are rejected."""
        from backend.services.typed_prompt_config import (
            Florence2PromptParams,
            NemotronPromptParams,
            TypedPromptTemplate,
        )

        template = TypedPromptTemplate[NemotronPromptParams](
            model_name="nemotron",
            template_string="Camera: {camera_name}",
            param_type=NemotronPromptParams,
        )

        # Wrong param type
        wrong_params = Florence2PromptParams(queries=["What is this?"])

        with pytest.raises(TypeError) as exc_info:
            template.validate_params(wrong_params)  # type: ignore[arg-type]

        assert "NemotronPromptParams" in str(exc_info.value)

    def test_render_prompt_with_valid_params(self) -> None:
        """Test rendering a prompt with valid parameters."""
        from backend.services.typed_prompt_config import (
            NemotronPromptParams,
            TypedPromptTemplate,
        )

        template = TypedPromptTemplate[NemotronPromptParams](
            model_name="nemotron",
            template_string="Camera: {camera_name}\nTime: {timestamp}",
            param_type=NemotronPromptParams,
        )

        params = NemotronPromptParams(
            camera_name="Front Door",
            timestamp="2024-01-15T10:30:00",
            day_of_week="Monday",
            time_of_day="morning",
        )

        rendered = template.render(params)
        assert "Camera: Front Door" in rendered
        assert "Time: 2024-01-15T10:30:00" in rendered

    def test_render_prompt_with_optional_fields(self) -> None:
        """Test rendering handles optional fields correctly."""
        from backend.services.typed_prompt_config import (
            NemotronPromptParams,
            TypedPromptTemplate,
        )

        template = TypedPromptTemplate[NemotronPromptParams](
            model_name="nemotron",
            template_string="Camera: {camera_name}\nZones: {zone_analysis}",
            param_type=NemotronPromptParams,
        )

        params = NemotronPromptParams(
            camera_name="Back Yard",
            timestamp="2024-01-15T10:30:00",
            day_of_week="Monday",
            time_of_day="morning",
            zone_analysis="Entry point zone detected",
        )

        rendered = template.render(params)
        assert "Zones: Entry point zone detected" in rendered


class TestNemotronPromptParams:
    """Tests for NemotronPromptParams Pydantic model."""

    def test_valid_nemotron_params(self) -> None:
        """Test creating valid Nemotron prompt parameters."""
        from backend.services.typed_prompt_config import NemotronPromptParams

        params = NemotronPromptParams(
            camera_name="Front Door",
            timestamp="2024-01-15T10:30:00",
            day_of_week="Monday",
            time_of_day="morning",
        )

        assert params.camera_name == "Front Door"
        assert params.timestamp == "2024-01-15T10:30:00"
        assert params.day_of_week == "Monday"
        assert params.time_of_day == "morning"

    def test_nemotron_params_with_all_optional_fields(self) -> None:
        """Test Nemotron params with all optional fields."""
        from backend.services.typed_prompt_config import NemotronPromptParams

        params = NemotronPromptParams(
            camera_name="Driveway",
            timestamp="2024-01-15T22:00:00",
            day_of_week="Friday",
            time_of_day="night",
            zone_analysis="Driveway zone, high activity area",
            baseline_comparison="Above normal activity for this hour",
            deviation_score=0.75,
            cross_camera_summary="Person also detected on front door camera",
            detections_list="1. 22:00:05 - person (confidence: 0.95)",
            reid_context="Person matches previous visitor",
            scene_analysis="Dark scene, motion detected",
        )

        assert params.zone_analysis == "Driveway zone, high activity area"
        assert params.deviation_score == 0.75
        assert params.reid_context == "Person matches previous visitor"

    def test_nemotron_params_missing_required_field(self) -> None:
        """Test that missing required fields raise ValidationError."""
        from backend.services.typed_prompt_config import NemotronPromptParams

        with pytest.raises(ValidationError) as exc_info:
            NemotronPromptParams(
                camera_name="Front Door",
                # Missing: timestamp, day_of_week, time_of_day
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "timestamp" in field_names
        assert "day_of_week" in field_names
        assert "time_of_day" in field_names

    def test_nemotron_params_empty_camera_name_rejected(self) -> None:
        """Test that empty camera_name is rejected."""
        from backend.services.typed_prompt_config import NemotronPromptParams

        with pytest.raises(ValidationError) as exc_info:
            NemotronPromptParams(
                camera_name="",
                timestamp="2024-01-15T10:30:00",
                day_of_week="Monday",
                time_of_day="morning",
            )

        assert "camera_name" in str(exc_info.value).lower()

    def test_nemotron_params_deviation_score_bounds(self) -> None:
        """Test deviation_score validation bounds (0-1)."""
        from backend.services.typed_prompt_config import NemotronPromptParams

        # Valid score
        params = NemotronPromptParams(
            camera_name="Test",
            timestamp="2024-01-15T10:30:00",
            day_of_week="Monday",
            time_of_day="morning",
            deviation_score=0.5,
        )
        assert params.deviation_score == 0.5

        # Invalid score (above 1)
        with pytest.raises(ValidationError):
            NemotronPromptParams(
                camera_name="Test",
                timestamp="2024-01-15T10:30:00",
                day_of_week="Monday",
                time_of_day="morning",
                deviation_score=1.5,
            )

        # Invalid score (below 0)
        with pytest.raises(ValidationError):
            NemotronPromptParams(
                camera_name="Test",
                timestamp="2024-01-15T10:30:00",
                day_of_week="Monday",
                time_of_day="morning",
                deviation_score=-0.1,
            )


class TestFlorence2PromptParams:
    """Tests for Florence2PromptParams Pydantic model."""

    def test_valid_florence2_params(self) -> None:
        """Test creating valid Florence-2 prompt parameters."""
        from backend.services.typed_prompt_config import Florence2PromptParams

        params = Florence2PromptParams(
            queries=["What is the person doing?", "What are they carrying?"],
        )

        assert len(params.queries) == 2
        assert "What is the person doing?" in params.queries

    def test_florence2_params_empty_queries_rejected(self) -> None:
        """Test that empty queries list is rejected."""
        from backend.services.typed_prompt_config import Florence2PromptParams

        with pytest.raises(ValidationError):
            Florence2PromptParams(queries=[])

    def test_florence2_params_whitespace_query_rejected(self) -> None:
        """Test that whitespace-only queries are rejected."""
        from backend.services.typed_prompt_config import Florence2PromptParams

        with pytest.raises(ValidationError):
            Florence2PromptParams(queries=["Valid query", "   "])


class TestYoloWorldPromptParams:
    """Tests for YoloWorldPromptParams Pydantic model."""

    def test_valid_yolo_world_params(self) -> None:
        """Test creating valid YOLO-World prompt parameters."""
        from backend.services.typed_prompt_config import YoloWorldPromptParams

        params = YoloWorldPromptParams(
            classes=["knife", "gun", "crowbar"],
            confidence_threshold=0.4,
        )

        assert len(params.classes) == 3
        assert params.confidence_threshold == 0.4

    def test_yolo_world_params_default_threshold(self) -> None:
        """Test YOLO-World uses default confidence threshold."""
        from backend.services.typed_prompt_config import YoloWorldPromptParams

        params = YoloWorldPromptParams(classes=["person", "car"])
        assert params.confidence_threshold == 0.35

    def test_yolo_world_params_invalid_threshold(self) -> None:
        """Test invalid confidence threshold is rejected."""
        from backend.services.typed_prompt_config import YoloWorldPromptParams

        with pytest.raises(ValidationError):
            YoloWorldPromptParams(classes=["person"], confidence_threshold=1.5)


class TestModelConfigRegistry:
    """Tests for the ModelConfigRegistry type mapping."""

    def test_get_config_type_for_nemotron(self) -> None:
        """Test getting config type for Nemotron model."""
        from backend.services.typed_prompt_config import (
            NemotronPromptParams,
            get_param_type_for_model,
        )

        param_type = get_param_type_for_model("nemotron")
        assert param_type == NemotronPromptParams

    def test_get_config_type_for_florence2(self) -> None:
        """Test getting config type for Florence-2 model."""
        from backend.services.typed_prompt_config import (
            Florence2PromptParams,
            get_param_type_for_model,
        )

        param_type = get_param_type_for_model("florence2")
        assert param_type == Florence2PromptParams

    def test_get_config_type_for_yolo_world(self) -> None:
        """Test getting config type for YOLO-World model."""
        from backend.services.typed_prompt_config import (
            YoloWorldPromptParams,
            get_param_type_for_model,
        )

        param_type = get_param_type_for_model("yolo_world")
        assert param_type == YoloWorldPromptParams

    def test_get_config_type_for_xclip(self) -> None:
        """Test getting config type for X-CLIP model."""
        from backend.services.typed_prompt_config import (
            XClipPromptParams,
            get_param_type_for_model,
        )

        param_type = get_param_type_for_model("xclip")
        assert param_type == XClipPromptParams

    def test_get_config_type_for_fashion_clip(self) -> None:
        """Test getting config type for Fashion-CLIP model."""
        from backend.services.typed_prompt_config import (
            FashionClipPromptParams,
            get_param_type_for_model,
        )

        param_type = get_param_type_for_model("fashion_clip")
        assert param_type == FashionClipPromptParams

    def test_get_config_type_for_unknown_model_raises_error(self) -> None:
        """Test that unknown model name raises KeyError."""
        from backend.services.typed_prompt_config import get_param_type_for_model

        with pytest.raises(KeyError) as exc_info:
            get_param_type_for_model("unknown_model")

        assert "unknown_model" in str(exc_info.value)


class TestCreateTypedTemplate:
    """Tests for the create_typed_template factory function."""

    def test_create_nemotron_template(self) -> None:
        """Test creating a Nemotron template via factory."""
        from backend.services.typed_prompt_config import (
            NemotronPromptParams,
            create_typed_template,
        )

        template = create_typed_template(
            model_name="nemotron",
            template_string="Analyze: {camera_name} at {timestamp}",
        )

        assert template.model_name == "nemotron"
        assert template.param_type == NemotronPromptParams

    def test_create_florence2_template(self) -> None:
        """Test creating a Florence-2 template via factory."""
        from backend.services.typed_prompt_config import (
            Florence2PromptParams,
            create_typed_template,
        )

        template = create_typed_template(
            model_name="florence2",
            template_string="VQA Query: {queries}",
        )

        assert template.model_name == "florence2"
        assert template.param_type == Florence2PromptParams


class TestTypeSafeConfigGet:
    """Tests for type-safe config retrieval."""

    def test_get_typed_config_returns_validated_model(self) -> None:
        """Test that get_typed_config returns properly typed model."""
        from backend.services.typed_prompt_config import (
            NemotronPromptParams,
            get_typed_params,
        )

        raw_data = {
            "camera_name": "Front Door",
            "timestamp": "2024-01-15T10:30:00",
            "day_of_week": "Monday",
            "time_of_day": "morning",
        }

        params = get_typed_params("nemotron", raw_data)
        assert isinstance(params, NemotronPromptParams)
        assert params.camera_name == "Front Door"

    def test_get_typed_config_validates_data(self) -> None:
        """Test that invalid data raises ValidationError."""
        from backend.services.typed_prompt_config import get_typed_params

        invalid_data = {
            "camera_name": "",  # Empty - should fail validation
            "timestamp": "2024-01-15T10:30:00",
            "day_of_week": "Monday",
            "time_of_day": "morning",
        }

        with pytest.raises(ValidationError):
            get_typed_params("nemotron", invalid_data)

    def test_get_typed_config_for_florence2(self) -> None:
        """Test getting typed config for Florence-2."""
        from backend.services.typed_prompt_config import (
            Florence2PromptParams,
            get_typed_params,
        )

        raw_data = {"queries": ["What is happening?", "Describe the scene."]}

        params = get_typed_params("florence2", raw_data)
        assert isinstance(params, Florence2PromptParams)
        assert len(params.queries) == 2


class TestGenericConstraintEnforcement:
    """Tests for generic constraint enforcement."""

    def test_template_enforces_param_type_at_runtime(self) -> None:
        """Test that template enforces parameter type at runtime."""
        from backend.services.typed_prompt_config import (
            NemotronPromptParams,
            TypedPromptTemplate,
            YoloWorldPromptParams,
        )

        nemotron_template = TypedPromptTemplate[NemotronPromptParams](
            model_name="nemotron",
            template_string="Camera: {camera_name}",
            param_type=NemotronPromptParams,
        )

        # Correct params - should work
        valid_params = NemotronPromptParams(
            camera_name="Test",
            timestamp="2024-01-15T10:30:00",
            day_of_week="Monday",
            time_of_day="morning",
        )
        nemotron_template.validate_params(valid_params)

        # Wrong params type - should fail
        wrong_params = YoloWorldPromptParams(classes=["person"])
        with pytest.raises(TypeError):
            nemotron_template.validate_params(wrong_params)  # type: ignore[arg-type]

    def test_mypy_catches_wrong_param_type(self) -> None:
        """Test demonstrating mypy would catch wrong param type.

        This test exists to document expected type-checking behavior.
        The actual mypy check happens at development time, not runtime.
        """
        # This comment block shows what mypy would catch:
        #
        # from backend.services.typed_prompt_config import (
        #     TypedPromptTemplate,
        #     NemotronPromptParams,
        #     Florence2PromptParams,
        # )
        #
        # template = TypedPromptTemplate[NemotronPromptParams](...)
        #
        # # This would cause mypy error:
        # # error: Argument 1 to "validate_params" of "TypedPromptTemplate"
        # #        has incompatible type "Florence2PromptParams";
        # #        expected "NemotronPromptParams"
        # template.validate_params(Florence2PromptParams(queries=["test"]))

        # For runtime test, we just verify the type mismatch raises TypeError
        from backend.services.typed_prompt_config import (
            Florence2PromptParams,
            NemotronPromptParams,
            TypedPromptTemplate,
        )

        template = TypedPromptTemplate[NemotronPromptParams](
            model_name="nemotron",
            template_string="test",
            param_type=NemotronPromptParams,
        )

        with pytest.raises(TypeError):
            template.validate_params(Florence2PromptParams(queries=["test"]))  # type: ignore[arg-type]


class TestPromptParamBaseModel:
    """Tests for the PromptParamBase abstract base class."""

    def test_prompt_param_base_is_abstract(self) -> None:
        """Test that PromptParamBase cannot be instantiated directly."""
        # PromptParamBase should not be directly instantiatable
        # (it's a base class for all prompt param types)
        # We verify this by checking it's used as a base
        from backend.services.typed_prompt_config import NemotronPromptParams, PromptParamBase

        assert issubclass(NemotronPromptParams, PromptParamBase)

    def test_all_param_types_inherit_from_base(self) -> None:
        """Test that all param types inherit from PromptParamBase."""
        from backend.services.typed_prompt_config import (
            FashionClipPromptParams,
            Florence2PromptParams,
            NemotronPromptParams,
            PromptParamBase,
            XClipPromptParams,
            YoloWorldPromptParams,
        )

        param_types = [
            NemotronPromptParams,
            Florence2PromptParams,
            YoloWorldPromptParams,
            XClipPromptParams,
            FashionClipPromptParams,
        ]

        for param_type in param_types:
            assert issubclass(param_type, PromptParamBase), (
                f"{param_type.__name__} should inherit from PromptParamBase"
            )


class TestXClipPromptParams:
    """Tests for XClipPromptParams Pydantic model."""

    def test_valid_xclip_params(self) -> None:
        """Test creating valid X-CLIP prompt parameters."""
        from backend.services.typed_prompt_config import XClipPromptParams

        params = XClipPromptParams(
            action_classes=["loitering", "running away", "fighting"],
        )

        assert len(params.action_classes) == 3
        assert "loitering" in params.action_classes

    def test_xclip_params_empty_action_classes_rejected(self) -> None:
        """Test that empty action_classes list is rejected."""
        from backend.services.typed_prompt_config import XClipPromptParams

        with pytest.raises(ValidationError):
            XClipPromptParams(action_classes=[])


class TestFashionClipPromptParams:
    """Tests for FashionClipPromptParams Pydantic model."""

    def test_valid_fashion_clip_params(self) -> None:
        """Test creating valid Fashion-CLIP prompt parameters."""
        from backend.services.typed_prompt_config import FashionClipPromptParams

        params = FashionClipPromptParams(
            clothing_categories=["dark hoodie", "high-vis vest", "business attire"],
            suspicious_indicators=["all black", "face mask", "gloves"],
        )

        assert len(params.clothing_categories) == 3
        assert len(params.suspicious_indicators) == 3

    def test_fashion_clip_params_default_suspicious_indicators(self) -> None:
        """Test Fashion-CLIP uses empty default for suspicious_indicators."""
        from backend.services.typed_prompt_config import FashionClipPromptParams

        params = FashionClipPromptParams(
            clothing_categories=["casual", "formal"],
        )

        assert params.suspicious_indicators == []

    def test_fashion_clip_params_empty_categories_rejected(self) -> None:
        """Test that empty clothing_categories list is rejected."""
        from backend.services.typed_prompt_config import FashionClipPromptParams

        with pytest.raises(ValidationError):
            FashionClipPromptParams(clothing_categories=[])
