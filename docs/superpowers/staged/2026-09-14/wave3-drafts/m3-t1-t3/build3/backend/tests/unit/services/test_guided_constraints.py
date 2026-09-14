"""Unit tests for guided_constraints service.

Tests cover:
- Choice list constants have expected values
- get_guided_choice_config() returns correct structure for each field
- get_guided_choice_config() returns None for unknown fields
- get_guided_regex_config() returns correct regex patterns
- get_guided_regex_config() returns None for unknown fields
- validate_risk_level() accepts valid levels and rejects invalid ones
- validate_recommended_action() accepts valid actions and rejects invalid ones
- validate_entity_type() accepts valid types and rejects invalid ones
- validate_threat_level() accepts valid levels and rejects invalid ones
"""

from __future__ import annotations

import pytest

from backend.services.guided_constraints import (
    ENTITY_TYPE_CHOICES,
    RECOMMENDED_ACTION_CHOICES,
    RISK_LEVEL_CHOICES,
    THREAT_LEVEL_CHOICES,
    get_guided_choice_config,
    get_guided_regex_config,
    validate_entity_type,
    validate_recommended_action,
    validate_risk_level,
    validate_threat_level,
)

# =============================================================================
# RISK_LEVEL_CHOICES Tests
# =============================================================================


class TestRiskLevelChoices:
    """Tests for RISK_LEVEL_CHOICES constant."""

    def test_risk_level_choices_is_list(self) -> None:
        """Test that RISK_LEVEL_CHOICES is a list."""
        assert isinstance(RISK_LEVEL_CHOICES, list)

    def test_risk_level_choices_has_four_values(self) -> None:
        """Test that RISK_LEVEL_CHOICES has exactly four values."""
        assert len(RISK_LEVEL_CHOICES) == 4

    def test_risk_level_choices_contains_low(self) -> None:
        """Test that RISK_LEVEL_CHOICES contains 'low'."""
        assert "low" in RISK_LEVEL_CHOICES

    def test_risk_level_choices_contains_medium(self) -> None:
        """Test that RISK_LEVEL_CHOICES contains 'medium'."""
        assert "medium" in RISK_LEVEL_CHOICES

    def test_risk_level_choices_contains_high(self) -> None:
        """Test that RISK_LEVEL_CHOICES contains 'high'."""
        assert "high" in RISK_LEVEL_CHOICES

    def test_risk_level_choices_contains_critical(self) -> None:
        """Test that RISK_LEVEL_CHOICES contains 'critical'."""
        assert "critical" in RISK_LEVEL_CHOICES

    def test_risk_level_choices_order(self) -> None:
        """Test that RISK_LEVEL_CHOICES is in severity order."""
        assert RISK_LEVEL_CHOICES == ["low", "medium", "high", "critical"]


# =============================================================================
# RECOMMENDED_ACTION_CHOICES Tests
# =============================================================================


