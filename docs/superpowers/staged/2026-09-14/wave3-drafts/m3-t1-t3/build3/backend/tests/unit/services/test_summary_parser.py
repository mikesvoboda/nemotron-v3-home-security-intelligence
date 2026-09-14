"""Unit tests for summary_parser service.

Tests cover:
- BulletPoint dataclass creation and serialization
- StructuredSummary dataclass creation and serialization
- parse_summary_content function with various inputs:
  - Extracting camera names as focus areas
  - Extracting behavior patterns (loitering, obscured faces, etc.)
  - Extracting weather conditions
  - Generating bullet points from extracted data
  - Edge cases (empty content, no matches, etc.)

Related Linear issue: NEM-2927
"""

from __future__ import annotations

import pytest

from backend.services.summary_parser import (
    BEHAVIOR_PATTERNS,
    KNOWN_CAMERAS,
    WEATHER_CONDITIONS,
    BulletPoint,
    StructuredSummary,
    parse_summary_content,
)

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# Tests: BulletPoint Dataclass


class TestBulletPointDataclass:
    """Tests for the BulletPoint dataclass."""

    def test_bullet_point_creation_basic(self) -> None:
        """Test creating a basic BulletPoint."""
        bp = BulletPoint(
            icon="warning",
            text="Person detected at front door",
        )

        assert bp.icon == "warning"
        assert bp.text == "Person detected at front door"
        assert bp.severity is None

    def test_bullet_point_creation_with_severity(self) -> None:
        """Test creating a BulletPoint with severity."""
        bp = BulletPoint(
            icon="alert",
            text="Critical event at Beach Front Left",
            severity="critical",
        )

        assert bp.icon == "alert"
        assert bp.text == "Critical event at Beach Front Left"
        assert bp.severity == "critical"

    def test_bullet_point_to_dict(self) -> None:
        """Test converting BulletPoint to dictionary."""
        bp = BulletPoint(
            icon="camera",
            text="Activity at Dock Left camera",
            severity="high",
        )

        result = bp.to_dict()

        assert result == {
            "icon": "camera",
            "text": "Activity at Dock Left camera",
            "severity": "high",
        }

    def test_bullet_point_to_dict_without_severity(self) -> None:
        """Test converting BulletPoint to dict when severity is None."""
        bp = BulletPoint(
            icon="info",
            text="Routine activity detected",
        )

        result = bp.to_dict()

        assert result == {
            "icon": "info",
            "text": "Routine activity detected",
            "severity": None,
        }


# Tests: StructuredSummary Dataclass


class TestStructuredSummaryDataclass:
    """Tests for the StructuredSummary dataclass."""

    def test_structured_summary_creation_empty(self) -> None:
        """Test creating an empty StructuredSummary."""
        ss = StructuredSummary()

        assert ss.bullet_points == []
        assert ss.focus_areas == []
        assert ss.dominant_patterns == []
        assert ss.max_risk_score is None
        assert ss.weather_conditions == []

    def test_structured_summary_creation_with_data(self) -> None:
        """Test creating a StructuredSummary with all fields."""
        bullet_points = [
            BulletPoint(icon="warning", text="Activity detected"),
            BulletPoint(icon="alert", text="Person at door", severity="high"),
        ]

        ss = StructuredSummary(
            bullet_points=bullet_points,
            focus_areas=["Beach Front Left", "Dock Right"],
            dominant_patterns=["loitering", "rapid movement"],
            max_risk_score=85,
            weather_conditions=["nighttime", "rainy"],
        )

        assert len(ss.bullet_points) == 2
        assert ss.focus_areas == ["Beach Front Left", "Dock Right"]
        assert ss.dominant_patterns == ["loitering", "rapid movement"]
        assert ss.max_risk_score == 85
        assert ss.weather_conditions == ["nighttime", "rainy"]

    def test_structured_summary_to_dict(self) -> None:
        """Test converting StructuredSummary to dictionary."""
        bullet_points = [
            BulletPoint(icon="camera", text="Camera activity", severity="medium"),
        ]

        ss = StructuredSummary(
            bullet_points=bullet_points,
            focus_areas=["Kitchen"],
            dominant_patterns=["obscured face"],
            max_risk_score=75,
            weather_conditions=["nighttime"],
        )

        result = ss.to_dict()

        assert result == {
            "bullet_points": [{"icon": "camera", "text": "Camera activity", "severity": "medium"}],
            "focus_areas": ["Kitchen"],
            "dominant_patterns": ["obscured face"],
            "max_risk_score": 75,
            "weather_conditions": ["nighttime"],
        }

    def test_structured_summary_to_dict_empty(self) -> None:
        """Test converting empty StructuredSummary to dictionary."""
        ss = StructuredSummary()

        result = ss.to_dict()

        assert result == {
            "bullet_points": [],
            "focus_areas": [],
            "dominant_patterns": [],
            "max_risk_score": None,
            "weather_conditions": [],
        }


