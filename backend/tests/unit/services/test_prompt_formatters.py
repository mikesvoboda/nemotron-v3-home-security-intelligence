"""Unit tests for MODEL_ZOO_ENHANCED prompt template structure (R8 S2).

The per-enrichment formatter zoo retired with the Nemotron tier; what these
tests pin is the surviving contract on the template itself: placeholder
coverage (NEM-3041 KeyError guards) and ChatML/output structure.
"""

from __future__ import annotations

from backend.services.prompts import MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT


class TestPromptTemplateStructure:
    """Tests for the MODEL_ZOO_ENHANCED prompt template structure."""

    def test_template_has_all_required_fields(self) -> None:
        """Test that the template contains all required placeholder fields."""
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

        for required_field in required_fields:
            assert required_field in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT, (
                f"Missing required field: {required_field}"
            )

    def test_template_has_chatml_format(self) -> None:
        """Test that the template uses ChatML format."""
        assert "<|im_start|>system" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "<|im_start|>user" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "<|im_start|>assistant" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "<|im_end|>" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT

    def test_template_has_risk_interpretation_guide(self) -> None:
        """Test that the template contains the risk interpretation guide."""
        assert "## Risk Interpretation Guide" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "### Violence Detection" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "### Weather Context" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "### Clothing/Attire Risk Factors" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "### Vehicle Analysis" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "### Pet Detection" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT

    def test_template_has_json_output_format(self) -> None:
        """Test that the template specifies JSON output format."""
        assert "Output JSON" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"risk_score"' in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"risk_level"' in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"summary"' in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"reasoning"' in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"entities"' in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"flags"' in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"recommended_action"' in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"confidence_factors"' in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT


class TestModelZooEnhancedPromptNewFields:
    """Tests for new fields in MODEL_ZOO_ENHANCED prompt template."""

    def test_template_has_ondemand_enrichment_field(self) -> None:
        """Test that template contains the new ondemand_enrichment_context field."""
        assert "{ondemand_enrichment_context}" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT

    def test_template_has_threat_detection_guide(self) -> None:
        """Test that template contains threat detection risk interpretation."""
        assert "### Threat Detection (Weapons)" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "weapon detection" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT.lower()

    def test_template_has_action_recognition_guide(self) -> None:
        """Test that template contains action recognition risk interpretation."""
        assert "### Action Recognition" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "Sneaking" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT

    def test_template_has_demographics_guide(self) -> None:
        """Test that template contains demographics context guidance."""
        assert "### Demographics Context" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "Do NOT use demographics to escalate" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT


class TestPromptTemplatePlaceholders:
    """Tests to ensure all prompt templates have their placeholders satisfied.

    These tests prevent KeyError bugs like the one in NEM-3041 where
    MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT.format() failed because
    'ondemand_enrichment_context' wasn't being passed.
    """

    def test_risk_analysis_prompt_placeholders(self) -> None:
        """Test RISK_ANALYSIS_PROMPT has all placeholders documented."""
        import re

        from backend.services.prompts import RISK_ANALYSIS_PROMPT

        # Extract all placeholders from the template
        placeholders = set(re.findall(r"\{(\w+)\}", RISK_ANALYSIS_PROMPT))

        # Expected placeholders for basic prompt
        expected = {
            "camera_name",
            "start_time",
            "end_time",
            "detections_list",
        }

        assert placeholders == expected, (
            f"Unexpected placeholders. Expected: {expected}, Found: {placeholders}"
        )

    def test_model_zoo_enhanced_prompt_placeholders(self) -> None:
        """Test MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT has all placeholders documented.

        This test would have caught the bug where 'ondemand_enrichment_context'
        was missing from the format() call.
        """
        import re

        placeholders = set(re.findall(r"\{(\w+)\}", MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT))

        expected = {
            "camera_name",
            "timestamp",
            "day_of_week",
            "time_of_day",
            "weather_context",
            "image_quality_context",
            "camera_health_context",
            "detections_with_all_attributes",
            "confidence_quality_summary",
            "violence_context",
            "pose_analysis",
            "action_recognition",
            "trajectory_context",
            "vehicle_classification_context",
            "vehicle_damage_context",
            "clothing_analysis_context",
            "pet_classification_context",
            "depth_context",
            "reid_context",
            "cross_camera_person_tracking",
            "zone_analysis",
            "baseline_comparison",
            "deviation_score",
            "cross_camera_summary",
            "scene_analysis",
            "ondemand_enrichment_context",
            "clip_analysis_context",
        }

        assert placeholders == expected, (
            f"Unexpected placeholders. Expected: {expected}, Found: {placeholders}"
        )


