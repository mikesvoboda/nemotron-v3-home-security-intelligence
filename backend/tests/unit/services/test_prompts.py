"""Unit tests for backend/services/prompts.py (R8 S2 -- surviving surface only).

The legacy Model-Zoo formatter zoo retired with the Nemotron tier. What is
left in prompts.py is the two risk templates, the summary-prompt builders and
the per-class anomaly formatter, and this suite pins exactly that.

Tests cover:
- Prompt template constants (RISK_ANALYSIS_PROMPT,
  MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT)
- Variable substitution in prompts and ChatML structure
- Calibration guidance that survives inside the templates
- format_class_anomaly_context / ClassAnomalyResult
- Summary prompt templates and build_summary_prompt
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.services.prompts import (
    MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
    RISK_ANALYSIS_PROMPT,
    SUMMARY_EMPTY_STATE_INSTRUCTION,
    SUMMARY_EVENT_FORMAT,
    SUMMARY_PROMPT_TEMPLATE,
    SUMMARY_SYSTEM_PROMPT,
    ClassAnomalyResult,
    build_summary_prompt,
    format_class_anomaly_context,
)


@dataclass
class MockClassBaseline:
    """Mock ClassBaseline for testing format_class_anomaly_context.

    Implements the ClassBaselineProtocol interface with frequency and sample_count.
    """

    frequency: float
    sample_count: int


class TestRiskAnalysisPromptTemplate:
    """Tests for the basic RISK_ANALYSIS_PROMPT template."""

    def test_template_exists(self) -> None:
        """Test that the basic prompt template is defined."""
        assert RISK_ANALYSIS_PROMPT is not None
        assert isinstance(RISK_ANALYSIS_PROMPT, str)
        assert len(RISK_ANALYSIS_PROMPT) > 0

    def test_template_has_chatml_format(self) -> None:
        """Test that the template uses ChatML format for Nemotron."""
        assert "<|im_start|>system" in RISK_ANALYSIS_PROMPT
        assert "<|im_start|>user" in RISK_ANALYSIS_PROMPT
        assert "<|im_start|>assistant" in RISK_ANALYSIS_PROMPT
        assert "<|im_end|>" in RISK_ANALYSIS_PROMPT

    def test_template_has_required_placeholders(self) -> None:
        """Test that the template contains required placeholder variables."""
        required_placeholders = [
            "{camera_name}",
            "{start_time}",
            "{end_time}",
            "{detections_list}",
        ]
        for placeholder in required_placeholders:
            assert placeholder in RISK_ANALYSIS_PROMPT, f"Missing placeholder: {placeholder}"

    def test_template_has_json_output_format(self) -> None:
        """Test that the template specifies JSON output format."""
        assert '"risk_score"' in RISK_ANALYSIS_PROMPT
        assert '"risk_level"' in RISK_ANALYSIS_PROMPT
        assert '"summary"' in RISK_ANALYSIS_PROMPT
        assert '"reasoning"' in RISK_ANALYSIS_PROMPT

    def test_template_has_risk_level_guidance(self) -> None:
        """Test that the template provides risk level ranges matching DB taxonomy."""
        assert "low (0-29)" in RISK_ANALYSIS_PROMPT
        assert "medium (30-59)" in RISK_ANALYSIS_PROMPT
        assert "high (60-84)" in RISK_ANALYSIS_PROMPT
        assert "critical (85-100)" in RISK_ANALYSIS_PROMPT

    def test_template_variable_substitution(self) -> None:
        """Test that template variables can be properly substituted."""
        substituted = RISK_ANALYSIS_PROMPT.format(
            camera_name="front_door",
            start_time="2024-01-01 10:00:00",
            end_time="2024-01-01 10:01:30",
            detections_list="person: 95%, car: 87%",
        )
        assert "front_door" in substituted
        assert "2024-01-01 10:00:00" in substituted
        assert "2024-01-01 10:01:30" in substituted
        assert "person: 95%, car: 87%" in substituted

    def test_template_substitution_with_special_characters(self) -> None:
        """Test substitution works with special characters."""
        special_chars = 'Camera <"test"> & sensors'
        substituted = RISK_ANALYSIS_PROMPT.format(
            camera_name=special_chars,
            start_time="2024-01-01 10:00:00",
            end_time="2024-01-01 10:01:30",
            detections_list="person: 95%",
        )
        assert special_chars in substituted

    def test_template_substitution_with_unicode(self) -> None:
        """Test substitution works with unicode characters."""
        unicode_text = "Camera name with unicode characters"
        substituted = RISK_ANALYSIS_PROMPT.format(
            camera_name=unicode_text,
            start_time="2024-01-01 10:00:00",
            end_time="2024-01-01 10:01:30",
            detections_list="detection list",
        )
        assert unicode_text in substituted


class TestModelZooEnhancedRiskAnalysisPromptTemplate:
    """Tests for the MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT template."""

    def test_template_exists(self) -> None:
        """Test that the model zoo enhanced prompt template is defined."""
        assert MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT is not None

    def test_template_is_largest(self) -> None:
        """Test that model zoo template is the most comprehensive."""
        assert len(MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT) > len(RISK_ANALYSIS_PROMPT)

    def test_template_has_all_model_zoo_fields(self) -> None:
        """Test that the template has all model zoo enrichment fields."""
        required_fields = [
            "{camera_name}",
            "{timestamp}",
            "{day_of_week}",
            "{time_of_day}",
            "{weather_context}",
            "{image_quality_context}",
            "{detections_with_all_attributes}",
            "{violence_context}",
            "{pose_analysis}",
            "{action_recognition}",
            "{vehicle_classification_context}",
            "{vehicle_damage_context}",
            "{clothing_analysis_context}",
            "{pet_classification_context}",
            "{depth_context}",
            "{reid_context}",
            "{zone_analysis}",
            "{baseline_comparison}",
            "{deviation_score}",
            "{cross_camera_summary}",
            "{scene_analysis}",
        ]
        for template_field in required_fields:
            assert template_field in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT, (
                f"Missing field: {template_field}"
            )

    def test_template_has_comprehensive_risk_interpretation(self) -> None:
        """Test that the template has comprehensive risk interpretation guide."""
        sections = [
            "### Violence Detection",
            "### Weather Context",
            "### Clothing/Attire Risk Factors",
            "### Vehicle Analysis",
            "### Pet Detection",
            "### Pose/Behavior Analysis",
            "### Image Quality",
            "### Time Context",
            "### Risk Levels",
        ]
        for section in sections:
            assert section in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT, f"Missing section: {section}"

    def test_template_has_comprehensive_json_output(self) -> None:
        """Test that the template has comprehensive JSON output format."""
        output_fields = [
            '"risk_score"',
            '"risk_level"',
            '"summary"',
            '"reasoning"',
            '"entities"',
            '"flags"',
            '"recommended_action"',
            '"confidence_factors"',
        ]
        for output_field in output_fields:
            assert output_field in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT, (
                f"Missing output field: {output_field}"
            )


def _not_risk_factors_section(prompt: str) -> str:
    """Pull the NOT RISK FACTORS section out of a live template (R8 S2).

    The NON_RISK_FACTORS constant retired with the Nemotron tier; the guidance
    survives embedded in both risk templates, so the pins below read it from
    there instead of a standalone constant.
    """
    start = prompt.find("## NOT RISK FACTORS")
    assert start >= 0, "template should carry the NOT RISK FACTORS section"
    end = prompt.find("\n\n", start)
    return prompt[start : end if end > 0 else len(prompt)]


class TestNonRiskFactors:
    """Tests for the NOT RISK FACTORS guidance (NEM-3880).

    These tests verify that the prompts include explicit guidance about
    items that should NOT be flagged as suspicious.
    """

    def test_non_risk_factors_exists(self) -> None:
        """Test that both live templates define the section."""
        for prompt in (RISK_ANALYSIS_PROMPT, MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT):
            section = _not_risk_factors_section(prompt)
            assert isinstance(section, str)
            assert len(section) > 0

    def test_non_risk_factors_includes_trees(self) -> None:
        """Test that trees are explicitly listed as non-risk factors."""
        for prompt in (RISK_ANALYSIS_PROMPT, MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT):
            assert "tree" in _not_risk_factors_section(prompt).lower()

    def test_non_risk_factors_includes_timestamps(self) -> None:
        """Test that timestamps are explicitly listed as non-risk factors."""
        for prompt in (RISK_ANALYSIS_PROMPT, MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT):
            assert "timestamp" in _not_risk_factors_section(prompt).lower()

    def test_non_risk_factors_includes_presence(self) -> None:
        """Test that simple presence is listed as non-risk factor."""
        for prompt in (RISK_ANALYSIS_PROMPT, MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT):
            lower_text = _not_risk_factors_section(prompt).lower()
            assert "simply being present" in lower_text or "simply present" in lower_text

    def test_non_risk_factors_includes_vegetation(self) -> None:
        """Test that vegetation is listed as non-risk factor."""
        for prompt in (RISK_ANALYSIS_PROMPT, MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT):
            lower_text = _not_risk_factors_section(prompt).lower()
            assert "vegetation" in lower_text or "plants" in lower_text

    def test_non_risk_factors_includes_wildlife(self) -> None:
        """Test that wildlife is listed as non-risk factor."""
        for prompt in (RISK_ANALYSIS_PROMPT, MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT):
            lower_text = _not_risk_factors_section(prompt).lower()
            has_wildlife = "wildlife" in lower_text
            has_animals = "bird" in lower_text and "squirrel" in lower_text
            assert has_wildlife or has_animals

    def test_non_risk_factors_includes_shadows(self) -> None:
        """Test that shadows are listed as non-risk factor."""
        for prompt in (RISK_ANALYSIS_PROMPT, MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT):
            assert "shadow" in _not_risk_factors_section(prompt).lower()

    def test_non_risk_factors_includes_weather(self) -> None:
        """Test that weather conditions are listed as non-risk factor."""
        for prompt in (RISK_ANALYSIS_PROMPT, MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT):
            assert "weather" in _not_risk_factors_section(prompt).lower()


class TestCalibrationGuidelines:
    """Tests for calibration guidelines in prompts (NEM-3880).

    These tests verify that all prompt templates include proper
    score calibration guidelines to prevent over-alerting.
    """

    def test_all_prompts_have_non_risk_factors_guidance(self) -> None:
        """Test that all prompt templates mention non-risk factors."""
        prompts_to_check = [
            ("RISK_ANALYSIS_PROMPT", RISK_ANALYSIS_PROMPT),
            ("MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT", MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT),
        ]
        for name, prompt in prompts_to_check:
            has_tree = "tree" in prompt.lower()
            has_header = "NOT RISK FACTORS" in prompt
            assert has_tree or has_header, f"{name} should mention non-risk factors"

    def test_all_prompts_have_calibrated_score_ranges(self) -> None:
        """Test that all prompt templates have calibrated score ranges matching DB taxonomy."""
        prompts_to_check = [
            ("RISK_ANALYSIS_PROMPT", RISK_ANALYSIS_PROMPT),
            ("MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT", MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT),
        ]
        for name, prompt in prompts_to_check:
            # Each prompt should have the calibrated LOW range (0-29)
            has_range = "0-29" in prompt or "(0-29)" in prompt
            assert has_range, f"{name} should have calibrated LOW range (0-29)"

    def test_prompts_emphasize_lower_scores_as_default(self) -> None:
        """Test that surviving prompts emphasize defaulting to lower scores (R8 S2)."""
        prompts_to_check = [
            ("RISK_ANALYSIS_PROMPT", RISK_ANALYSIS_PROMPT),
        ]
        for name, prompt in prompts_to_check:
            # Should mention defaulting to lower scores
            lower_prompt = prompt.lower()
            has_default = "default" in lower_prompt and "lower" in lower_prompt
            assert has_default, f"{name} should emphasize defaulting to lower scores"


class TestFormatClassAnomalyContext:
    """Tests for format_class_anomaly_context function.

    This function identifies per-class anomalies by comparing current detection
    counts against historical baselines. It flags:
    - Rare classes (expected < 0.1/hr) when detected
    - Unusual volume (3x normal) for any class
    """

    def test_empty_detections(self) -> None:
        """Test formatting with no detections returns empty string."""
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=2,
            detections={},
            baselines={},
        )
        assert context == ""
        assert anomalies == []

    def test_no_baselines_returns_empty(self) -> None:
        """Test that detections without baselines return empty (insufficient data)."""
        detections = {"person": 3, "vehicle": 2}
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=2,
            detections=detections,
            baselines={},  # No baselines
        )
        assert context == ""
        assert anomalies == []

    def test_insufficient_samples_returns_empty(self) -> None:
        """Test that baselines with < 10 samples are ignored."""
        detections = {"person": 3}
        baselines = {
            "cam1:2:person": MockClassBaseline(frequency=1.0, sample_count=5)  # Only 5 samples
        }
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=2,
            detections=detections,
            baselines=baselines,
        )
        assert context == ""
        assert anomalies == []

    def test_rare_class_person_high_severity(self) -> None:
        """Test that rare person detection gets high severity."""
        detections = {"person": 1}
        baselines = {
            "cam1:2:person": MockClassBaseline(frequency=0.05, sample_count=20)  # Rare: < 0.1/hr
        }
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=2,
            detections=detections,
            baselines=baselines,
        )

        assert "## CLASS-SPECIFIC ANOMALIES" in context
        assert "[HIGH]" in context
        assert "person RARE at this hour" in context
        assert "expected: 0.1/hr" in context or "expected: 0.0/hr" in context
        assert len(anomalies) == 1
        assert anomalies[0].class_name == "person"
        assert anomalies[0].severity == "high"
        assert anomalies[0].risk_modifier == 15

    def test_rare_class_vehicle_high_severity(self) -> None:
        """Test that rare vehicle detection gets high severity."""
        detections = {"vehicle": 1}
        baselines = {"cam1:3:vehicle": MockClassBaseline(frequency=0.02, sample_count=15)}
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=3,
            detections=detections,
            baselines=baselines,
        )

        assert "[HIGH]" in context
        assert "vehicle RARE at this hour" in context
        assert anomalies[0].severity == "high"

    def test_rare_class_dog_medium_severity(self) -> None:
        """Test that rare non-security class gets medium severity."""
        detections = {"dog": 1}
        baselines = {"cam1:4:dog": MockClassBaseline(frequency=0.01, sample_count=25)}
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=4,
            detections=detections,
            baselines=baselines,
        )

        assert "[MEDIUM]" in context
        assert "dog RARE at this hour" in context
        assert anomalies[0].severity == "medium"

    def test_unusual_volume_3x_normal(self) -> None:
        """Test that 3x normal volume is flagged as unusual."""
        detections = {"person": 10}
        baselines = {
            "cam1:14:person": MockClassBaseline(frequency=3.0, sample_count=50)  # 10 > 3*3 = 9
        }
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=14,
            detections=detections,
            baselines=baselines,
        )

        assert "## CLASS-SPECIFIC ANOMALIES" in context
        assert "[MEDIUM]" in context
        assert "person UNUSUAL volume" in context
        assert "10 vs expected 3.0" in context
        assert len(anomalies) == 1
        assert anomalies[0].severity == "medium"

    def test_normal_volume_not_flagged(self) -> None:
        """Test that normal volume (< 3x) is not flagged."""
        detections = {"person": 5}
        baselines = {
            "cam1:10:person": MockClassBaseline(frequency=3.0, sample_count=30)  # 5 < 3*3 = 9
        }
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=10,
            detections=detections,
            baselines=baselines,
        )

        assert context == ""
        assert anomalies == []

    def test_exactly_3x_not_flagged(self) -> None:
        """Test that exactly 3x normal is not flagged (must be > 3x)."""
        detections = {"person": 9}
        baselines = {
            "cam1:12:person": MockClassBaseline(frequency=3.0, sample_count=25)  # 9 == 3*3
        }
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=12,
            detections=detections,
            baselines=baselines,
        )

        assert context == ""
        assert anomalies == []

    def test_multiple_anomalies(self) -> None:
        """Test formatting with multiple anomalies from different classes."""
        detections = {"person": 1, "vehicle": 1, "dog": 2}
        baselines = {
            "cam1:3:person": MockClassBaseline(frequency=0.05, sample_count=20),  # Rare
            "cam1:3:vehicle": MockClassBaseline(frequency=0.03, sample_count=15),  # Rare
            "cam1:3:dog": MockClassBaseline(frequency=5.0, sample_count=30),  # Normal
        }
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=3,
            detections=detections,
            baselines=baselines,
        )

        assert "## CLASS-SPECIFIC ANOMALIES" in context
        assert "person RARE" in context
        assert "vehicle RARE" in context
        assert "dog" not in context  # Not anomalous
        assert len(anomalies) == 2

    def test_class_anomaly_result_attributes(self) -> None:
        """Test that ClassAnomalyResult has correct attributes."""
        result = ClassAnomalyResult(
            class_name="person",
            message="person RARE at this hour (expected: 0.1/hr, actual: 1)",
            severity="high",
            risk_modifier=15,
        )

        assert result.class_name == "person"
        assert "RARE" in result.message
        assert result.severity == "high"
        assert result.risk_modifier == 15

    def test_different_camera_different_hour(self) -> None:
        """Test that baseline key includes camera and hour."""
        detections = {"person": 1}
        baselines = {
            # Wrong camera
            "cam2:5:person": MockClassBaseline(frequency=0.05, sample_count=20),
            # Wrong hour
            "cam1:6:person": MockClassBaseline(frequency=0.05, sample_count=20),
        }
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=5,
            detections=detections,
            baselines=baselines,
        )

        # Should not match because key is cam1:5:person which doesn't exist
        assert context == ""
        assert anomalies == []

    def test_car_truck_motorcycle_high_severity(self) -> None:
        """Test that car, truck, motorcycle variants get high severity."""
        for vehicle_class in ["car", "truck", "motorcycle"]:
            detections = {vehicle_class: 1}
            baselines = {
                f"cam1:2:{vehicle_class}": MockClassBaseline(frequency=0.02, sample_count=20)
            }
            context, anomalies = format_class_anomaly_context(
                camera_id="cam1",
                current_hour=2,
                detections=detections,
                baselines=baselines,
            )

            assert "[HIGH]" in context, f"{vehicle_class} should get HIGH severity"
            assert anomalies[0].severity == "high"

    def test_non_security_classes_medium_severity(self) -> None:
        """Test that non-security classes (cat, bird, etc.) get medium severity."""
        for cls in ["cat", "bird", "backpack"]:
            detections = {cls: 1}
            baselines = {f"cam1:2:{cls}": MockClassBaseline(frequency=0.02, sample_count=20)}
            context, anomalies = format_class_anomaly_context(
                camera_id="cam1",
                current_hour=2,
                detections=detections,
                baselines=baselines,
            )

            assert "[MEDIUM]" in context, f"{cls} should get MEDIUM severity"
            assert anomalies[0].severity == "medium"


class TestEdgeCasesAndSpecialCharacters:
    """Tests for edge cases and special character handling in prompt substitution."""

    def test_prompt_substitution_with_html_entities(self) -> None:
        """Test prompt substitution handles HTML-like characters."""
        prompt = RISK_ANALYSIS_PROMPT.format(
            camera_name="<script>alert('xss')</script>",
            start_time="2024-01-01 10:00:00",
            end_time="2024-01-01 10:01:00",
            detections_list="person: 90%",
        )
        # Should include the text as-is (no HTML escaping needed for LLM)
        assert "<script>" in prompt

    def test_prompt_substitution_with_newlines(self) -> None:
        """Test prompt substitution handles newlines in values."""
        multi_line = "person: 95%\ncar: 88%\ndog: 72%"
        prompt = RISK_ANALYSIS_PROMPT.format(
            camera_name="test_cam",
            start_time="2024-01-01 10:00:00",
            end_time="2024-01-01 10:01:00",
            detections_list=multi_line,
        )
        assert "person: 95%\ncar: 88%\ndog: 72%" in prompt

    def test_prompt_substitution_with_empty_strings(self) -> None:
        """Test prompt substitution handles empty strings."""
        prompt = RISK_ANALYSIS_PROMPT.format(
            camera_name="",
            start_time="",
            end_time="",
            detections_list="",
        )
        assert "Camera: \n" in prompt

    def test_prompt_substitution_with_very_long_input(self) -> None:
        """Test prompt substitution handles very long inputs."""
        long_list = "\n".join([f"object_{i}: {90 - i % 20}%" for i in range(100)])
        prompt = RISK_ANALYSIS_PROMPT.format(
            camera_name="test_cam",
            start_time="2024-01-01 10:00:00",
            end_time="2024-01-01 10:01:00",
            detections_list=long_list,
        )
        assert "object_0: 90%" in prompt
        assert "object_99:" in prompt


class TestPromptTemplateConsistency:
    """Tests to verify consistency across all prompt templates."""

    def test_all_templates_have_assistant_marker(self) -> None:
        """Test all templates end with assistant marker for completion."""
        templates = [
            RISK_ANALYSIS_PROMPT,
            MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
        ]
        for template in templates:
            assert template.strip().endswith(
                "<|im_start|>assistant\n"
            ) or template.strip().endswith("<|im_start|>assistant"), (
                "Template should end with assistant marker"
            )

    def test_all_templates_have_system_message(self) -> None:
        """Test all templates have system message."""
        templates = [
            RISK_ANALYSIS_PROMPT,
            MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
        ]
        for template in templates:
            assert "<|im_start|>system" in template
            # Updated to accept "home security analyst" role (NEM-3019)
            has_role = (
                "risk analyzer" in template.lower() or "home security analyst" in template.lower()
            )
            assert has_role, (
                "Template should define system role as risk analyzer or home security analyst"
            )

    def test_all_templates_specify_json_output(self) -> None:
        """Test all templates specify JSON output format."""
        templates = [
            RISK_ANALYSIS_PROMPT,
            MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
        ]
        for template in templates:
            # Each should mention JSON output
            assert "json" in template.lower() or "JSON" in template

    def test_all_templates_have_risk_score_output(self) -> None:
        """Test all templates include risk_score in expected output."""
        templates = [
            RISK_ANALYSIS_PROMPT,
            MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
        ]
        for template in templates:
            assert '"risk_score"' in template


class TestSummaryPromptTemplates:
    """Tests for summary generation prompt templates."""

    def test_summary_system_prompt_exists(self) -> None:
        """Test that SUMMARY_SYSTEM_PROMPT is defined."""
        assert SUMMARY_SYSTEM_PROMPT is not None
        assert isinstance(SUMMARY_SYSTEM_PROMPT, str)
        assert len(SUMMARY_SYSTEM_PROMPT) > 0

    def test_summary_system_prompt_content(self) -> None:
        """Test that SUMMARY_SYSTEM_PROMPT has expected content."""
        assert "security analyst" in SUMMARY_SYSTEM_PROMPT.lower()
        assert "homeowner" in SUMMARY_SYSTEM_PROMPT.lower()
        assert "informative" in SUMMARY_SYSTEM_PROMPT.lower()
        assert "alarming" in SUMMARY_SYSTEM_PROMPT.lower()

    def test_summary_prompt_template_exists(self) -> None:
        """Test that SUMMARY_PROMPT_TEMPLATE is defined."""
        assert SUMMARY_PROMPT_TEMPLATE is not None
        assert isinstance(SUMMARY_PROMPT_TEMPLATE, str)
        assert len(SUMMARY_PROMPT_TEMPLATE) > 0

    def test_summary_prompt_template_has_required_placeholders(self) -> None:
        """Test that SUMMARY_PROMPT_TEMPLATE contains required placeholders."""
        required_placeholders = [
            "{window_start}",
            "{window_end}",
            "{period_type}",
            "{event_count}",
            "{event_details}",
            "{empty_state_instruction}",
        ]
        for placeholder in required_placeholders:
            assert placeholder in SUMMARY_PROMPT_TEMPLATE, f"Missing placeholder: {placeholder}"

    def test_summary_prompt_template_instructions(self) -> None:
        """Test that SUMMARY_PROMPT_TEMPLATE has proper instructions."""
        assert "2-4 sentences" in SUMMARY_PROMPT_TEMPLATE
        assert "calm" in SUMMARY_PROMPT_TEMPLATE.lower()
        assert "informative" in SUMMARY_PROMPT_TEMPLATE.lower()
        assert "patterns" in SUMMARY_PROMPT_TEMPLATE.lower()

    def test_summary_empty_state_instruction_exists(self) -> None:
        """Test that SUMMARY_EMPTY_STATE_INSTRUCTION is defined."""
        assert SUMMARY_EMPTY_STATE_INSTRUCTION is not None
        assert isinstance(SUMMARY_EMPTY_STATE_INSTRUCTION, str)
        assert len(SUMMARY_EMPTY_STATE_INSTRUCTION) > 0

    def test_summary_empty_state_instruction_content(self) -> None:
        """Test that SUMMARY_EMPTY_STATE_INSTRUCTION has expected content."""
        assert "{period}" in SUMMARY_EMPTY_STATE_INSTRUCTION
        assert "reassuring" in SUMMARY_EMPTY_STATE_INSTRUCTION.lower()
        assert "quiet" in SUMMARY_EMPTY_STATE_INSTRUCTION.lower()

    def test_summary_event_format_exists(self) -> None:
        """Test that SUMMARY_EVENT_FORMAT is defined."""
        assert SUMMARY_EVENT_FORMAT is not None
        assert isinstance(SUMMARY_EVENT_FORMAT, str)
        assert len(SUMMARY_EVENT_FORMAT) > 0

    def test_summary_event_format_has_required_placeholders(self) -> None:
        """Test that SUMMARY_EVENT_FORMAT contains required placeholders."""
        required_placeholders = [
            "{index}",
            "{timestamp}",
            "{camera_name}",
            "{risk_level}",
            "{risk_score}",
            "{event_summary}",
            "{object_types}",
        ]
        for placeholder in required_placeholders:
            assert placeholder in SUMMARY_EVENT_FORMAT, f"Missing placeholder: {placeholder}"


class TestBuildSummaryPrompt:
    """Tests for build_summary_prompt function."""

    def test_with_events(self) -> None:
        """Test build_summary_prompt with events."""
        events = [
            {
                "timestamp": "2:15 PM",
                "camera_name": "Front Door",
                "risk_level": "critical",
                "risk_score": 92,
                "summary": "Unknown person at front door",
                "object_types": "person",
            }
        ]

        system, user = build_summary_prompt(
            window_start="2:00 PM",
            window_end="3:00 PM",
            period_type="hour",
            events=events,
        )

        assert "security analyst" in system.lower()
        assert "2:15 PM" in user
        assert "Front Door" in user
        assert "critical" in user
        assert "92/100" in user
        assert "Unknown person at front door" in user
        assert "person" in user
        assert "High/Critical Events:** 1" in user

    def test_empty_events(self) -> None:
        """Test build_summary_prompt with no events."""
        _, user = build_summary_prompt(
            window_start="12:00 AM",
            window_end="11:59 PM",
            period_type="day",
            events=[],
            routine_count=15,
        )

        assert "No high or critical events" in user
        assert "15" in user  # routine count
        assert "reassuring" in user.lower()

    def test_empty_events_no_routine(self) -> None:
        """Test build_summary_prompt with no events and no routine count."""
        _, user = build_summary_prompt(
            window_start="2:00 PM",
            window_end="3:00 PM",
            period_type="hour",
            events=[],
            routine_count=0,
        )

        assert "No high or critical events" in user
        assert "routine/low-priority detections" not in user

    def test_multiple_events(self) -> None:
        """Test build_summary_prompt with multiple events."""
        events = [
            {
                "timestamp": "1:00 PM",
                "camera_name": "Driveway",
                "risk_level": "high",
                "risk_score": 75,
                "summary": "Vehicle detected",
                "object_types": "vehicle",
            },
            {
                "timestamp": "1:05 PM",
                "camera_name": "Front Door",
                "risk_level": "critical",
                "risk_score": 88,
                "summary": "Person at door",
                "object_types": "person",
            },
        ]

        _, user = build_summary_prompt(
            window_start="1:00 PM",
            window_end="2:00 PM",
            period_type="hour",
            events=events,
        )

        assert "Event 1" in user
        assert "Event 2" in user
        assert "Driveway" in user
        assert "Front Door" in user
        assert "High/Critical Events:** 2" in user

    def test_period_types(self) -> None:
        """Test build_summary_prompt with different period types."""
        _, hourly = build_summary_prompt(
            window_start="2:00 PM",
            window_end="3:00 PM",
            period_type="hour",
            events=[],
        )

        _, daily = build_summary_prompt(
            window_start="12:00 AM",
            window_end="11:59 PM",
            period_type="day",
            events=[],
        )

        assert "hour" in hourly
        assert "day" in daily

    def test_returns_tuple(self) -> None:
        """Test that build_summary_prompt returns a tuple of two strings."""
        result = build_summary_prompt(
            window_start="2:00 PM",
            window_end="3:00 PM",
            period_type="hour",
            events=[],
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)  # system prompt
        assert isinstance(result[1], str)  # user prompt

    def test_system_prompt_consistency(self) -> None:
        """Test that system prompt is always the same."""
        _, _ = build_summary_prompt(
            window_start="2:00 PM",
            window_end="3:00 PM",
            period_type="hour",
            events=[],
        )

        system1, _ = build_summary_prompt(
            window_start="1:00 AM",
            window_end="2:00 AM",
            period_type="day",
            events=[
                {
                    "timestamp": "1:30 AM",
                    "camera_name": "Backyard",
                    "risk_level": "high",
                    "risk_score": 70,
                    "summary": "Motion detected",
                    "object_types": "person",
                }
            ],
        )

        system2, _ = build_summary_prompt(
            window_start="9:00 AM",
            window_end="10:00 AM",
            period_type="hour",
            events=[],
            routine_count=5,
        )

        assert system1 == system2
        assert system1 == SUMMARY_SYSTEM_PROMPT

    def test_event_formatting_includes_all_fields(self) -> None:
        """Test that event formatting includes all event fields."""
        events = [
            {
                "timestamp": "3:45 PM",
                "camera_name": "Side Gate",
                "risk_level": "high",
                "risk_score": 78,
                "summary": "Person lingering near side gate",
                "object_types": "person, backpack",
            }
        ]

        _, user = build_summary_prompt(
            window_start="3:00 PM",
            window_end="4:00 PM",
            period_type="hour",
            events=events,
        )

        # All event fields should be in the prompt
        assert "3:45 PM" in user
        assert "Side Gate" in user
        assert "high" in user
        assert "78/100" in user
        assert "Person lingering near side gate" in user
        assert "person, backpack" in user

    def test_no_empty_state_instruction_when_events_present(self) -> None:
        """Test that empty state instruction is not included when events exist."""
        events = [
            {
                "timestamp": "2:15 PM",
                "camera_name": "Front Door",
                "risk_level": "critical",
                "risk_score": 90,
                "summary": "Alert",
                "object_types": "person",
            }
        ]

        _, user = build_summary_prompt(
            window_start="2:00 PM",
            window_end="3:00 PM",
            period_type="hour",
            events=events,
        )

        # Should not contain reassuring message when there are events
        assert "reassuring" not in user.lower()
        assert "No high-priority security events" not in user

    def test_window_times_in_output(self) -> None:
        """Test that window times are included in the prompt."""
        _, user = build_summary_prompt(
            window_start="9:00 AM",
            window_end="10:00 AM",
            period_type="hour",
            events=[],
        )

        assert "9:00 AM" in user
        assert "10:00 AM" in user


class TestPromptModuleImports:
    """Tests for module structure and exports (R8 S2 -- surviving exports only)."""

    def test_all_format_functions_importable(self) -> None:
        """Test the surviving formatters are importable and callable."""
        from backend.services.prompts import (
            ClassAnomalyResult,
            build_summary_prompt,
            format_class_anomaly_context,
        )

        assert callable(build_summary_prompt)
        assert callable(format_class_anomaly_context)
        # Verify ClassAnomalyResult is a dataclass
        assert hasattr(ClassAnomalyResult, "__dataclass_fields__")

    def test_all_prompt_templates_importable(self) -> None:
        """Test all prompt templates are importable."""
        from backend.services.prompts import (
            MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
            RISK_ANALYSIS_PROMPT,
            SUMMARY_EMPTY_STATE_INSTRUCTION,
            SUMMARY_EVENT_FORMAT,
            SUMMARY_PROMPT_TEMPLATE,
            SUMMARY_SYSTEM_PROMPT,
        )

        # Verify they are strings
        assert isinstance(RISK_ANALYSIS_PROMPT, str)
        assert isinstance(MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT, str)
        assert isinstance(SUMMARY_SYSTEM_PROMPT, str)
        assert isinstance(SUMMARY_PROMPT_TEMPLATE, str)
        assert isinstance(SUMMARY_EMPTY_STATE_INSTRUCTION, str)
        assert isinstance(SUMMARY_EVENT_FORMAT, str)


class TestPromptTemplatesHaveCalibrationAtTop:
    """Tests to verify all prompt templates have calibration guidance at the TOP.

    NEM-3019 requires risk modifiers to appear FIRST in the user prompt,
    not buried at the bottom where they may be ignored.
    """

    def test_model_zoo_prompt_has_scoring_reference_early(self) -> None:
        """Test that MODEL_ZOO_ENHANCED prompt has scoring reference near the top."""
        prompt = MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT

        # Find position of key sections
        detections_pos = prompt.find("## Detections") or prompt.find(
            "{detections_with_all_attributes}"
        )
        scoring_pos = prompt.find("## SCORING REFERENCE") or prompt.find("SCORING REFERENCE")

        # Scoring reference should appear BEFORE detections
        # (unless it's in a different structure, then it should be early)
        if scoring_pos > 0 and detections_pos > 0:
            assert scoring_pos < detections_pos, (
                "Scoring reference should appear before detections in prompt"
            )

    def test_basic_prompt_has_scoring_reference(self) -> None:
        """Test that basic RISK_ANALYSIS_PROMPT has scoring reference."""
        prompt = RISK_ANALYSIS_PROMPT

        # Should have scoring reference or calibration guidance
        has_scoring = "SCORING REFERENCE" in prompt or "| Scenario" in prompt
        has_calibration = "CALIBRATION" in prompt or "calibration" in prompt
        has_risk_levels = "low (0-29)" in prompt and "critical (85-100)" in prompt

        assert has_scoring or has_calibration or has_risk_levels, (
            "Basic prompt should have scoring reference or calibration"
        )


class TestPromptTemplatesUseCalibrationSystemPrompt:
    """Tests to verify prompt templates use the calibrated system prompt."""

    def test_model_zoo_prompt_uses_calibrated_system_prompt(self) -> None:
        """Test that MODEL_ZOO_ENHANCED uses calibrated system message."""
        prompt = MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT

        # Should include calibration concepts in system section
        system_section = (
            prompt.split("<|im_start|>user")[0] if "<|im_start|>user" in prompt else prompt
        )

        # Check for key calibration concepts
        has_calibration = any(
            [
                "Most detections are NOT threats" in system_section,
                "CRITICAL PRINCIPLE" in system_section,
                "miscalibrated" in system_section,
                "home security analyst" in system_section,
            ]
        )

        assert has_calibration, "MODEL_ZOO_ENHANCED system section should have calibration guidance"

    def test_basic_prompt_uses_calibrated_system_prompt(self) -> None:
        """Test that basic RISK_ANALYSIS_PROMPT uses calibrated system message."""
        prompt = RISK_ANALYSIS_PROMPT

        # Should include calibration concepts in system section
        system_section = (
            prompt.split("<|im_start|>user")[0] if "<|im_start|>user" in prompt else prompt
        )

        # Check for key calibration concepts
        has_calibration = any(
            [
                "Most detections are NOT threats" in system_section,
                "CRITICAL PRINCIPLE" in system_section,
                "miscalibrated" in system_section,
                "home security analyst" in system_section,
            ]
        )

        assert has_calibration, "Basic prompt system section should have calibration guidance"


class TestPromptTemplatesContainCrossCamera:
    """Verify prompt templates include the cross-camera person tracking placeholder."""

    def test_model_zoo_enhanced_has_placeholder(self):
        assert "{cross_camera_person_tracking}" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT

    def test_model_zoo_enhanced_has_risk_guide_section(self):
        """The risk interpretation guide should include cross-camera tracking guidance."""
        assert "Cross-Camera Person Tracking" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "perimeter" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT.lower()
