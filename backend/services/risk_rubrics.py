"""Rubric-based risk scoring for consistent LLM risk calibration.

This module provides explicit rubrics for the LLM-as-a-Judge pattern,
ensuring consistent and reproducible risk assessments. The rubrics define
clear scoring criteria for threat level, intent, and time context.

The scoring formula combines these dimensions:
    risk_score = (threat_level * 25) + (intent * 15) + (time_context * 10)

With maximum values (4, 3, 2), the theoretical max is 165, capped at 100.

See NEM-3728 for implementation details.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class Rubric:
    """A scoring rubric with named levels and descriptions.

    Attributes:
        name: Human-readable name for the rubric dimension
        description: Explanation of what this rubric measures
        scoring: Dict mapping level numbers (as strings) to descriptions
    """

    name: str
    description: str
    scoring: dict[str, str]


# =============================================================================
# Predefined Rubrics
# =============================================================================

THREAT_LEVEL_RUBRIC = Rubric(
    name="Threat Level",
    description="Assessment of immediate physical threat to property or persons",
    scoring={
        "0": "No threat - Normal expected activity (resident, family, service worker)",
        "1": "Minimal threat - Unusual but explainable (unknown person on public sidewalk)",
        "2": "Moderate threat - Warrants attention (lingering, repeated passes)",
        "3": "High threat - Clear suspicious intent (testing doors, peering in windows)",
        "4": "Critical threat - Active danger (break-in, weapon visible, violence)",
    },
)

INTENT_RUBRIC = Rubric(
    name="Apparent Intent",
    description="Assessment of individual's apparent purpose at property",
    scoring={
        "0": "Benign intent - Clear legitimate purpose (delivery, visiting, work)",
        "1": "Unclear intent - Cannot determine purpose",
        "2": "Questionable intent - Behavior suggests reconnaissance",
        "3": "Malicious intent - Actions indicate criminal purpose",
    },
)

TIME_CONTEXT_RUBRIC = Rubric(
    name="Time Context",
    description="Appropriateness of activity for the time of day",
    scoring={
        "0": "Normal timing - Activity expected at this hour",
        "1": "Unusual timing - Activity uncommon but not alarming",
        "2": "Suspicious timing - Activity rarely occurs at this hour",
    },
)


# =============================================================================
# Scoring Functions
# =============================================================================


def calculate_risk_score(threat_level: int, intent: int, time_context: int) -> int:
    """Calculate final risk score from rubric scores.

    The formula weights threat level most heavily, followed by intent,
    then time context:
        risk_score = (threat_level * 25) + (intent * 15) + (time_context * 10)

    The result is capped at 100 to maintain the 0-100 risk score range.

    Args:
        threat_level: Threat level score (0-4)
        intent: Apparent intent score (0-3)
        time_context: Time context score (0-2)

    Returns:
        Risk score clamped to 0-100 range.
    """
    raw_score = (threat_level * 25) + (intent * 15) + (time_context * 10)
    return min(100, max(0, raw_score))


# =============================================================================
# Pydantic Models
# =============================================================================


class RubricScores(BaseModel):
    """Rubric-based scores for LLM risk assessment output.

    This model validates that the LLM returns scores within the valid
    ranges for each rubric dimension.

    Attributes:
        threat_level: Physical threat score (0-4)
        apparent_intent: Intent assessment score (0-3)
        time_context: Time appropriateness score (0-2)
    """

    threat_level: int = Field(ge=0, le=4, description="Physical threat level (0-4)")
    apparent_intent: int = Field(ge=0, le=3, description="Apparent intent score (0-3)")
    time_context: int = Field(ge=0, le=2, description="Time context score (0-2)")


# =============================================================================
# Utility Functions
# =============================================================================


def format_rubric_for_prompt(rubric: Rubric) -> str:
    """Format a single rubric for inclusion in an LLM prompt.

    Args:
        rubric: The Rubric to format

    Returns:
        Formatted string suitable for prompt inclusion
    """
    lines = [f"### {rubric.name}", f"{rubric.description}", ""]
    for level, description in sorted(rubric.scoring.items(), key=lambda x: int(x[0])):
        lines.append(f"- **{level}**: {description}")
    return "\n".join(lines)


def get_all_rubrics() -> list[Rubric]:
    """Get all predefined rubrics.

    Returns:
        List of all rubric definitions
    """
    return [THREAT_LEVEL_RUBRIC, INTENT_RUBRIC, TIME_CONTEXT_RUBRIC]


def _format_all_rubrics_for_prompt() -> str:
    """Format all rubrics for LLM prompt inclusion.

    Returns:
        Formatted string with all rubrics
    """
    sections = []
    for rubric in get_all_rubrics():
        sections.append(format_rubric_for_prompt(rubric))
    return "\n\n".join(sections)


# =============================================================================
# Rubric-Enhanced Prompt
# =============================================================================

RUBRIC_ENHANCED_PROMPT = """<|im_start|>system
You are a home security analyst for a residential property.

