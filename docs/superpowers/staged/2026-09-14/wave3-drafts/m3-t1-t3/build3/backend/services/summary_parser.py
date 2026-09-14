"""Summary parser service for extracting structured data from LLM summaries.

This service parses LLM-generated narrative summaries and extracts structured
data including:
- Bullet points with icons and severity
- Focus areas (camera names mentioned)
- Dominant behavior patterns (loitering, obscured faces, etc.)
- Weather conditions (rainy, nighttime, etc.)
- Maximum risk score from events

The extracted data is used by the dashboard UI to display visual summaries
with icons and categorized information.

Example:
    content = "Activity at Beach Front Left with loitering behavior."
    events = [{"risk_score": 85, "risk_level": "high"}]
    structured = parse_summary_content(content, events=events)
    print(structured.focus_areas)  # ["Beach Front Left"]
    print(structured.dominant_patterns)  # ["loitering"]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "BEHAVIOR_PATTERNS",
    "KNOWN_CAMERAS",
    "WEATHER_CONDITIONS",
    "BulletPoint",
    "StructuredSummary",
    "parse_summary_content",
]

# Known camera names in the system
KNOWN_CAMERAS: list[str] = [
    "Beach Front Left",
    "Beach Front Right",
    "Dock Left",
    "Dock Right",
    "Kitchen",
    "Ami Frontyard Left",
    "Ami Frontyard Right",
]

# Behavior patterns to detect in summaries
BEHAVIOR_PATTERNS: list[str] = [
    "loitering",
    "obscured face",
    "rapid movement",
    "suspicious behavior",
    "unusual activity",
    "unauthorized access",
    "trespassing",
    "prowling",
]

# Weather/environmental conditions to detect
WEATHER_CONDITIONS: list[str] = [
    "rainy",
    "nighttime",
    "foggy",
    "stormy",
    "dark",
    "low visibility",
]

# Icon mapping for bullet points based on content type
ICON_MAPPING: dict[str, str] = {
    "camera": "camera",
    "person": "person",
    "vehicle": "car",
    "alert": "alert-triangle",
    "warning": "alert-circle",
    "info": "info",
    "weather": "cloud",
    "time": "clock",
}


@dataclass
class BulletPoint:
    """A single bullet point for display in the dashboard summary.

    Attributes:
        icon: Icon identifier for the bullet point (e.g., "warning", "camera")
        text: The text content of the bullet point
        severity: Optional severity level ("low", "medium", "high", "critical")
    """

    icon: str
    text: str
    severity: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with icon, text, and severity keys.
        """
        return {
            "icon": self.icon,
            "text": self.text,
            "severity": self.severity,
        }