class TestRecommendedActionChoices:
    """Tests for RECOMMENDED_ACTION_CHOICES constant."""

    def test_recommended_action_choices_is_list(self) -> None:
        """Test that RECOMMENDED_ACTION_CHOICES is a list."""
        assert isinstance(RECOMMENDED_ACTION_CHOICES, list)

    def test_recommended_action_choices_has_five_values(self) -> None:
        """Test that RECOMMENDED_ACTION_CHOICES has exactly five values."""
        assert len(RECOMMENDED_ACTION_CHOICES) == 5

    def test_recommended_action_choices_contains_none(self) -> None:
        """Test that RECOMMENDED_ACTION_CHOICES contains 'none'."""
        assert "none" in RECOMMENDED_ACTION_CHOICES

    def test_recommended_action_choices_contains_review_later(self) -> None:
        """Test that RECOMMENDED_ACTION_CHOICES contains 'review_later'."""
        assert "review_later" in RECOMMENDED_ACTION_CHOICES

    def test_recommended_action_choices_contains_review_soon(self) -> None:
        """Test that RECOMMENDED_ACTION_CHOICES contains 'review_soon'."""
        assert "review_soon" in RECOMMENDED_ACTION_CHOICES

    def test_recommended_action_choices_contains_alert_homeowner(self) -> None:
        """Test that RECOMMENDED_ACTION_CHOICES contains 'alert_homeowner'."""
        assert "alert_homeowner" in RECOMMENDED_ACTION_CHOICES

    def test_recommended_action_choices_contains_immediate_response(self) -> None:
        """Test that RECOMMENDED_ACTION_CHOICES contains 'immediate_response'."""
        assert "immediate_response" in RECOMMENDED_ACTION_CHOICES

    def test_recommended_action_choices_order(self) -> None:
        """Test that RECOMMENDED_ACTION_CHOICES is in urgency order."""
        assert RECOMMENDED_ACTION_CHOICES == [
            "none",
            "review_later",
            "review_soon",
            "alert_homeowner",
            "immediate_response",
        ]


# =============================================================================
# ENTITY_TYPE_CHOICES Tests
# =============================================================================


class TestEntityTypeChoices:
    """Tests for ENTITY_TYPE_CHOICES constant."""

    def test_entity_type_choices_is_list(self) -> None:
        """Test that ENTITY_TYPE_CHOICES is a list."""
        assert isinstance(ENTITY_TYPE_CHOICES, list)

    def test_entity_type_choices_has_four_values(self) -> None:
        """Test that ENTITY_TYPE_CHOICES has exactly four values."""
        assert len(ENTITY_TYPE_CHOICES) == 4

    def test_entity_type_choices_contains_person(self) -> None:
        """Test that ENTITY_TYPE_CHOICES contains 'person'."""
        assert "person" in ENTITY_TYPE_CHOICES

    def test_entity_type_choices_contains_vehicle(self) -> None:
        """Test that ENTITY_TYPE_CHOICES contains 'vehicle'."""
        assert "vehicle" in ENTITY_TYPE_CHOICES

    def test_entity_type_choices_contains_animal(self) -> None:
        """Test that ENTITY_TYPE_CHOICES contains 'animal'."""
        assert "animal" in ENTITY_TYPE_CHOICES

    def test_entity_type_choices_contains_object(self) -> None:
        """Test that ENTITY_TYPE_CHOICES contains 'object'."""
        assert "object" in ENTITY_TYPE_CHOICES


# =============================================================================
# THREAT_LEVEL_CHOICES Tests
# =============================================================================


class TestThreatLevelChoices:
    """Tests for THREAT_LEVEL_CHOICES constant."""

    def test_threat_level_choices_is_list(self) -> None:
        """Test that THREAT_LEVEL_CHOICES is a list."""
        assert isinstance(THREAT_LEVEL_CHOICES, list)

    def test_threat_level_choices_has_three_values(self) -> None:
        """Test that THREAT_LEVEL_CHOICES has exactly three values."""
        assert len(THREAT_LEVEL_CHOICES) == 3

    def test_threat_level_choices_contains_low(self) -> None:
        """Test that THREAT_LEVEL_CHOICES contains 'low'."""
        assert "low" in THREAT_LEVEL_CHOICES

    def test_threat_level_choices_contains_medium(self) -> None:
        """Test that THREAT_LEVEL_CHOICES contains 'medium'."""
        assert "medium" in THREAT_LEVEL_CHOICES

    def test_threat_level_choices_contains_high(self) -> None:
        """Test that THREAT_LEVEL_CHOICES contains 'high'."""
        assert "high" in THREAT_LEVEL_CHOICES

    def test_threat_level_choices_order(self) -> None:
        """Test that THREAT_LEVEL_CHOICES is in severity order."""
        assert THREAT_LEVEL_CHOICES == ["low", "medium", "high"]