class TestPromptTemplateFormatting:
    """Tests that verify prompts can be formatted without KeyError.

    These tests attempt to format each template with a valid set of parameters
    to catch missing placeholder bugs early.
    """

    def test_risk_analysis_prompt_formats_successfully(self) -> None:
        """Test RISK_ANALYSIS_PROMPT can be formatted without errors."""
        from backend.services.prompts import RISK_ANALYSIS_PROMPT

        params = {
            "camera_name": "Front Door",
            "start_time": "2024-01-20 10:00:00",
            "end_time": "2024-01-20 10:01:30",
            "detections_list": "1 person detected",
        }

        try:
            result = RISK_ANALYSIS_PROMPT.format(**params)
            assert len(result) > 0
            assert "Front Door" in result
        except KeyError as e:
            raise AssertionError(f"Missing placeholder in RISK_ANALYSIS_PROMPT: {e}") from e

    def test_model_zoo_enhanced_prompt_formats_successfully(self) -> None:
        """Test MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT can be formatted without errors.

        This test would have caught the bug where 'ondemand_enrichment_context'
        was missing from the format() call in nemotron_analyzer.py.
        """
        params = {
            "camera_name": "Front Door",
            "timestamp": "2024-01-20 10:00:00 to 10:01:30",
            "day_of_week": "Saturday",
            "time_of_day": "day",
            "weather_context": "Weather: clear (90% confidence)",
            "image_quality_context": "Image quality: Good (score: 85/100)",
            "camera_health_context": "No tampering detected",
            "detections_with_all_attributes": "1 person detected",
            "confidence_quality_summary": "Detection confidence: GOOD (75-90%)",
            "violence_context": "",
            "pose_analysis": "Pose analysis: standing (90% confidence)",
            "action_recognition": "Action: walking (85% confidence)",
            "trajectory_context": "Movement: approaching entry point",
            "vehicle_classification_context": "Vehicle classification: No vehicles analyzed",
            "vehicle_damage_context": "Vehicle damage: No vehicles analyzed for damage",
            "clothing_analysis_context": "Clothing: blue jacket, dark pants",
            "pet_classification_context": "Pet classification: No animals detected",
            "depth_context": "Depth analysis: Person at 3m distance",
            "reid_context": "Re-ID: No previous sightings",
            "cross_camera_person_tracking": "No cross-camera person movement detected",
            "zone_analysis": "entry_point zone",
            "baseline_comparison": "Normal activity for this time",
            "deviation_score": "0.15",
            "cross_camera_summary": "No cross-camera activity",
            "scene_analysis": "Person approaching front door",
            "ondemand_enrichment_context": "",
            "clip_analysis_context": "CLIP scene: person at door (0.85 confidence)",
        }

        try:
            result = MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT.format(**params)
            assert len(result) > 0
            assert "Front Door" in result
            assert "Saturday" in result
        except KeyError as e:
            raise AssertionError(
                f"Missing placeholder in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT: {e}. "
                f"This is the bug that NEM-3041 fixed!"
            ) from e

    def test_model_zoo_enhanced_prompt_with_ondemand_enrichment(self) -> None:
        """Test MODEL_ZOO_ENHANCED with actual on-demand enrichment content."""
        params = {
            "camera_name": "Front Door",
            "timestamp": "2024-01-20 10:00:00 to 10:01:30",
            "day_of_week": "Saturday",
            "time_of_day": "day",
            "weather_context": "Weather: clear",
            "image_quality_context": "Image quality: Good",
            "camera_health_context": "No tampering detected",
            "detections_with_all_attributes": "1 person detected",
            "confidence_quality_summary": "Detection confidence: GOOD",
            "violence_context": "",
            "pose_analysis": "Pose: standing",
            "action_recognition": "Action: walking",
            "trajectory_context": "Movement: approaching",
            "vehicle_classification_context": "No vehicles",
            "vehicle_damage_context": "No damage",
            "clothing_analysis_context": "Clothing: casual",
            "pet_classification_context": "No pets",
            "depth_context": "Depth: 3m",
            "reid_context": "No previous sightings",
            "cross_camera_person_tracking": "No cross-camera movement",
            "zone_analysis": "entry_point",
            "baseline_comparison": "Normal",
            "deviation_score": "0.15",
            "cross_camera_summary": "None",
            "scene_analysis": "Person at door",
            "ondemand_enrichment_context": (
                "## Person Analysis\n"
                "### Pose & Posture\n"
                "Pose: standing (92% confidence)\n"
                "Suspicious posture: No\n"
            ),
            "clip_analysis_context": "CLIP: person at door",
        }

        result = MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT.format(**params)
        assert len(result) > 0
        assert "Person Analysis" in result
        assert "standing" in result


