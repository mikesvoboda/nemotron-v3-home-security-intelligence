"""Unit tests for comparison_engine.py.

ABOUTME: Tests for the ComparisonEngine class, particularly the semantic
caption matching functionality that uses synonym expansion for Florence
caption validation.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path for imports - must be before script imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402

from scripts.synthetic.comparison_engine import (  # noqa: E402
    CAPTION_SYNONYMS,
    ComparisonEngine,
    check_caption_keywords_with_synonyms,
)


class TestCaptionSynonymsDictionary:
    """Tests for the CAPTION_SYNONYMS dictionary structure."""

    def test_synonyms_dict_exists(self):
        """CAPTION_SYNONYMS should be a dictionary."""
        assert isinstance(CAPTION_SYNONYMS, dict)

    def test_synonyms_contains_package(self):
        """Package synonyms should include common alternatives."""
        assert "package" in CAPTION_SYNONYMS
        synonyms = CAPTION_SYNONYMS["package"]
        assert "box" in synonyms
        assert "parcel" in synonyms
        assert "cardboard box" in synonyms
        assert "delivery" in synonyms

    def test_synonyms_contains_person(self):
        """Person synonyms should include common alternatives."""
        assert "person" in CAPTION_SYNONYMS
        synonyms = CAPTION_SYNONYMS["person"]
        assert "man" in synonyms
        assert "woman" in synonyms
        assert "individual" in synonyms
        assert "figure" in synonyms
        assert "someone" in synonyms

    def test_synonyms_contains_car(self):
        """Car synonyms should include vehicle alternatives."""
        assert "car" in CAPTION_SYNONYMS
        synonyms = CAPTION_SYNONYMS["car"]
        assert "vehicle" in synonyms
        assert "automobile" in synonyms
        assert "sedan" in synonyms
        assert "suv" in synonyms

    def test_synonyms_contains_door(self):
        """Door synonyms should include entrance alternatives."""
        assert "door" in CAPTION_SYNONYMS
        synonyms = CAPTION_SYNONYMS["door"]
        assert "entrance" in synonyms
        assert "doorway" in synonyms

    def test_synonyms_contains_pets(self):
        """Pet synonyms should include common alternatives."""
        assert "dog" in CAPTION_SYNONYMS
        synonyms = CAPTION_SYNONYMS["dog"]
        assert "canine" in synonyms
        assert "puppy" in synonyms

        assert "cat" in CAPTION_SYNONYMS
        synonyms = CAPTION_SYNONYMS["cat"]
        assert "feline" in synonyms
        assert "kitten" in synonyms

    def test_synonyms_all_lowercase(self):
        """All synonyms should be lowercase for case-insensitive matching."""
        for keyword, synonyms in CAPTION_SYNONYMS.items():
            assert keyword == keyword.lower(), f"Key '{keyword}' should be lowercase"
            for syn in synonyms:
                assert syn == syn.lower(), f"Synonym '{syn}' for '{keyword}' should be lowercase"


class TestCheckCaptionKeywordsWithSynonyms:
    """Tests for the check_caption_keywords_with_synonyms function."""

    def test_exact_match_succeeds(self):
        """Exact keyword match should succeed."""
        assert check_caption_keywords_with_synonyms(
            "A person standing near a package", ["person", "package"]
        )

    def test_synonym_match_succeeds(self):
        """Synonym match should succeed."""
        # "cardboard box" is a synonym for "package"
        assert check_caption_keywords_with_synonyms(
            "A man holding a cardboard box", ["person", "package"]
        )

    def test_multiple_synonyms_match(self):
        """Multiple synonym matches should all succeed."""
        # "woman" is synonym for "person", "parcel" is synonym for "package"
        assert check_caption_keywords_with_synonyms(
            "A woman delivering a parcel to the doorway", ["person", "package", "door"]
        )

    def test_case_insensitive_matching(self):
        """Matching should be case-insensitive."""
        assert check_caption_keywords_with_synonyms(
            "A PERSON standing by the DOOR", ["person", "door"]
        )

    def test_missing_keyword_fails(self):
        """Missing keyword with no synonym match should fail."""
        assert not check_caption_keywords_with_synonyms(
            "A person standing alone", ["person", "package"]
        )

    def test_empty_keywords_succeeds(self):
        """Empty keyword list should always succeed."""
        assert check_caption_keywords_with_synonyms("Any caption text", [])

    def test_empty_caption_fails(self):
        """Empty caption should fail if keywords required."""
        assert not check_caption_keywords_with_synonyms("", ["person"])

    def test_unknown_keyword_uses_literal_match(self):
        """Unknown keyword not in SYNONYMS should use literal match."""
        assert check_caption_keywords_with_synonyms("A mysterious object appeared", ["mysterious"])
        assert not check_caption_keywords_with_synonyms("A strange object appeared", ["mysterious"])

    def test_partial_word_match_succeeds(self):
        """Partial word match within caption should succeed."""
        # "person" should match in "A person's car"
        assert check_caption_keywords_with_synonyms("A person's car", ["person"])

    def test_vehicle_synonyms(self):
        """Vehicle-related synonyms should work."""
        assert check_caption_keywords_with_synonyms("A sedan parked in the driveway", ["car"])
        assert check_caption_keywords_with_synonyms("An SUV pulling into the garage", ["car"])

    def test_porch_and_house_synonyms(self):
        """Porch and house synonyms should be recognized."""
        assert check_caption_keywords_with_synonyms(
            "Someone standing at the front steps", ["porch"]
        )
        assert check_caption_keywords_with_synonyms(
            "A residential building with a fence", ["house"]
        )

    def test_walking_and_running_synonyms(self):
        """Action synonyms should be recognized."""
        assert check_caption_keywords_with_synonyms("A man approaching the entrance", ["walking"])
        assert check_caption_keywords_with_synonyms("Someone sprinting away", ["running"])


class TestComparisonEngineFlorenceCaption:
    """Tests for ComparisonEngine._compare_florence_caption with semantic matching."""

    @pytest.fixture
    def engine(self):
        """Create a ComparisonEngine instance."""
        return ComparisonEngine()

    def test_must_contain_with_exact_match(self, engine):
        """must_contain with exact match should pass."""
        expected = {"must_contain": ["person", "package"]}
        actual = "A person is holding a package near the door"

        results = engine._compare_florence_caption(expected, actual)

        assert len(results) == 1
        assert results[0].passed
        assert results[0].field_name == "florence_caption.must_contain"

    def test_must_contain_with_synonym_match(self, engine):
        """must_contain with synonym match should pass."""
        expected = {"must_contain": ["person", "package"]}
        actual = "A woman is carrying a cardboard box"

        results = engine._compare_florence_caption(expected, actual)

        assert len(results) == 1
        assert results[0].passed

    def test_must_contain_with_missing_keyword(self, engine):
        """must_contain with missing keyword should fail."""
        expected = {"must_contain": ["person", "weapon"]}
        actual = "A person standing alone"

        results = engine._compare_florence_caption(expected, actual)

        assert len(results) == 1
        assert not results[0].passed
        assert "missing_keywords" in results[0].diff

    def test_must_not_contain_with_no_matches(self, engine):
        """must_not_contain with no matches should pass."""
        expected = {"must_not_contain": ["suspicious", "threat"]}
        actual = "A delivery driver with a package"

        results = engine._compare_florence_caption(expected, actual)

        assert len(results) == 1
        assert results[0].passed

    def test_must_not_contain_with_match(self, engine):
        """must_not_contain with match should fail."""
        expected = {"must_not_contain": ["suspicious", "threat"]}
        actual = "A suspicious person lurking near the door"

        results = engine._compare_florence_caption(expected, actual)

        assert len(results) == 1
        assert not results[0].passed

    def test_combined_must_contain_and_must_not_contain(self, engine):
        """Both must_contain and must_not_contain should be validated."""
        expected = {
            "must_contain": ["person", "package"],
            "must_not_contain": ["stealing", "theft"],
        }
        actual = "A delivery person with a parcel at the front door"

        results = engine._compare_florence_caption(expected, actual)

        assert len(results) == 2
        assert all(r.passed for r in results)

    def test_actual_as_dict_with_caption_key(self, engine):
        """Should handle actual as dict with 'caption' key."""
        expected = {"must_contain": ["person"]}
        actual = {"caption": "A man walking down the street"}

        results = engine._compare_florence_caption(expected, actual)

        assert len(results) == 1
        assert results[0].passed

    def test_actual_as_none(self, engine):
        """Should handle None actual value."""
        expected = {"must_contain": ["person"]}
        actual = None

        results = engine._compare_florence_caption(expected, actual)

        assert len(results) == 1
        assert not results[0].passed


class TestComparisonEngineFullIntegration:
    """Integration tests for full comparison flow with Florence captions."""

    @pytest.fixture
    def engine(self):
        """Create a ComparisonEngine instance."""
        return ComparisonEngine()

    def test_realistic_package_theft_scenario(self, engine):
        """Test a realistic package theft scenario with semantic matching."""
        expected = {
            "florence_caption": {
                "must_contain": ["person", "package"],
                "must_not_contain": ["delivery", "uniform"],
            }
        }
        # Florence returns "cardboard box" instead of "package"
        actual = {"florence_caption": "A figure bending down near a cardboard box on the porch"}

        result = engine.compare(expected, actual)

        # Should pass because "figure" matches "person" and "cardboard box" matches "package"
        assert result.passed
        assert result.summary["passed"] == 2
        assert result.summary["failed"] == 0

    def test_realistic_delivery_driver_scenario(self, engine):
        """Test a realistic delivery driver scenario with semantic matching."""
        expected = {
            "florence_caption": {
                "must_contain": ["person", "package"],
                "must_not_contain": ["suspicious", "threat", "stealing"],
            }
        }
        # Florence returns natural language description
        actual = {
            "florence_caption": "A man in a brown uniform delivering a parcel to the doorstep"
        }

        result = engine.compare(expected, actual)

        assert result.passed
        assert result.summary["failed"] == 0

    def test_scenario_with_synonym_vehicle(self, engine):
        """Test scenario with vehicle synonym matching."""
        expected = {
            "florence_caption": {
                "must_contain": ["car", "person"],
            }
        }
        # Florence uses "sedan" instead of "car"
        actual = {"florence_caption": "A woman getting out of a sedan in the driveway"}

        result = engine.compare(expected, actual)

        assert result.passed
