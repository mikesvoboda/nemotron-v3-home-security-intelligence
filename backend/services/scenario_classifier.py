"""Scenario classification and risk score adjustment module.

This module provides consistent risk scoring for specific security scenarios
that should have minimum floor scores, regardless of other contextual factors.

The module addresses:
- Threshold boundary oscillation via hysteresis buffers
- Inconsistent graffiti/property crime scoring via scenario floor scores
- Tailgating detection escalation

See NEM-4522 for implementation details.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from backend.core.logging import get_logger

logger = get_logger(__name__)


class ScenarioType(str, Enum):
    """Enumeration of classifiable security scenarios.

    Each scenario type has an associated minimum risk score floor
    to ensure consistent scoring across the AI pipeline.
    """

    # Property crimes - minimum HIGH risk (65+)
    GRAFFITI = "graffiti"
    VANDALISM = "vandalism"
    PROPERTY_DAMAGE = "property_damage"

    # Access control violations - minimum MEDIUM-HIGH risk (55+)
    TAILGATING = "tailgating"
    PIGGYBACKING = "piggybacking"
    UNAUTHORIZED_ACCESS = "unauthorized_access"

    # Vehicle crimes - minimum HIGH risk (60+)
    VEHICLE_TAMPERING = "vehicle_tampering"
    CAR_BREAK_IN = "car_break_in"

    # Trespassing - minimum MEDIUM risk (45+)
    TRESPASSING = "trespassing"
    FENCE_CLIMBING = "fence_climbing"

    # Suspicious reconnaissance - minimum MEDIUM risk (40+)
    CASING = "casing"
    PHOTOGRAPHING_PROPERTY = "photographing_property"

    # Package theft - minimum HIGH risk (70+)
    PACKAGE_THEFT = "package_theft"

    # Critical threats - minimum CRITICAL risk (85+)
    WEAPON_VISIBLE = "weapon_visible"
    BREAK_IN_ATTEMPT = "break_in_attempt"

    # Not classified as a specific scenario
    UNCLASSIFIED = "unclassified"


@dataclass(frozen=True, slots=True)
class ScenarioFloorScore:
    """Configuration for scenario-specific minimum risk scores.

    Attributes:
        scenario_type: The scenario type this applies to
        floor_score: Minimum risk score (score will never be below this)
        keywords: Detection keywords that trigger this scenario
        action_patterns: Action recognition patterns that indicate this scenario
        description: Human-readable description for logging
    """

    scenario_type: ScenarioType
    floor_score: int
    keywords: frozenset[str]
    action_patterns: frozenset[str]
    description: str


# =============================================================================
# Scenario Floor Score Configuration
# =============================================================================
# These define minimum risk scores for specific scenarios to ensure consistent
# classification. The floor score ensures that even if the LLM underscores,
# the final risk level is appropriate for the scenario severity.

SCENARIO_FLOOR_SCORES: dict[ScenarioType, ScenarioFloorScore] = {
    # Property Crimes - minimum HIGH risk
    ScenarioType.GRAFFITI: ScenarioFloorScore(
        scenario_type=ScenarioType.GRAFFITI,
        floor_score=65,  # Ensures HIGH classification
        keywords=frozenset(
            {
                "graffiti",
                "spray paint",
                "spray can",
                "tagging",
                "paint",
                "marking",
                "defacing",
            }
        ),
        action_patterns=frozenset(
            {
                "spraying",
                "painting",
                "tagging",
                "vandalizing property",
                "a person vandalizing",
            }
        ),
        description="Graffiti or property defacement detected",
    ),
    ScenarioType.VANDALISM: ScenarioFloorScore(
        scenario_type=ScenarioType.VANDALISM,
        floor_score=65,  # Ensures HIGH classification
        keywords=frozenset(
            {
                "vandal",
                "vandalism",
                "smash",
                "smashing",
                "breaking",
                "destroying",
                "damage",
                "damaging",
            }
        ),
        action_patterns=frozenset(
            {
                "vandalism",
                "smashing",
                "breaking",
                "destroying",
                "a person vandalizing",
            }
        ),
        description="Vandalism or property destruction detected",
    ),
    ScenarioType.PROPERTY_DAMAGE: ScenarioFloorScore(
        scenario_type=ScenarioType.PROPERTY_DAMAGE,
        floor_score=60,  # Ensures HIGH classification
        keywords=frozenset(
            {
                "broken window",
                "shattered glass",
                "damage",
                "damaged",
                "destruction",
            }
        ),
        action_patterns=frozenset(
            {
                "breaking window",
                "smashing",
            }
        ),
        description="Property damage indicators detected",
    ),
    # Access Control Violations - minimum MEDIUM-HIGH risk
    ScenarioType.TAILGATING: ScenarioFloorScore(
        scenario_type=ScenarioType.TAILGATING,
        floor_score=55,  # Ensures elevated MEDIUM classification
        keywords=frozenset(
            {
                "tailgat",  # Matches tailgate, tailgating
                "following closely",
                "unauthorized entry",
                "door held open",
                "held door",
                "sneaking in",
                "slipping in",
            }
        ),
        action_patterns=frozenset(
            {
                "tailgating",
                "following",
                "sneaking",
                "slipping through",
            }
        ),
        description="Tailgating or unauthorized entry attempt detected",
    ),
    ScenarioType.PIGGYBACKING: ScenarioFloorScore(
        scenario_type=ScenarioType.PIGGYBACKING,
        floor_score=55,  # Ensures elevated MEDIUM classification
        keywords=frozenset(
            {
                "piggyback",
                "following behind",
                "entering with",
                "entering behind",
            }
        ),
        action_patterns=frozenset(
            {
                "piggybacking",
                "following behind",
            }
        ),
        description="Piggybacking entry attempt detected",
    ),
    ScenarioType.UNAUTHORIZED_ACCESS: ScenarioFloorScore(
        scenario_type=ScenarioType.UNAUTHORIZED_ACCESS,
        floor_score=60,  # Ensures HIGH classification
        keywords=frozenset(
            {
                "unauthorized",
                "restricted area",
                "no access",
                "trespassing",
                "breaking in",
            }
        ),
        action_patterns=frozenset(
            {
                "breaking in",
                "forcing entry",
                "picking lock",
            }
        ),
        description="Unauthorized access attempt detected",
    ),
    # Vehicle Crimes - minimum HIGH risk
    ScenarioType.VEHICLE_TAMPERING: ScenarioFloorScore(
        scenario_type=ScenarioType.VEHICLE_TAMPERING,
        floor_score=65,  # Ensures HIGH classification
        keywords=frozenset(
            {
                "checking car doors",
                "trying door handle",
                "car door",
                "vehicle door",
                "tampering",
            }
        ),
        action_patterns=frozenset(
            {
                "checking_car_doors",
                "trying a door handle",
                "checking car doors",
                "a person trying a door handle",
            }
        ),
        description="Vehicle tampering activity detected",
    ),
    ScenarioType.CAR_BREAK_IN: ScenarioFloorScore(
        scenario_type=ScenarioType.CAR_BREAK_IN,
        floor_score=75,  # Ensures HIGH classification
        keywords=frozenset(
            {
                "car break",
                "vehicle break",
                "smash and grab",
                "window smash",
            }
        ),
        action_patterns=frozenset(
            {
                "breaking in",
                "smashing window",
            }
        ),
        description="Vehicle break-in detected",
    ),
    # Trespassing - minimum MEDIUM risk
    ScenarioType.TRESPASSING: ScenarioFloorScore(
        scenario_type=ScenarioType.TRESPASSING,
        floor_score=45,  # Ensures MEDIUM classification
        keywords=frozenset(
            {
                "trespass",
                "unauthorized",
                "no entry",
                "private property",
            }
        ),
        action_patterns=frozenset(
            {
                "trespassing",
                "entering unauthorized",
            }
        ),
        description="Trespassing detected",
    ),
    ScenarioType.FENCE_CLIMBING: ScenarioFloorScore(
        scenario_type=ScenarioType.FENCE_CLIMBING,
        floor_score=55,  # Ensures elevated MEDIUM classification
        keywords=frozenset(
            {
                "climbing fence",
                "over fence",
                "fence climb",
                "scaling",
                "jumping fence",
            }
        ),
        action_patterns=frozenset(
            {
                "climbing",
                "climbing over fence",
                "scaling",
                "jumping over",
            }
        ),
        description="Fence climbing or scaling detected",
    ),
    # Suspicious Reconnaissance - minimum MEDIUM risk
    ScenarioType.CASING: ScenarioFloorScore(
        scenario_type=ScenarioType.CASING,
        floor_score=40,  # Ensures MEDIUM classification
        keywords=frozenset(
            {
                "casing",
                "surveying",
                "watching",
                "observing",
                "reconnaissance",
            }
        ),
        action_patterns=frozenset(
            {
                "looking around suspiciously",
                "a person looking around suspiciously",
                "casing",
                "surveying",
            }
        ),
        description="Possible reconnaissance activity detected",
    ),
    ScenarioType.PHOTOGRAPHING_PROPERTY: ScenarioFloorScore(
        scenario_type=ScenarioType.PHOTOGRAPHING_PROPERTY,
        floor_score=35,  # Ensures elevated LOW-MEDIUM classification
        keywords=frozenset(
            {
                "photographing",
                "taking photos",
                "taking pictures",
                "camera",
                "recording",
            }
        ),
        action_patterns=frozenset(
            {
                "photographing",
                "taking photos",
                "recording",
            }
        ),
        description="Photographing property detected",
    ),
    # Package theft - minimum HIGH risk (70+)
    ScenarioType.PACKAGE_THEFT: ScenarioFloorScore(
        scenario_type=ScenarioType.PACKAGE_THEFT,
        floor_score=70,  # Ensures HIGH classification - theft in progress
        keywords=frozenset(
            {
                "package theft",
                "stealing package",
                "taking package",
                "porch pirate",
                "delivery theft",
                "stolen package",
                "grabbing package",
                "package taken",
            }
        ),
        action_patterns=frozenset(
            {
                "stealing",
                "taking package",
                "grabbing delivery",
                "porch piracy",
            }
        ),
        description="Package theft detected",
    ),
    # Critical threats - minimum CRITICAL risk
    ScenarioType.WEAPON_VISIBLE: ScenarioFloorScore(
        scenario_type=ScenarioType.WEAPON_VISIBLE,
        floor_score=95,  # Ensures CRITICAL classification - immediate threat
        keywords=frozenset(
            {
                "weapon",
                "gun",
                "knife",
                "firearm",
                "armed",
                "pistol",
                "rifle",
                "machete",
                "blade",
            }
        ),
        action_patterns=frozenset(
            {
                "wielding weapon",
                "holding gun",
                "armed person",
                "brandishing",
            }
        ),
        description="Visible weapon detected - CRITICAL",
    ),
    ScenarioType.BREAK_IN_ATTEMPT: ScenarioFloorScore(
        scenario_type=ScenarioType.BREAK_IN_ATTEMPT,
        floor_score=85,  # Ensures CRITICAL classification - active threat
        keywords=frozenset(
            {
                "break-in",
                "break in",
                "breaking in",
                "forced entry",
                "forcing entry",
                "breaking window",
                "smashing window",
                "picking lock",
                "prying door",
                "kicking door",
                "home invasion",
            }
        ),
        action_patterns=frozenset(
            {
                "breaking_in",
                "forcing entry",
                "breaking window",
                "kicking door",
                "prying open",
            }
        ),
        description="Break-in attempt detected - CRITICAL",
    ),
}


# =============================================================================
# Hysteresis Configuration for Threshold Boundaries
# =============================================================================
# Hysteresis prevents oscillation at severity boundaries by requiring a score
# to move beyond a buffer zone before changing classification.


@dataclass(frozen=True, slots=True)
class HysteresisConfig:
    """Configuration for hysteresis at severity boundaries.

    Attributes:
        low_medium_boundary: The boundary between LOW and MEDIUM (default: 29)
        medium_high_boundary: The boundary between MEDIUM and HIGH (default: 59)
        high_critical_boundary: The boundary between HIGH and CRITICAL (default: 84)
        buffer_size: Points above/below boundary that maintain previous level
    """

    low_medium_boundary: int = 29
    medium_high_boundary: int = 59
    high_critical_boundary: int = 84
    buffer_size: int = 3  # 3-point buffer on each side


# Default hysteresis configuration
DEFAULT_HYSTERESIS = HysteresisConfig()


def apply_hysteresis(
    new_score: int,
    previous_score: int | None,
    config: HysteresisConfig = DEFAULT_HYSTERESIS,
) -> int:
    """Apply hysteresis to prevent oscillation at threshold boundaries.

    When a new score is within the buffer zone of a threshold, and the previous
    score was on the opposite side, the new score is adjusted to stay on the
    previous side of the threshold. This prevents rapid flip-flopping between
    severity levels.

    Args:
        new_score: The newly calculated risk score (0-100)
        previous_score: The previous risk score for this entity (None if first score)
        config: Hysteresis configuration with boundaries and buffer size

    Returns:
        Adjusted risk score that may be shifted to prevent oscillation

    Example:
        # If previous score was 27 (LOW) and new score is 31 (MEDIUM),
        # but 31 is within the buffer zone (27-32), keep it LOW (29)
        >>> apply_hysteresis(31, 27)
        29
    """
    if previous_score is None:
        return new_score

    boundaries = [
        config.low_medium_boundary,
        config.medium_high_boundary,
        config.high_critical_boundary,
    ]

    for boundary in boundaries:
        buffer_low = boundary - config.buffer_size
        buffer_high = boundary + config.buffer_size + 1

        # Check if new score is in the buffer zone around this boundary
        if buffer_low < new_score <= buffer_high:
            # If previous score was below the boundary, keep new score below
            if previous_score <= boundary and new_score > boundary:
                adjusted = boundary
                logger.debug(
                    f"Hysteresis applied: {new_score} -> {adjusted} "
                    f"(staying below {boundary} boundary, previous={previous_score})"
                )
                return adjusted
            # If previous score was above the boundary, keep new score above
            elif previous_score > boundary and new_score <= boundary:
                adjusted = boundary + 1
                logger.debug(
                    f"Hysteresis applied: {new_score} -> {adjusted} "
                    f"(staying above {boundary} boundary, previous={previous_score})"
                )
                return adjusted

    return new_score


# =============================================================================
# Scenario Classification
# =============================================================================


def _has_person_detected(
    detections: list[dict[str, Any]] | None,
    combined_text: str,
) -> bool:
    """Check if a person is detected in the scene.

    This helper determines if there's evidence of a person (perpetrator) present,
    which is critical for distinguishing active crimes from historical evidence.

    Args:
        detections: List of detection dictionaries
        combined_text: Combined lowercase text from summary/reasoning

    Returns:
        True if a person is detected or mentioned, False otherwise
    """
    # Check detections for person object type
    if detections:
        for detection in detections:
            obj_type = str(detection.get("object_type", "")).lower()
            label = str(detection.get("label", "")).lower()
            if "person" in obj_type or "person" in label:
                return True
            # Also check for human-related labels
            if any(h in obj_type or h in label for h in ("human", "man", "woman", "individual")):
                return True

    # Negative person indicators - phrases that explicitly say NO person is present
    # These override positive person mentions in the same text
    no_person_indicators = (
        "no person",
        "no one",
        "no individuals",
        "no people",
        "empty scene",
        "no suspect",
        "no perpetrator",
        "nobody",
        "no humans",
    )
    if any(neg in combined_text for neg in no_person_indicators):
        return False

    # Check text for person-related keywords indicating active perpetrator
    person_indicators = (
        "person",
        "individual",
        "suspect",
        "perpetrator",
        "man",
        "woman",
        "someone",
        "intruder",
        "vandal",
    )
    return any(indicator in combined_text for indicator in person_indicators)


def _is_historical_graffiti(combined_text: str) -> bool:
    """Check if graffiti is explicitly historical (pre-existing) rather than active.

    Pre-existing graffiti without a perpetrator should score LOW (0-20),
    while active graffiti with perpetrator should score HIGH (65-85).

    This returns True ONLY if there are explicit historical indicators.
    If no explicit indicators are found, we default to treating graffiti
    as potentially active (since seeing graffiti usually means recent vandalism).

    Args:
        combined_text: Combined lowercase text from summary/reasoning

    Returns:
        True if graffiti is explicitly marked as historical/pre-existing
    """
    # Keywords indicating historical/pre-existing graffiti
    historical_indicators = (
        "pre-existing",
        "preexisting",
        "existing graffiti",
        "old graffiti",
        "previous graffiti",
        "historical graffiti",
        "already there",
        "was already",
        "no person detected",
        "no one detected",
        "empty scene",
        "no perpetrator",
        "no suspect",
        "no individuals",
    )
    return any(indicator in combined_text for indicator in historical_indicators)


def classify_scenario(
    detections: list[dict[str, Any]] | None = None,
    action_result: dict[str, Any] | None = None,
    summary: str | None = None,
    reasoning: str | None = None,
) -> list[ScenarioType]:
    """Classify the scenario based on detection data and AI analysis.

    Examines detection labels, action recognition results, and LLM output
    to identify specific security scenarios that require floor scores.

    Special handling for temporal context:
    - Graffiti with perpetrator present = HIGH risk (65-85)
    - Pre-existing graffiti without person = LOW risk (0-20, no floor applied)

    Args:
        detections: List of detection dictionaries with object_type, labels, etc.
        action_result: Action recognition result with detected_action key
        summary: LLM-generated summary text to scan for scenario keywords
        reasoning: LLM-generated reasoning text to scan for scenario keywords

    Returns:
        List of identified ScenarioTypes (may be multiple or empty)
    """
    identified_scenarios: set[ScenarioType] = set()

    # Combine all text sources for keyword search
    text_sources: list[str] = []
    if summary:
        text_sources.append(summary.lower())
    if reasoning:
        text_sources.append(reasoning.lower())

    # Add detection labels and object types
    if detections:
        for detection in detections:
            if obj_type := detection.get("object_type"):
                text_sources.append(str(obj_type).lower())
            if label := detection.get("label"):
                text_sources.append(str(label).lower())
            if description := detection.get("description"):
                text_sources.append(str(description).lower())

    combined_text = " ".join(text_sources)

    # Pre-compute person presence for scenarios that require it
    has_person = _has_person_detected(detections, combined_text)
    is_historical = _is_historical_graffiti(combined_text)

    # Check each scenario's keywords against the combined text
    for scenario_type, floor_config in SCENARIO_FLOOR_SCORES.items():
        matched = False

        # Check keywords
        for keyword in floor_config.keywords:
            if keyword in combined_text:
                matched = True
                logger.debug(f"Scenario {scenario_type.value} matched keyword: {keyword}")
                break

        # Check action patterns
        if not matched and action_result:
            detected_action = action_result.get("detected_action", "").lower()
            for pattern in floor_config.action_patterns:
                if pattern.lower() in detected_action or detected_action in pattern.lower():
                    matched = True
                    logger.debug(
                        f"Scenario {scenario_type.value} matched action: {detected_action}"
                    )
                    break

        if matched:
            # Special handling for graffiti: check for historical context
            # NEM-4543: Active vandalism with perpetrator = HIGH (65-85)
            #           Pre-existing graffiti with explicit "no person" = LOW (0-20)
            #
            # Default behavior: If graffiti is mentioned without explicit
            # historical markers, treat it as active vandalism (apply floor score).
            # Only skip the floor score if explicitly marked as historical AND
            # no person is detected.
            if scenario_type == ScenarioType.GRAFFITI:
                if is_historical and not has_person:
                    # Explicitly historical graffiti with no person = skip floor
                    logger.debug(
                        f"Scenario {scenario_type.value} NOT classified: "
                        f"explicitly historical graffiti with no person detected"
                    )
                else:
                    # Either:
                    # 1. Person is detected (active vandalism)
                    # 2. No explicit historical markers (assume recent/active)
                    identified_scenarios.add(scenario_type)
                    logger.debug(
                        f"Scenario {scenario_type.value} classified: "
                        f"active vandalism (has_person={has_person}, "
                        f"is_historical={is_historical})"
                    )
            else:
                identified_scenarios.add(scenario_type)

    if identified_scenarios:
        logger.info(
            f"Classified scenarios: {[s.value for s in identified_scenarios]}",
            extra={"scenario_count": len(identified_scenarios)},
        )

    return list(identified_scenarios)


def get_scenario_floor_score(scenarios: list[ScenarioType]) -> int:
    """Get the maximum floor score from a list of identified scenarios.

    When multiple scenarios are identified, returns the highest floor score
    to ensure the most serious scenario dictates the minimum risk level.

    Args:
        scenarios: List of identified ScenarioTypes

    Returns:
        Maximum floor score from all identified scenarios, or 0 if none
    """
    if not scenarios:
        return 0

    floor_scores = [
        SCENARIO_FLOOR_SCORES[s].floor_score for s in scenarios if s in SCENARIO_FLOOR_SCORES
    ]

    return max(floor_scores) if floor_scores else 0


def apply_scenario_floor(
    risk_score: int,
    scenarios: list[ScenarioType],
) -> tuple[int, bool]:
    """Apply scenario floor score to ensure minimum risk classification.

    If the identified scenarios have a floor score higher than the calculated
    risk score, the floor score is applied to ensure appropriate classification.

    Args:
        risk_score: The calculated risk score (0-100)
        scenarios: List of identified ScenarioTypes

    Returns:
        Tuple of (adjusted_score, was_adjusted)
    """
    floor_score = get_scenario_floor_score(scenarios)

    if floor_score > risk_score:
        logger.info(
            f"Scenario floor applied: {risk_score} -> {floor_score}",
            extra={
                "original_score": risk_score,
                "floor_score": floor_score,
                "scenarios": [s.value for s in scenarios],
            },
        )
        return floor_score, True

    return risk_score, False


# =============================================================================
# Tailgating-Specific Detection
# =============================================================================
# Tailgating requires special detection logic as it involves temporal patterns
# (one person following another through a door/gate)


@dataclass
class TailgatingIndicator:
    """Indicators for tailgating detection.

    Attributes:
        detected: Whether tailgating was detected
        confidence: Confidence level (0.0-1.0)
        description: Human-readable description
        persons_involved: Number of persons involved in the tailgating
        time_gap_seconds: Time gap between persons entering
    """

    detected: bool = False
    confidence: float = 0.0
    description: str = ""
    persons_involved: int = 0
    time_gap_seconds: float | None = None


def detect_tailgating(
    detections: list[dict[str, Any]],
    zone_type: str | None = None,
) -> TailgatingIndicator:
    """Detect potential tailgating based on detection patterns.

    Analyzes person detections near entry points for patterns that suggest
    tailgating (multiple persons entering in quick succession, one following
    closely behind another).

    Args:
        detections: List of detection dictionaries with timestamps and positions
        zone_type: The type of zone (entry_point, gate, door, etc.)

    Returns:
        TailgatingIndicator with detection results
    """
    # Filter to person detections only
    person_detections = [d for d in detections if (d.get("object_type") or "").lower() == "person"]

    if len(person_detections) < 2:
        return TailgatingIndicator()

    # Check if this is an entry point zone (higher tailgating risk)
    is_entry_zone = zone_type in ("entry_point", "door", "gate", "entrance")

    # Analyze temporal proximity of person detections
    # Sort by timestamp
    sorted_detections = sorted(
        person_detections,
        key=lambda d: d.get("detected_at", d.get("timestamp", 0)),
    )

    # Check for rapid succession entries (within 5 seconds)
    TAILGATING_WINDOW_SECONDS = 5.0
    consecutive_entries = 0
    min_time_gap = float("inf")

    for i in range(1, len(sorted_detections)):
        prev_time = sorted_detections[i - 1].get("detected_at", 0)
        curr_time = sorted_detections[i].get("detected_at", 0)

        # Handle both timestamp formats
        if hasattr(prev_time, "timestamp"):
            prev_time = prev_time.timestamp()
        if hasattr(curr_time, "timestamp"):
            curr_time = curr_time.timestamp()

        time_gap = abs(float(curr_time) - float(prev_time))

        if time_gap <= TAILGATING_WINDOW_SECONDS:
            consecutive_entries += 1
            min_time_gap = min(min_time_gap, time_gap)

    if consecutive_entries > 0:
        # Calculate confidence based on number of entries and time gap
        # Closer time gaps and more people = higher confidence
        base_confidence = min(0.5 + (consecutive_entries * 0.15), 0.9)

        # Boost confidence for entry point zones
        if is_entry_zone:
            base_confidence = min(base_confidence + 0.2, 0.95)

        # Reduce confidence for larger time gaps
        if min_time_gap > 3.0:
            base_confidence *= 0.8
        elif min_time_gap > 2.0:
            base_confidence *= 0.9

        return TailgatingIndicator(
            detected=True,
            confidence=base_confidence,
            description=f"{consecutive_entries + 1} persons detected entering in quick succession",
            persons_involved=consecutive_entries + 1,
            time_gap_seconds=min_time_gap if min_time_gap != float("inf") else None,
        )

    return TailgatingIndicator()


# =============================================================================
# Risk Score Adjustment Pipeline
# =============================================================================


def adjust_risk_score(
    raw_score: int,
    detections: list[dict[str, Any]] | None = None,
    action_result: dict[str, Any] | None = None,
    summary: str | None = None,
    reasoning: str | None = None,
    previous_score: int | None = None,
    zone_type: str | None = None,
    apply_hysteresis_adjustment: bool = True,
) -> tuple[int, dict[str, Any]]:
    """Apply all risk score adjustments including scenarios and hysteresis.

    This is the main entry point for risk score adjustment. It applies:
    1. Scenario classification and floor scores
    2. Tailgating detection and escalation
    3. Hysteresis to prevent threshold oscillation

    Args:
        raw_score: The raw risk score from LLM analysis (0-100)
        detections: List of detection dictionaries
        action_result: Action recognition result
        summary: LLM-generated summary
        reasoning: LLM-generated reasoning
        previous_score: Previous risk score for hysteresis (optional)
        zone_type: Zone type for tailgating detection
        apply_hysteresis_adjustment: Whether to apply hysteresis (default True)

    Returns:
        Tuple of (adjusted_score, adjustment_metadata)

        adjustment_metadata contains:
            - scenarios: List of identified scenario types
            - floor_applied: Whether a floor score was applied
            - floor_score: The floor score that was applied (if any)
            - tailgating: TailgatingIndicator results
            - hysteresis_applied: Whether hysteresis adjusted the score
            - original_score: The raw score before adjustments
    """
    metadata: dict[str, Any] = {
        "original_score": raw_score,
        "scenarios": [],
        "floor_applied": False,
        "floor_score": 0,
        "tailgating": None,
        "hysteresis_applied": False,
    }

    adjusted_score = raw_score

    # Step 1: Classify scenarios
    scenarios = classify_scenario(
        detections=detections,
        action_result=action_result,
        summary=summary,
        reasoning=reasoning,
    )
    metadata["scenarios"] = [s.value for s in scenarios]

    # Step 2: Apply scenario floor scores
    adjusted_score, floor_applied = apply_scenario_floor(adjusted_score, scenarios)
    metadata["floor_applied"] = floor_applied
    if floor_applied:
        metadata["floor_score"] = get_scenario_floor_score(scenarios)

    # Step 3: Detect and escalate tailgating
    if detections:
        tailgating = detect_tailgating(detections, zone_type)
        if tailgating.detected:
            metadata["tailgating"] = {
                "detected": tailgating.detected,
                "confidence": tailgating.confidence,
                "description": tailgating.description,
                "persons_involved": tailgating.persons_involved,
                "time_gap_seconds": tailgating.time_gap_seconds,
            }

            # Ensure tailgating triggers at least the tailgating floor score
            tailgating_floor = SCENARIO_FLOOR_SCORES[ScenarioType.TAILGATING].floor_score

            # Scale floor by confidence
            effective_floor = int(tailgating_floor * tailgating.confidence)

            if effective_floor > adjusted_score:
                logger.info(
                    f"Tailgating escalation: {adjusted_score} -> {effective_floor}",
                    extra={
                        "tailgating_confidence": tailgating.confidence,
                        "persons_involved": tailgating.persons_involved,
                    },
                )
                adjusted_score = effective_floor
                metadata["floor_applied"] = True

    # Step 4: Apply hysteresis to prevent threshold oscillation
    if apply_hysteresis_adjustment and previous_score is not None:
        pre_hysteresis = adjusted_score
        adjusted_score = apply_hysteresis(adjusted_score, previous_score)
        if adjusted_score != pre_hysteresis:
            metadata["hysteresis_applied"] = True
            logger.debug(
                f"Hysteresis adjustment: {pre_hysteresis} -> {adjusted_score} "
                f"(previous={previous_score})"
            )

    # Ensure score is in valid range
    adjusted_score = max(0, min(100, adjusted_score))

    return adjusted_score, metadata


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "DEFAULT_HYSTERESIS",
    "SCENARIO_FLOOR_SCORES",
    "HysteresisConfig",
    "ScenarioFloorScore",
    "ScenarioType",
    "TailgatingIndicator",
    "adjust_risk_score",
    "apply_hysteresis",
    "apply_scenario_floor",
    "classify_scenario",
    "detect_tailgating",
    "get_scenario_floor_score",
]