# =============================================================================
# get_guided_choice_config Tests
# =============================================================================


class TestGetGuidedChoiceConfig:
    """Tests for get_guided_choice_config function."""

    def test_risk_level_returns_correct_structure(self) -> None:
        """Test that risk_level field returns correct config structure."""
        config = get_guided_choice_config("risk_level")
        assert config is not None
        assert "nvext" in config
        assert "guided_choice" in config["nvext"]
        assert config["nvext"]["guided_choice"] == RISK_LEVEL_CHOICES

    def test_recommended_action_returns_correct_structure(self) -> None:
        """Test that recommended_action field returns correct config structure."""
        config = get_guided_choice_config("recommended_action")
        assert config is not None
        assert "nvext" in config
        assert "guided_choice" in config["nvext"]
        assert config["nvext"]["guided_choice"] == RECOMMENDED_ACTION_CHOICES

    def test_entity_type_returns_correct_structure(self) -> None:
        """Test that entity_type field returns correct config structure."""
        config = get_guided_choice_config("entity_type")
        assert config is not None
        assert "nvext" in config
        assert "guided_choice" in config["nvext"]
        assert config["nvext"]["guided_choice"] == ENTITY_TYPE_CHOICES

    def test_threat_level_returns_correct_structure(self) -> None:
        """Test that threat_level field returns correct config structure."""
        config = get_guided_choice_config("threat_level")
        assert config is not None
        assert "nvext" in config
        assert "guided_choice" in config["nvext"]
        assert config["nvext"]["guided_choice"] == THREAT_LEVEL_CHOICES

    def test_unknown_field_returns_none(self) -> None:
        """Test that unknown field returns None."""
        config = get_guided_choice_config("unknown_field")
        assert config is None

    def test_empty_string_returns_none(self) -> None:
        """Test that empty string returns None."""
        config = get_guided_choice_config("")
        assert config is None

    def test_case_sensitive_field_names(self) -> None:
        """Test that field names are case-sensitive."""
        config = get_guided_choice_config("Risk_Level")
        assert config is None
        config = get_guided_choice_config("RISK_LEVEL")
        assert config is None


# =============================================================================
# get_guided_regex_config Tests
# =============================================================================


class TestGetGuidedRegexConfig:
    """Tests for get_guided_regex_config function."""

    def test_risk_score_returns_correct_structure(self) -> None:
        """Test that risk_score field returns correct config structure."""
        config = get_guided_regex_config("risk_score")
        assert config is not None
        assert "nvext" in config
        assert "guided_regex" in config["nvext"]
        assert config["nvext"]["guided_regex"] == r"[0-9]|[1-9][0-9]|100"

    def test_threat_level_score_returns_correct_structure(self) -> None:
        """Test that threat_level_score field returns correct config structure."""
        config = get_guided_regex_config("threat_level_score")
        assert config is not None
        assert "nvext" in config
        assert "guided_regex" in config["nvext"]
        assert config["nvext"]["guided_regex"] == r"[0-4]"

    def test_intent_score_returns_correct_structure(self) -> None:
        """Test that intent_score field returns correct config structure."""
        config = get_guided_regex_config("intent_score")
        assert config is not None
        assert "nvext" in config
        assert "guided_regex" in config["nvext"]
        assert config["nvext"]["guided_regex"] == r"[0-3]"

    def test_time_context_score_returns_correct_structure(self) -> None:
        """Test that time_context_score field returns correct config structure."""
        config = get_guided_regex_config("time_context_score")
        assert config is not None
        assert "nvext" in config
        assert "guided_regex" in config["nvext"]
        assert config["nvext"]["guided_regex"] == r"[0-2]"

    def test_unknown_field_returns_none(self) -> None:
        """Test that unknown field returns None."""
        config = get_guided_regex_config("unknown_field")
        assert config is None

    def test_empty_string_returns_none(self) -> None:
        """Test that empty string returns None."""
        config = get_guided_regex_config("")
        assert config is None

    def test_case_sensitive_field_names(self) -> None:
        """Test that field names are case-sensitive."""
        config = get_guided_regex_config("Risk_Score")
        assert config is None
        config = get_guided_regex_config("RISK_SCORE")
        assert config is None


