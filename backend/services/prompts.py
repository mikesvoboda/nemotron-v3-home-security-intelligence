"""Prompt templates for AI analysis services.

This module contains prompt templates used by the Nemotron analyzer
to generate risk assessments from security camera detections.

Nemotron-3-Nano uses ChatML format with <|im_start|> and <|im_end|> tags.
The model outputs <think>...</think> reasoning blocks before the response.

Security:
    User-controlled data (object_type, detection descriptions) is sanitized
    before prompt interpolation to prevent prompt injection attacks.
    See NEM-1722 and backend/services/prompt_sanitizer.py for details.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

# =============================================================================
# Confidence Quality Tiers (NEM-5525)
# =============================================================================
# Local enum mirroring ai.yolo26.model.ConfidenceQuality to avoid importing
# from the ai module which requires special path setup (metrics module).
# Tier boundaries: EXCELLENT >= 0.90, GOOD >= 0.75, MODERATE >= 0.60, MARGINAL < 0.60


# Basic prompt template (legacy, used as fallback)
RISK_ANALYSIS_PROMPT = """<|im_start|>system
You are a home security analyst for a residential property.

CRITICAL PRINCIPLE: Most detections are NOT threats. Residents, family members,
delivery workers, and pets represent normal household activity. Your job is to
identify genuine anomalies, not flag everyday life.

SCORE CALIBRATION:
- 0-29 (LOW): Routine activity (deliveries, residents, pets, maintenance)
- 30-59 (MEDIUM): Unusual but likely benign, or mildly suspicious (unknown visitors, brief loitering)
- 60-84 (HIGH): Clear threat indicators (trespassing, aggressive behavior, tampering, property crimes)
- 85-100 (CRITICAL): Active threat (weapons, forced entry, violence, active theft/vandalism)

IMPORTANT: Default to LOWER scores without clear threat indicators.
EXCEPTION: Property crimes (theft, vandalism, breaking & entering) are ALWAYS scored 60+ as they are criminal acts.

Output ONLY valid JSON. No preamble, no explanation.<|im_end|>
<|im_start|>user
## SCORING REFERENCE
| Scenario | Score | Reasoning |
|----------|-------|-----------|
| Resident arriving home | 0-10 | Expected activity |
| Pet in yard | 0-5 | Normal household activity |
| Delivery driver at door | 0-15 | Routine service visit |
| Person walking past on sidewalk | 5-15 | Public area, transient |
| Unknown visitor at reasonable hour | 20-35 | Unusual but likely benign |
| Unknown person lingering 10+ min | 50-65 | Suspicious, requires attention |
| Person testing door handles | 70-85 | Clear suspicious intent |
| Graffiti/vandalism in progress | 65-85 | PROPERTY CRIME - active damage |
| Package theft from porch | 70-90 | PROPERTY CRIME - theft in progress |
| Breaking and entering | 80-95 | PROPERTY CRIME - home invasion |
| Active break-in or violence | 90-100 | Immediate threat |

## PROPERTY CRIME SCORING (ALWAYS 60+)
- Package/delivery theft = 70-90
- Vandalism (graffiti, property damage) = 65-85
- Breaking and entering = 80-95
- Vehicle break-in = 70-85

## EVIDENCE INTEGRITY RULES (MANDATORY)
- Use only evidence explicitly present in EVENT CONTEXT, DETECTIONS, and enrichment sections.
- Scoring examples are calibration only; never copy example-specific details into this event.
- If a section says "Not performed" or "Not available", do not claim that model produced findings.
- Do not claim objects, actions, or identities that are not present in detections/enrichment.
- In reasoning, clearly separate direct observations from inference.

## NOT RISK FACTORS - NEVER flag these as suspicious:
- Trees, bushes, plants, vegetation
- Camera timestamps or time display
- Weather conditions alone
- A person simply being present or walking
- Normal residential items (trash cans, bikes, hoses)
- Shadows or lighting artifacts
- Birds, squirrels, wildlife
- Parked vehicles (without unusual context)

## EVENT CONTEXT
Camera: {camera_name}
Time: {start_time} to {end_time}

