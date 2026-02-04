"""Unit tests for format_scene_ocr_context() in backend/services/prompts.py.

Tests cover:
- None input returns empty string
- Empty results format correctly
- Scene texts format with all fields
- Detection OCR with service matches
- Confidence filtering (exclude < 0.50)
- JSON output is valid and parseable

See docs/plans/2026-02-04-scene-ocr-design.md for the Scene OCR feature design.
"""

from __future__ import annotations

import json

from backend.services.prompts import format_scene_ocr_context
from backend.services.scene_ocr_service import (
    DetectionOCRResult,
    SceneOCRResult,
    SceneTextResult,
    ServiceMatch,
)


class TestFormatSceneOCRContextNoneInput:
    """Tests for None input handling."""

    def test_none_input_returns_empty_string(self) -> None:
        """None input should return empty string."""
        result = format_scene_ocr_context(None)
        assert result == ""


class TestFormatSceneOCRContextEmptyResults:
    """Tests for empty result handling."""

    def test_empty_scene_ocr_result_returns_empty_string(self) -> None:
        """Empty SceneOCRResult (no scene_texts, no detection_ocr) returns empty string."""
        scene_ocr = SceneOCRResult(
            scene_texts=[],
            detection_ocr={},
            processing_time_ms=0.0,
        )
        result = format_scene_ocr_context(scene_ocr)
        assert result == ""

    def test_only_low_confidence_texts_returns_empty_string(self) -> None:
        """Scene with only low-confidence texts (< 0.50) returns empty string."""
        scene_ocr = SceneOCRResult(
            scene_texts=[
                SceneTextResult(
                    value="NOISE",
                    confidence=0.30,
                    bbox=(10, 20, 100, 50),
                    text_type="sign",
                ),
                SceneTextResult(
                    value="SHADOW",
                    confidence=0.49,
                    bbox=(200, 300, 400, 500),
                    text_type=None,
                ),
            ],
            detection_ocr={},
        )
        result = format_scene_ocr_context(scene_ocr)
        assert result == ""


class TestFormatSceneOCRContextSceneTexts:
    """Tests for scene text formatting."""

    def test_scene_texts_format_with_all_fields(self) -> None:
        """Scene texts should include value, type, and confidence."""
        scene_ocr = SceneOCRResult(
            scene_texts=[
                SceneTextResult(
                    value="123",
                    confidence=0.88,
                    bbox=(50, 20, 90, 45),
                    text_type="house_number",
                ),
                SceneTextResult(
                    value="Main St",
                    confidence=0.92,
                    bbox=(200, 10, 320, 40),
                    text_type="street_sign",
                ),
            ],
            detection_ocr={},
        )
        result = format_scene_ocr_context(scene_ocr)

        # Verify JSON is parseable
        parsed = json.loads(result)

        # Verify structure
        assert "scene_text" in parsed
        assert "detection_ocr" in parsed

        # Verify scene_text contents
        assert len(parsed["scene_text"]) == 2

        # Check first text
        text_123 = next(t for t in parsed["scene_text"] if t["value"] == "123")
        assert text_123["type"] == "house_number"
        assert text_123["confidence"] == 0.88

        # Check second text
        text_main = next(t for t in parsed["scene_text"] if t["value"] == "Main St")
        assert text_main["type"] == "street_sign"
        assert text_main["confidence"] == 0.92

    def test_scene_text_with_null_type(self) -> None:
        """Scene text with no text_type should include null in output."""
        scene_ocr = SceneOCRResult(
            scene_texts=[
                SceneTextResult(
                    value="STOP",
                    confidence=0.96,
                    bbox=(600, 30, 680, 110),
                    text_type=None,
                ),
            ],
            detection_ocr={},
        )
        result = format_scene_ocr_context(scene_ocr)
        parsed = json.loads(result)

        assert len(parsed["scene_text"]) == 1
        assert parsed["scene_text"][0]["value"] == "STOP"
        assert parsed["scene_text"][0]["type"] is None
        assert parsed["scene_text"][0]["confidence"] == 0.96

    def test_confidence_is_rounded_to_two_decimals(self) -> None:
        """Confidence values should be rounded to 2 decimal places."""
        scene_ocr = SceneOCRResult(
            scene_texts=[
                SceneTextResult(
                    value="TEST",
                    confidence=0.87654321,
                    bbox=(10, 20, 30, 40),
                    text_type="sign",
                ),
            ],
            detection_ocr={},
        )
        result = format_scene_ocr_context(scene_ocr)
        parsed = json.loads(result)

        assert parsed["scene_text"][0]["confidence"] == 0.88