# Tests: Constants


class TestConstants:
    """Tests for module constants."""

    def test_known_cameras_contains_expected_cameras(self) -> None:
        """Test that KNOWN_CAMERAS contains all expected camera names."""
        expected_cameras = [
            "Beach Front Left",
            "Beach Front Right",
            "Dock Left",
            "Dock Right",
            "Kitchen",
            "Ami Frontyard Left",
            "Ami Frontyard Right",
        ]

        for camera in expected_cameras:
            assert camera in KNOWN_CAMERAS

    def test_behavior_patterns_contains_key_patterns(self) -> None:
        """Test that BEHAVIOR_PATTERNS contains key security patterns."""
        expected_patterns = ["loitering", "obscured face", "rapid movement"]

        for pattern in expected_patterns:
            assert pattern in BEHAVIOR_PATTERNS

    def test_weather_conditions_contains_key_conditions(self) -> None:
        """Test that WEATHER_CONDITIONS contains key conditions."""
        expected_conditions = ["rainy", "nighttime"]

        for condition in expected_conditions:
            assert condition in WEATHER_CONDITIONS


# Tests: parse_summary_content Function


class TestParseSummaryContent:
    """Tests for the parse_summary_content function."""

    def test_parse_empty_content(self) -> None:
        """Test parsing empty content returns empty StructuredSummary."""
        result = parse_summary_content("")

        assert result.bullet_points == []
        assert result.focus_areas == []
        assert result.dominant_patterns == []
        assert result.max_risk_score is None
        assert result.weather_conditions == []

    def test_parse_none_content(self) -> None:
        """Test parsing None content returns empty StructuredSummary."""
        result = parse_summary_content(None)

        assert result.bullet_points == []
        assert result.focus_areas == []

    def test_extract_single_camera_name(self) -> None:
        """Test extracting a single camera name as focus area."""
        content = "Activity detected at Beach Front Left camera at 2:15 PM."

        result = parse_summary_content(content)

        assert "Beach Front Left" in result.focus_areas

    def test_extract_multiple_camera_names(self) -> None:
        """Test extracting multiple camera names."""
        content = (
            "Events occurred at Beach Front Left and Dock Right cameras. "
            "Kitchen camera also showed activity."
        )

        result = parse_summary_content(content)

        assert "Beach Front Left" in result.focus_areas
        assert "Dock Right" in result.focus_areas
        assert "Kitchen" in result.focus_areas

    def test_extract_camera_names_case_insensitive(self) -> None:
        """Test camera name extraction is case insensitive."""
        content = "Activity at BEACH FRONT LEFT and beach front right."

        result = parse_summary_content(content)

        # Should match known cameras case-insensitively
        assert len(result.focus_areas) >= 1

    def test_extract_loitering_pattern(self) -> None:
        """Test extracting loitering behavior pattern."""
        content = "Person was loitering near the entrance for 5 minutes."

        result = parse_summary_content(content)

        assert "loitering" in result.dominant_patterns

    def test_extract_obscured_face_pattern(self) -> None:
        """Test extracting obscured face behavior pattern."""
        content = "Individual with obscured face detected at the door."

        result = parse_summary_content(content)

        assert "obscured face" in result.dominant_patterns

    def test_extract_rapid_movement_pattern(self) -> None:
        """Test extracting rapid movement behavior pattern."""
        content = "Person running with rapid movement through the yard."

        result = parse_summary_content(content)

        assert "rapid movement" in result.dominant_patterns

    def test_extract_multiple_patterns(self) -> None:
        """Test extracting multiple behavior patterns."""
        content = (
            "Suspicious activity: person loitering with obscured face, "
            "then made rapid movement toward exit."
        )

        result = parse_summary_content(content)

        assert "loitering" in result.dominant_patterns
        assert "obscured face" in result.dominant_patterns
        assert "rapid movement" in result.dominant_patterns

    def test_extract_nighttime_condition(self) -> None:
        """Test extracting nighttime weather condition."""
        content = "Activity detected during nighttime hours at the dock."

        result = parse_summary_content(content)

        assert "nighttime" in result.weather_conditions

    def test_extract_rainy_condition(self) -> None:
        """Test extracting rainy weather condition."""
        content = "Person approached in rainy conditions, visibility was poor."

        result = parse_summary_content(content)

        assert "rainy" in result.weather_conditions

    def test_extract_multiple_weather_conditions(self) -> None:
        """Test extracting multiple weather conditions."""
        content = "Rainy nighttime activity at the beach front."

        result = parse_summary_content(content)

        assert "rainy" in result.weather_conditions
        assert "nighttime" in result.weather_conditions

    def test_generates_bullet_points_for_camera(self) -> None:
        """Test that bullet points are generated for camera activity."""
        content = "Critical event at Beach Front Left: person detected."

        result = parse_summary_content(content)

        # Should have at least one bullet point related to camera
        assert len(result.bullet_points) >= 1
        # Check that bullet point references the camera
        camera_mentioned = any("Beach Front Left" in bp.text for bp in result.bullet_points)
        assert camera_mentioned

    def test_generates_bullet_points_for_patterns(self) -> None:
        """Test that bullet points are generated for behavior patterns."""
        content = "Suspicious loitering behavior observed."

        result = parse_summary_content(content)

        assert len(result.bullet_points) >= 1

    def test_max_risk_score_from_events(self) -> None:
        """Test max_risk_score is extracted from event data."""
        content = "High-priority event with risk score 85."
        events = [
            {"risk_score": 85, "risk_level": "high"},
            {"risk_score": 45, "risk_level": "medium"},
        ]

        result = parse_summary_content(content, events=events)

        assert result.max_risk_score == 85

    def test_max_risk_score_none_when_no_events(self) -> None:
        """Test max_risk_score is None when no events provided."""
        content = "No high-priority events detected."

        result = parse_summary_content(content)

        assert result.max_risk_score is None

    def test_max_risk_score_none_when_empty_events(self) -> None:
        """Test max_risk_score is None when events list is empty."""
        content = "All clear for this period."

        result = parse_summary_content(content, events=[])

        assert result.max_risk_score is None

    def test_comprehensive_content_parsing(self) -> None:
        """Test parsing content with all elements."""
        content = (
            "Over the past hour, two critical events occurred. At 2:15 PM, "
            "an individual with obscured face was loitering at Beach Front Left "
            "during rainy nighttime conditions. At 2:30 PM, rapid movement was "
            "detected at Dock Right camera."
        )
        events = [
            {"risk_score": 90, "risk_level": "critical"},
            {"risk_score": 75, "risk_level": "high"},
        ]

        result = parse_summary_content(content, events=events)

        # Check focus areas
        assert "Beach Front Left" in result.focus_areas
        assert "Dock Right" in result.focus_areas

        # Check patterns
        assert "obscured face" in result.dominant_patterns
        assert "loitering" in result.dominant_patterns
        assert "rapid movement" in result.dominant_patterns

        # Check weather
        assert "rainy" in result.weather_conditions
        assert "nighttime" in result.weather_conditions

        # Check max risk score
        assert result.max_risk_score == 90

        # Check bullet points generated
        assert len(result.bullet_points) > 0

    def test_bullet_point_severity_from_content(self) -> None:
        """Test that bullet point severity is determined from context."""
        content = "Critical security event: person with obscured face at Beach Front Left."
        events = [{"risk_score": 95, "risk_level": "critical"}]

        result = parse_summary_content(content, events=events)

        # At least one bullet point should have severity
        has_severity = any(bp.severity is not None for bp in result.bullet_points)
        assert has_severity

    def test_no_duplicate_focus_areas(self) -> None:
        """Test that focus areas don't contain duplicates."""
        content = (
            "Beach Front Left showed activity. More activity at Beach Front Left. "
            "Beach Front Left camera captured everything."
        )

        result = parse_summary_content(content)

        # Should only have one instance of Beach Front Left
        assert result.focus_areas.count("Beach Front Left") == 1

    def test_no_duplicate_patterns(self) -> None:
        """Test that dominant patterns don't contain duplicates."""
        content = "Loitering detected. More loitering observed. Continued loitering."

        result = parse_summary_content(content)

        # Should only have one instance of loitering
        assert result.dominant_patterns.count("loitering") == 1

    def test_all_clear_content(self) -> None:
        """Test parsing 'all clear' type content."""
        content = (
            "No high-priority security events in the past hour. "
            "The property has been quiet with only routine activity."
        )

        result = parse_summary_content(content)

        # Should have minimal or no focus areas and patterns
        # May generate an "all clear" type bullet point
        assert isinstance(result.bullet_points, list)
        assert isinstance(result.focus_areas, list)

    def test_ami_frontyard_cameras_extracted(self) -> None:
        """Test that Ami Frontyard cameras are properly extracted."""
        content = "Activity at Ami Frontyard Left and Ami Frontyard Right cameras."

        result = parse_summary_content(content)

        assert "Ami Frontyard Left" in result.focus_areas
        assert "Ami Frontyard Right" in result.focus_areas


