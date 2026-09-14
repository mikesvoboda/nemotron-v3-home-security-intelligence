"""Unit tests for prompt config JSON structure validation.

Tests cover:
- NemotronConfig validation (system_prompt, temperature, max_tokens)
- Florence2Config validation (vqa_queries)
- YoloWorldConfig validation (object_classes, confidence_threshold)
- XClipConfig validation (action_classes)
- FashionClipConfig validation (clothing_categories, suspicious_indicators)
- validate_config_for_model helper function

NEM-1331: Add Pydantic validator for prompt config JSON structure before database persistence
"""

import pytest
from pydantic import ValidationError

from backend.api.schemas.prompt_management import (
    AIModelEnum,
    FashionClipConfig,
    Florence2Config,
    NemotronConfig,
    XClipConfig,
    YoloWorldConfig,
    validate_config_for_model,
)

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Test: NemotronConfig Validation
# =============================================================================


class TestNemotronConfigValidation:
    """Tests for Nemotron configuration validation."""

    def test_valid_config_with_all_fields(self):
        """Test valid config with all fields."""
        config = NemotronConfig(
            system_prompt="You are a security analyzer.",
            temperature=0.7,
            max_tokens=2048,
        )
        assert config.system_prompt == "You are a security analyzer."
        assert config.temperature == 0.7
        assert config.max_tokens == 2048

    def test_valid_config_with_defaults(self):
        """Test valid config uses defaults for optional fields."""
        config = NemotronConfig(system_prompt="Test prompt")
        assert config.system_prompt == "Test prompt"
        assert config.temperature == 0.7  # default
        assert config.max_tokens == 2048  # default

    def test_missing_system_prompt_raises_error(self):
        """Test missing system_prompt raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            NemotronConfig()  # type: ignore[call-arg]
        assert "system_prompt" in str(exc_info.value)

    def test_empty_system_prompt_raises_error(self):
        """Test empty system_prompt raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            NemotronConfig(system_prompt="")
        assert "system_prompt" in str(exc_info.value).lower()

    def test_whitespace_only_system_prompt_raises_error(self):
        """Test whitespace-only system_prompt raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            NemotronConfig(system_prompt="   \n\t  ")
        assert "whitespace" in str(exc_info.value).lower()

    def test_temperature_below_zero_raises_error(self):
        """Test temperature below 0 raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            NemotronConfig(system_prompt="Test", temperature=-0.1)
        assert "temperature" in str(exc_info.value).lower()

    def test_temperature_above_two_raises_error(self):
        """Test temperature above 2 raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            NemotronConfig(system_prompt="Test", temperature=2.1)
        assert "temperature" in str(exc_info.value).lower()

    def test_temperature_edge_values_valid(self):
        """Test temperature edge values (0 and 2) are valid."""
        config_low = NemotronConfig(system_prompt="Test", temperature=0.0)
        config_high = NemotronConfig(system_prompt="Test", temperature=2.0)
        assert config_low.temperature == 0.0
        assert config_high.temperature == 2.0

    def test_max_tokens_below_one_raises_error(self):
        """Test max_tokens below 1 raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            NemotronConfig(system_prompt="Test", max_tokens=0)
        assert "max_tokens" in str(exc_info.value).lower()

    def test_max_tokens_above_limit_raises_error(self):
        """Test max_tokens above 16384 raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            NemotronConfig(system_prompt="Test", max_tokens=16385)
        assert "max_tokens" in str(exc_info.value).lower()


# =============================================================================
# Test: Florence2Config Validation
# =============================================================================


class TestFlorence2ConfigValidation:
    """Tests for Florence-2 configuration validation."""

    def test_valid_config(self):
        """Test valid config with VQA queries."""
        config = Florence2Config(vqa_queries=["What is happening?", "Who is in the scene?"])
        assert len(config.vqa_queries) == 2

    def test_missing_vqa_queries_raises_error(self):
        """Test missing vqa_queries raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            Florence2Config()  # type: ignore[call-arg]
        assert "vqa_queries" in str(exc_info.value)

    def test_empty_vqa_queries_raises_error(self):
        """Test empty vqa_queries list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            Florence2Config(vqa_queries=[])
        errors = str(exc_info.value).lower()
        assert "vqa_queries" in errors or "min_length" in errors

    def test_vqa_queries_with_empty_string_raises_error(self):
        """Test vqa_queries containing empty string raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            Florence2Config(vqa_queries=["Valid query", ""])
        assert "empty" in str(exc_info.value).lower() or "whitespace" in str(exc_info.value).lower()

    def test_vqa_queries_with_whitespace_only_raises_error(self):
        """Test vqa_queries containing whitespace-only string raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            Florence2Config(vqa_queries=["Valid query", "   "])
        assert "whitespace" in str(exc_info.value).lower()


# =============================================================================
# Test: YoloWorldConfig Validation
# =============================================================================


class TestYoloWorldConfigValidation:
    """Tests for YOLO-World configuration validation."""

    def test_valid_config(self):
        """Test valid config with object classes."""
        config = YoloWorldConfig(
            object_classes=["person", "car", "knife"],
            confidence_threshold=0.5,
        )
        assert len(config.object_classes) == 3
        assert config.confidence_threshold == 0.5

    def test_valid_config_with_default_threshold(self):
        """Test valid config uses default confidence threshold."""
        config = YoloWorldConfig(object_classes=["person"])
        assert config.confidence_threshold == 0.35  # default

    def test_missing_object_classes_raises_error(self):
        """Test missing object_classes raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            YoloWorldConfig()  # type: ignore[call-arg]
        assert "object_classes" in str(exc_info.value)

    def test_empty_object_classes_raises_error(self):
        """Test empty object_classes list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            YoloWorldConfig(object_classes=[])
        errors = str(exc_info.value).lower()
        assert "object_classes" in errors or "min_length" in errors

    def test_object_classes_with_empty_string_raises_error(self):
        """Test object_classes containing empty string raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            YoloWorldConfig(object_classes=["person", ""])
        assert "empty" in str(exc_info.value).lower() or "whitespace" in str(exc_info.value).lower()

    def test_confidence_threshold_below_zero_raises_error(self):
        """Test confidence_threshold below 0 raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            YoloWorldConfig(object_classes=["person"], confidence_threshold=-0.1)
        assert "confidence_threshold" in str(exc_info.value).lower()

    def test_confidence_threshold_above_one_raises_error(self):
        """Test confidence_threshold above 1 raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            YoloWorldConfig(object_classes=["person"], confidence_threshold=1.1)
        assert "confidence_threshold" in str(exc_info.value).lower()

    def test_confidence_threshold_edge_values_valid(self):
        """Test confidence_threshold edge values (0 and 1) are valid."""
        config_low = YoloWorldConfig(object_classes=["person"], confidence_threshold=0.0)
        config_high = YoloWorldConfig(object_classes=["person"], confidence_threshold=1.0)
        assert config_low.confidence_threshold == 0.0
        assert config_high.confidence_threshold == 1.0