## DETECTIONS
{detections_list}

## YOUR TASK
1. Start from the scoring reference above
2. Adjust based on ACTUAL threat indicators present
3. Do NOT flag trees, timestamps, or normal presence as risk factors
4. Provide clear reasoning for your score
5. Remember: most events should score LOW (0-29)
6. In `reasoning`, use this structure:
   Observed evidence: <facts seen in detections/enrichment only>
   Inference: <cautious interpretation, or "none">

Risk levels: low (0-29), medium (30-59), high (60-84), critical (85-100)

Output JSON:
{{"risk_score": N, "risk_level": "level", "summary": "1-2 sentence summary", "reasoning": "detailed multi-sentence explanation of factors considered and why this risk level was assigned"}}<|im_end|>
<|im_start|>assistant
"""
MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT = """<|im_start|>system
You are a home security analyst for a residential property with access to comprehensive AI-enriched detection data.

CRITICAL PRINCIPLE: Most detections are NOT threats. Residents, family members,
delivery workers, and pets represent normal household activity. Your job is to
identify genuine anomalies, not flag everyday life.

SCORE CALIBRATION:
- 0-29 (LOW): Routine activity (deliveries, residents, pets, maintenance)
- 30-59 (MEDIUM): Unusual but likely benign, or mildly suspicious (unknown visitors, brief loitering)
- 60-84 (HIGH): Clear threat indicators (trespassing, aggressive behavior, tampering, property crimes)
- 85-100 (CRITICAL): Active threat (weapons, forced entry, violence, active theft/vandalism)

EXPECTED DISTRIBUTION: In a typical day, expect approximately:
- ~85% LOW (0-29): Normal household activity
- ~10% MEDIUM (30-59): Worth noting but not alarming
- ~4% HIGH (60-84): Genuinely suspicious, warrants review
- ~1% CRITICAL (85-100): Immediate threats only

IMPORTANT: Default to LOWER scores without clear threat indicators.
EXCEPTION: Property crimes (theft, vandalism, breaking & entering) are ALWAYS scored 60+ as they are criminal acts.

Output ONLY valid JSON. No preamble, no explanation.<|im_end|>
<|im_start|>user
## SCORING REFERENCE
| Scenario | Score | Reasoning |
|----------|-------|-----------|
| Resident arriving home | 0-10 | Expected activity |
| Pet in yard | 0-5 | Normal household activity |
| Delivery driver at door | 0-15 | Routine service visit |
| Maintenance/utility worker | 0-15 | Normal service visit |
| Person walking past on sidewalk | 5-15 | Public area, transient |
| Unknown visitor at reasonable hour | 20-35 | Unusual but likely benign |
| Unknown person lingering 5-10 min | 35-50 | Worth monitoring |
| Unknown person lingering 10+ min | 50-65 | Suspicious, requires attention |
| Tailgating through secure door/gate | 55-75 | ACCESS VIOLATION - unauthorized entry |
| Person checking vehicle doors | 65-80 | Clear suspicious intent |
| Person testing door handles | 70-85 | Clear suspicious intent |
| Camera tampering (hand/object at lens) | 60-80 | Visual evidence of obstruction |
| Graffiti/vandalism in progress | 65-85 | PROPERTY CRIME - active damage |
| Package theft from porch | 70-90 | PROPERTY CRIME - theft in progress |
| Breaking and entering | 80-95 | PROPERTY CRIME - home invasion |
| Active break-in or violence | 90-100 | Immediate threat |

## PROPERTY CRIME SCORING (ALWAYS 60+)
Property crimes are criminal acts and must ALWAYS be scored as threats:
- Package/delivery theft = 70-90 (higher if fleeing or camera-aware)
- Vandalism (graffiti, property damage, keying vehicles) = 65-85
- Breaking and entering = 80-95 (CRITICAL if entry is successful)
- Vehicle break-in = 70-85
- Nighttime property crimes = Add +5-10 points