# =============================================================================
# Regex Pattern Validation Tests
# =============================================================================


class TestRegexPatterns:
    """Tests to verify regex patterns match expected values."""

    def test_risk_score_regex_matches_0(self) -> None:
        """Test that risk_score regex matches '0'."""
        import re

        config = get_guided_regex_config("risk_score")
        assert config is not None
        pattern = config["nvext"]["guided_regex"]
        assert re.fullmatch(pattern, "0") is not None

    def test_risk_score_regex_matches_single_digits(self) -> None:
        """Test that risk_score regex matches single digits 0-9."""
        import re

        config = get_guided_regex_config("risk_score")
        assert config is not None
        pattern = config["nvext"]["guided_regex"]
        for i in range(10):
            assert re.fullmatch(pattern, str(i)) is not None

    def test_risk_score_regex_matches_double_digits(self) -> None:
        """Test that risk_score regex matches double digits 10-99."""
        import re

        config = get_guided_regex_config("risk_score")
        assert config is not None
        pattern = config["nvext"]["guided_regex"]
        for i in range(10, 100):
            assert re.fullmatch(pattern, str(i)) is not None

    def test_risk_score_regex_matches_100(self) -> None:
        """Test that risk_score regex matches '100'."""
        import re

        config = get_guided_regex_config("risk_score")
        assert config is not None
        pattern = config["nvext"]["guided_regex"]
        assert re.fullmatch(pattern, "100") is not None

    def test_threat_level_score_regex_matches_0_to_4(self) -> None:
        """Test that threat_level_score regex matches 0-4."""
        import re

        config = get_guided_regex_config("threat_level_score")
        assert config is not None
        pattern = config["nvext"]["guided_regex"]
        for i in range(5):
            assert re.fullmatch(pattern, str(i)) is not None

    def test_threat_level_score_regex_rejects_5(self) -> None:
        """Test that threat_level_score regex rejects '5'."""
        import re

        config = get_guided_regex_config("threat_level_score")
        assert config is not None
        pattern = config["nvext"]["guided_regex"]
        assert re.fullmatch(pattern, "5") is None

    def test_intent_score_regex_matches_0_to_3(self) -> None:
        """Test that intent_score regex matches 0-3."""
        import re

        config = get_guided_regex_config("intent_score")
        assert config is not None
        pattern = config["nvext"]["guided_regex"]
        for i in range(4):
            assert re.fullmatch(pattern, str(i)) is not None

    def test_intent_score_regex_rejects_4(self) -> None:
        """Test that intent_score regex rejects '4'."""
        import re

        config = get_guided_regex_config("intent_score")
        assert config is not None
        pattern = config["nvext"]["guided_regex"]
        assert re.fullmatch(pattern, "4") is None

    def test_time_context_score_regex_matches_0_to_2(self) -> None:
        """Test that time_context_score regex matches 0-2."""
        import re

        config = get_guided_regex_config("time_context_score")
        assert config is not None
        pattern = config["nvext"]["guided_regex"]
        for i in range(3):
            assert re.fullmatch(pattern, str(i)) is not None

    def test_time_context_score_regex_rejects_3(self) -> None:
        """Test that time_context_score regex rejects '3'."""
        import re

        config = get_guided_regex_config("time_context_score")
        assert config is not None
        pattern = config["nvext"]["guided_regex"]
        assert re.fullmatch(pattern, "3") is None


# =============================================================================
# validate_risk_level Tests
# =============================================================================