class TestPromptFormattingCatchesMissingPlaceholders:
    """Tests that demonstrate how formatting errors are caught.

    These tests intentionally omit placeholders to verify that KeyError
    is raised appropriately.
    """

    def test_missing_placeholder_raises_keyerror(self) -> None:
        """Test that missing placeholders raise KeyError."""
        from backend.services.prompts import RISK_ANALYSIS_PROMPT

        incomplete_params = {
            "camera_name": "Front Door",
            "start_time": "2024-01-20 10:00:00",
            # Missing: end_time, detections_list
        }

        try:
            RISK_ANALYSIS_PROMPT.format(**incomplete_params)
            raise AssertionError("Expected KeyError for missing placeholders")
        except KeyError as e:
            # This is expected - missing placeholders should raise KeyError
            assert str(e) in ("'end_time'", "'detections_list'")

    def test_model_zoo_missing_ondemand_enrichment_raises_keyerror(self) -> None:
        """Test that missing ondemand_enrichment_context raises KeyError.

        This reproduces the original bug from NEM-3041.
        """
        params = {
            "camera_name": "Front Door",
            "timestamp": "2024-01-20 10:00:00 to 10:01:30",
            "day_of_week": "Saturday",
            "time_of_day": "day",
            "weather_context": "clear",
            "image_quality_context": "Good",
            "camera_health_context": "No tampering",
            "detections_with_all_attributes": "1 person",
            "confidence_quality_summary": "GOOD",
            "violence_context": "None",
            "pose_analysis": "standing",
            "action_recognition": "walking",
            "trajectory_context": "approaching",
            "vehicle_classification_context": "No vehicles",
            "vehicle_damage_context": "No damage",
            "clothing_analysis_context": "casual",
            "pet_classification_context": "No pets",
            "depth_context": "3m",
            "reid_context": "No previous sightings",
            "cross_camera_person_tracking": "No movement",
            "zone_analysis": "entry_point",
            "baseline_comparison": "Normal",
            "deviation_score": "0.15",
            "cross_camera_summary": "None",
            "scene_analysis": "Person at door",
            "clip_analysis_context": "CLIP: person at door",
            # INTENTIONALLY MISSING: ondemand_enrichment_context
        }

        try:
            MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT.format(**params)
            raise AssertionError(
                "Expected KeyError for missing 'ondemand_enrichment_context'. "
                "This is the bug that was fixed in NEM-3041!"
            )
        except KeyError as e:
            assert "ondemand_enrichment_context" in str(e)