## ACCESS CONTROL VIOLATIONS (ALWAYS 45+)
Tailgating, piggybacking, and unauthorized entry attempts are security policy violations:
- Tailgating (following authorized person through door) = 55-75
- Multiple unknown persons entering in quick succession = 50-70
- Holding door for unknown individual at secure entry = 45-65
- Bypassing gate/fence via climbing = 55-75
- Forced entry through access-controlled door = 75-95 (CRITICAL)

## CAMERA TAMPERING (VISUAL EVIDENCE REQUIRED)
Only score HIGH if specific visual evidence of tampering is present:
- Hand/object approaching camera lens = 60-80
- Spray paint or obstruction applied to camera = 65-80
- Camera physically moved or covered = 60-75
- NOT tampering: image quality degradation alone, weather effects, lens flare, motion blur

## NOT RISK FACTORS - NEVER flag these as suspicious:
- Trees, bushes, plants, vegetation
- Camera timestamps or time display
- Weather conditions alone (use only for detection confidence)
- A person simply being present or walking
- Normal residential items (trash cans, bikes, hoses)
- Shadows or lighting artifacts
- Wildlife (birds, squirrels)
- Parked vehicles (without unusual context)
- Camera angle or field of view
- Image quality or resolution
- Presence of multiple objects in frame

IMPORTANT DEFAULTS:
- Without clear threat indicators, DEFAULT to lower scores
- A person simply standing or walking is NOT suspicious (score 0-15)
- Presence on property alone does NOT indicate threat
- Being "unknown" only matters if behavior is also unusual

## Scoring Examples
Use these worked examples to calibrate your scoring. Most events (85%+) should be LOW.
Examples are calibration references only; never copy their specific details into your answer.

**Example 1 — Score: 5 (LOW)**
Tuesday 2:45 PM. Front door camera. Known resident detected (face match confidence 0.97, household member "Sarah"). Walking from familiar sedan in driveway to front door. CLIP scene: 'normal activity' (0.89). Pose: upright walking. Action: approaching door normally.
Reasoning: Recognized household member, daytime arrival, matched vehicle — routine homecoming. Score: 5.

**Example 2 — Score: 8 (LOW)**
Wednesday 11:20 AM. Porch camera. One person detected wearing brown uniform (Florence-2: "person in brown shorts and collared shirt carrying cardboard box"). Delivery vehicle (CLIP: 'delivery van') parked at curb. Person approached porch, placed package, departed within 40 seconds. Pose: upright, bending. Action: placing object on ground.
Reasoning: Delivery uniform, delivery vehicle, brief visit, package placement behavior — routine delivery. Score: 8.

**Example 3 — Score: 3 (LOW)**
Saturday 10:00 AM. Backyard camera. Pet classification: dog (confidence 0.96, breed: Labrador). Known household pet re-ID match. No persons detected. CLIP scene: 'normal activity' (0.91). Zone: backyard (private, low-sensitivity).
Reasoning: High-confidence pet detection matching known household animal, no humans present — normal pet activity. Score: 3.

**Example 4 — Score: 10 (LOW)**
Thursday 9:15 AM. Driveway camera. One person detected wearing high-visibility vest and work boots (Florence-2: "person in orange safety vest holding clipboard"). White work van with company lettering parked in driveway. Pose: standing upright. Action: walking around property perimeter. Zone: driveway (semi-private). Duration: 8 minutes.
Reasoning: Service worker attire, marked commercial vehicle, business hours, expected maintenance-type behavior. Score: 10.

**Example 5 — Score: 12 (LOW)**
Monday 3:30 PM. Front yard camera. One person detected (unknown, no face match). Walking on public sidewalk past property, never entered private zone. CLIP scene: 'normal activity' (0.78). Pose: upright walking. Duration in frame: 15 seconds. Zone: sidewalk (public).
Reasoning: Person remained on public sidewalk, transient presence, no approach to property — ordinary pedestrian. Score: 12.

**Example 6 — Score: 25 (LOW)**
Sunday 4:10 PM. Front door camera. One person detected (unknown, no face match, no household re-ID). Approached front porch and rang doorbell. Wearing casual clothing (Florence-2: "person in jeans and blue jacket"). Pose: standing upright at door. No suspicious items. CLIP scene: 'person at door' (0.72). Zone: porch (entry point). Duration: 45 seconds then departed.
Reasoning: Unknown visitor but used doorbell, daytime, reasonable hour, no concealment or suspicious behavior — likely solicitor or neighbor. Score: 25.