class TestFormatSceneOCRContextDetectionOCR:
    """Tests for detection OCR formatting."""

    def test_detection_ocr_formats_correctly(self) -> None:
        """Detection OCR should be keyed by detection_id with texts array."""
        scene_ocr = SceneOCRResult(
            scene_texts=[],
            detection_ocr={
                "det_001": DetectionOCRResult(
                    detection_id="det_001",
                    texts=[
                        {"value": "FedEx", "confidence": 0.94, "region": "chest"},
                        {"value": "Ground", "confidence": 0.89, "region": "back"},
                    ],
                    service_match=None,
                ),
            },
        )
        result = format_scene_ocr_context(scene_ocr)
        parsed = json.loads(result)

        assert "det_001" in parsed["detection_ocr"]
        det_001 = parsed["detection_ocr"]["det_001"]

        assert len(det_001["texts"]) == 2
        assert det_001["texts"][0]["value"] == "FedEx"
        assert det_001["texts"][0]["confidence"] == 0.94
        assert det_001["texts"][0]["region"] == "chest"
        assert det_001["service_match"] is None

    def test_detection_ocr_with_service_match(self) -> None:
        """Detection OCR with service_match should include match details."""
        service_match = ServiceMatch(
            provider="FedEx",
            category="DELIVERY",
            confidence=0.97,
            risk_modifier="low_risk_service",
        )
        scene_ocr = SceneOCRResult(
            scene_texts=[],
            detection_ocr={
                "det_002": DetectionOCRResult(
                    detection_id="det_002",
                    texts=[
                        {"value": "FedEx", "confidence": 0.94, "region": "side"},
                    ],
                    service_match=service_match,
                ),
            },
        )
        result = format_scene_ocr_context(scene_ocr)
        parsed = json.loads(result)

        det_002 = parsed["detection_ocr"]["det_002"]
        assert det_002["service_match"] is not None
        assert det_002["service_match"]["provider"] == "FedEx"
        assert det_002["service_match"]["category"] == "DELIVERY"
        assert det_002["service_match"]["confidence"] == 0.97
        assert det_002["service_match"]["risk_modifier"] == "low_risk_service"

    def test_multiple_detections(self) -> None:
        """Multiple detections should all be included in output."""
        scene_ocr = SceneOCRResult(
            scene_texts=[],
            detection_ocr={
                "det_001": DetectionOCRResult(
                    detection_id="det_001",
                    texts=[{"value": "Joe's Plumbing", "confidence": 0.91, "region": "chest"}],
                    service_match=ServiceMatch(
                        provider="Joe's Plumbing",
                        category="PLUMBING",
                        confidence=0.95,
                        risk_modifier="low_risk_service",
                    ),
                ),
                "det_002": DetectionOCRResult(
                    detection_id="det_002",
                    texts=[
                        {"value": "Amazon", "confidence": 0.88, "region": "side"},
                        {"value": "Prime", "confidence": 0.75, "region": "side"},
                    ],
                    service_match=ServiceMatch(
                        provider="Amazon",
                        category="DELIVERY",
                        confidence=0.92,
                        risk_modifier="low_risk_service",
                    ),
                ),
            },
        )
        result = format_scene_ocr_context(scene_ocr)
        parsed = json.loads(result)

        assert len(parsed["detection_ocr"]) == 2
        assert "det_001" in parsed["detection_ocr"]
        assert "det_002" in parsed["detection_ocr"]