class TestValidateRiskLevel:
    """Tests for validate_risk_level function."""

    def test_accepts_low(self) -> None:
        """Test that validate_risk_level accepts 'low'."""
        assert validate_risk_level("low") is True

    def test_accepts_medium(self) -> None:
        """Test that validate_risk_level accepts 'medium'."""
        assert validate_risk_level("medium") is True

    def test_accepts_high(self) -> None:
        """Test that validate_risk_level accepts 'high'."""
        assert validate_risk_level("high") is True

    def test_accepts_critical(self) -> None:
        """Test that validate_risk_level accepts 'critical'."""
        assert validate_risk_level("critical") is True

    def test_rejects_invalid_level(self) -> None:
        """Test that validate_risk_level rejects invalid levels."""
        assert validate_risk_level("extreme") is False
        assert validate_risk_level("severe") is False
        assert validate_risk_level("moderate") is False

    def test_rejects_empty_string(self) -> None:
        """Test that validate_risk_level rejects empty string."""
        assert validate_risk_level("") is False

    def test_rejects_uppercase(self) -> None:
        """Test that validate_risk_level rejects uppercase variants."""
        assert validate_risk_level("LOW") is False
        assert validate_risk_level("High") is False
        assert validate_risk_level("CRITICAL") is False

    def test_rejects_numeric_string(self) -> None:
        """Test that validate_risk_level rejects numeric strings."""
        assert validate_risk_level("1") is False
        assert validate_risk_level("100") is False


class TestValidateRiskLevelParametrized:
    """Parametrized tests for validate_risk_level."""

    @pytest.mark.parametrize("level", RISK_LEVEL_CHOICES)
    def test_all_valid_levels_accepted(self, level: str) -> None:
        """Test that all valid risk levels are accepted."""
        assert validate_risk_level(level) is True

    @pytest.mark.parametrize(
        "level",
        [
            "invalid",
            "extreme",
            "LOW",
            "MEDIUM",
            "HIGH",
            "CRITICAL",
            "",
            "none",
            "urgent",
            " low",
            "low ",
        ],
    )
    def test_invalid_levels_rejected(self, level: str) -> None:
        """Test that invalid risk levels are rejected."""
        assert validate_risk_level(level) is False


# =============================================================================
# validate_recommended_action Tests
# =============================================================================


class TestValidateRecommendedAction:
    """Tests for validate_recommended_action function."""

    def test_accepts_none(self) -> None:
        """Test that validate_recommended_action accepts 'none'."""
        assert validate_recommended_action("none") is True

    def test_accepts_review_later(self) -> None:
        """Test that validate_recommended_action accepts 'review_later'."""
        assert validate_recommended_action("review_later") is True

    def test_accepts_review_soon(self) -> None:
        """Test that validate_recommended_action accepts 'review_soon'."""
        assert validate_recommended_action("review_soon") is True

    def test_accepts_alert_homeowner(self) -> None:
        """Test that validate_recommended_action accepts 'alert_homeowner'."""
        assert validate_recommended_action("alert_homeowner") is True

    def test_accepts_immediate_response(self) -> None:
        """Test that validate_recommended_action accepts 'immediate_response'."""
        assert validate_recommended_action("immediate_response") is True

    def test_rejects_invalid_action(self) -> None:
        """Test that validate_recommended_action rejects invalid actions."""
        assert validate_recommended_action("call_police") is False
        assert validate_recommended_action("ignore") is False
        assert validate_recommended_action("notify") is False

    def test_rejects_empty_string(self) -> None:
        """Test that validate_recommended_action rejects empty string."""
        assert validate_recommended_action("") is False

    def test_rejects_uppercase(self) -> None:
        """Test that validate_recommended_action rejects uppercase variants."""
        assert validate_recommended_action("NONE") is False
        assert validate_recommended_action("Alert_Homeowner") is False

    def test_rejects_similar_but_incorrect(self) -> None:
        """Test that validate_recommended_action rejects similar but incorrect values."""
        assert validate_recommended_action("review-later") is False
        assert validate_recommended_action("review_now") is False
        assert validate_recommended_action("immediate") is False