**Example 7 — Score: 32 (MEDIUM)**
Saturday 2:00 PM. Street camera. Unfamiliar dark sedan parked on street near property for 20 minutes. No vehicle match in household database. No persons exited vehicle during observation. CLIP scene: 'parked vehicle on street' (0.65). Zone: street (public). Departed without incident.
Reasoning: Unknown vehicle but on public street, daytime, no persons approached property, short duration — unusual but benign. Score: 32.

**Example 8 — Score: 40 (MEDIUM)**
Tuesday 7:15 PM. Driveway camera. One person detected (unknown, no face match, no household re-ID). Standing near garage door for 2 minutes, looking at house. No suspicious pose (upright, standing). No face covering. Casual clothing (Florence-2: "person in gray t-shirt and khaki shorts"). CLIP scene: 'person loitering' (0.45). Zone: driveway (semi-private). Dusk lighting. Departed on foot after 2.5 minutes. No suspicious items detected.
Reasoning: Unknown person lingering near garage at dusk is unusual — not on public sidewalk and no apparent purpose. However, no suspicious behavior (no face covering, no crouching, no testing doors), moderate duration, and still daylight. Worth noting but not alarming. Score: 40.

**Example 9 — Score: 50 (MEDIUM)**
Wednesday 7:30 PM. Front door camera. One person detected (unknown, no face match). Approached front door but did NOT ring doorbell. Stood at door for 35 seconds, looked through side window (action: looking through window). Casual dark clothing (Florence-2: "person in dark hoodie and jeans"). CLIP scene: 'person loitering' (0.58). Zone: porch (entry point). Departed after 50 seconds total.
Reasoning: Unknown person at entry point, no doorbell ring, peering through window suggests possible casing behavior, but short duration and evening (not late night) temper concern. Score: 50.

**Example 10 — Score: 72 (HIGH)**
Thursday 1:15 AM. Backyard camera. One person detected (unknown, no face match). Wearing dark clothing, hood up, face partially concealed (SegFormer: face_covered=true). Crouching near back door (pose: crouching). Checking door handle (action: checking door handles). CLIP scene: 'suspicious approach' (0.71), threat pattern match: 'person checking door handles' (0.68). Zone: back door (entry point, high-sensitivity). Duration: 90 seconds. Visual anomaly score: 0.62.
Reasoning: Late night, unknown person, face concealed, crouching at entry point, actively testing door handle — multiple high-risk indicators converging. Score: 72.

**Example 11 — Score: 88 (CRITICAL)**
Friday 2:40 AM. Front porch camera. One person detected (unknown, no face match). Grabbed delivered package from porch (action: picking up object and running). CLIP scene: 'property intrusion' (0.81), threat pattern match: 'a person stealing a package from a porch' (0.85). Person fled toward street immediately after grabbing package (pose: running, facing away). Dark clothing, face concealed. Zone: porch (entry point). Duration in frame: 8 seconds. Vehicle waiting at curb.
Reasoning: Active theft — package taken and suspect fled to waiting vehicle. Property crime (package theft) with flight behavior and getaway vehicle. Score: 88.

## EVENT CONTEXT
Camera: {camera_name}
Time: {timestamp}
Day: {day_of_week}
Lighting: {time_of_day}

## Environmental Context
{weather_context}
{image_quality_context}

{camera_health_context}

## DETECTIONS WITH FULL ENRICHMENT
{detections_with_all_attributes}

{confidence_quality_summary}

## Violence Analysis
{violence_context}

## Behavioral Analysis
{pose_analysis}
{action_recognition}

## Trajectory Analysis (Movement Patterns)
{trajectory_context}

## Vehicle Analysis
{vehicle_classification_context}
{vehicle_damage_context}

## Person Analysis
{clothing_analysis_context}

## Pet Detection (False Positive Check)
{pet_classification_context}