class TestFormatSceneOCRContextConfidenceFiltering:
    """Tests for confidence threshold filtering."""

    def test_scene_texts_below_threshold_excluded(self) -> None:
        """Scene texts below 0.50 confidence should be excluded."""
        scene_ocr = SceneOCRResult(
            scene_texts=[
                SceneTextResult(
                    value="HIGH_CONF",
                    confidence=0.85,
                    bbox=(10, 20, 100, 50),
                    text_type="sign",
                ),
                SceneTextResult(
                    value="LOW_CONF",
                    confidence=0.45,
                    bbox=(200, 300, 400, 500),
                    text_type="sign",
                ),
                SceneTextResult(
                    value="EXACTLY_THRESHOLD",
                    confidence=0.50,
                    bbox=(500, 600, 700, 800),
                    text_type="sign",
                ),
            ],
            detection_ocr={},
        )
        result = format_scene_ocr_context(scene_ocr)
        parsed = json.loads(result)

        # Should have 2 texts (0.85 and 0.50, but not 0.45)
        values = [t["value"] for t in parsed["scene_text"]]
        assert "HIGH_CONF" in values
        assert "EXACTLY_THRESHOLD" in values
        assert "LOW_CONF" not in values

    def test_detection_texts_below_threshold_excluded(self) -> None:
        """Detection texts below 0.50 confidence should be excluded."""
        scene_ocr = SceneOCRResult(
            scene_texts=[],
            detection_ocr={
                "det_001": DetectionOCRResult(
                    detection_id="det_001",
                    texts=[
                        {"value": "FedEx", "confidence": 0.94, "region": "chest"},
                        {"value": "NOISE", "confidence": 0.30, "region": "arm"},
                        {"value": "Ground", "confidence": 0.50, "region": "back"},
                    ],
                    service_match=None,
                ),
            },
        )
        result = format_scene_ocr_context(scene_ocr)
        parsed = json.loads(result)

        texts = parsed["detection_ocr"]["det_001"]["texts"]
        values = [t["value"] for t in texts]

        assert "FedEx" in values
        assert "Ground" in values
        assert "NOISE" not in values

    def test_detection_excluded_if_all_texts_below_threshold_and_no_service_match(self) -> None:
        """Detection should be excluded if all texts are low-confidence and no service match."""
        scene_ocr = SceneOCRResult(
            scene_texts=[
                SceneTextResult(
                    value="VALID",
                    confidence=0.80,
                    bbox=(10, 20, 100, 50),
                    text_type="sign",
                ),
            ],
            detection_ocr={
                "det_001": DetectionOCRResult(
                    detection_id="det_001",
                    texts=[
                        {"value": "NOISE1", "confidence": 0.30, "region": "chest"},
                        {"value": "NOISE2", "confidence": 0.40, "region": "arm"},
                    ],
                    service_match=None,
                ),
            },
        )
        result = format_scene_ocr_context(scene_ocr)
        parsed = json.loads(result)

        # Detection with all low-confidence texts and no service_match should be excluded
        assert "det_001" not in parsed["detection_ocr"]

    def test_detection_included_if_service_match_present_even_with_low_conf_texts(self) -> None:
        """Detection with service_match should be included even if texts are low-confidence."""
        scene_ocr = SceneOCRResult(
            scene_texts=[],
            detection_ocr={
                "det_001": DetectionOCRResult(
                    detection_id="det_001",
                    texts=[
                        {"value": "FdEx", "confidence": 0.45, "region": "chest"},  # Fuzzy match
                    ],
                    service_match=ServiceMatch(
                        provider="FedEx",
                        category="DELIVERY",
                        confidence=0.85,  # Boosted by fuzzy matching
                        risk_modifier="low_risk_service",
                    ),
                ),
            },
        )
        result = format_scene_ocr_context(scene_ocr)
        parsed = json.loads(result)

        # Detection should be included because of service_match
        assert "det_001" in parsed["detection_ocr"]
        # But low-confidence text should still be filtered out
        assert len(parsed["detection_ocr"]["det_001"]["texts"]) == 0
        # Service match should be present
        assert parsed["detection_ocr"]["det_001"]["service_match"]["provider"] == "FedEx"