# =============================================================================
# Test: XClipConfig Validation
# =============================================================================


class TestXClipConfigValidation:
    """Tests for X-CLIP configuration validation."""

    def test_valid_config(self):
        """Test valid config with action classes."""
        config = XClipConfig(action_classes=["walking", "running", "standing"])
        assert len(config.action_classes) == 3

    def test_missing_action_classes_raises_error(self):
        """Test missing action_classes raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            XClipConfig()  # type: ignore[call-arg]
        assert "action_classes" in str(exc_info.value)

    def test_empty_action_classes_raises_error(self):
        """Test empty action_classes list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            XClipConfig(action_classes=[])
        errors = str(exc_info.value).lower()
        assert "action_classes" in errors or "min_length" in errors

    def test_action_classes_with_empty_string_raises_error(self):
        """Test action_classes containing empty string raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            XClipConfig(action_classes=["walking", ""])
        assert "empty" in str(exc_info.value).lower() or "whitespace" in str(exc_info.value).lower()


# =============================================================================
# Test: FashionClipConfig Validation
# =============================================================================


class TestFashionClipConfigValidation:
    """Tests for Fashion-CLIP configuration validation."""

    def test_valid_config(self):
        """Test valid config with clothing categories."""
        config = FashionClipConfig(
            clothing_categories=["casual", "formal", "athletic"],
            suspicious_indicators=["all black", "face mask"],
        )
        assert len(config.clothing_categories) == 3
        assert len(config.suspicious_indicators) == 2

    def test_valid_config_without_suspicious_indicators(self):
        """Test valid config with default suspicious_indicators."""
        config = FashionClipConfig(clothing_categories=["casual"])
        assert config.suspicious_indicators == []

    def test_missing_clothing_categories_raises_error(self):
        """Test missing clothing_categories raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            FashionClipConfig()  # type: ignore[call-arg]
        assert "clothing_categories" in str(exc_info.value)

    def test_empty_clothing_categories_raises_error(self):
        """Test empty clothing_categories list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            FashionClipConfig(clothing_categories=[])
        errors = str(exc_info.value).lower()
        assert "clothing_categories" in errors or "min_length" in errors

    def test_clothing_categories_with_empty_string_raises_error(self):
        """Test clothing_categories containing empty string raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            FashionClipConfig(clothing_categories=["casual", ""])
        assert "empty" in str(exc_info.value).lower() or "whitespace" in str(exc_info.value).lower()


# =============================================================================
# Test: validate_config_for_model Helper Function
# =============================================================================