## Spatial Context
{depth_context}

## Re-Identification
{reid_context}

{cross_camera_person_tracking}

## Zone Analysis
{zone_analysis}

## Baseline Comparison
{baseline_comparison}
Deviation score: {deviation_score}

## Cross-Camera Activity
{cross_camera_summary}

## Scene Analysis
{scene_analysis}

## On-Demand Analysis Results
{ondemand_enrichment_context}

## CLIP Scene Intelligence
{clip_analysis_context}

## Risk Interpretation Guide

### Detection Confidence Quality (NEM-5525)
- EXCELLENT/GOOD confidence: Trust detection fully, weight normally in risk assessment
- MODERATE confidence: Consider but corroborate with other signals (pose, CLIP, behavior)
- MARGINAL confidence (<60%): Treat as uncertain — do not base risk score primarily on this detection
- If all detections are MARGINAL, reduce overall confidence in assessment

### Violence Detection
- Violence detected = CRITICAL CONCERN - immediate alert required
- Confidence > 90% with 2+ persons = verified violent incident

### Weather Context
- Foggy/rainy: Reduced visibility may affect detection accuracy
- Night + rain: Particularly challenging conditions, weight other evidence
- Clear conditions: High confidence in detections

### Clothing/Attire Risk Factors
- All black + face covering (mask/balaclava) = HIGH RISK
- Dark hoodie + gloves at night = suspicious, warrant attention
- High-visibility vest or delivery uniform = service worker, score 0-15
- Any delivery/postal uniform = routine activity, score 0-15
- SegFormer face_covered + suspicious items = increased risk

### Vehicle Analysis
- Work van during business hours = likely delivery (lower risk)
- Work van at night without markings = suspicious
- Articulated truck in residential = unusual
- Damage (glass_shatter + lamp_broken at night) = possible break-in/vandalism

### Pet Detection
- High-confidence cat/dog (>85%) = likely false positive
- Pet-only event with no persons = skip alert, minimal risk
- Consider: pets don't trigger entry point concerns

### Pose/Behavior Analysis
- Crouching near entry points = suspicious
- Loitering > 30 seconds = increased concern
- Running away from camera = flight response, investigate
- Checking car doors = potential vehicle crime

### Trajectory Analysis (Movement Patterns)
- stationary at entry point for 30+ seconds = loitering, increased concern
- approaching entry point = person moving toward door/gate, monitor closely
- circling = person returning to same area, suspicious reconnaissance pattern
- wandering in private zone = non-directed movement, possible casing behavior
- departing after brief visit = likely delivery or visit, lower concern
- Fast speed + approaching = urgent/aggressive approach, escalate
- Multiple zone transitions (entering/exiting) = exploring the property, suspicious
- Entry point approach warning = highest trajectory concern, consider escalating

### Cross-Camera Person Tracking
- Same person seen on multiple cameras = deliberate movement through property
- Perimeter camera -> entry point camera = approaching access point, INCREASE risk (+10-20)
- Entry point camera -> perimeter camera = departing, generally lower concern
- Rapid camera transitions (<2 min) = fast movement through property, evaluate urgency
- Extended presence across cameras (>10 min) = prolonged presence on property, INCREASE risk
- Unknown person on multiple cameras at night = HIGH concern, possible casing/surveillance
- Known/household person on multiple cameras = NORMAL movement, do not escalate
- First-time person (no re-ID matches) = note as new, but do not escalate on that alone

### Threat Detection (Weapons)
- ANY weapon detection = CRITICAL priority, immediate alert
- Gun detected (confidence > 50%) = escalate to highest priority
- Knife detected near persons = HIGH risk
- Multiple weapons = compound threat, CRITICAL

### Action Recognition
- Sneaking/creeping = HIGH RISK behavior
- Breaking window/picking lock = IMMEDIATE threat, CRITICAL
- Climbing over fence = unauthorized entry attempt, HIGH
- Looking through window = suspicious, MEDIUM
- Normal walking = LOW risk baseline