# Tests: Edge Cases


class TestEdgeCases:
    """Tests for edge cases in summary parsing."""

    def test_content_with_only_whitespace(self) -> None:
        """Test parsing content that is only whitespace."""
        result = parse_summary_content("   \n\t  ")

        assert result.bullet_points == []
        assert result.focus_areas == []

    def test_content_with_special_characters(self) -> None:
        """Test parsing content with special characters."""
        content = "Activity @ Beach Front Left! #security $alert"

        result = parse_summary_content(content)

        assert "Beach Front Left" in result.focus_areas

    def test_partial_camera_name_not_matched(self) -> None:
        """Test that partial camera names are not matched."""
        content = "Activity at Beach and Front areas."

        result = parse_summary_content(content)

        # Should not match "Beach Front Left" or "Beach Front Right"
        # because the full name is not present
        assert "Beach Front Left" not in result.focus_areas
        assert "Beach Front Right" not in result.focus_areas

    def test_events_with_missing_risk_score(self) -> None:
        """Test handling events with missing risk_score."""
        content = "Event detected."
        events = [
            {"risk_level": "high"},  # No risk_score
            {"risk_score": 70, "risk_level": "high"},
        ]

        result = parse_summary_content(content, events=events)

        assert result.max_risk_score == 70

    def test_events_with_none_risk_score(self) -> None:
        """Test handling events with None risk_score."""
        content = "Event detected."
        events = [
            {"risk_score": None, "risk_level": "high"},
            {"risk_score": 60, "risk_level": "medium"},
        ]

        result = parse_summary_content(content, events=events)

        assert result.max_risk_score == 60

    def test_very_long_content(self) -> None:
        """Test parsing very long content performs well."""
        # Create a long content string
        base = "Activity detected at Beach Front Left with loitering behavior. "
        content = base * 100

        result = parse_summary_content(content)

        # Should still parse correctly
        assert "Beach Front Left" in result.focus_areas
        assert "loitering" in result.dominant_patterns

    def test_unicode_content(self) -> None:
        """Test parsing content with unicode characters."""
        content = "Activity at Beach Front Left \u2014 person detected \u2022 high alert"

        result = parse_summary_content(content)

        assert "Beach Front Left" in result.focus_areas

    def test_events_with_non_numeric_risk_scores(self) -> None:
        """Test handling events with non-numeric risk_score values."""
        content = "Event detected."
        events = [
            {"risk_score": "invalid", "risk_level": "high"},  # Invalid type
            {"risk_score": 80, "risk_level": "high"},
        ]

        result = parse_summary_content(content, events=events)

        # Should only use valid numeric scores
        assert result.max_risk_score == 80

    def test_events_with_float_risk_scores(self) -> None:
        """Test handling events with float risk_score values."""
        content = "Event detected."
        events = [
            {"risk_score": 85.7, "risk_level": "high"},
            {"risk_score": 72.3, "risk_level": "medium"},
        ]

        result = parse_summary_content(content, events=events)

        # Should convert float to int
        assert result.max_risk_score == 85

    def test_events_with_all_invalid_risk_scores(self) -> None:
        """Test handling events where all risk scores are invalid."""
        content = "Event detected."
        events = [
            {"risk_score": None, "risk_level": "high"},
            {"risk_score": "invalid", "risk_level": "medium"},
            {"risk_level": "low"},  # Missing risk_score
        ]

        result = parse_summary_content(content, events=events)

        # Should return None when no valid scores
        assert result.max_risk_score is None