class TestValidateConfigForModel:
    """Tests for validate_config_for_model helper function."""

    # Nemotron validation
    def test_nemotron_valid_config(self):
        """Test nemotron with valid config returns no errors."""
        errors = validate_config_for_model(
            AIModelEnum.NEMOTRON,
            {"system_prompt": "You are a security analyzer.", "temperature": 0.7},
        )
        assert errors == []

    def test_nemotron_missing_system_prompt(self):
        """Test nemotron with missing system_prompt returns error."""
        errors = validate_config_for_model(
            AIModelEnum.NEMOTRON,
            {"temperature": 0.7},
        )
        assert len(errors) > 0
        assert any("system_prompt" in e.lower() for e in errors)

    def test_nemotron_invalid_temperature(self):
        """Test nemotron with invalid temperature returns error."""
        errors = validate_config_for_model(
            AIModelEnum.NEMOTRON,
            {"system_prompt": "Test", "temperature": 3.0},
        )
        assert len(errors) > 0

    # Florence2 validation
    def test_florence2_valid_config(self):
        """Test florence2 with valid config returns no errors."""
        errors = validate_config_for_model(
            AIModelEnum.FLORENCE2,
            {"vqa_queries": ["What is this?", "Describe the scene."]},
        )
        assert errors == []

    def test_florence2_missing_vqa_queries(self):
        """Test florence2 with missing vqa_queries returns error."""
        errors = validate_config_for_model(
            AIModelEnum.FLORENCE2,
            {},
        )
        assert len(errors) > 0
        assert any("vqa_queries" in e.lower() for e in errors)

    def test_florence2_empty_vqa_queries(self):
        """Test florence2 with empty vqa_queries returns error."""
        errors = validate_config_for_model(
            AIModelEnum.FLORENCE2,
            {"vqa_queries": []},
        )
        assert len(errors) > 0

    # YoloWorld validation
    def test_yolo_world_valid_config(self):
        """Test yolo_world with valid config returns no errors."""
        errors = validate_config_for_model(
            AIModelEnum.YOLO_WORLD,
            {"object_classes": ["person", "car"], "confidence_threshold": 0.5},
        )
        assert errors == []

    def test_yolo_world_missing_object_classes(self):
        """Test yolo_world with missing object_classes returns error."""
        errors = validate_config_for_model(
            AIModelEnum.YOLO_WORLD,
            {"confidence_threshold": 0.5},
        )
        assert len(errors) > 0
        assert any("object_classes" in e.lower() for e in errors)

    def test_yolo_world_invalid_threshold(self):
        """Test yolo_world with invalid confidence_threshold returns error."""
        errors = validate_config_for_model(
            AIModelEnum.YOLO_WORLD,
            {"object_classes": ["person"], "confidence_threshold": 1.5},
        )
        assert len(errors) > 0

    # XClip validation
    def test_xclip_valid_config(self):
        """Test xclip with valid config returns no errors."""
        errors = validate_config_for_model(
            AIModelEnum.XCLIP,
            {"action_classes": ["walking", "running"]},
        )
        assert errors == []

    def test_xclip_missing_action_classes(self):
        """Test xclip with missing action_classes returns error."""
        errors = validate_config_for_model(
            AIModelEnum.XCLIP,
            {},
        )
        assert len(errors) > 0
        assert any("action_classes" in e.lower() for e in errors)

    # FashionClip validation
    def test_fashion_clip_valid_config(self):
        """Test fashion_clip with valid config returns no errors."""
        errors = validate_config_for_model(
            AIModelEnum.FASHION_CLIP,
            {"clothing_categories": ["casual", "formal"]},
        )
        assert errors == []

    def test_fashion_clip_missing_clothing_categories(self):
        """Test fashion_clip with missing clothing_categories returns error."""
        errors = validate_config_for_model(
            AIModelEnum.FASHION_CLIP,
            {},
        )
        assert len(errors) > 0
        assert any("clothing_categories" in e.lower() for e in errors)

    def test_fashion_clip_with_suspicious_indicators(self):
        """Test fashion_clip with optional suspicious_indicators returns no errors."""
        errors = validate_config_for_model(
            AIModelEnum.FASHION_CLIP,
            {
                "clothing_categories": ["casual"],
                "suspicious_indicators": ["all black", "face mask"],
            },
        )
        assert errors == []

    # Edge cases
    def test_config_with_extra_fields_accepted(self):
        """Test that extra fields in config are accepted (not strict)."""
        errors = validate_config_for_model(
            AIModelEnum.NEMOTRON,
            {
                "system_prompt": "Test",
                "extra_field": "should be ignored",
                "another_extra": 123,
            },
        )
        assert errors == []

    def test_config_with_version_field(self):
        """Test that version field doesn't cause validation errors."""
        errors = validate_config_for_model(
            AIModelEnum.NEMOTRON,
            {"system_prompt": "Test", "version": 5},
        )
        assert errors == []