### Property Crime Recognition (ALWAYS score 60+)
Property crimes are CRIMINAL ACTS, not just suspicious behavior:
- Vandalism/graffiti in progress = 65-85 (HIGH priority)
- Package theft = 70-90 (person taking delivered packages)
- Vehicle break-in = 70-85 (checking car doors, breaking windows)
- Breaking and entering = 80-95 (forced entry attempt)
- Property destruction = 65-85 (keying cars, breaking objects)
- Fleeing after crime = Add +10 points (awareness of wrongdoing)

### CLIP Scene Intelligence
- Scene Classification: Use the top classification label as additional context
  - 'normal activity' with high confidence (>0.6) = routine, lower risk
  - 'person loitering' or 'suspicious approach' = consider upgrading risk
  - 'property intrusion' or 'trespassing' = significant risk factor
  - 'delivery in progress' or 'service worker visiting' = routine, lower risk
- Threat Pattern Matches: High similarity scores (>0.3) indicate visual match to known threats
  - Multiple threat patterns matching (>0.3 each) = compound risk, consider upgrading
  - 'person checking door handles' + nighttime = HIGH risk
  - 'delivery person leaving a package' high score = routine activity
- Visual Anomaly Score: Measures deviation from camera's normal baseline
  - 0.0-0.2 = normal scene (weight other evidence normally)
  - 0.2-0.5 = minor deviation (slight concern, note in reasoning)
  - 0.5-0.7 = significant deviation (notable change, investigate context)
  - 0.7-1.0 = major deviation (dramatically different from normal - high concern)
- CLIP results are complementary to other models - use them to corroborate or adjust

### Demographics Context
- Age and gender are contextual factors only
- Do NOT use demographics to escalate or de-escalate risk
- Demographics help describe individuals for identification, not risk assessment
- Treat all individuals equally regardless of demographic factors

### Image Quality
- Sudden quality drop = possible camera obstruction/tampering
- Motion blur + person = fast movement (running)
- Consistent low quality = camera maintenance needed

### Camera Tampering (SSIM-based scene change detection)
- view_blocked + unknown person = ADD +30 to risk score (intentional obstruction)
- view_tampered + any intrusion indicator = ESCALATE TO CRITICAL
- angle_changed = detection baselines may not apply, note in reasoning
- Any unacknowledged scene change = detection confidence is degraded

### Time Context
- Late night (11pm-5am) + artificial light = concerning
- Business hours + service uniform = normal activity
- Weekend + unknown vehicle = note but lower concern

### Risk Levels
- low (0-29): Normal activity, no action needed
- medium (30-59): Notable activity, worth reviewing
- high (60-84): Clear threat indicators, recommend alert
- critical (85-100): Immediate threat, urgent action required

## YOUR TASK
1. Start from the scoring reference above
2. Adjust based on ACTUAL threat indicators present
3. Do NOT flag non-risk factors (trees, timestamps, normal presence)
4. Provide clear reasoning for your score
5. Remember: most events should score LOW (0-29)
6. Treat examples as calibration only; do not copy their scenario details
7. In `reasoning`, use this structure:
   Observed evidence: <facts seen in detections/enrichment only>
   Inference: <cautious interpretation, or "none">
8. If key enrichment is unavailable, explicitly say it is unavailable rather than guessing

Output JSON with comprehensive analysis:
{{"risk_score": N, "risk_level": "level", "summary": "1-2 sentence summary", "reasoning": "detailed multi-paragraph explanation of all factors considered", "entities": [{{"type": "person|vehicle|pet", "description": "detailed description with attributes", "threat_level": "low|medium|high"}}], "flags": [{{"type": "violence|suspicious_attire|vehicle_damage|unusual_behavior|quality_issue", "description": "text", "severity": "warning|alert|critical"}}], "recommended_action": "specific action to take", "confidence_factors": {{"detection_quality": "good|fair|poor", "weather_impact": "none|minor|significant", "enrichment_coverage": "full|partial|minimal"}}}}<|im_end|>
<|im_start|>assistant
"""
SUMMARY_SYSTEM_PROMPT = """You are a home security analyst providing clear, concise summaries for a homeowner. Your summaries should be informative but not alarming. Focus on facts and actionable information.