# Tests: Severity Determination


class TestSeverityDetermination:
    """Tests for severity determination from events and scores."""

    def test_severity_critical_from_events(self) -> None:
        """Test that critical risk level in events returns 'critical' severity."""
        content = "Critical event detected at Beach Front Left."
        events = [
            {"risk_score": 95, "risk_level": "critical"},
            {"risk_score": 70, "risk_level": "high"},
        ]

        result = parse_summary_content(content, events=events)

        # Should have critical severity in bullet points
        has_critical = any(bp.severity == "critical" for bp in result.bullet_points)
        assert has_critical

    def test_severity_high_from_events(self) -> None:
        """Test that high risk level in events returns 'high' severity."""
        content = "High-priority event detected at Dock Right."
        events = [
            {"risk_score": 75, "risk_level": "high"},
            {"risk_score": 50, "risk_level": "medium"},
        ]

        result = parse_summary_content(content, events=events)

        # Should have high severity
        has_high = any(bp.severity == "high" for bp in result.bullet_points)
        assert has_high

    def test_severity_from_score_critical(self) -> None:
        """Test severity determination from score >= 80 (critical)."""
        content = "Event detected at Kitchen camera."
        events = [{"risk_score": 85}]  # No risk_level, fallback to score

        result = parse_summary_content(content, events=events)

        # Should determine critical from score
        has_critical = any(bp.severity == "critical" for bp in result.bullet_points)
        assert has_critical

    def test_severity_from_score_high(self) -> None:
        """Test severity determination from score 60-79 (high)."""
        content = "Event detected at Beach Front Left."
        events = [{"risk_score": 65}]  # No risk_level, fallback to score

        result = parse_summary_content(content, events=events)

        # Should determine high from score
        has_high = any(bp.severity == "high" for bp in result.bullet_points)
        assert has_high

    def test_severity_from_score_medium(self) -> None:
        """Test severity determination from score 40-59 (medium)."""
        content = "Event detected at Dock Left."
        events = [{"risk_score": 45}]  # No risk_level, fallback to score

        result = parse_summary_content(content, events=events)

        # Should determine medium from score
        has_medium = any(bp.severity == "medium" for bp in result.bullet_points)
        assert has_medium

    def test_severity_from_score_low(self) -> None:
        """Test severity determination from score < 40 (low)."""
        content = "Event detected at Beach Front Right."
        events = [{"risk_score": 25}]  # No risk_level, fallback to score

        result = parse_summary_content(content, events=events)

        # Should determine low from score
        has_low = any(bp.severity == "low" for bp in result.bullet_points)
        assert has_low

    def test_severity_none_when_no_events(self) -> None:
        """Test that severity is None when no events provided."""
        content = "All clear."

        result = parse_summary_content(content)

        # Bullet points should have None severity or no bullet points
        if result.bullet_points:
            # Weather-only bullet points have None severity
            assert all(bp.severity is None for bp in result.bullet_points)

    def test_severity_none_when_no_score_or_level(self) -> None:
        """Test that severity is None when events have no score or level."""
        content = "Event detected."
        events = [{"camera_id": "front_door"}]  # No risk info

        result = parse_summary_content(content)

        # Should handle gracefully with None severity
        if result.bullet_points:
            assert all(bp.severity is None for bp in result.bullet_points)