CRITICAL PRINCIPLE: Most detections are NOT threats. Residents, family members,
delivery workers, and pets represent normal household activity. Your job is to
identify genuine anomalies, not flag everyday life.

CALIBRATION: In a typical day, expect:
- 80% of events to be LOW risk (0-29): Normal activity
- 15% to be MEDIUM risk (30-59): Worth noting but not alarming
- 4% to be HIGH risk (60-84): Genuinely suspicious, warrants review
- 1% to be CRITICAL (85-100): Immediate threats only

If you're scoring >20% of events as HIGH or CRITICAL, you are miscalibrated.

Output ONLY valid JSON. No preamble, no explanation.<|im_end|>
<|im_start|>user
## RUBRIC-BASED SCORING

You MUST score each detection using these explicit rubrics. Your final risk_score
is calculated from your rubric scores using this formula:

**Formula: (threat_level * 25) + (apparent_intent * 15) + (time_context * 10)**

Maximum possible score is 100 (scores above 100 are capped).

### Threat Level
Assessment of immediate physical threat to property or persons

- **0**: No threat - Normal expected activity (resident, family, service worker)
- **1**: Minimal threat - Unusual but explainable (unknown person on public sidewalk)
- **2**: Moderate threat - Warrants attention (lingering, repeated passes)
- **3**: High threat - Clear suspicious intent (testing doors, peering in windows)
- **4**: Critical threat - Active danger (break-in, weapon visible, violence)

### Apparent Intent
Assessment of individual's apparent purpose at property

- **0**: Benign intent - Clear legitimate purpose (delivery, visiting, work)
- **1**: Unclear intent - Cannot determine purpose
- **2**: Questionable intent - Behavior suggests reconnaissance
- **3**: Malicious intent - Actions indicate criminal purpose

### Time Context
Appropriateness of activity for the time of day

- **0**: Normal timing - Activity expected at this hour
- **1**: Unusual timing - Activity uncommon but not alarming
- **2**: Suspicious timing - Activity rarely occurs at this hour

## SCORING EXAMPLES

| Scenario | Threat | Intent | Time | Score | Level |
|----------|--------|--------|------|-------|-------|
| Resident arriving home | 0 | 0 | 0 | 0 | LOW |
| Delivery driver at door | 0 | 0 | 0 | 0 | LOW |
| Unknown person on sidewalk | 1 | 1 | 0 | 40 | MEDIUM |
| Unknown person lingering (night) | 2 | 2 | 2 | 90 | CRITICAL |
| Person testing door handles | 3 | 3 | 0 | 100 | CRITICAL |
| Active break-in | 4 | 3 | 2 | 100 | CRITICAL |

## EVENT CONTEXT
Camera: {camera_name}
Time: {start_time} to {end_time}

## DETECTIONS
{detections_list}

## YOUR TASK
1. Evaluate each rubric dimension independently
2. Assign scores based on the rubric definitions above
3. Calculate risk_score using the formula
4. Provide reasoning that references specific rubric levels

Risk levels: low (0-29), medium (30-59), high (60-84), critical (85-100)

Output JSON with rubric_scores:
{{"risk_score": N, "risk_level": "level", "summary": "1-2 sentence summary", "reasoning": "detailed explanation referencing rubric levels", "rubric_scores": {{"threat_level": N, "apparent_intent": N, "time_context": N}}}}<|im_end|>
<|im_start|>assistant
"""