CRITICAL RULES:
- ONLY describe events that are explicitly listed in the data provided to you.
- If no events are provided, state clearly that no security events were detected. Do NOT fabricate, invent, or hallucinate any activity descriptions.
- Never infer or imagine events that are not in the provided data."""
SUMMARY_PROMPT_TEMPLATE = """Summarize the following security events for the homeowner.

**Time Window:** {window_start} to {window_end}
**Period:** {period_type}
**High/Critical Events:** {event_count}

{event_details}

**Instructions:**
1. Write a concise narrative summary (2-4 sentences maximum)
2. Highlight what happened and when
3. Note any patterns (e.g., person and vehicle arriving together, repeated activity)
4. Mention which areas of the property were affected
5. Use a calm, informative tone - avoid alarmist language

{empty_state_instruction}

**Response Format:**
Write only the summary paragraph. No headers, bullets, or formatting. Just natural prose."""
SUMMARY_EMPTY_STATE_INSTRUCTION = """IMPORTANT: There are ZERO events in this period. The event list above is empty.
You MUST respond with ONLY a brief reassuring "all clear" message such as:
"No high-priority security events detected in the past {period}. The property has been quiet."
Do NOT invent, fabricate, or describe any activity. There were no events — say so directly.
You may mention the count of lower-priority detections if provided, but do NOT describe what those detections were."""
SUMMARY_EVENT_FORMAT = """
Event {index}:
- Time: {timestamp}
- Camera: {camera_name}
- Risk Level: {risk_level} ({risk_score}/100)
- Summary: {event_summary}
- Objects Detected: {object_types}
"""


class ClassBaselineProtocol(Protocol):
    """Protocol for ClassBaseline-like objects.

    This protocol allows the format_class_anomaly_context function to work
    with both the actual ClassBaseline model and mock objects in tests.
    """

    frequency: float
    sample_count: int


@dataclass
class ClassAnomalyResult:
    """Result from per-class anomaly detection.

    Attributes:
        class_name: The detection class (e.g., "person", "vehicle")
        message: Human-readable anomaly description
        severity: "high" for security-relevant classes, "medium" for others
        risk_modifier: Suggested risk score adjustment (typically +15)
    """

    class_name: str
    message: str
    severity: str
    risk_modifier: int = 15


def format_class_anomaly_context(
    camera_id: str,
    current_hour: int,
    detections: dict[str, int],
    baselines: Mapping[str, ClassBaselineProtocol],
) -> tuple[str, list[ClassAnomalyResult]]:
    """Format per-class anomaly detection for prompt context.

    Analyzes current detection counts against historical baselines to identify
    anomalous activity patterns. Flags rare classes when detected and unusual
    volumes when counts exceed 3x normal.

    Args:
        camera_id: Camera identifier for baseline lookup
        current_hour: Current hour (0-23) for baseline lookup
        detections: Dict mapping class name to detection count
        baselines: Dict mapping "{camera_id}:{hour}:{class}" to ClassBaseline

    Returns:
        Tuple of (formatted_string, list[ClassAnomalyResult]):
        - formatted_string: Formatted context for prompt inclusion, or empty
          string if no anomalies
        - anomalies: List of ClassAnomalyResult objects for risk adjustment

    Example:
        >>> detections = {"person": 3, "dog": 1}
        >>> baselines = {"cam1:2:person": ClassBaseline(frequency=1.0, sample_count=20)}
        >>> context, anomalies = format_class_anomaly_context("cam1", 2, detections, baselines)
        >>> print(context)
        ## CLASS-SPECIFIC ANOMALIES
        [MEDIUM] person UNUSUAL volume (3 vs expected 1.0)
        [HIGH] dog RARE at this hour (expected: 0.0/hr, actual: 1)
    """
    # Security-relevant classes get high severity
    high_severity_classes = frozenset({"person", "vehicle", "car", "truck", "motorcycle"})

    anomalies: list[ClassAnomalyResult] = []

    for cls, count in detections.items():
        baseline_key = f"{camera_id}:{current_hour}:{cls}"
        baseline = baselines.get(baseline_key)

        # Skip if insufficient data (< 10 samples)
        if baseline is None or baseline.sample_count < 10:
            continue

        expected = baseline.frequency

        # Case 1: Rare class (expected < 0.1/hr) detected
        if expected < 0.1:
            if count >= 1:
                severity = "high" if cls in high_severity_classes else "medium"
                anomalies.append(
                    ClassAnomalyResult(
                        class_name=cls,
                        message=f"{cls} RARE at this hour (expected: {expected:.1f}/hr, actual: {count})",
                        severity=severity,
                        risk_modifier=15,
                    )
                )
        # Case 2: Unusual volume (3x normal)
        elif count > expected * 3:
            anomalies.append(
                ClassAnomalyResult(
                    class_name=cls,
                    message=f"{cls} UNUSUAL volume ({count} vs expected {expected:.1f})",
                    severity="medium",
                    risk_modifier=15,
                )
            )

    if not anomalies:
        return "", []

    lines = ["## CLASS-SPECIFIC ANOMALIES"]
    for a in anomalies:
        # Use text markers instead of emojis for compatibility
        icon = "[HIGH]" if a.severity == "high" else "[MEDIUM]"
        lines.append(f"{icon} {a.message}")

    return "\n".join(lines), anomalies


def build_summary_prompt(
    window_start: str,
    window_end: str,
    period_type: str,  # "hour" or "day"
    events: list[dict[str, Any]],
    routine_count: int = 0,
) -> tuple[str, str]:
    """Build the system and user prompts for summary generation.

    Args:
        window_start: Formatted start time (e.g., "2:00 PM")
        window_end: Formatted end time (e.g., "3:00 PM")
        period_type: "hour" for hourly, "day" for daily
        events: List of event dicts with keys: timestamp, camera_name,
                risk_level, risk_score, summary, object_types
        routine_count: Number of low/medium events (for empty state context)

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    event_count = len(events)

    # Build event details section
    if events:
        event_details = "**Event Details:**\n"
        for i, event in enumerate(events, 1):
            event_details += SUMMARY_EVENT_FORMAT.format(
                index=i,
                timestamp=event["timestamp"],
                camera_name=event["camera_name"],
                risk_level=event["risk_level"],
                risk_score=event["risk_score"],
                event_summary=event["summary"],
                object_types=event["object_types"],
            )
    else:
        event_details = "**Event Details:**\nNo high or critical events in this period."
        if routine_count > 0:
            event_details += f"\n({routine_count} routine/low-priority detections occurred)"

    # Build empty state instruction
    if event_count == 0:
        empty_instruction = SUMMARY_EMPTY_STATE_INSTRUCTION.format(period=period_type)
    else:
        empty_instruction = ""

    user_prompt = SUMMARY_PROMPT_TEMPLATE.format(
        window_start=window_start,
        window_end=window_end,
        period_type=period_type,
        event_count=event_count,
        event_details=event_details,
        empty_state_instruction=empty_instruction,
    )

    return SUMMARY_SYSTEM_PROMPT, user_prompt


class EnrichmentResultLike(Protocol):
    """The enrichment-RESULT surface the pipeline audit still reads (R8 S2).

    It used to be the shape `build_enrichment_sections` rendered into the
    legacy prompt; that function retired with the enrichment tier, and this
    protocol's one remaining consumer is
    ``pipeline_quality_audit_service``, whose model-contribution flags read
    the same computed-attribute names the retired ``EnrichmentResult``
    dataclass carried. The shipped pipeline passes ``None`` here (the VLM
    path produces no enrichment result); mocks in the audit tests carry these
    attributes. Named ``...Like`` precisely because the concrete class is
    gone - it describes a shape, not an importable type.
    """

    has_vision_extraction: bool
    person_reid_matches: dict[str, Any]
    vehicle_reid_matches: dict[str, Any]
    has_violence: bool
    has_clothing_classifications: bool
    has_vehicle_classifications: bool
    has_vehicle_damage: bool
    has_pet_classifications: bool
    weather_classification: Any | None
    has_image_quality: bool
