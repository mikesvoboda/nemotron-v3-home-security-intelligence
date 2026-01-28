"""Unit tests for validate_synthetic_quality.py.

ABOUTME: Tests for the synthetic data quality validation script that audits
scenario templates for content policy restrictions and prompt-image alignment.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Add project root to path for imports - must be before script imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.validate_synthetic_quality import (  # noqa: E402
    KNOWN_CONTENT_RESTRICTIONS,
    ContentPolicyConstraint,
    ScenarioAlignment,
    ValidationReport,
    analyze_scenario_for_restrictions,
    audit_all_scenarios,
    audit_scenario,
    determine_alignment_status,
    generate_recommendation,
)


class TestContentPolicyConstraints:
    """Tests for content policy constraint definitions."""

    def test_known_restrictions_exist(self):
        """KNOWN_CONTENT_RESTRICTIONS should be a non-empty list."""
        assert isinstance(KNOWN_CONTENT_RESTRICTIONS, list)
        assert len(KNOWN_CONTENT_RESTRICTIONS) > 0

    def test_all_constraints_have_required_fields(self):
        """Each constraint should have all required fields."""
        for constraint in KNOWN_CONTENT_RESTRICTIONS:
            assert isinstance(constraint, ContentPolicyConstraint)
            assert constraint.category
            assert constraint.description
            assert isinstance(constraint.affected_elements, list)
            assert len(constraint.affected_elements) > 0
            assert constraint.recommendation

    def test_weapons_constraint_exists(self):
        """Weapons category should be defined."""
        categories = [c.category for c in KNOWN_CONTENT_RESTRICTIONS]
        assert "weapons" in categories

    def test_violence_constraint_exists(self):
        """Violence category should be defined."""
        categories = [c.category for c in KNOWN_CONTENT_RESTRICTIONS]
        assert "violence" in categories

    def test_crime_constraint_exists(self):
        """Crime category should be defined."""
        categories = [c.category for c in KNOWN_CONTENT_RESTRICTIONS]
        assert "crime" in categories

    def test_weapons_includes_common_types(self):
        """Weapons constraint should include common weapon types."""
        weapons_constraint = next(c for c in KNOWN_CONTENT_RESTRICTIONS if c.category == "weapons")
        elements = weapons_constraint.affected_elements

        assert "handgun" in elements
        assert "knife" in elements
        assert "weapon" in elements


class TestAnalyzeScenarioForRestrictions:
    """Tests for analyze_scenario_for_restrictions function."""

    def test_empty_scenario_returns_no_restrictions(self):
        """Empty scenario should have no content restrictions."""
        scenario: dict[str, Any] = {"name": "test", "subjects": []}
        risks, elements = analyze_scenario_for_restrictions(scenario)
        assert risks == []
        assert elements == []

    def test_scenario_with_weapon_detected(self):
        """Scenario containing weapon references should be flagged."""
        scenario = {
            "name": "armed_person",
            "subjects": [
                {
                    "type": "person",
                    "weapon": {"type": "handgun", "visibility": "visible"},
                }
            ],
        }
        risks, elements = analyze_scenario_for_restrictions(scenario)
        assert "weapons" in risks
        assert "handgun" in elements

    def test_scenario_with_violence_detected(self):
        """Scenario containing violence references should be flagged."""
        scenario = {
            "name": "aggressive_person",
            "subjects": [
                {
                    "type": "person",
                    "behavior_notes": "aggressive posture, threatening behavior",
                }
            ],
        }
        risks, elements = analyze_scenario_for_restrictions(scenario)
        assert "violence" in risks
        assert "aggressive" in elements
        assert "threatening" in elements

    def test_scenario_with_crime_detected(self):
        """Scenario containing crime references should be flagged."""
        scenario = {
            "name": "burglary",
            "subjects": [
                {
                    "type": "person",
                    "action": "break_in",
                    "behavior_notes": "attempting burglary",
                }
            ],
        }
        risks, elements = analyze_scenario_for_restrictions(scenario)
        assert "crime" in risks
        assert "break_in" in elements
        assert "burglary" in elements

    def test_scenario_with_face_concealment_detected(self):
        """Scenario containing face concealment references should be flagged."""
        scenario = {
            "name": "hooded_person",
            "subjects": [
                {
                    "type": "person",
                    "appearance": {"hood_up": True, "face_visible": False},
                }
            ],
        }
        risks, elements = analyze_scenario_for_restrictions(scenario)
        assert "face_concealment" in risks
        assert "hood_up" in elements

    def test_benign_scenario_not_flagged(self):
        """Benign scenario should not be flagged."""
        scenario = {
            "name": "delivery_person",
            "subjects": [
                {
                    "type": "person",
                    "role": "delivery_driver",
                    "action": "delivering_package",
                    "appearance": {"uniform": "delivery_uniform"},
                }
            ],
        }
        risks, elements = analyze_scenario_for_restrictions(scenario)
        # Should have no high-risk categories (weapons, violence)
        assert "weapons" not in risks
        assert "violence" not in risks

    def test_multiple_risks_detected(self):
        """Scenario with multiple risks should flag all of them."""
        scenario = {
            "name": "armed_intruder",
            "subjects": [
                {
                    "type": "person",
                    "role": "intruder",
                    "weapon": {"type": "handgun"},
                    "action": "break_in",
                    "behavior_notes": "aggressive, forcing entry",
                    "appearance": {"mask": True},
                }
            ],
        }
        risks, elements = analyze_scenario_for_restrictions(scenario)
        assert "weapons" in risks
        assert "violence" in risks
        assert "crime" in risks
        assert "face_concealment" in risks


class TestDetermineAlignmentStatus:
    """Tests for determine_alignment_status function."""

    def test_no_risks_returns_likely_valid(self):
        """No risks should return likely_valid with high confidence."""
        status, confidence = determine_alignment_status([], [])
        assert status == "likely_valid"
        assert confidence == "high"

    def test_weapons_risk_returns_misaligned(self):
        """Weapons risk should return likely_misaligned with high confidence."""
        status, confidence = determine_alignment_status(["weapons"], ["handgun"])
        assert status == "likely_misaligned"
        assert confidence == "high"

    def test_violence_risk_returns_misaligned(self):
        """Violence risk should return likely_misaligned with high confidence."""
        status, confidence = determine_alignment_status(["violence"], ["aggressive"])
        assert status == "likely_misaligned"
        assert confidence == "high"

    def test_crime_risk_returns_misaligned_medium(self):
        """Crime risk alone should return likely_misaligned with medium confidence."""
        status, confidence = determine_alignment_status(["crime"], ["theft"])
        assert status == "likely_misaligned"
        assert confidence == "medium"

    def test_face_concealment_risk_returns_misaligned_medium(self):
        """Face concealment risk alone should return likely_misaligned with medium confidence."""
        status, confidence = determine_alignment_status(["face_concealment"], ["mask"])
        assert status == "likely_misaligned"
        assert confidence == "medium"

    def test_multiple_high_risks(self):
        """Multiple high risks should return misaligned with high confidence."""
        status, confidence = determine_alignment_status(
            ["weapons", "violence"], ["handgun", "aggressive"]
        )
        assert status == "likely_misaligned"
        assert confidence == "high"


class TestGenerateRecommendation:
    """Tests for generate_recommendation function."""

    def test_likely_valid_recommendation(self):
        """Likely valid scenarios should get simple recommendation."""
        rec = generate_recommendation("likely_valid", [], "normal")
        assert "AI-generated images should work well" in rec

    def test_weapons_recommendation(self):
        """Weapons risk should recommend stock footage."""
        rec = generate_recommendation("likely_misaligned", ["weapons"], "threats")
        assert "stock footage" in rec.lower() or "Pexels" in rec

    def test_violence_recommendation(self):
        """Violence risk should recommend staged footage."""
        rec = generate_recommendation("likely_misaligned", ["violence"], "threats")
        assert "staged" in rec.lower() or "actors" in rec.lower()

    def test_crime_recommendation(self):
        """Crime risk should recommend stock or manual update."""
        rec = generate_recommendation("likely_misaligned", ["crime"], "threats")
        assert "stock" in rec.lower() or "expected_labels" in rec


class TestAuditScenario:
    """Tests for audit_scenario function."""

    def test_audit_weapon_visible_scenario(self):
        """weapon_visible scenario should be flagged as misaligned."""
        alignment = audit_scenario("weapon_visible")
        assert alignment.scenario_id == "weapon_visible"
        assert alignment.alignment_status == "likely_misaligned"
        assert alignment.confidence == "high"
        assert "weapons" in alignment.content_policy_risks

    def test_audit_break_in_attempt_scenario(self):
        """break_in_attempt scenario should be flagged as misaligned."""
        alignment = audit_scenario("break_in_attempt")
        assert alignment.scenario_id == "break_in_attempt"
        assert alignment.alignment_status == "likely_misaligned"
        # Should have multiple risk categories
        assert len(alignment.content_policy_risks) >= 2

    def test_audit_package_theft_scenario(self):
        """package_theft scenario should be flagged as misaligned."""
        alignment = audit_scenario("package_theft")
        assert alignment.scenario_id == "package_theft"
        assert alignment.alignment_status == "likely_misaligned"
        assert "crime" in alignment.content_policy_risks

    def test_audit_vehicle_parking_scenario(self):
        """vehicle_parking scenario should be valid."""
        alignment = audit_scenario("vehicle_parking")
        assert alignment.scenario_id == "vehicle_parking"
        assert alignment.alignment_status == "likely_valid"

    def test_audit_nonexistent_scenario(self):
        """Non-existent scenario should return unknown status."""
        alignment = audit_scenario("nonexistent_scenario_xyz")
        assert alignment.alignment_status == "unknown"
        assert "Error" in alignment.notes or "Failed" in alignment.recommendation


class TestAuditAllScenarios:
    """Tests for audit_all_scenarios function."""

    def test_audit_all_returns_validation_report(self):
        """audit_all_scenarios should return a ValidationReport."""
        report = audit_all_scenarios()
        assert isinstance(report, ValidationReport)
        assert report.total_scenarios > 0
        assert len(report.scenarios) == report.total_scenarios

    def test_audit_all_counts_match(self):
        """Counts in report should add up correctly."""
        report = audit_all_scenarios()
        assert (
            report.likely_valid + report.likely_misaligned + report.unknown
            == report.total_scenarios
        )

    def test_audit_all_has_summary(self):
        """Report should have a non-empty summary."""
        report = audit_all_scenarios()
        assert report.summary
        assert str(report.total_scenarios) in report.summary

    def test_threats_category_has_misaligned_scenarios(self):
        """Threats category should have misaligned scenarios."""
        report = audit_all_scenarios()
        threats_scenarios = [s for s in report.scenarios if s.category == "threats"]
        misaligned = [s for s in threats_scenarios if s.alignment_status == "likely_misaligned"]
        # All threat scenarios should be misaligned due to content policies
        assert len(misaligned) == len(threats_scenarios)

    def test_report_generated_at_is_set(self):
        """Report should have generated_at timestamp."""
        report = audit_all_scenarios()
        assert report.generated_at
        # Should be ISO format
        assert "T" in report.generated_at or "-" in report.generated_at


class TestScenarioAlignmentDataclass:
    """Tests for ScenarioAlignment dataclass."""

    def test_create_alignment(self):
        """Should be able to create ScenarioAlignment."""
        alignment = ScenarioAlignment(
            scenario_id="test",
            category="threats",
            name="Test Scenario",
            alignment_status="likely_misaligned",
            confidence="high",
            content_policy_risks=["weapons"],
            problematic_elements=["handgun"],
            recommendation="Use stock footage",
            notes="Test note",
        )
        assert alignment.scenario_id == "test"
        assert alignment.alignment_status == "likely_misaligned"
        assert "weapons" in alignment.content_policy_risks

    def test_alignment_default_notes(self):
        """Notes should default to empty string."""
        alignment = ScenarioAlignment(
            scenario_id="test",
            category="normal",
            name="Test",
            alignment_status="likely_valid",
            confidence="high",
            content_policy_risks=[],
            problematic_elements=[],
            recommendation="OK",
        )
        assert alignment.notes == ""


class TestValidationReportDataclass:
    """Tests for ValidationReport dataclass."""

    def test_create_report(self):
        """Should be able to create ValidationReport."""
        report = ValidationReport(
            generated_at="2026-01-27T12:00:00Z",
            total_scenarios=10,
            likely_valid=3,
            likely_misaligned=6,
            unknown=1,
            scenarios=[],
            summary="Test summary",
        )
        assert report.total_scenarios == 10
        assert report.likely_valid == 3

    def test_report_default_values(self):
        """Report should have sensible defaults."""
        report = ValidationReport(
            generated_at="2026-01-27T12:00:00Z",
            total_scenarios=0,
            likely_valid=0,
            likely_misaligned=0,
            unknown=0,
        )
        assert report.scenarios == []
        assert report.summary == ""
