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
        """Test that invalid parameter types are rejected. Nemotron is the only registry
        entry now (the four vision models retired, B3.3 box 4), so the wrong-type object is
        a bare PromptParamBase -- every non-Nemotron params object must refuse."""
        from backend.services.typed_prompt_config import (
            NemotronPromptParams,
            PromptParamBase,
            TypedPromptTemplate,
        )

        template = TypedPromptTemplate[NemotronPromptParams](
            model_name="nemotron",
            template_string="Camera: {camera_name}",
            param_type=NemotronPromptParams,
        )

        # Wrong param type: a PromptParamBase that is not NemotronPromptParams
        wrong_params = PromptParamBase.model_construct()

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


class TestGenericConstraintEnforcement:
    """Tests for generic constraint enforcement."""

    def test_template_enforces_param_type_at_runtime(self) -> None:
        """Test that template enforces parameter type at runtime."""
        from backend.services.typed_prompt_config import (
            NemotronPromptParams,
            PromptParamBase,
            TypedPromptTemplate,
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

        # Wrong params type - should fail (a bare base, since Nemotron is the only
        # registry entry after the four vision models retired, B3.3 box 4)
        wrong_params = PromptParamBase.model_construct()
        with pytest.raises(TypeError):
            nemotron_template.validate_params(wrong_params)  # type: ignore[arg-type]

    def test_mypy_catches_wrong_param_type(self) -> None:
        """Test demonstrating mypy would catch wrong param type.

        This test exists to document expected type-checking behavior.
        The actual mypy check happens at development time, not runtime.
        """
        # (mypy example removed with the retired vision-model params, B3.3 box 4)

        # For runtime test, we just verify the type mismatch raises TypeError
        from backend.services.typed_prompt_config import (
            NemotronPromptParams,
            PromptParamBase,
            TypedPromptTemplate,
        )

        template = TypedPromptTemplate[NemotronPromptParams](
            model_name="nemotron",
            template_string="test",
            param_type=NemotronPromptParams,
        )

        with pytest.raises(TypeError):
            template.validate_params(PromptParamBase.model_construct())  # type: ignore[arg-type]


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
            NemotronPromptParams,
            PromptParamBase,
        )

        param_types = [
            NemotronPromptParams,
        ]

        for param_type in param_types:
            assert issubclass(param_type, PromptParamBase), (
                f"{param_type.__name__} should inherit from PromptParamBase"
            )