class TestFormatSceneOCRContextJSONValidity:
    """Tests for JSON output validity."""

    def test_output_is_valid_json(self) -> None:
        """Output should be valid JSON that can be parsed."""
        scene_ocr = SceneOCRResult(
            scene_texts=[
                SceneTextResult(
                    value='Test "Quoted" Text',  # Contains special characters
                    confidence=0.80,
                    bbox=(10, 20, 100, 50),
                    text_type="sign",
                ),
            ],
            detection_ocr={},
        )
        result = format_scene_ocr_context(scene_ocr)

        # Should not raise
        parsed = json.loads(result)
        assert parsed is not None

    def test_output_has_proper_indentation(self) -> None:
        """Output should have indent=2 for readability."""
        scene_ocr = SceneOCRResult(
            scene_texts=[
                SceneTextResult(
                    value="TEST",
                    confidence=0.90,
                    bbox=(10, 20, 100, 50),
                    text_type="sign",
                ),
            ],
            detection_ocr={},
        )
        result = format_scene_ocr_context(scene_ocr)

        # Check for indentation (2 spaces)
        assert "  " in result
        # Newlines should be present for pretty printing
        assert "\n" in result

    def test_special_characters_in_text_are_escaped(self) -> None:
        """Special characters in text values should be properly escaped."""
        scene_ocr = SceneOCRResult(
            scene_texts=[
                SceneTextResult(
                    value='Test\nNewline\tTab"Quote',
                    confidence=0.80,
                    bbox=(10, 20, 100, 50),
                    text_type="sign",
                ),
            ],
            detection_ocr={},
        )
        result = format_scene_ocr_context(scene_ocr)

        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed["scene_text"][0]["value"] == 'Test\nNewline\tTab"Quote'


class TestFormatSceneOCRContextCompleteExample:
    """Integration test with complete realistic example."""

    def test_complete_realistic_example(self) -> None:
        """Test with a complete realistic scene OCR result."""
        scene_ocr = SceneOCRResult(
            scene_texts=[
                SceneTextResult(
                    value="123",
                    confidence=0.88,
                    bbox=(50, 20, 90, 45),
                    text_type="house_number",
                ),
                SceneTextResult(
                    value="Main St",
                    confidence=0.92,
                    bbox=(200, 10, 320, 40),
                    text_type="street_sign",
                ),
                SceneTextResult(
                    value="STOP",
                    confidence=0.96,
                    bbox=(600, 30, 680, 110),
                    text_type="sign",
                ),
            ],
            detection_ocr={
                "det_001": DetectionOCRResult(
                    detection_id="det_001",
                    texts=[
                        {"value": "Joe's Plumbing", "confidence": 0.91, "region": "chest"},
                    ],
                    service_match=ServiceMatch(
                        provider="Joe's Plumbing",
                        category="PLUMBING",
                        confidence=0.95,
                        risk_modifier="low_risk_service",
                    ),
                ),
                "det_002": DetectionOCRResult(
                    detection_id="det_002",
                    texts=[
                        {"value": "FedEx", "confidence": 0.94, "region": "side"},
                        {"value": "Ground", "confidence": 0.89, "region": "side"},
                    ],
                    service_match=ServiceMatch(
                        provider="FedEx",
                        category="DELIVERY",
                        confidence=0.97,
                        risk_modifier="low_risk_service",
                    ),
                ),
            },
            processing_time_ms=150.5,
        )

        result = format_scene_ocr_context(scene_ocr)
        parsed = json.loads(result)

        # Verify scene_text
        assert len(parsed["scene_text"]) == 3
        values = [t["value"] for t in parsed["scene_text"]]
        assert "123" in values
        assert "Main St" in values
        assert "STOP" in values

        # Verify detection_ocr
        assert len(parsed["detection_ocr"]) == 2

        # Verify det_001 (person with plumbing uniform)
        det_001 = parsed["detection_ocr"]["det_001"]
        assert det_001["texts"][0]["value"] == "Joe's Plumbing"
        assert det_001["service_match"]["category"] == "PLUMBING"

        # Verify det_002 (FedEx vehicle)
        det_002 = parsed["detection_ocr"]["det_002"]
        text_values = [t["value"] for t in det_002["texts"]]
        assert "FedEx" in text_values
        assert "Ground" in text_values
        assert det_002["service_match"]["provider"] == "FedEx"
        assert det_002["service_match"]["category"] == "DELIVERY"
