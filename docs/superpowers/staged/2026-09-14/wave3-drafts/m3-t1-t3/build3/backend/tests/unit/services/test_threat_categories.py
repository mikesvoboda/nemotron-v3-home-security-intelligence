"""Unit tests for backend/services/threat_categories.py

Tests for threat category classification system based on NVIDIA's safety
categories for home surveillance applications.

Test Categories:
- ThreatCategory enum values and serialization
- THREAT_CATEGORY_DESCRIPTIONS completeness
- get_category_prompt_section() output format
- Category serialization/deserialization with Pydantic

References:
- NEM-3730: Add Threat Category Classification
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from backend.services.threat_categories import (
    THREAT_CATEGORY_DESCRIPTIONS,
    ThreatCategory,
    get_category_prompt_section,
)

# =============================================================================
# Test Classes for ThreatCategory Enum
# =============================================================================


class TestThreatCategoryEnumValues:
    """Tests for ThreatCategory enum values and structure."""

    def test_all_expected_categories_exist(self) -> None:
        """Test that all expected threat categories are defined."""
        expected_categories = {
            "violence",
            "weapon_visible",
            "criminal_planning",
            "threat_intimidation",
            "fraud_deception",
            "illegal_activity",
            "property_damage",
            "trespassing",
            "theft_attempt",
            "surveillance_casing",
            "none",
        }
        actual_categories = {cat.value for cat in ThreatCategory}
        assert actual_categories == expected_categories

    def test_category_count(self) -> None:
        """Test that we have the expected number of categories."""
        # 10 threat categories + 1 NONE category
        assert len(ThreatCategory) == 11

    def test_violence_category(self) -> None:
        """Test VIOLENCE category value."""
        assert ThreatCategory.VIOLENCE.value == "violence"

    def test_weapon_visible_category(self) -> None:
        """Test WEAPON_VISIBLE category value."""
        assert ThreatCategory.WEAPON_VISIBLE.value == "weapon_visible"

    def test_criminal_planning_category(self) -> None:
        """Test CRIMINAL_PLANNING category value."""
        assert ThreatCategory.CRIMINAL_PLANNING.value == "criminal_planning"

    def test_threat_intimidation_category(self) -> None:
        """Test THREAT_INTIMIDATION category value."""
        assert ThreatCategory.THREAT_INTIMIDATION.value == "threat_intimidation"

    def test_fraud_deception_category(self) -> None:
        """Test FRAUD_DECEPTION category value."""
        assert ThreatCategory.FRAUD_DECEPTION.value == "fraud_deception"

    def test_illegal_activity_category(self) -> None:
        """Test ILLEGAL_ACTIVITY category value."""
        assert ThreatCategory.ILLEGAL_ACTIVITY.value == "illegal_activity"

    def test_property_damage_category(self) -> None:
        """Test PROPERTY_DAMAGE category value."""
        assert ThreatCategory.PROPERTY_DAMAGE.value == "property_damage"

    def test_trespassing_category(self) -> None:
        """Test TRESPASSING category value."""
        assert ThreatCategory.TRESPASSING.value == "trespassing"

    def test_theft_attempt_category(self) -> None:
        """Test THEFT_ATTEMPT category value."""
        assert ThreatCategory.THEFT_ATTEMPT.value == "theft_attempt"

    def test_surveillance_casing_category(self) -> None:
        """Test SURVEILLANCE_CASING category value."""
        assert ThreatCategory.SURVEILLANCE_CASING.value == "surveillance_casing"

    def test_none_category(self) -> None:
        """Test NONE category value."""
        assert ThreatCategory.NONE.value == "none"


class TestThreatCategoryStrEnum:
    """Tests for ThreatCategory str enum behavior."""

    def test_category_is_string(self) -> None:
        """Test that ThreatCategory values are strings."""
        for category in ThreatCategory:
            assert isinstance(category.value, str)
            # str enum also makes the enum itself act as a string
            assert isinstance(category, str)

    def test_string_comparison(self) -> None:
        """Test that categories can be compared to strings."""
        assert ThreatCategory.VIOLENCE == "violence"
        assert ThreatCategory.NONE == "none"

    def test_string_representation(self) -> None:
        """Test string representation of categories."""
        assert str(ThreatCategory.VIOLENCE) == "violence"
        assert str(ThreatCategory.WEAPON_VISIBLE) == "weapon_visible"


# =============================================================================
# Test Classes for THREAT_CATEGORY_DESCRIPTIONS
# =============================================================================


class TestThreatCategoryDescriptions:
    """Tests for THREAT_CATEGORY_DESCRIPTIONS completeness and format."""

    def test_all_categories_have_descriptions(self) -> None:
        """Test that every ThreatCategory has a description."""
        for category in ThreatCategory:
            assert category in THREAT_CATEGORY_DESCRIPTIONS, (
                f"Missing description for {category.name}"
            )

    def test_descriptions_are_non_empty_strings(self) -> None:
        """Test that all descriptions are non-empty strings."""
        for category, description in THREAT_CATEGORY_DESCRIPTIONS.items():
            assert isinstance(description, str), f"Description for {category.name} is not a string"
            assert len(description) > 0, f"Description for {category.name} is empty"

    def test_violence_description(self) -> None:
        """Test VIOLENCE category has appropriate description."""
        desc = THREAT_CATEGORY_DESCRIPTIONS[ThreatCategory.VIOLENCE]
        assert "violence" in desc.lower() or "fighting" in desc.lower()

    def test_weapon_visible_description(self) -> None:
        """Test WEAPON_VISIBLE category has appropriate description."""
        desc = THREAT_CATEGORY_DESCRIPTIONS[ThreatCategory.WEAPON_VISIBLE]
        assert "weapon" in desc.lower() or "firearm" in desc.lower()

    def test_theft_attempt_description(self) -> None:
        """Test THEFT_ATTEMPT category has appropriate description."""
        desc = THREAT_CATEGORY_DESCRIPTIONS[ThreatCategory.THEFT_ATTEMPT]
        assert "property" in desc.lower() or "taking" in desc.lower()

    def test_trespassing_description(self) -> None:
        """Test TRESPASSING category has appropriate description."""
        desc = THREAT_CATEGORY_DESCRIPTIONS[ThreatCategory.TRESPASSING]
        assert "unauthorized" in desc.lower() or "entry" in desc.lower()

    def test_none_description(self) -> None:
        """Test NONE category has appropriate description."""
        desc = THREAT_CATEGORY_DESCRIPTIONS[ThreatCategory.NONE]
        assert "no threat" in desc.lower() or "none" in desc.lower()

    def test_no_extra_descriptions(self) -> None:
        """Test that there are no extra descriptions without matching categories."""
        description_keys = set(THREAT_CATEGORY_DESCRIPTIONS.keys())
        category_values = set(ThreatCategory)
        assert description_keys == category_values, (
            f"Extra descriptions: {description_keys - category_values}"
        )


# =============================================================================
# Test Classes for get_category_prompt_section()
# =============================================================================


class TestGetCategoryPromptSection:
    """Tests for get_category_prompt_section() output format."""

    def test_returns_string(self) -> None:
        """Test that function returns a string."""
        result = get_category_prompt_section()
        assert isinstance(result, str)

    def test_starts_with_header(self) -> None:
        """Test that output starts with THREAT CATEGORIES header."""
        result = get_category_prompt_section()
        lines = result.strip().split("\n")
        assert lines[0] == "## THREAT CATEGORIES"

    def test_contains_all_categories(self) -> None:
        """Test that output contains all threat categories."""
        result = get_category_prompt_section()
        for category in ThreatCategory:
            assert category.value in result, (
                f"Category {category.value} not found in prompt section"
            )

    def test_contains_all_descriptions(self) -> None:
        """Test that output contains all category descriptions."""
        result = get_category_prompt_section()
        for description in THREAT_CATEGORY_DESCRIPTIONS.values():
            assert description in result, f"Description '{description}' not found in prompt section"

    def test_line_format(self) -> None:
        """Test that category lines follow expected format."""
        result = get_category_prompt_section()
        lines = result.strip().split("\n")
        # Skip header line
        category_lines = [line for line in lines[1:] if line.strip()]

        for line in category_lines:
            # Each line should start with "- " (bullet point)
            assert line.startswith("- "), f"Line does not start with '- ': {line}"
            # Each line should contain ": " (category: description separator)
            assert ": " in line, f"Line does not contain ': ': {line}"

    def test_output_is_multiline(self) -> None:
        """Test that output is properly formatted as multiple lines."""
        result = get_category_prompt_section()
        lines = result.strip().split("\n")
        # Header + at least 11 category lines
        assert len(lines) >= 12

    def test_violence_line_format(self) -> None:
        """Test specific format for VIOLENCE category line."""
        result = get_category_prompt_section()
        assert f"- {ThreatCategory.VIOLENCE.value}: " in result

    def test_none_category_included(self) -> None:
        """Test that NONE category is included in output."""
        result = get_category_prompt_section()
        assert f"- {ThreatCategory.NONE.value}: " in result


# =============================================================================
# Test Classes for Serialization/Deserialization
# =============================================================================


class TestCategorySerialization:
    """Tests for category serialization and deserialization."""

    def test_category_to_json_string(self) -> None:
        """Test that category serializes to JSON string value."""

        class TestModel(BaseModel):
            category: ThreatCategory

        model = TestModel(category=ThreatCategory.VIOLENCE)
        json_data = model.model_dump_json()
        assert '"violence"' in json_data

    def test_category_from_string(self) -> None:
        """Test that category can be deserialized from string."""

        class TestModel(BaseModel):
            category: ThreatCategory

        model = TestModel(category="violence")  # type: ignore[arg-type]
        assert model.category == ThreatCategory.VIOLENCE

    def test_category_list_serialization(self) -> None:
        """Test that list of categories serializes correctly."""

        class TestModel(BaseModel):
            categories: list[ThreatCategory]

        model = TestModel(categories=[ThreatCategory.VIOLENCE, ThreatCategory.WEAPON_VISIBLE])
        json_data = model.model_dump_json()
        assert '"violence"' in json_data
        assert '"weapon_visible"' in json_data

    def test_category_list_deserialization(self) -> None:
        """Test that list of categories deserializes from strings."""

        class TestModel(BaseModel):
            categories: list[ThreatCategory]

        model = TestModel(categories=["violence", "weapon_visible"])  # type: ignore[list-item]
        assert ThreatCategory.VIOLENCE in model.categories
        assert ThreatCategory.WEAPON_VISIBLE in model.categories

    def test_optional_category_none(self) -> None:
        """Test that optional category handles None correctly."""

        class TestModel(BaseModel):
            primary_threat: ThreatCategory | None = None

        model = TestModel()
        assert model.primary_threat is None

    def test_optional_category_set(self) -> None:
        """Test that optional category can be set."""

        class TestModel(BaseModel):
            primary_threat: ThreatCategory | None = None

        model = TestModel(primary_threat=ThreatCategory.TRESPASSING)
        assert model.primary_threat == ThreatCategory.TRESPASSING

    def test_invalid_category_raises_error(self) -> None:
        """Test that invalid category value raises validation error."""
        from pydantic import ValidationError

        class TestModel(BaseModel):
            category: ThreatCategory

        with pytest.raises(ValidationError):
            TestModel(category="invalid_category")  # type: ignore[arg-type]


# =============================================================================
# Test Classes for Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_category_iteration(self) -> None:
        """Test that categories can be iterated."""
        categories = list(ThreatCategory)
        assert len(categories) == 11

    def test_category_membership(self) -> None:
        """Test category membership checking."""
        assert "violence" in [cat.value for cat in ThreatCategory]
        assert "invalid" not in [cat.value for cat in ThreatCategory]

    def test_category_hashable(self) -> None:
        """Test that categories are hashable (can be used in sets/dicts)."""
        category_set = {ThreatCategory.VIOLENCE, ThreatCategory.WEAPON_VISIBLE}
        assert len(category_set) == 2
        assert ThreatCategory.VIOLENCE in category_set

    def test_category_equality(self) -> None:
        """Test category equality comparisons."""
        assert ThreatCategory.VIOLENCE == ThreatCategory.VIOLENCE
        assert ThreatCategory.VIOLENCE != ThreatCategory.NONE

    def test_prompt_section_idempotent(self) -> None:
        """Test that get_category_prompt_section returns consistent results."""
        result1 = get_category_prompt_section()
        result2 = get_category_prompt_section()
        assert result1 == result2