class TestValidateRecommendedActionParametrized:
    """Parametrized tests for validate_recommended_action."""

    @pytest.mark.parametrize("action", RECOMMENDED_ACTION_CHOICES)
    def test_all_valid_actions_accepted(self, action: str) -> None:
        """Test that all valid recommended actions are accepted."""
        assert validate_recommended_action(action) is True

    @pytest.mark.parametrize(
        "action",
        [
            "invalid",
            "call_police",
            "NONE",
            "",
            "ignore",
            "notify",
            " none",
            "none ",
            "review-later",
        ],
    )
    def test_invalid_actions_rejected(self, action: str) -> None:
        """Test that invalid recommended actions are rejected."""
        assert validate_recommended_action(action) is False


# =============================================================================
# validate_entity_type Tests
# =============================================================================


class TestValidateEntityType:
    """Tests for validate_entity_type function."""

    def test_accepts_person(self) -> None:
        """Test that validate_entity_type accepts 'person'."""
        assert validate_entity_type("person") is True

    def test_accepts_vehicle(self) -> None:
        """Test that validate_entity_type accepts 'vehicle'."""
        assert validate_entity_type("vehicle") is True

    def test_accepts_animal(self) -> None:
        """Test that validate_entity_type accepts 'animal'."""
        assert validate_entity_type("animal") is True

    def test_accepts_object(self) -> None:
        """Test that validate_entity_type accepts 'object'."""
        assert validate_entity_type("object") is True

    def test_rejects_invalid_type(self) -> None:
        """Test that validate_entity_type rejects invalid types."""
        assert validate_entity_type("robot") is False
        assert validate_entity_type("human") is False
        assert validate_entity_type("car") is False

    def test_rejects_empty_string(self) -> None:
        """Test that validate_entity_type rejects empty string."""
        assert validate_entity_type("") is False

    def test_rejects_uppercase(self) -> None:
        """Test that validate_entity_type rejects uppercase variants."""
        assert validate_entity_type("PERSON") is False
        assert validate_entity_type("Vehicle") is False


class TestValidateEntityTypeParametrized:
    """Parametrized tests for validate_entity_type."""

    @pytest.mark.parametrize("entity_type", ENTITY_TYPE_CHOICES)
    def test_all_valid_types_accepted(self, entity_type: str) -> None:
        """Test that all valid entity types are accepted."""
        assert validate_entity_type(entity_type) is True

    @pytest.mark.parametrize(
        "entity_type",
        [
            "invalid",
            "robot",
            "PERSON",
            "",
            "human",
            "car",
            " person",
            "person ",
        ],
    )
    def test_invalid_types_rejected(self, entity_type: str) -> None:
        """Test that invalid entity types are rejected."""
        assert validate_entity_type(entity_type) is False


# =============================================================================
# validate_threat_level Tests
# =============================================================================


class TestValidateThreatLevel:
    """Tests for validate_threat_level function."""

    def test_accepts_low(self) -> None:
        """Test that validate_threat_level accepts 'low'."""
        assert validate_threat_level("low") is True

    def test_accepts_medium(self) -> None:
        """Test that validate_threat_level accepts 'medium'."""
        assert validate_threat_level("medium") is True

    def test_accepts_high(self) -> None:
        """Test that validate_threat_level accepts 'high'."""
        assert validate_threat_level("high") is True

    def test_rejects_critical(self) -> None:
        """Test that validate_threat_level rejects 'critical' (not in THREAT_LEVEL_CHOICES)."""
        assert validate_threat_level("critical") is False

    def test_rejects_invalid_level(self) -> None:
        """Test that validate_threat_level rejects invalid levels."""
        assert validate_threat_level("extreme") is False
        assert validate_threat_level("severe") is False

    def test_rejects_empty_string(self) -> None:
        """Test that validate_threat_level rejects empty string."""
        assert validate_threat_level("") is False

    def test_rejects_uppercase(self) -> None:
        """Test that validate_threat_level rejects uppercase variants."""
        assert validate_threat_level("LOW") is False
        assert validate_threat_level("High") is False