@dataclass
class StructuredSummary:
    """Structured data extracted from an LLM-generated summary.

    Contains categorized information extracted from the narrative summary
    for display in the dashboard UI.

    Attributes:
        bullet_points: List of BulletPoint objects for visual display
        focus_areas: Camera names that were mentioned in the summary
        dominant_patterns: Behavior patterns detected (loitering, etc.)
        max_risk_score: Maximum risk score from the events (0-100)
        weather_conditions: Weather/environmental conditions mentioned
    """

    bullet_points: list[BulletPoint] = field(default_factory=list)
    focus_areas: list[str] = field(default_factory=list)
    dominant_patterns: list[str] = field(default_factory=list)
    max_risk_score: int | None = None
    weather_conditions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with all fields, bullet_points as list of dicts.
        """
        return {
            "bullet_points": [bp.to_dict() for bp in self.bullet_points],
            "focus_areas": self.focus_areas,
            "dominant_patterns": self.dominant_patterns,
            "max_risk_score": self.max_risk_score,
            "weather_conditions": self.weather_conditions,
        }


def parse_summary_content(
    content: str | None,
    events: list[dict[str, Any]] | None = None,
) -> StructuredSummary:
    """Parse LLM summary content and extract structured data.

    Analyzes the narrative summary text to extract:
    - Camera names mentioned (matched against known cameras)
    - Behavior patterns (loitering, obscured faces, etc.)
    - Weather conditions (rainy, nighttime, etc.)
    - Generates bullet points from extracted data

    Also extracts the maximum risk score from the provided events.

    Args:
        content: The LLM-generated narrative summary text
        events: Optional list of event dictionaries with risk_score and risk_level

    Returns:
        StructuredSummary with extracted data

    Example:
        content = "Person loitering at Beach Front Left during nighttime."
        events = [{"risk_score": 85, "risk_level": "high"}]
        result = parse_summary_content(content, events=events)
        # result.focus_areas = ["Beach Front Left"]
        # result.dominant_patterns = ["loitering"]
        # result.weather_conditions = ["nighttime"]
        # result.max_risk_score = 85
    """
    # Handle None or empty content
    if not content or not content.strip():
        return StructuredSummary()

    content_lower = content.lower()

    # Extract focus areas (camera names)
    focus_areas = _extract_camera_names(content_lower)

    # Extract behavior patterns
    dominant_patterns = _extract_patterns(content_lower)

    # Extract weather conditions
    weather_conditions = _extract_weather_conditions(content_lower)

    # Calculate max risk score from events
    max_risk_score = _calculate_max_risk_score(events)

    # Determine overall severity from events
    overall_severity = _determine_severity(events, max_risk_score)

    # Generate bullet points from extracted data
    bullet_points = _generate_bullet_points(
        content=content,
        focus_areas=focus_areas,
        dominant_patterns=dominant_patterns,
        weather_conditions=weather_conditions,
        severity=overall_severity,
    )

    return StructuredSummary(
        bullet_points=bullet_points,
        focus_areas=focus_areas,
        dominant_patterns=dominant_patterns,
        max_risk_score=max_risk_score,
        weather_conditions=weather_conditions,
    )


def _extract_camera_names(content_lower: str) -> list[str]:
    """Extract camera names from content.

    Args:
        content_lower: Lowercased content for matching

    Returns:
        List of unique camera names found, preserving original casing.
    """
    found_cameras: list[str] = []

    for camera in KNOWN_CAMERAS:
        # Case-insensitive search
        if camera.lower() in content_lower and camera not in found_cameras:
            found_cameras.append(camera)

    return found_cameras


def _extract_patterns(content_lower: str) -> list[str]:
    """Extract behavior patterns from content.

    Args:
        content_lower: Lowercased content for matching

    Returns:
        List of unique behavior patterns found.
    """
    found_patterns: list[str] = []

    for pattern in BEHAVIOR_PATTERNS:
        if pattern.lower() in content_lower and pattern not in found_patterns:
            found_patterns.append(pattern)

    return found_patterns


def _extract_weather_conditions(content_lower: str) -> list[str]:
    """Extract weather/environmental conditions from content.

    Args:
        content_lower: Lowercased content for matching

    Returns:
        List of unique weather conditions found.
    """
    found_conditions: list[str] = []

    for condition in WEATHER_CONDITIONS:
        if condition.lower() in content_lower and condition not in found_conditions:
            found_conditions.append(condition)

    return found_conditions


def _calculate_max_risk_score(events: list[dict[str, Any]] | None) -> int | None:
    """Calculate the maximum risk score from events.

    Args:
        events: List of event dictionaries with optional risk_score

    Returns:
        Maximum risk score found, or None if no valid scores.
    """
    if not events:
        return None

    valid_scores: list[int | float] = []
    for e in events:
        score = e.get("risk_score")
        if score is not None and isinstance(score, int | float):
            valid_scores.append(score)

    if not valid_scores:
        return None

    return int(max(valid_scores))


def _determine_severity(
    events: list[dict[str, Any]] | None,
    max_risk_score: int | None,
) -> str | None:
    """Determine overall severity from events and risk score.

    Args:
        events: List of event dictionaries
        max_risk_score: Maximum risk score

    Returns:
        Severity string ("low", "medium", "high", "critical") or None.
    """
    if not events:
        return None

    # Check for critical or high risk levels in events
    risk_levels = [e.get("risk_level", "").lower() for e in events if e.get("risk_level")]

    if "critical" in risk_levels:
        return "critical"
    if "high" in risk_levels:
        return "high"

    # Fall back to risk score
    return _severity_from_score(max_risk_score)


def _severity_from_score(score: int | None) -> str | None:
    """Determine severity level from a risk score.

    Args:
        score: Risk score (0-100) or None

    Returns:
        Severity string or None if no score provided.
    """
    if score is None:
        return None
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _generate_bullet_points(
    content: str,
    focus_areas: list[str],
    dominant_patterns: list[str],
    weather_conditions: list[str],
    severity: str | None,
) -> list[BulletPoint]:
    """Generate bullet points from extracted data.

    Creates informative bullet points for the dashboard UI based on
    the extracted cameras, patterns, and conditions.

    Args:
        content: Original content text
        focus_areas: Extracted camera names
        dominant_patterns: Extracted behavior patterns
        weather_conditions: Extracted weather conditions
        severity: Overall severity level

    Returns:
        List of BulletPoint objects for display.
    """
    bullet_points: list[BulletPoint] = []

    # Generate bullet point for each focus area (camera)
    for camera in focus_areas:
        # Find context around the camera mention
        camera_context = _extract_camera_context(content, camera)

        bullet_points.append(
            BulletPoint(
                icon="camera",
                text=f"Activity at {camera}" + (f": {camera_context}" if camera_context else ""),
                severity=severity,
            )
        )

    # Generate bullet points for significant patterns
    for pattern in dominant_patterns:
        # Only add if not already covered by camera bullet points
        already_mentioned = any(pattern.lower() in bp.text.lower() for bp in bullet_points)
        if not already_mentioned:
            icon = _get_pattern_icon(pattern)
            bullet_points.append(
                BulletPoint(
                    icon=icon,
                    text=f"{pattern.capitalize()} behavior detected",
                    severity=severity,
                )
            )

    # Add weather condition bullet point if notable
    if weather_conditions and not bullet_points:
        # Only add weather if there are no other bullet points
        conditions_text = ", ".join(weather_conditions)
        bullet_points.append(
            BulletPoint(
                icon="cloud",
                text=f"Activity during {conditions_text} conditions",
                severity=None,  # Weather is informational
            )
        )

    return bullet_points


def _extract_camera_context(content: str, camera: str) -> str:
    """Extract brief context around a camera mention.

    Tries to find relevant context text near the camera name mention.

    Args:
        content: Full content text
        camera: Camera name to find context for

    Returns:
        Brief context string, or empty string if none found.
    """
    # Find the camera mention and get surrounding text
    pattern = re.compile(
        rf"(?:at\s+)?{re.escape(camera)}[:\s]+([^.!?]+)",
        re.IGNORECASE,
    )

    match = pattern.search(content)
    if match:
        context = match.group(1).strip()
        # Limit length and clean up
        if len(context) > 50:
            context = context[:47] + "..."
        return context

    return ""


def _get_pattern_icon(pattern: str) -> str:
    """Get appropriate icon for a behavior pattern.

    Args:
        pattern: Behavior pattern name

    Returns:
        Icon identifier string.
    """
    pattern_icons = {
        "loitering": "alert-circle",
        "obscured face": "alert-triangle",
        "rapid movement": "zap",
        "suspicious behavior": "alert-triangle",
        "unusual activity": "alert-circle",
        "unauthorized access": "shield-alert",
        "trespassing": "shield-x",
        "prowling": "eye",
    }

    return pattern_icons.get(pattern.lower(), "alert-circle")
