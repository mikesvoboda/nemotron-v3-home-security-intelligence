"""Unit tests for prompt config JSON structure validation.

Tests cover:
- NemotronConfig validation (system_prompt, temperature, max_tokens)
- validate_config_for_model helper function

NEM-1331: Add Pydantic validator for prompt config JSON structure before database persistence
"""

import pytest
from pydantic import ValidationError

from backend.api.schemas.prompt_management import (
    AIModelEnum,
    NemotronConfig,
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