class TestValidateThreatLevelParametrized:
    """Parametrized tests for validate_threat_level."""

    @pytest.mark.parametrize("level", THREAT_LEVEL_CHOICES)
    def test_all_valid_levels_accepted(self, level: str) -> None:
        """Test that all valid threat levels are accepted."""
        assert validate_threat_level(level) is True

    @pytest.mark.parametrize(
        "level",
        [
            "invalid",
            "critical",
            "LOW",
            "MEDIUM",
            "HIGH",
            "",
            "none",
            " low",
            "low ",
        ],
    )
    def test_invalid_levels_rejected(self, level: str) -> None:
        """Test that invalid threat levels are rejected."""
        assert validate_threat_level(level) is False


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for guided_constraints module."""

    def test_all_choice_lists_are_non_empty(self) -> None:
        """Test that all choice lists have at least one value."""
        assert len(RISK_LEVEL_CHOICES) > 0
        assert len(RECOMMENDED_ACTION_CHOICES) > 0
        assert len(ENTITY_TYPE_CHOICES) > 0
        assert len(THREAT_LEVEL_CHOICES) > 0

    def test_all_choice_lists_contain_strings(self) -> None:
        """Test that all choice lists contain only strings."""
        for choice in RISK_LEVEL_CHOICES:
            assert isinstance(choice, str)
        for choice in RECOMMENDED_ACTION_CHOICES:
            assert isinstance(choice, str)
        for choice in ENTITY_TYPE_CHOICES:
            assert isinstance(choice, str)
        for choice in THREAT_LEVEL_CHOICES:
            assert isinstance(choice, str)

    def test_all_choice_lists_have_unique_values(self) -> None:
        """Test that all choice lists have unique values."""
        assert len(RISK_LEVEL_CHOICES) == len(set(RISK_LEVEL_CHOICES))
        assert len(RECOMMENDED_ACTION_CHOICES) == len(set(RECOMMENDED_ACTION_CHOICES))
        assert len(ENTITY_TYPE_CHOICES) == len(set(ENTITY_TYPE_CHOICES))
        assert len(THREAT_LEVEL_CHOICES) == len(set(THREAT_LEVEL_CHOICES))

    def test_validation_functions_match_choice_lists(self) -> None:
        """Test that validation functions match their respective choice lists."""
        for level in RISK_LEVEL_CHOICES:
            assert validate_risk_level(level) is True

        for action in RECOMMENDED_ACTION_CHOICES:
            assert validate_recommended_action(action) is True

        for entity_type in ENTITY_TYPE_CHOICES:
            assert validate_entity_type(entity_type) is True

        for threat_level in THREAT_LEVEL_CHOICES:
            assert validate_threat_level(threat_level) is True

    def test_guided_choice_configs_match_choice_lists(self) -> None:
        """Test that guided_choice configs match their respective choice lists."""
        risk_config = get_guided_choice_config("risk_level")
        assert risk_config is not None
        assert risk_config["nvext"]["guided_choice"] == RISK_LEVEL_CHOICES

        action_config = get_guided_choice_config("recommended_action")
        assert action_config is not None
        assert action_config["nvext"]["guided_choice"] == RECOMMENDED_ACTION_CHOICES

        entity_config = get_guided_choice_config("entity_type")
        assert entity_config is not None
        assert entity_config["nvext"]["guided_choice"] == ENTITY_TYPE_CHOICES

        threat_config = get_guided_choice_config("threat_level")
        assert threat_config is not None
        assert threat_config["nvext"]["guided_choice"] == THREAT_LEVEL_CHOICES