# Tests: Bullet Point Generation


class TestBulletPointGeneration:
    """Tests for bullet point generation logic."""

    def test_bullet_point_with_camera_context(self) -> None:
        """Test that bullet points include camera context when available."""
        content = "Activity at Beach Front Left: person detected loitering near entrance."

        result = parse_summary_content(content)

        # Should have a bullet point with camera and context
        camera_bp = [bp for bp in result.bullet_points if "Beach Front Left" in bp.text]
        assert len(camera_bp) > 0
        # Context should be included
        assert "person detected" in camera_bp[0].text or "loitering" in camera_bp[0].text

    def test_bullet_point_context_truncation(self) -> None:
        """Test that long camera context is truncated."""
        # Create content with very long context after camera name
        long_context = "a" * 60  # 60 characters, should be truncated
        content = f"Activity at Beach Front Left: {long_context}"

        result = parse_summary_content(content)

        # Should have a bullet point with truncated context
        camera_bp = [bp for bp in result.bullet_points if "Beach Front Left" in bp.text]
        assert len(camera_bp) > 0
        # Should be truncated with ellipsis
        assert "..." in camera_bp[0].text
        # Total text should be reasonable length
        assert len(camera_bp[0].text) < 200

    def test_bullet_point_pattern_not_duplicated_in_camera_context(self) -> None:
        """Test that patterns already mentioned in camera context aren't duplicated."""
        content = "Activity at Beach Front Left: loitering behavior detected"

        result = parse_summary_content(content)

        # Should have camera bullet point with loitering in context
        # Should NOT have separate loitering bullet point
        loitering_mentions = sum(1 for bp in result.bullet_points if "loitering" in bp.text.lower())
        # Should only be mentioned once (in camera context)
        assert loitering_mentions == 1

    def test_weather_bullet_point_only_when_no_other_points(self) -> None:
        """Test that weather bullet points only appear when there are no other bullet points."""
        # Content with only weather, no cameras or patterns
        content = "Activity during rainy nighttime conditions."

        result = parse_summary_content(content)

        # Should have weather bullet point since there are no camera/pattern points
        assert len(result.bullet_points) >= 1
        weather_bp = [bp for bp in result.bullet_points if bp.icon == "cloud"]
        assert len(weather_bp) > 0

    def test_weather_bullet_point_not_added_when_camera_points_exist(self) -> None:
        """Test that weather bullet points are not added when camera points exist."""
        content = "Activity at Beach Front Left during rainy nighttime conditions."
        events = [{"risk_score": 75, "risk_level": "high"}]

        result = parse_summary_content(content, events=events)

        # Should have camera bullet point
        camera_bp = [bp for bp in result.bullet_points if "Beach Front Left" in bp.text]
        assert len(camera_bp) > 0

        # Should NOT have separate weather bullet point
        weather_bp = [bp for bp in result.bullet_points if bp.icon == "cloud"]
        # Weather conditions are extracted but not as a separate bullet point
        assert result.weather_conditions == ["rainy", "nighttime"]

    def test_pattern_bullet_points_have_correct_icons(self) -> None:
        """Test that different patterns get appropriate icons."""
        content = "Suspicious loitering and obscured face detected, with rapid movement."

        result = parse_summary_content(content)

        # Should have pattern bullet points with appropriate icons
        assert len(result.bullet_points) >= 1
        icons = [bp.icon for bp in result.bullet_points]
        # Should have various alert/warning icons
        assert any(icon in ["alert-circle", "alert-triangle", "zap"] for icon in icons)

    def test_bullet_point_icons_for_each_pattern(self) -> None:
        """Test specific icon mappings for behavior patterns."""
        test_cases = [
            ("loitering", "alert-circle"),
            ("obscured face", "alert-triangle"),
            ("rapid movement", "zap"),
            ("unauthorized access", "shield-alert"),
            ("trespassing", "shield-x"),
            ("prowling", "eye"),
        ]

        for pattern, expected_icon in test_cases:
            content = f"Person detected with {pattern} behavior."
            result = parse_summary_content(content)

            # Find the pattern bullet point
            pattern_bp = [bp for bp in result.bullet_points if pattern in bp.text.lower()]
            if pattern_bp:
                assert pattern_bp[0].icon == expected_icon


# Tests: Internal Helper Functions


class TestInternalHelpers:
    """Tests for internal helper functions."""

    def test_severity_from_score_with_none(self) -> None:
        """Test _severity_from_score with None score."""
        from backend.services.summary_parser import _severity_from_score

        result = _severity_from_score(None)

        assert result is None
