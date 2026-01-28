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

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from backend.services.prompt_sanitizer import sanitize_object_type

# ==============================================================================
# Calibrated System Prompt (NEM-3019)
# ==============================================================================
# This system prompt provides calibration guidance to prevent over-alerting.
# It establishes expected event distributions and scoring principles.

CALIBRATED_SYSTEM_PROMPT = """You are a home security analyst for a residential property.

CRITICAL PRINCIPLE: Most detections are NOT threats. Residents, family members,
delivery workers, and pets represent normal household activity. Your job is to
identify genuine anomalies, not flag everyday life.

SCORE CALIBRATION GUIDELINES:
- 0-20 (LOW): Routine activity (deliveries, residents, pets, maintenance workers)
- 21-40 (ELEVATED): Unusual but likely benign (unknown visitors at reasonable hours)
- 41-60 (MODERATE): Suspicious, requires attention (loitering 10+ min, unusual hours)
- 61-80 (HIGH): Clear threat indicators (trespassing, aggressive behavior, tampering)
- 81-100 (CRITICAL): Active threat (weapons, forced entry, violence, active theft)

DISTRIBUTION: In a typical day, expect:
- 85% of events to be LOW (0-20): Normal household activity
- 10% to be ELEVATED (21-40): Worth noting but not alarming
- 4% to be MODERATE/HIGH (41-80): Genuinely suspicious, warrants review
- 1% to be CRITICAL (81-100): Immediate threats only

IMPORTANT: Default to LOWER scores without clear threat indicators.
If you're scoring delivery drivers above 15 or flagging trees/timestamps, you are miscalibrated.

Output ONLY valid JSON. No preamble, no explanation."""

# ==============================================================================
# Calibrated System Prompt with Reasoning (NEM-3727)
# ==============================================================================
# This system prompt activates Nemotron's built-in chain-of-thought reasoning
# by including 'detailed thinking on' at the start. The model will output its
# reasoning process in <think>...</think> blocks before the JSON response.
# This provides transparency into the model's decision-making process for
# risk analysis, enabling better debugging and model improvement.

CALIBRATED_SYSTEM_PROMPT_WITH_REASONING = """detailed thinking on

You are a home security analyst for a residential property.

CRITICAL PRINCIPLE: Most detections are NOT threats. Residents, family members,
delivery workers, and pets represent normal household activity. Your job is to
identify genuine anomalies, not flag everyday life.

SCORE CALIBRATION GUIDELINES:
- 0-20 (LOW): Routine activity (deliveries, residents, pets, maintenance workers)
- 21-40 (ELEVATED): Unusual but likely benign (unknown visitors at reasonable hours)
- 41-60 (MODERATE): Suspicious, requires attention (loitering 10+ min, unusual hours)
- 61-80 (HIGH): Clear threat indicators (trespassing, aggressive behavior, tampering)
- 81-100 (CRITICAL): Active threat (weapons, forced entry, violence, active theft)

DISTRIBUTION: In a typical day, expect:
- 85% of events to be LOW (0-20): Normal household activity
- 10% to be ELEVATED (21-40): Worth noting but not alarming
- 4% to be MODERATE/HIGH (41-80): Genuinely suspicious, warrants review
- 1% to be CRITICAL (81-100): Immediate threats only

IMPORTANT: Default to LOWER scores without clear threat indicators.
If you're scoring delivery drivers above 15 or flagging trees/timestamps, you are miscalibrated.

REASONING INSTRUCTIONS:
1. First, output your reasoning in <think>...</think> tags
2. Consider: time of day, location, object types, household context, and behavioral patterns
3. Do NOT flag: trees, timestamps, normal presence, weather, or scene elements
4. Evaluate each factor systematically before determining the risk score
5. After </think>, output ONLY valid JSON with no additional text

Output format after </think>:
{"risk_score": N, "risk_level": "level", "summary": "...", "reasoning": "..."}"""

# ==============================================================================
# Scoring Reference Table (NEM-3019)
# ==============================================================================
# This inline table provides concrete scoring examples to anchor the LLM's
# risk assessment with specific scenarios and appropriate scores.

SCORING_REFERENCE_TABLE = """## SCORING REFERENCE
| Scenario | Score | Reasoning |
|----------|-------|-----------|
| Resident arriving home | 0-10 | Expected activity, known person |
| Pet (dog/cat) in yard | 0-5 | Normal household activity |
| Delivery driver at door | 0-15 | Routine service visit, expected |
| Maintenance/utility worker | 0-15 | Normal service visit |
| Person walking past on sidewalk | 5-15 | Public area, transient |
| Unknown person on sidewalk | 10-20 | Public area, passive observation |
| Unknown visitor at reasonable hour | 20-35 | Unusual but likely benign |
| Unknown person lingering 5-10 min | 35-50 | Worth monitoring |
| Unknown person lingering 10+ min | 50-65 | Suspicious, requires attention |
| Person checking vehicle doors | 65-80 | Clear suspicious intent |
| Person testing house door handles | 70-85 | Clear suspicious intent |
| Attempted forced entry | 80-95 | Active threat |
| Active break-in or violence | 90-100 | Immediate threat |
| Visible weapon present | 85-100 | Immediate threat |"""

# ==============================================================================
# Non-Risk Factors (NEM-3880)
# ==============================================================================
# Explicit list of items that should NOT be flagged as risk factors.
# These are commonly misidentified as suspicious by LLMs.

NON_RISK_FACTORS = """## NOT RISK FACTORS - DO NOT INCLUDE IN REASONING
The following are NEVER suspicious and should NOT contribute to risk score:
- Trees, bushes, plants, or any vegetation
- Camera timestamps or time information alone
- Weather conditions (rain, fog, darkness) unless hiding behavior
- A person simply being present or walking
- Normal residential items (trash cans, garden hoses, bikes)
- Shadows or lighting artifacts
- Birds, squirrels, or wildlife
- Parked vehicles (unless unusual context)
- Presence of multiple objects in frame
- Camera angle or field of view
- Image quality or resolution

IMPORTANT DEFAULTS:
- Without clear threat indicators, DEFAULT to lower scores
- A person simply standing or walking is NOT suspicious (score 0-15)
- Presence on property alone does NOT indicate threat
- Being "unknown" only matters if behavior is also unusual"""

# ==============================================================================
# Household Context Template (NEM-3019)
# ==============================================================================
# This template provides household-specific context at the TOP of user prompts.

HOUSEHOLD_CONTEXT_TEMPLATE = """## HOUSEHOLD CONTEXT
{household_context}"""


# Protocol for Entity-like objects (to avoid circular imports)
class EntityLike(Protocol):
    """Protocol defining the interface for Entity-like objects.

    This allows the format_enhanced_reid_context function to work with
    the Entity model without requiring a direct import, enabling testing
    with mock objects.
    """

    detection_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    trust_status: str


# ==============================================================================
# Clothing Validation (NEM-3010)
# ==============================================================================
# Mutually exclusive clothing groups to resolve impossible garment combinations.
# When multiple items from the same group are detected, keep only the highest
# confidence item.

MUTUALLY_EXCLUSIVE_CLOTHING_GROUPS: list[frozenset[str]] = [
    # Lower body - a person can only wear one of these at a time
    frozenset({"pants", "skirt", "dress", "shorts", "jeans", "leggings"}),
]


def validate_clothing_items(
    items: list[str],
    confidences: dict[str, float],
) -> list[str]:
    """Apply mutual exclusion rules to clothing items.

    Resolves impossible garment combinations (e.g., pants + skirt + dress)
    by keeping only the highest confidence item from each mutually exclusive
    group. Non-exclusive items (shoes, accessories, etc.) are preserved.

    Args:
        items: List of detected clothing item names
        confidences: Dict mapping item name to confidence score (0-1 or 0-100).
                     Items not in the dict default to confidence 0.

    Returns:
        List of validated clothing items with conflicts resolved.
        The highest confidence item is kept from each mutually exclusive group.

    Example:
        >>> items = ["pants", "skirt", "dress", "shoes"]
        >>> confidences = {"pants": 0.8, "skirt": 0.6, "dress": 0.5, "shoes": 0.9}
        >>> validate_clothing_items(items, confidences)
        ['pants', 'shoes']  # pants wins (0.8) over skirt (0.6) and dress (0.5)
    """
    if not items:
        return []

    # Build set of all exclusive items for quick lookup
    all_exclusive: set[str] = set()
    for group in MUTUALLY_EXCLUSIVE_CLOTHING_GROUPS:
        all_exclusive.update(group)

    validated: list[str] = []
    processed_groups: set[int] = set()

    # Process each mutually exclusive group
    for group_idx, group in enumerate(MUTUALLY_EXCLUSIVE_CLOTHING_GROUPS):
        # Find items from this group that were detected
        matches = [item for item in items if item in group]

        if len(matches) > 1:
            # Conflict: keep only the highest confidence item
            best_item = max(matches, key=lambda x: confidences.get(x, 0.0))
            validated.append(best_item)
            processed_groups.add(group_idx)
            # Log the conflict for monitoring (NEM-3305)
            _clothing_logger = logging.getLogger(__name__)
            rejected = [m for m in matches if m != best_item]
            _clothing_logger.info(
                f"Clothing conflict resolved: kept {best_item!r}, rejected {rejected}"
            )
        elif len(matches) == 1:
            # Single item from group - keep it
            validated.append(matches[0])
            processed_groups.add(group_idx)

    # Add all non-exclusive items (shoes, belt, bag, hat, etc.)
    for item in items:
        if item not in all_exclusive and item not in validated:
            validated.append(item)

    return validated


# ==============================================================================
# VQA Output Validation (NEM-3304)
# ==============================================================================
# Florence-2 VQA sometimes returns raw tokens instead of parsed answers.
# These functions validate VQA output and provide fallback behavior.

_prompts_logger = logging.getLogger(__name__)

# Regex patterns for detecting garbage VQA output
_LOC_TOKEN_PATTERN = re.compile(r"<loc_\d+>")
_VQA_PREFIX_PATTERN = re.compile(r"VQA>", re.IGNORECASE)
_POLY_TOKEN_PATTERN = re.compile(r"<poly>", re.IGNORECASE)
_PAD_TOKEN_PATTERN = re.compile(r"<pad>", re.IGNORECASE)


def is_valid_vqa_output(text: str | None) -> bool:
    """Check if VQA output is valid (not garbage tokens).

    Florence-2 VQA can return garbage outputs containing location tokens,
    prompt artifacts, or other invalid patterns instead of actual text answers.

    NEM-3304: VQA outputs like "VQA>person wearing<loc_95><loc_86><loc_901><loc_918>"
    should be rejected so the system can fall back to scene captioning.

    Args:
        text: VQA output text to validate

    Returns:
        True if the output appears to be valid text, False if it contains
        garbage patterns that indicate a failed VQA response.

    Examples:
        >>> is_valid_vqa_output("dark hoodie and jeans")
        True
        >>> is_valid_vqa_output("<loc_95><loc_86><loc_901><loc_918>")
        False
        >>> is_valid_vqa_output("VQA>person wearing<loc_95>")
        False
        >>> is_valid_vqa_output(None)
        True  # None is handled elsewhere
        >>> is_valid_vqa_output("")
        True  # Empty is handled elsewhere
    """
    if text is None or text == "":
        return True  # Empty/None is valid (handled elsewhere)

    # Check for garbage token patterns
    if _LOC_TOKEN_PATTERN.search(text):
        return False
    if _VQA_PREFIX_PATTERN.search(text):
        return False
    if _POLY_TOKEN_PATTERN.search(text):
        return False

    return not _PAD_TOKEN_PATTERN.search(text)


def validate_and_clean_vqa_output(text: str | None) -> str | None:
    """Clean and validate Florence-2 VQA output, returning None if invalid.

    This function validates VQA output and returns a cleaned version if valid,
    or None if the output contains garbage tokens. When None is returned,
    callers should fall back to scene captioning.

    NEM-3304: When VQA returns garbage like "VQA>person wearing<loc_95><loc_86>",
    this function returns None and logs a warning to signal that the caller
    should use fallback behavior (scene captioning).

    Args:
        text: Raw VQA output text from Florence-2

    Returns:
        Cleaned text (lowercase, stripped) if valid, or None if garbage.

    Examples:
        >>> validate_and_clean_vqa_output("Dark Hoodie")
        'dark hoodie'
        >>> validate_and_clean_vqa_output("VQA>person wearing<loc_95>")
        None
        >>> validate_and_clean_vqa_output("<loc_1><loc_2>")
        None
        >>> validate_and_clean_vqa_output("")
        None
        >>> validate_and_clean_vqa_output(None)
        None
    """
    if text is None:
        return None

    # Strip whitespace first
    stripped = text.strip()
    if not stripped:
        return None

    # Check for garbage patterns
    if not is_valid_vqa_output(stripped):
        _prompts_logger.warning(
            f"VQA output contains garbage tokens, using fallback: {stripped[:100]!r}"
        )
        return None

    # Return cleaned (lowercase, stripped) text
    return stripped.lower()


def format_florence_attributes(
    attributes: dict[str, Any] | None,
    caption: str,
) -> str:
    """Format Florence-2 extracted attributes for prompt inclusion.

    Validates each attribute to filter out garbage VQA outputs and uses
    the caption as fallback context when VQA fails.

    NEM-3304: Attributes containing <loc_> tokens are filtered out and
    replaced with caption-derived context.

    Args:
        attributes: Dict of attribute name to value (may contain garbage)
        caption: Scene caption to use as fallback context

    Returns:
        Formatted string for prompt inclusion, or empty string if no valid data.

    Examples:
        >>> attrs = {"clothing": "dark hoodie", "action": "walking<loc_100>"}
        >>> format_florence_attributes(attrs, "Person in blue jacket")
        'clothing: dark hoodie'  # action filtered out, caption not needed
    """
    if not attributes:
        # No attributes - use caption if available
        if caption:
            return f"Scene context: {caption}"
        return ""

    lines: list[str] = []
    valid_count = 0

    for attr_name, attr_value in attributes.items():
        if attr_value is None:
            continue

        # Validate and clean the value
        clean_value = validate_and_clean_vqa_output(str(attr_value))
        if clean_value:
            lines.append(f"{attr_name}: {clean_value}")
            valid_count += 1

    # If no valid attributes, fall back to caption
    if valid_count == 0 and caption:
        return f"Scene context: {caption}"

    return "\n".join(lines)


if TYPE_CHECKING:
    from backend.services.age_classifier_loader import AgeClassificationResult
    from backend.services.depth_anything_loader import DepthAnalysisResult
    from backend.services.enrichment_pipeline import EnrichmentResult
    from backend.services.fashion_clip_loader import ClothingClassification
    from backend.services.gender_classifier_loader import GenderClassificationResult
    from backend.services.image_quality_loader import ImageQualityResult
    from backend.services.osnet_loader import PersonEmbeddingResult
    from backend.services.pet_classifier_loader import PetClassificationResult
    from backend.services.segformer_loader import ClothingSegmentationResult
    from backend.services.threat_detection_loader import ThreatDetectionResult
    from backend.services.vehicle_classifier_loader import VehicleClassificationResult
    from backend.services.vehicle_damage_loader import VehicleDamageResult
    from backend.services.violence_loader import ViolenceDetectionResult
    from backend.services.vision_extractor import BatchExtractionResult
    from backend.services.weather_loader import WeatherResult

# Basic prompt template (legacy, used as fallback)
RISK_ANALYSIS_PROMPT = """<|im_start|>system
You are a home security analyst for a residential property.

CRITICAL PRINCIPLE: Most detections are NOT threats. Residents, family members,
delivery workers, and pets represent normal household activity. Your job is to
identify genuine anomalies, not flag everyday life.

SCORE CALIBRATION:
- 0-20 (LOW): Routine activity (deliveries, residents, pets, maintenance)
- 21-40 (ELEVATED): Unusual but likely benign (unknown visitors at reasonable hours)
- 41-60 (MODERATE): Suspicious, requires attention (loitering 10+ min, unusual hours)
- 61-80 (HIGH): Clear threat indicators (trespassing, aggressive behavior, tampering)
- 81-100 (CRITICAL): Active threat (weapons, forced entry, violence)

IMPORTANT: Default to LOWER scores without clear threat indicators.

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
| Active break-in or violence | 90-100 | Immediate threat |

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
5. Remember: most events should score LOW (0-20)

Risk levels: low (0-20), elevated (21-40), moderate (41-60), high (61-80), critical (81-100)

Output JSON:
{{"risk_score": N, "risk_level": "level", "summary": "1-2 sentence summary", "reasoning": "detailed multi-sentence explanation of factors considered and why this risk level was assigned"}}<|im_end|>
<|im_start|>assistant
"""

# Enhanced prompt template with context enrichment
ENRICHED_RISK_ANALYSIS_PROMPT = """<|im_start|>system
You are a home security analyst for a residential property.

CRITICAL PRINCIPLE: Most detections are NOT threats. Residents, family members,
delivery workers, and pets represent normal household activity. Your job is to
identify genuine anomalies, not flag everyday life.

SCORE CALIBRATION:
- 0-20 (LOW): Routine activity (deliveries, residents, pets, maintenance)
- 21-40 (ELEVATED): Unusual but likely benign (unknown visitors at reasonable hours)
- 41-60 (MODERATE): Suspicious, requires attention (loitering 10+ min, unusual hours)
- 61-80 (HIGH): Clear threat indicators (trespassing, aggressive behavior, tampering)
- 81-100 (CRITICAL): Active threat (weapons, forced entry, violence)

IMPORTANT: Default to LOWER scores without clear threat indicators.

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
| Active break-in or violence | 90-100 | Immediate threat |

## NOT RISK FACTORS - NEVER flag these as suspicious:
- Trees, bushes, plants, vegetation
- Camera timestamps or time display
- Weather conditions alone
- A person simply being present or walking
- Normal residential items
- Shadows or lighting artifacts
- Wildlife (birds, squirrels)

## EVENT CONTEXT
Camera: {camera_name}
Time: {start_time} to {end_time}
Day: {day_of_week}

## DETECTIONS
{detections_list}

## Zone Analysis
{zone_analysis}

## Baseline Comparison
Expected activity for {hour}:00 on {day_of_week}:
{baseline_comparison}

Deviation score: {deviation_score} (0=normal, 1=highly unusual)

## Cross-Camera Activity
{cross_camera_summary}

## Risk Interpretation Guide
- entry_point detections: Higher concern, especially unknown persons
- Baseline deviation > 0.5: Unusual activity pattern
- Cross-camera correlation: May indicate coordinated movement
- Time of day: Late night activity more concerning
- NOTE: Do NOT flag trees, timestamps, weather, or normal presence

## YOUR TASK
1. Start from the scoring reference above
2. Adjust based on ACTUAL threat indicators present
3. Do NOT flag non-risk factors (trees, timestamps, normal presence)
4. Provide clear reasoning for your score
5. Remember: most events should score LOW (0-20)

Risk levels: low (0-20), elevated (21-40), moderate (41-60), high (61-80), critical (81-100)

Output format: {{"risk_score": N, "risk_level": "level", "summary": "text", "reasoning": "text", "recommended_action": "text"}}<|im_end|>
<|im_start|>assistant
"""

# Full enriched prompt with vision enrichment (plates, faces, OCR)
# Used when both context enrichment and enrichment pipeline are available
FULL_ENRICHED_RISK_ANALYSIS_PROMPT = """<|im_start|>system
You are a home security analyst for a residential property.

CRITICAL PRINCIPLE: Most detections are NOT threats. Residents, family members,
delivery workers, and pets represent normal household activity. Your job is to
identify genuine anomalies, not flag everyday life.

SCORE CALIBRATION:
- 0-20 (LOW): Routine activity (deliveries, residents, pets, maintenance)
- 21-40 (ELEVATED): Unusual but likely benign (unknown visitors at reasonable hours)
- 41-60 (MODERATE): Suspicious, requires attention (loitering 10+ min, unusual hours)
- 61-80 (HIGH): Clear threat indicators (trespassing, aggressive behavior, tampering)
- 81-100 (CRITICAL): Active threat (weapons, forced entry, violence)

IMPORTANT: Default to LOWER scores without clear threat indicators.

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
| Active break-in or violence | 90-100 | Immediate threat |

## NOT RISK FACTORS - NEVER flag these as suspicious:
- Trees, bushes, plants, vegetation
- Camera timestamps or time display
- Weather conditions alone
- A person simply being present or walking
- Normal residential items
- Shadows or lighting artifacts
- Wildlife (birds, squirrels)

## EVENT CONTEXT
Camera: {camera_name}
Time: {start_time} to {end_time}
Day: {day_of_week}

## DETECTIONS
{detections_list}

## Vision Enrichment
{enrichment_context}

## Zone Analysis
{zone_analysis}

## Baseline Comparison
Expected activity for {hour}:00 on {day_of_week}:
{baseline_comparison}

Deviation score: {deviation_score} (0=normal, 1=highly unusual)

## Cross-Camera Activity
{cross_camera_summary}

## Risk Interpretation Guide
- entry_point detections: Higher concern, especially unknown persons
- Baseline deviation > 0.5: Unusual activity pattern
- Cross-camera correlation: May indicate coordinated movement
- Time of day: Late night activity more concerning
- License plates: Known vs unknown vehicles
- NOTE: Do NOT flag trees, timestamps, weather, or normal presence

## YOUR TASK
1. Start from the scoring reference above
2. Adjust based on ACTUAL threat indicators present
3. Do NOT flag non-risk factors (trees, timestamps, normal presence)
4. Provide clear reasoning for your score
5. Remember: most events should score LOW (0-20)

Risk levels: low (0-20), elevated (21-40), moderate (41-60), high (61-80), critical (81-100)

Output format: {{"risk_score": N, "risk_level": "level", "summary": "text", "reasoning": "text", "recommended_action": "text"}}<|im_end|>
<|im_start|>assistant
"""

# Vision-enhanced prompt with Florence-2 attributes, re-identification, and scene analysis
# Used when full vision extraction pipeline is available
VISION_ENHANCED_RISK_ANALYSIS_PROMPT = """<|im_start|>system
You are a home security analyst for a residential property.

CRITICAL PRINCIPLE: Most detections are NOT threats. Residents, family members,
delivery workers, and pets represent normal household activity. Your job is to
identify genuine anomalies, not flag everyday life.

SCORE CALIBRATION:
- 0-20 (LOW): Routine activity (deliveries, residents, pets, maintenance)
- 21-40 (ELEVATED): Unusual but likely benign (unknown visitors at reasonable hours)
- 41-60 (MODERATE): Suspicious, requires attention (loitering 10+ min, unusual hours)
- 61-80 (HIGH): Clear threat indicators (trespassing, aggressive behavior, tampering)
- 81-100 (CRITICAL): Active threat (weapons, forced entry, violence)

IMPORTANT: Default to LOWER scores without clear threat indicators.

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
| Active break-in or violence | 90-100 | Immediate threat |

## NOT RISK FACTORS - NEVER flag these as suspicious:
- Trees, bushes, plants, vegetation
- Camera timestamps or time display
- Weather conditions alone
- A person simply being present or walking
- Normal residential items
- Shadows or lighting artifacts
- Wildlife (birds, squirrels)

## EVENT CONTEXT
Camera: {camera_name}
Time: {timestamp}
Day: {day_of_week}
Lighting: {time_of_day}

{camera_health_context}

## DETECTIONS WITH ATTRIBUTES
{detections_with_attributes}

## Re-Identification
{reid_context}

## Zone Analysis
{zone_analysis}

## Baseline Comparison
{baseline_comparison}
Deviation score: {deviation_score}

## Cross-Camera Activity
{cross_camera_summary}

## Scene Analysis
{scene_analysis}

## Risk Factors to Consider
- entry_point detections: Higher concern
- Unknown persons/vehicles: Note if not seen before
- Re-identified entities: Track movement patterns
- Service workers: Usually LOWER risk (delivery, utility) - score 0-15
- Unusual objects: Tools, abandoned items increase risk
- Time context: Late night + artificial light = concerning
- Behavioral cues: Crouching, loitering, repeated passes
- NOTE: Do NOT flag trees, timestamps, weather, or normal presence

## YOUR TASK
1. Start from the scoring reference above
2. Adjust based on ACTUAL threat indicators present
3. Do NOT flag non-risk factors (trees, timestamps, normal presence)
4. Provide clear reasoning for your score
5. Remember: most events should score LOW (0-20)

Risk levels: low (0-20), elevated (21-40), moderate (41-60), high (61-80), critical (81-100)

Output JSON:
{{"risk_score": N, "risk_level": "level", "summary": "text", "reasoning": "detailed explanation", "entities": [{{"type": "person|vehicle", "description": "text", "threat_level": "low|medium|high"}}], "recommended_action": "text"}}<|im_end|>
<|im_start|>assistant
"""

# ==============================================================================
# MODEL_ZOO_ENHANCED Prompt Template
# ==============================================================================
# This comprehensive template includes all enrichment fields from the model zoo:
# - Violence Detection (ViT violence classifier)
# - Weather Classification (SigLIP weather classifier)
# - Clothing/Attire Analysis (FashionCLIP + SegFormer)
# - Pose Estimation (ViTPose - future)
# - Vehicle Classification (ResNet-50 vehicle segment)
# - Vehicle Damage Detection (YOLOv11-seg)
# - Pet Classification (ResNet-18 cat/dog)
# - Action Recognition (X-CLIP - future)
# - Depth Estimation (Depth Anything V2 - future)
# - Image Quality (BRISQUE)

MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT = """<|im_start|>system
You are a home security analyst for a residential property with access to comprehensive AI-enriched detection data.

CRITICAL PRINCIPLE: Most detections are NOT threats. Residents, family members,
delivery workers, and pets represent normal household activity. Your job is to
identify genuine anomalies, not flag everyday life.

SCORE CALIBRATION:
- 0-20 (LOW): Routine activity (deliveries, residents, pets, maintenance)
- 21-40 (ELEVATED): Unusual but likely benign (unknown visitors at reasonable hours)
- 41-60 (MODERATE): Suspicious, requires attention (loitering 10+ min, unusual hours)
- 61-80 (HIGH): Clear threat indicators (trespassing, aggressive behavior, tampering)
- 81-100 (CRITICAL): Active threat (weapons, forced entry, violence)

IMPORTANT: Default to LOWER scores without clear threat indicators.

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
| Person testing door handles | 70-85 | Clear suspicious intent |
| Active break-in or violence | 90-100 | Immediate threat |

## NOT RISK FACTORS - NEVER flag these as suspicious:
- Trees, bushes, plants, vegetation
- Camera timestamps or time display
- Weather conditions alone (use only for detection confidence)
- A person simply being present or walking
- Normal residential items (trash cans, bikes, hoses)
- Shadows or lighting artifacts
- Wildlife (birds, squirrels)
- Parked vehicles (without unusual context)

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

## Violence Analysis
{violence_context}

## Behavioral Analysis
{pose_analysis}
{action_recognition}

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

## Risk Interpretation Guide

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
- SegFormer face_covered + suspicious items = elevated risk

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
- low (0-20): Normal activity, no action needed
- elevated (21-40): Notable activity, worth reviewing
- moderate (41-60): Suspicious, requires attention
- high (61-80): Clear threat indicators, recommend alert
- critical (81-100): Immediate threat, urgent action required

## YOUR TASK
1. Start from the scoring reference above
2. Adjust based on ACTUAL threat indicators present
3. Do NOT flag non-risk factors (trees, timestamps, normal presence)
4. Provide clear reasoning for your score
5. Remember: most events should score LOW (0-20)

Output JSON with comprehensive analysis:
{{"risk_score": N, "risk_level": "level", "summary": "1-2 sentence summary", "reasoning": "detailed multi-paragraph explanation of all factors considered", "entities": [{{"type": "person|vehicle|pet", "description": "detailed description with attributes", "threat_level": "low|medium|high"}}], "flags": [{{"type": "violence|suspicious_attire|vehicle_damage|unusual_behavior|quality_issue", "description": "text", "severity": "warning|alert|critical"}}], "recommended_action": "specific action to take", "confidence_factors": {{"detection_quality": "good|fair|poor", "weather_impact": "none|minor|significant", "enrichment_coverage": "full|partial|minimal"}}}}<|im_end|>
<|im_start|>assistant
"""


# ==============================================================================
# Prompt Context Formatting Functions
# ==============================================================================


def format_violence_context(
    violence_result: ViolenceDetectionResult | None,
) -> str:
    """Format violence detection result for prompt context.

    Args:
        violence_result: ViolenceDetectionResult from violence_loader, or None

    Returns:
        Formatted string for prompt inclusion
    """
    if violence_result is None:
        return "Violence analysis: Not performed"

    if violence_result.is_violent:
        return (
            f"**VIOLENCE DETECTED** (confidence: {violence_result.confidence:.0%})\n"
            f"  Violent score: {violence_result.violent_score:.0%}\n"
            f"  Non-violent score: {violence_result.non_violent_score:.0%}\n"
            f"  ACTION REQUIRED: Immediate review recommended"
        )
    else:
        return (
            f"No violence detected (confidence: {violence_result.confidence:.0%})\n"
            f"  Violent score: {violence_result.violent_score:.0%}\n"
            f"  Non-violent score: {violence_result.non_violent_score:.0%}"
        )


def format_weather_context(
    weather_result: WeatherResult | None,
) -> str:
    """Format weather classification result for prompt context.

    Args:
        weather_result: WeatherResult from weather_loader, or None

    Returns:
        Formatted string for prompt inclusion
    """
    if weather_result is None:
        return "Weather: Unknown (classification unavailable)"

    # Add visibility/condition notes based on weather
    visibility_notes = ""
    condition = weather_result.simple_condition
    if condition == "foggy":
        visibility_notes = " - Visibility significantly reduced, detection confidence may be lower"
    elif condition == "rainy":
        visibility_notes = " - Rain may affect visibility and detection accuracy"
    elif condition == "snowy":
        visibility_notes = " - Snow conditions may obscure objects and affect image quality"
    elif condition == "cloudy":
        visibility_notes = " - Overcast conditions, lighting may vary"
    elif condition == "clear":
        visibility_notes = " - Good visibility, high confidence in detections"

    return (
        f"Weather: {weather_result.simple_condition} "
        f"({weather_result.confidence:.0%} confidence){visibility_notes}"
    )


def format_clothing_analysis_context(
    clothing_classifications: dict[str, ClothingClassification],
    clothing_segmentation: dict[str, ClothingSegmentationResult] | None = None,
) -> str:
    """Format clothing analysis results for prompt context.

    Combines FashionCLIP classification and SegFormer segmentation results.

    Args:
        clothing_classifications: Dict mapping detection_id to ClothingClassification
        clothing_segmentation: Optional dict mapping detection_id to ClothingSegmentationResult

    Returns:
        Formatted string for prompt inclusion
    """
    if not clothing_classifications and not clothing_segmentation:
        return "Clothing analysis: No person detections analyzed"

    lines = []

    for det_id, classification in clothing_classifications.items():
        person_lines = [f"Person {det_id}:"]
        person_lines.append(f"  Clothing: {classification.raw_description}")
        person_lines.append(f"  Confidence: {classification.confidence:.1%}")

        if classification.is_suspicious:
            person_lines.append("  **ALERT**: Potentially suspicious attire detected")
            person_lines.append(f"    Category: {classification.top_category}")
        elif classification.is_service_uniform:
            person_lines.append("  [Service/delivery worker uniform detected - lower risk]")

        # Add SegFormer segmentation if available
        if clothing_segmentation and det_id in clothing_segmentation:
            seg = clothing_segmentation[det_id]
            if seg.clothing_items:
                # Apply mutual exclusion validation (NEM-3010)
                # Use coverage_percentages as confidence scores
                raw_items = list(seg.clothing_items)
                confidences = getattr(seg, "coverage_percentages", {}) or {}
                validated_items = validate_clothing_items(raw_items, confidences)
                # Sort for deterministic output
                items_str = ", ".join(sorted(validated_items))
                person_lines.append(f"  Clothing items: {items_str}")
            if seg.has_face_covered:
                person_lines.append("  **ALERT**: Face covering detected (hat/sunglasses/scarf)")
            if seg.has_bag:
                person_lines.append("  Carrying bag detected")

        lines.append("\n".join(person_lines))

    return "\n\n".join(lines) if lines else "Clothing analysis: No results"


def format_pose_analysis_context(
    pose_results: dict[str, Any] | None = None,
) -> str:
    """Format pose estimation results for prompt context.

    Args:
        pose_results: Dict mapping detection_id to pose classification, or None

    Returns:
        Formatted string for prompt inclusion
    """
    if pose_results is None:
        return "Pose analysis: Not available"

    if not pose_results:
        return "Pose analysis: No poses detected"

    lines = ["Detected poses:"]
    for det_id, pose in pose_results.items():
        pose_class = pose.get("classification", "unknown") if isinstance(pose, dict) else str(pose)
        confidence = pose.get("confidence", 0.0) if isinstance(pose, dict) else 0.0

        # Risk flagging for suspicious poses
        risk_note = ""
        if pose_class.lower() in ("crouching", "crawling"):
            risk_note = " [SUSPICIOUS: Low posture near ground]"
        elif pose_class.lower() == "running":
            risk_note = " [NOTE: Fast movement detected]"
        elif pose_class.lower() == "lying":
            risk_note = " [NOTE: Person on ground - may need attention]"

        lines.append(f"  Person {det_id}: {pose_class} ({confidence:.0%}){risk_note}")

    return "\n".join(lines)


# ==============================================================================
# Pose/Scene Conflict Resolution (NEM-3011)
# ==============================================================================

# Conflict resolution rules: (pose, scene_keyword) -> winner
# "pose" means prefer pose detection, "scene" means prefer scene analysis
POSE_SCENE_CONFLICTS: dict[tuple[str, str], str] = {
    ("running", "sitting"): "scene",
    ("running", "standing"): "conditional",  # depends on motion blur
    ("crouching", "walking"): "pose",
}


def resolve_pose_scene_conflict(
    pose: str,
    pose_confidence: float,  # noqa: ARG001 - reserved for future use
    scene_description: str,
    has_motion_blur: bool,
) -> dict[str, Any]:
    """Resolve conflicts between pose detection and scene analysis.

    When pose detection ("running") conflicts with scene analysis ("sitting"),
    this function determines which interpretation to trust based on predefined
    rules and contextual signals like motion blur.

    Args:
        pose: The detected pose (e.g., "running", "crouching", "standing")
        pose_confidence: Confidence score from pose detection (0-1)
        scene_description: Natural language description of the scene
        has_motion_blur: Whether motion blur was detected in the image

    Returns:
        Dictionary with:
            - resolved_pose: The pose to use (original pose or "unknown")
            - conflict_detected: Whether a conflict was found
            - resolution: Explanation of the resolution (if conflict detected)

    Example:
        >>> resolve_pose_scene_conflict("running", 0.85, "person sitting", False)
        {'resolved_pose': 'unknown', 'conflict_detected': True,
         'resolution': 'Preferred scene interpretation'}
    """
    if not scene_description:
        return {"resolved_pose": pose, "conflict_detected": False}

    scene_lower = scene_description.lower()

    for (pose_val, scene_val), resolution_rule in POSE_SCENE_CONFLICTS.items():
        if pose.lower() == pose_val and scene_val in scene_lower:
            # Handle conditional rules
            if resolution_rule == "conditional":
                # For running vs standing, motion blur suggests fast movement
                resolved_winner = "pose" if has_motion_blur else "scene"
            else:
                resolved_winner = resolution_rule

            if resolved_winner == "pose":
                return {
                    "resolved_pose": pose,
                    "conflict_detected": True,
                    "resolution": "Preferred pose interpretation",
                }
            else:  # resolved_winner == "scene"
                return {
                    "resolved_pose": "unknown",
                    "conflict_detected": True,
                    "resolution": "Preferred scene interpretation",
                }

    return {"resolved_pose": pose, "conflict_detected": False}


def format_pose_scene_conflict_warning(
    pose: str,
    scene_description: str,
    conflict_result: dict[str, Any],
) -> str | None:
    """Generate a warning message for pose/scene conflicts.

    When a conflict is detected between pose detection and scene analysis,
    this function generates a warning to inject into the prompt to inform
    the LLM about the conflicting signals.

    Args:
        pose: The original detected pose
        scene_description: The scene description from scene analysis
        conflict_result: Result from resolve_pose_scene_conflict()

    Returns:
        Warning string to inject into prompt, or None/empty string if no conflict

    Example:
        >>> warning = format_pose_scene_conflict_warning(
        ...     "running", "sitting on bench",
        ...     {"conflict_detected": True, "resolved_pose": "unknown", ...})
        >>> "SIGNAL CONFLICT" in warning
        True
    """
    if not conflict_result.get("conflict_detected"):
        return None

    # Extract the conflicting scene keyword from the description
    scene_keywords = ["sitting", "standing", "walking", "running", "lying"]
    scene_pose = "unknown"
    scene_lower = scene_description.lower()
    for keyword in scene_keywords:
        if keyword in scene_lower:
            scene_pose = keyword
            break

    warning = (
        f'**SIGNAL CONFLICT**: Pose model detected "{pose}" '
        f'but scene shows "{scene_pose}".\n'
        f"Confidence is LOW for behavioral analysis. Weight other evidence."
    )

    return warning


def format_action_recognition_context(
    action_results: dict[str, Any] | None = None,
) -> str:
    """Format action recognition results for prompt context.

    Args:
        action_results: Dict mapping detection_id to detected actions, or None

    Returns:
        Formatted string for prompt inclusion
    """
    if action_results is None:
        return "Action recognition: Not available"

    if not action_results:
        return "Action recognition: No actions detected"

    lines = ["Detected actions:"]

    # Security-relevant actions with risk levels
    high_risk_actions = frozenset(
        {
            "checking_car_doors",
            "breaking_in",
            "climbing",
            "running_away",
            "hiding",
            "fighting",
            "throwing",
        }
    )
    medium_risk_actions = frozenset(
        {
            "loitering",
            "pacing",
            "looking_around",
            "photographing",
            "crouching",
        }
    )

    for det_id, actions in action_results.items():
        action_list = actions if isinstance(actions, list) else [actions]
        for action in action_list:
            action_name = (
                action.get("action", str(action)) if isinstance(action, dict) else str(action)
            )
            confidence = action.get("confidence", 0.0) if isinstance(action, dict) else 0.0

            risk_level = ""
            if action_name.lower() in high_risk_actions:
                risk_level = " **HIGH RISK**"
            elif action_name.lower() in medium_risk_actions:
                risk_level = " [Suspicious]"

            lines.append(f"  Person {det_id}: {action_name} ({confidence:.0%}){risk_level}")

    return "\n".join(lines)


def format_temporal_action_context(
    action_result: dict[str, Any] | None,
    duration_seconds: float | None = None,
) -> str:
    """Format X-CLIP temporal action recognition results for prompt inclusion.

    This function formats the output from X-CLIP temporal action recognition
    for inclusion in Nemotron risk assessment prompts. It includes the detected
    action, confidence level, optional duration, and applicable risk modifiers.

    Args:
        action_result: Dictionary containing X-CLIP classification results with:
            - detected_action: The classified action string
            - confidence: Float 0-1 representing model confidence
        duration_seconds: Optional duration in seconds the action was observed

    Returns:
        Formatted string for prompt inclusion, or empty string if:
            - action_result is None or empty
            - No detected_action is present
            - Confidence is below 50% threshold

    Example:
        >>> result = format_temporal_action_context(
        ...     {"detected_action": "loitering", "confidence": 0.78},
        ...     duration_seconds=25.0
        ... )
        >>> "loitering" in result
        True
        >>> "+15 points" in result
        True
    """
    if not action_result:
        return ""

    detected_action = action_result.get("detected_action")
    confidence = action_result.get("confidence", 0)

    if not detected_action or confidence < 0.5:
        return ""  # Low confidence, don't include

    lines = ["## BEHAVIORAL ANALYSIS (Temporal)"]
    lines.append(f"Action detected: {detected_action} ({confidence:.0%} confidence)")

    if duration_seconds:
        lines.append(f"Duration: ~{duration_seconds:.0f} seconds across frames")

    # Risk modifiers based on action type
    RISK_MODIFIERS = {
        "loitering": "+15 points (suspicious lingering behavior)",
        "approaching_door": "+10 points (approach detected)",
        "running_away": "+20 points (fleeing behavior)",
        "checking_car_doors": "+25 points (vehicle tampering indicator)",
        "suspicious_behavior": "+20 points (unusual activity)",
        "breaking_in": "+40 points (intrusion indicator)",
        "vandalism": "+35 points (property damage indicator)",
    }

    # Also check for X-CLIP prompt variations
    ACTION_ALIASES = {
        "a person loitering": "loitering",
        "a person approaching a door": "approaching_door",
        "a person running away": "running_away",
        "a person looking around suspiciously": "suspicious_behavior",
        "a person trying a door handle": "checking_car_doors",
        "a person vandalizing property": "vandalism",
        "a person breaking in": "breaking_in",
    }

    normalized_action = ACTION_ALIASES.get(detected_action, detected_action)
    modifier = RISK_MODIFIERS.get(normalized_action)
    if modifier:
        lines.append(f"\u2192 RISK MODIFIER: {modifier}")

    return "\n".join(lines)


def format_vehicle_classification_context(
    vehicle_classifications: dict[str, VehicleClassificationResult],
) -> str:
    """Format vehicle classification results for prompt context.

    Args:
        vehicle_classifications: Dict mapping detection_id to VehicleClassificationResult

    Returns:
        Formatted string for prompt inclusion
    """
    if not vehicle_classifications:
        return "Vehicle classification: No vehicles analyzed"

    lines = []
    for det_id, classification in vehicle_classifications.items():
        vehicle_line = f"Vehicle {det_id}: {classification.display_name}"
        vehicle_line += f" ({classification.confidence:.0%} confidence)"

        if classification.is_commercial:
            vehicle_line += " [Commercial/delivery vehicle]"

        lines.append(vehicle_line)

        # Add alternative if confidence is low
        if classification.confidence < 0.6 and len(classification.all_scores) > 1:
            sorted_scores = sorted(
                classification.all_scores.items(), key=lambda x: x[1], reverse=True
            )
            if len(sorted_scores) > 1:
                alt_type, alt_score = sorted_scores[1]
                lines.append(f"    Alternative: {alt_type} ({alt_score:.1%})")

    return "\n".join(lines)


def format_vehicle_damage_context(
    vehicle_damage: dict[str, VehicleDamageResult],
    time_of_day: str | None = None,
) -> str:
    """Format vehicle damage detection results for prompt context.

    Args:
        vehicle_damage: Dict mapping detection_id to VehicleDamageResult
        time_of_day: Optional time context for risk assessment

    Returns:
        Formatted string for prompt inclusion
    """
    if not vehicle_damage:
        return "Vehicle damage: No vehicles analyzed for damage"

    # Filter to only damaged vehicles
    damaged_vehicles = {k: v for k, v in vehicle_damage.items() if v.has_damage}

    if not damaged_vehicles:
        return "Vehicle damage: No damage detected on any vehicles"

    lines = [f"Vehicle damage detected ({len(damaged_vehicles)} vehicles with damage):"]

    for det_id, damage in damaged_vehicles.items():
        lines.append(f"  Vehicle {det_id}:")
        lines.append(f"    Damage types: {', '.join(sorted(damage.damage_types))}")
        lines.append(f"    Total instances: {damage.total_damage_count}")
        lines.append(f"    Highest confidence: {damage.highest_confidence:.0%}")

        if damage.has_high_security_damage:
            lines.append("    **SECURITY ALERT**: High-priority damage detected")
            if "glass_shatter" in damage.damage_types:
                lines.append("      - Glass shatter: Possible break-in or vandalism")
            if "lamp_broken" in damage.damage_types:
                lines.append("      - Broken lamp: Possible vandalism or collision")

            # Time-based escalation
            if time_of_day and time_of_day.lower() in ("night", "late_night", "early_morning"):
                lines.append(f"    **TIME CONTEXT**: Damage detected during {time_of_day}")
                lines.append("      Elevated risk: Suspicious activity more likely at this hour")

    return "\n".join(lines)


def format_pet_classification_context(
    pet_classifications: dict[str, PetClassificationResult],
) -> str:
    """Format pet classification results for prompt context.

    Args:
        pet_classifications: Dict mapping detection_id to PetClassificationResult

    Returns:
        Formatted string for prompt inclusion
    """
    if not pet_classifications:
        return "Pet classification: No animals detected"

    lines = [f"Pet classification ({len(pet_classifications)} animals):"]

    has_confirmed_pets = False
    for det_id, pet in pet_classifications.items():
        confidence_note = ""
        if pet.confidence >= 0.85:
            confidence_note = " [HIGH CONFIDENCE - likely household pet]"
            has_confirmed_pets = True
        elif pet.confidence >= 0.70:
            confidence_note = " [Probable household pet]"
        else:
            confidence_note = " [Low confidence - may be wildlife]"

        lines.append(
            f"  Animal {det_id}: {pet.animal_type} ({pet.confidence:.0%}){confidence_note}"
        )

    if has_confirmed_pets:
        lines.append("")
        lines.append("  **FALSE POSITIVE NOTE**: High-confidence household pets detected.")
        lines.append("  Consider reducing risk score if no other suspicious activity present.")

    return "\n".join(lines)


def format_depth_context(
    depth_results: DepthAnalysisResult | None = None,
) -> str:
    """Format depth estimation results for prompt context.

    Args:
        depth_results: DepthAnalysisResult from depth_anything_loader, or None

    Returns:
        Formatted string for prompt inclusion
    """
    if depth_results is None:
        return "Depth analysis: Not available"

    if not depth_results.has_detections:
        return "Depth analysis: No detections analyzed"

    # Use the built-in context string method for detailed output
    return depth_results.to_context_string()


def format_image_quality_context(
    quality_result: ImageQualityResult | None,
    quality_change_detected: bool = False,
    quality_change_description: str = "",
) -> str:
    """Format image quality assessment for prompt context.

    Args:
        quality_result: ImageQualityResult from image_quality_loader, or None
        quality_change_detected: Whether a sudden quality change was detected
        quality_change_description: Description of the quality change

    Returns:
        Formatted string for prompt inclusion
    """
    if quality_result is None:
        return "Image quality: Not assessed"

    lines = []

    if quality_result.is_good_quality:
        lines.append(f"Image quality: Good (score: {quality_result.quality_score:.0f}/100)")
    else:
        issues_str = (
            ", ".join(quality_result.quality_issues)
            if quality_result.quality_issues
            else "general degradation"
        )
        lines.append(
            f"Image quality: Issues detected - {issues_str} "
            f"(score: {quality_result.quality_score:.0f}/100)"
        )

        if quality_result.is_blurry:
            lines.append("  - Blur detected: May indicate fast movement or camera issue")
        if quality_result.is_noisy:
            lines.append("  - Noise/artifacts detected: May affect detection accuracy")

    if quality_change_detected:
        lines.append("")
        lines.append(f"**QUALITY ALERT**: {quality_change_description}")
        lines.append("  Possible camera obstruction or tampering - investigate")

    return "\n".join(lines)


def format_camera_health_context(
    camera_id: str,  # noqa: ARG001 - Reserved for future camera-specific context
    recent_scene_changes: list[Any] | None,
) -> str:
    """Format camera health/tampering alerts for prompt.

    This function formats scene tampering detection data (SceneChange model) for
    inclusion in Nemotron prompts. Scene changes indicate potential camera tampering,
    blocked views, or angle changes that affect detection confidence.

    Risk Impact Rules (NEM-3012):
        - view_blocked during intrusion = +30 points to risk score
        - view_tampered + unknown person = escalate to CRITICAL

    Args:
        camera_id: Camera identifier (reserved for future camera-specific context)
        recent_scene_changes: List of SceneChange objects (or any object with
            similarity_score, change_type, and acknowledged attributes).
            Only the first unacknowledged scene change is used.

    Returns:
        Formatted string for prompt inclusion. Returns empty string if no
        unacknowledged scene changes exist.
    """
    # Handle None or empty list gracefully
    if not recent_scene_changes:
        return ""

    # Find the first unacknowledged scene change
    recent = None
    for sc in recent_scene_changes:
        if not getattr(sc, "acknowledged", True):
            recent = sc
            break

    if not recent:
        return ""

    lines = ["## CAMERA HEALTH ALERT"]

    change_type = getattr(recent, "change_type", "unknown")
    similarity_score = getattr(recent, "similarity_score", 0.0)

    if change_type == "view_blocked":
        lines.append(f"Camera view may be BLOCKED (similarity: {similarity_score:.0%})")
        lines.append("Detection confidence is DEGRADED")
        lines.append("RISK MODIFIER: +30 points if intrusion detected during blocked view")
    elif change_type == "angle_changed":
        lines.append(f"Camera angle has CHANGED (similarity: {similarity_score:.0%})")
        lines.append("Baseline patterns may not apply")
    elif change_type == "view_tampered":
        lines.append(f"Possible TAMPERING detected (similarity: {similarity_score:.0%})")
        lines.append("CRITICAL: Verify camera integrity")
        lines.append("ESCALATION: If unknown person detected, escalate to CRITICAL priority")
    else:
        # Unknown or other change types
        lines.append(f"Scene change detected (similarity: {similarity_score:.0%})")
        lines.append("Detection accuracy may be affected")

    return "\n".join(lines)


def format_threat_detection_context(
    threat_result: ThreatDetectionResult | None,
    time_of_day: str | None = None,
) -> str:
    """Format threat/weapon detection results for prompt context.

    Args:
        threat_result: ThreatDetectionResult from threat detection, or None
        time_of_day: Optional time context for risk assessment

    Returns:
        Formatted string for prompt inclusion
    """
    if threat_result is None:
        return "Threat detection: Not performed"

    if not threat_result.has_threats:
        return "Threat detection: No weapons or threatening objects detected"

    lines = ["**WEAPON/THREAT DETECTION**"]

    if threat_result.has_high_priority:
        lines.append("  CRITICAL ALERT: High-priority weapon detected!")
        lines.append("  Immediate review recommended.")

    lines.append(f"  Threats found: {threat_result.threat_summary}")
    lines.append(f"  Highest confidence: {threat_result.highest_confidence:.0%}")

    for threat in sorted(threat_result.threats, key=lambda t: t.confidence, reverse=True)[:5]:
        priority = " **HIGH PRIORITY**" if threat.is_high_priority else ""
        lines.append(f"    - {threat.class_name} ({threat.confidence:.0%}){priority}")

    # Time-based escalation
    if time_of_day and time_of_day.lower() in ("night", "late_night", "early_morning"):
        lines.append(f"  TIME CONTEXT: Detection during {time_of_day}")
        lines.append("  Elevated concern: Armed threat at unusual hour")

    return "\n".join(lines)


def format_age_classification_context(
    age_classifications: dict[str, AgeClassificationResult],
) -> str:
    """Format age classification results for prompt context.

    Args:
        age_classifications: Dict mapping detection_id to AgeClassificationResult

    Returns:
        Formatted string for prompt inclusion
    """
    if not age_classifications:
        return "Age estimation: No persons analyzed"

    lines = [f"Age estimation ({len(age_classifications)} persons):"]

    has_minors = False
    for det_id, age in age_classifications.items():
        confidence_note = ""
        if age.confidence < 0.5:
            confidence_note = " [LOW CONFIDENCE]"
        elif age.confidence < 0.7:
            confidence_note = " [medium confidence]"

        minor_marker = ""
        if age.is_minor:
            minor_marker = " **MINOR**"
            has_minors = True

        lines.append(
            f"  Person {det_id}: {age.display_name} ({age.confidence:.0%})"
            f"{confidence_note}{minor_marker}"
        )

    if has_minors:
        lines.append("")
        lines.append("  **NOTE**: Minor(s) detected - may indicate lost/unaccompanied child")
        lines.append("  Consider context and presence of adults when assessing risk")

    return "\n".join(lines)


def format_gender_classification_context(
    gender_classifications: dict[str, GenderClassificationResult],
) -> str:
    """Format gender classification results for prompt context.

    Args:
        gender_classifications: Dict mapping detection_id to GenderClassificationResult

    Returns:
        Formatted string for prompt inclusion
    """
    if not gender_classifications:
        return "Gender estimation: No persons analyzed"

    lines = [f"Gender estimation ({len(gender_classifications)} persons):"]

    for det_id, gender in gender_classifications.items():
        confidence_note = ""
        if gender.confidence < 0.6:
            confidence_note = " [low confidence]"

        lines.append(
            f"  Person {det_id}: {gender.gender} ({gender.confidence:.0%}){confidence_note}"
        )

    return "\n".join(lines)


def format_person_demographics_context(
    age_classifications: dict[str, AgeClassificationResult] | None,
    gender_classifications: dict[str, GenderClassificationResult] | None,
) -> str:
    """Format combined age and gender demographics for prompt context.

    Combines age and gender classifications into a unified person description
    for each detection ID.

    Args:
        age_classifications: Dict mapping detection_id to AgeClassificationResult, or None
        gender_classifications: Dict mapping detection_id to GenderClassificationResult, or None

    Returns:
        Formatted string combining age and gender for prompt context
    """
    if not age_classifications and not gender_classifications:
        return "Person demographics: Not analyzed"

    # Collect all person IDs
    all_ids: set[str] = set()
    if age_classifications:
        all_ids.update(age_classifications.keys())
    if gender_classifications:
        all_ids.update(gender_classifications.keys())

    if not all_ids:
        return "Person demographics: No persons analyzed"

    lines = [f"Person demographics ({len(all_ids)} persons):"]

    has_minors = False
    for det_id in sorted(all_ids):
        parts = [f"  Person {det_id}:"]

        # Add gender if available
        if gender_classifications and det_id in gender_classifications:
            gender = gender_classifications[det_id]
            parts.append(f" {gender.gender}")

        # Add age if available
        if age_classifications and det_id in age_classifications:
            age = age_classifications[det_id]
            parts.append(f", {age.display_name}")
            if age.is_minor:
                parts.append(" **MINOR**")
                has_minors = True

        # Add confidence notes
        notes = []
        if (
            gender_classifications
            and det_id in gender_classifications
            and gender_classifications[det_id].confidence < 0.6
        ):
            notes.append("gender uncertain")
        if (
            age_classifications
            and det_id in age_classifications
            and age_classifications[det_id].confidence < 0.6
        ):
            notes.append("age uncertain")
        if notes:
            parts.append(f" [{', '.join(notes)}]")

        lines.append("".join(parts))

    if has_minors:
        lines.append("")
        lines.append("  **NOTE**: Minor(s) detected - evaluate context carefully")

    return "\n".join(lines)


def format_person_reid_context(
    reid_matches: dict[str, list[tuple[PersonEmbeddingResult, float]]] | None,
) -> str:
    """Format person re-identification matches for prompt context.

    Args:
        reid_matches: Dict mapping detection_id to list of (match, similarity) tuples,
                     or None if re-id was not performed

    Returns:
        Formatted string for prompt inclusion
    """
    if reid_matches is None:
        return "Person re-identification: Not performed"

    if not reid_matches:
        return "Person re-identification: No matches found (all new individuals)"

    lines = ["Person re-identification:"]

    for det_id, matches in reid_matches.items():
        if not matches:
            lines.append(f"  Person {det_id}: New individual (no prior matches)")
            continue

        # Get top match
        top_match, top_sim = matches[0]
        match_id = top_match.detection_id or "unknown"

        if top_sim >= 0.9:
            lines.append(f"  Person {det_id}: HIGH CONFIDENCE match to {match_id} ({top_sim:.0%})")
        elif top_sim >= 0.8:
            lines.append(f"  Person {det_id}: Likely same person as {match_id} ({top_sim:.0%})")
        else:
            lines.append(f"  Person {det_id}: Possible match to {match_id} ({top_sim:.0%})")

        # Add additional matches if present
        for match, sim in matches[1:3]:
            alt_id = match.detection_id or "unknown"
            lines.append(f"    Alternative: {alt_id} ({sim:.0%})")

    return "\n".join(lines)


def _collect_detection_ids_from_enrichment(
    enrichment_result: EnrichmentResult | None,
    vision_extraction: BatchExtractionResult | None,
) -> dict[str, str]:
    """Collect all detection IDs from enrichment sources and infer their types.

    Returns a dict mapping detection_id to inferred class_name ('person' or 'vehicle').

    Note: Uses getattr with empty dict defaults to handle mock objects in tests
    that may not have all attributes.
    """
    detection_ids: dict[str, str] = {}

    # Collect from enrichment_result
    if enrichment_result:
        # Person detections from clothing/segmentation/pose
        for det_id in getattr(enrichment_result, "clothing_classifications", {}) or {}:
            detection_ids[det_id] = "person"
        for det_id in getattr(enrichment_result, "clothing_segmentation", {}) or {}:
            detection_ids[det_id] = "person"
        for det_id in getattr(enrichment_result, "pose_results", {}) or {}:
            detection_ids[det_id] = "person"

        # Vehicle detections
        for det_id in getattr(enrichment_result, "vehicle_classifications", {}) or {}:
            detection_ids[det_id] = "vehicle"
        for det_id in getattr(enrichment_result, "vehicle_damage", {}) or {}:
            detection_ids[det_id] = "vehicle"

        # Pet detections
        pet_classifications = getattr(enrichment_result, "pet_classifications", {}) or {}
        for det_id in pet_classifications:
            pet = pet_classifications[det_id]
            animal_type = getattr(pet, "animal_type", None)
            detection_ids[det_id] = animal_type or "animal"

    # Collect from vision_extraction (Florence-2)
    if vision_extraction:
        for det_id in getattr(vision_extraction, "person_attributes", {}) or {}:
            if det_id not in detection_ids:
                detection_ids[det_id] = "person"
        for det_id in getattr(vision_extraction, "vehicle_attributes", {}) or {}:
            if det_id not in detection_ids:
                detection_ids[det_id] = "vehicle"

    return detection_ids


def format_detections_with_all_enrichment(
    detections: list[dict[str, Any]],
    enrichment_result: EnrichmentResult | None = None,
    vision_extraction: BatchExtractionResult | None = None,
) -> str:
    """Format detections with all available enrichment data inline.

    Creates a comprehensive view of each detection with all extracted attributes
    for the MODEL_ZOO_ENHANCED prompt.

    Args:
        detections: List of detection dicts with class_name, confidence, bbox, detection_id
        enrichment_result: EnrichmentResult with all enrichment data
        vision_extraction: BatchExtractionResult with Florence-2 attributes

    Returns:
        Formatted string with detections and all their attributes

    Security:
        Sanitizes class_name/object_type to prevent prompt injection via
        adversarial ML model outputs. See NEM-1722.
    """
    # Collect detection IDs from enrichment sources
    enrichment_detection_ids = _collect_detection_ids_from_enrichment(
        enrichment_result, vision_extraction
    )

    # If detections list is empty but we have enrichment data, synthesize detections
    working_detections = list(detections)
    if not working_detections and enrichment_detection_ids:
        for det_id, class_name in enrichment_detection_ids.items():
            working_detections.append(
                {
                    "detection_id": det_id,
                    "class_name": class_name,
                    "confidence": 0.0,  # Unknown from enrichment alone
                    "bbox": [],  # Unknown from enrichment alone
                }
            )

    # Now check if we truly have no detections anywhere
    if not working_detections:
        return "No detections in this batch."

    lines = []

    for det in working_detections:
        det_id = str(det.get("detection_id", det.get("id", "")))
        # Sanitize class_name to prevent prompt injection (NEM-1722)
        raw_class_name = det.get("class_name", det.get("object_type", "unknown"))
        class_name = sanitize_object_type(raw_class_name)
        confidence = det.get("confidence", 0.0)
        bbox = det.get("bbox", [])

        # Base detection info
        bbox_str = f"[{', '.join(str(int(b)) for b in bbox)}]" if bbox else "[]"
        base_line = f"### {class_name.upper()} (ID: {det_id})"
        lines.append(base_line)
        lines.append(f"Confidence: {confidence:.0%}, Location: {bbox_str}")

        # Add Florence-2 vision attributes if available
        # NEM-3304: Validate VQA outputs to filter garbage tokens
        if vision_extraction:
            if det_id in vision_extraction.vehicle_attributes:
                v_attrs = vision_extraction.vehicle_attributes[det_id]
                attr_parts = []
                # Validate each VQA attribute before including (NEM-3304)
                if v_attrs.color and is_valid_vqa_output(v_attrs.color):
                    attr_parts.append(f"Color: {v_attrs.color}")
                if v_attrs.vehicle_type and is_valid_vqa_output(v_attrs.vehicle_type):
                    attr_parts.append(f"Type: {v_attrs.vehicle_type}")
                if v_attrs.is_commercial:
                    commercial = "Commercial vehicle"
                    if v_attrs.commercial_text and is_valid_vqa_output(v_attrs.commercial_text):
                        commercial += f" ({v_attrs.commercial_text})"
                    attr_parts.append(commercial)
                if attr_parts:
                    lines.append(f"Florence-2: {', '.join(attr_parts)}")
                if v_attrs.caption:
                    lines.append(f"Description: {v_attrs.caption}")

            elif det_id in vision_extraction.person_attributes:
                p_attrs = vision_extraction.person_attributes[det_id]
                attr_parts = []
                # Validate each VQA attribute before including (NEM-3304)
                if p_attrs.clothing and is_valid_vqa_output(p_attrs.clothing):
                    attr_parts.append(f"Wearing: {p_attrs.clothing}")
                if p_attrs.carrying and is_valid_vqa_output(p_attrs.carrying):
                    attr_parts.append(f"Carrying: {p_attrs.carrying}")
                if p_attrs.action and is_valid_vqa_output(p_attrs.action):
                    attr_parts.append(f"Action: {p_attrs.action}")
                if p_attrs.is_service_worker:
                    attr_parts.append("Service worker")
                if attr_parts:
                    lines.append(f"Florence-2: {', '.join(attr_parts)}")
                if p_attrs.caption:
                    lines.append(f"Description: {p_attrs.caption}")

        # Add enrichment pipeline data if available
        if enrichment_result:
            # Clothing classification (FashionCLIP)
            if det_id in enrichment_result.clothing_classifications:
                clothing = enrichment_result.clothing_classifications[det_id]
                clothing_line = f"Attire: {clothing.raw_description} ({clothing.confidence:.0%})"
                if clothing.is_suspicious:
                    clothing_line += " **SUSPICIOUS**"
                elif clothing.is_service_uniform:
                    clothing_line += " [Service uniform]"
                lines.append(clothing_line)

            # Clothing segmentation (SegFormer)
            if det_id in enrichment_result.clothing_segmentation:
                seg = enrichment_result.clothing_segmentation[det_id]
                if seg.clothing_items:
                    # Apply mutual exclusion validation (NEM-3010)
                    raw_items = list(seg.clothing_items)
                    confidences = getattr(seg, "coverage_percentages", {}) or {}
                    validated_items = validate_clothing_items(raw_items, confidences)
                    # Sort for deterministic output
                    items_str = ", ".join(sorted(validated_items))
                    lines.append(f"Clothing items: {items_str}")
                if seg.has_face_covered:
                    lines.append("Face covering: DETECTED **ALERT**")
                if seg.has_bag:
                    lines.append("Bag/backpack: Detected")

            # Vehicle classification (ResNet-50)
            if det_id in enrichment_result.vehicle_classifications:
                v_class = enrichment_result.vehicle_classifications[det_id]
                v_line = f"Vehicle type: {v_class.display_name} ({v_class.confidence:.0%})"
                if v_class.is_commercial:
                    v_line += " [Commercial]"
                lines.append(v_line)

            # Vehicle damage (YOLOv11)
            if det_id in enrichment_result.vehicle_damage:
                damage = enrichment_result.vehicle_damage[det_id]
                if damage.has_damage:
                    damage_line = f"Damage: {', '.join(sorted(damage.damage_types))}"
                    if damage.has_high_security_damage:
                        damage_line += " **HIGH SECURITY**"
                    lines.append(damage_line)

            # Pet classification (ResNet-18)
            if det_id in enrichment_result.pet_classifications:
                pet = enrichment_result.pet_classifications[det_id]
                pet_line = f"Pet: {pet.animal_type} ({pet.confidence:.0%})"
                if pet.confidence >= 0.85:
                    pet_line += " [Confirmed household pet - low risk]"
                lines.append(pet_line)

        lines.append("")  # Empty line between detections

    return "\n".join(lines).strip()


# ==============================================================================
# Summary Generation Prompt Templates
# ==============================================================================
# These templates are used by the SummaryGenerator service to create concise
# narrative summaries of security events for dashboard display.

SUMMARY_SYSTEM_PROMPT = """You are a home security analyst providing clear, concise summaries for a homeowner. Your summaries should be informative but not alarming. Focus on facts and actionable information."""

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

SUMMARY_EMPTY_STATE_INSTRUCTION = """If there are no high/critical events to summarize, write a brief reassuring message like:
"No high-priority security events in the past {period}. The property has been quiet with only routine activity detected."
You may mention the count of lower-priority detections if provided."""

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


# ==============================================================================
# Enhanced Re-Identification Context (NEM-3013)
# ==============================================================================


def format_enhanced_reid_context(
    person_id: int,
    entity: EntityLike | None,
    matches: list[Any],  # noqa: ARG001 - Reserved for future use
) -> str:
    """Format re-identification context with proper risk weighting.

    This function generates prompt context that clearly communicates the
    entity's familiarity level and the corresponding risk modifier to the LLM.
    This helps prevent over-scoring familiar/trusted individuals.

    Risk Modifier Table (NEM-3013):
    - Trusted frequent visitor (20+ over 7+ days): -40 points
    - Frequent visitor (20+ over 7+ days, not trusted): -20 points
    - Returning visitor (5+ detections): -10 points
    - Recent visitor (< 5 detections): No modifier
    - First time seen (no entity): Base risk 50

    Args:
        person_id: The detection/person identifier
        entity: Entity object with detection history, or None for first-time
        matches: List of ReIDMatch objects (not used for risk calculation,
                but may be used for additional context in future)

    Returns:
        Formatted string for prompt inclusion with familiarity level
        and risk modifier clearly stated.
    """
    lines = [f"## Person {person_id} Re-Identification"]

    if not entity:
        lines.append(f"Person {person_id}: FIRST TIME SEEN (unknown)")
        lines.append("-> Base risk: 50")
        return "\n".join(lines)

    # Calculate days known
    now = datetime.now(UTC)
    days_known = (now - entity.first_seen_at).days
    detection_count = entity.detection_count
    trust_status = entity.trust_status

    # Determine familiarity level and risk modifier
    if detection_count >= 20 and days_known >= 7:
        # Frequent visitor - check trust status for modifier
        lines.append(f"FREQUENT VISITOR: Seen {detection_count}x over {days_known} days")
        lines.append(f"Trust status: {trust_status}")
        if trust_status == "trusted":
            lines.append("-> RISK MODIFIER: -40 points (established trusted entity)")
        else:
            lines.append("-> RISK MODIFIER: -20 points (familiar but unverified)")
    elif detection_count >= 5:
        # Returning visitor
        lines.append(f"RETURNING VISITOR: Seen {detection_count}x")
        lines.append("-> RISK MODIFIER: -10 points (repeat visitor)")
    else:
        # Recent visitor with insufficient history
        lines.append(f"RECENT VISITOR: Seen {detection_count}x (first: {days_known}d ago)")
        lines.append("-> No risk modifier (insufficient history)")

    return "\n".join(lines)


# ==============================================================================
# Household Context Formatting (NEM-3024, NEM-3315)
# ==============================================================================


class HouseholdMatchLike(Protocol):
    """Protocol for HouseholdMatch-like objects used by format_household_context.

    This protocol allows the function to work with both the actual HouseholdMatch
    dataclass and mock objects in tests.

    Attributes:
        member_id: ID of the matched household member (for person matches)
        member_name: Name of the matched household member
        member_role: Role of the member (resident, family, service_worker, frequent_visitor)
        vehicle_id: ID of the matched registered vehicle
        vehicle_description: Description of the matched vehicle
        similarity: Cosine similarity score (0-1, or 1.0 for exact plate match)
        match_type: Type of match ("person", "license_plate", "vehicle_visual")
        schedule_status: Optional schedule check result (True=within schedule,
                        False=outside schedule, None=no schedule defined)
    """

    member_id: int | None
    member_name: str | None
    vehicle_id: int | None
    vehicle_description: str | None
    similarity: float
    match_type: str


def _get_member_role(match: HouseholdMatchLike) -> str | None:
    """Extract member_role from a HouseholdMatchLike object if available.

    Args:
        match: HouseholdMatchLike object that may have member_role attribute

    Returns:
        The member_role string if present, None otherwise
    """
    return getattr(match, "member_role", None)


def _get_schedule_status(match: HouseholdMatchLike) -> bool | None:
    """Extract schedule_status from a HouseholdMatchLike object if available.

    Args:
        match: HouseholdMatchLike object that may have schedule_status attribute

    Returns:
        The schedule_status (True/False/None) if present, None otherwise
    """
    return getattr(match, "schedule_status", None)


def check_member_schedule(  # noqa: PLR0911
    typical_schedule: dict[str, str] | None,
    current_time: datetime,
) -> bool | None:
    """Check if current time falls within a household member's typical schedule.

    This function interprets the typical_schedule JSONB field from HouseholdMember
    and determines if the current time falls within expected hours.

    Schedule format examples:
        - {"weekdays": "17:00-23:00", "weekends": "all_day"}
        - {"daily": "09:00-18:00"}
        - {"weekdays": "08:00-17:00", "saturday": "10:00-14:00"}

    Time range formats:
        - "HH:MM-HH:MM" - specific time range
        - "all_day" - entire day (00:00-23:59)
        - Empty or None - no schedule constraint

    Args:
        typical_schedule: JSONB dict with schedule specification, or None
        current_time: Current timestamp to check against schedule

    Returns:
        True if within schedule, False if outside schedule, None if no schedule defined

    Example:
        >>> schedule = {"weekdays": "09:00-17:00", "weekends": "all_day"}
        >>> # Monday at 10:00
        >>> check_member_schedule(schedule, datetime(2024, 1, 15, 10, 0))
        True
        >>> # Monday at 22:00
        >>> check_member_schedule(schedule, datetime(2024, 1, 15, 22, 0))
        False
    """
    if not typical_schedule:
        return None

    weekday = current_time.weekday()  # Monday=0, Sunday=6
    current_hour = current_time.hour
    current_minute = current_time.minute
    current_minutes = current_hour * 60 + current_minute

    # Determine which schedule key to use
    is_weekend = weekday >= 5  # Saturday=5, Sunday=6
    is_saturday = weekday == 5
    is_sunday = weekday == 6

    # Try to find applicable schedule in order of specificity
    schedule_value = None

    # Day-specific schedules (most specific)
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    if day_names[weekday] in typical_schedule:
        schedule_value = typical_schedule[day_names[weekday]]
    # Weekend/weekday schedules
    elif is_saturday and "saturday" in typical_schedule:
        schedule_value = typical_schedule["saturday"]
    elif is_sunday and "sunday" in typical_schedule:
        schedule_value = typical_schedule["sunday"]
    elif is_weekend and "weekends" in typical_schedule:
        schedule_value = typical_schedule["weekends"]
    elif not is_weekend and "weekdays" in typical_schedule:
        schedule_value = typical_schedule["weekdays"]
    # Daily schedule (least specific)
    elif "daily" in typical_schedule:
        schedule_value = typical_schedule["daily"]

    if schedule_value is None:
        return None

    # Parse the schedule value
    schedule_value = schedule_value.lower().strip()

    if schedule_value == "all_day":
        return True

    # Parse "HH:MM-HH:MM" format
    if "-" in schedule_value:
        try:
            start_str, end_str = schedule_value.split("-")
            start_parts = start_str.strip().split(":")
            end_parts = end_str.strip().split(":")

            start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])
            end_minutes = int(end_parts[0]) * 60 + int(end_parts[1])

            # Handle overnight schedules (e.g., "22:00-06:00")
            if end_minutes < start_minutes:
                return current_minutes >= start_minutes or current_minutes <= end_minutes
            else:
                return start_minutes <= current_minutes <= end_minutes
        except (ValueError, IndexError):
            _prompts_logger.warning(f"Invalid schedule time format: {schedule_value!r}")
            return None

    return None


def format_household_context(
    person_matches: Sequence[HouseholdMatchLike],
    vehicle_matches: Sequence[HouseholdMatchLike],
    current_time: datetime,  # noqa: ARG001  # Reserved for future schedule-based formatting
) -> str:
    """Format household matching results for prompt injection.

    This function generates prompt context that clearly communicates which
    persons and vehicles are recognized as household members/vehicles.
    Known individuals and vehicles receive reduced base risk scores.

    NEM-3315: Uses Unicode box-drawing characters for visual clarity and
    includes schedule status for known persons.

    Risk Calculation Rules (NEM-3315):
    - Known person within schedule: Base risk 5
    - Known person outside schedule: Base risk 20
    - Registered vehicle: Cap risk at 10 (min with person risk)
    - Unknown person: Base risk 50

    Args:
        person_matches: List of HouseholdMatch objects for matched persons.
                       Objects may optionally have member_role and schedule_status
                       attributes for enhanced context display.
        vehicle_matches: List of HouseholdMatch objects for matched vehicles
        current_time: Current timestamp for display in output

    Returns:
        Formatted string for prompt inclusion with risk modifiers clearly stated.

    Example output:
        ## RISK MODIFIERS (Apply These First)
        +----------------------------------------------------------------+
        | KNOWN PERSON: Mike (resident, 93% match)                       |
        |   Schedule: Within expected hours                              |
        | REGISTERED VEHICLE: Silver Tesla Model 3                       |
        +----------------------------------------------------------------+
        -> Calculated base risk: 5
    """
    # Box-drawing characters for visual formatting
    # Using ASCII characters for broad terminal compatibility
    box_width = 64
    top_border = "+" + "-" * box_width + "+"
    bottom_border = "+" + "-" * box_width + "+"

    lines = ["## RISK MODIFIERS (Apply These First)"]
    lines.append(top_border)

    base_risk = 50  # Default for unknown

    # Format person matches
    if person_matches:
        for match in person_matches:
            similarity_pct = int(match.similarity * 100)

            # Get optional attributes
            member_role = _get_member_role(match)
            schedule_status = _get_schedule_status(match)

            # Format person line with role if available
            if member_role:
                person_line = (
                    f"| KNOWN PERSON: {match.member_name} ({member_role}, {similarity_pct}% match)"
                )
            else:
                person_line = f"| KNOWN PERSON: {match.member_name} ({similarity_pct}% match)"
            lines.append(person_line)

            # Format schedule status if available (NEM-3315)
            if schedule_status is True:
                lines.append("|   Schedule: Within expected hours")
                base_risk = 5
            elif schedule_status is False:
                lines.append("|   Schedule: Outside normal hours")
                base_risk = 20
            else:
                # No schedule defined - use similarity-based risk (legacy behavior)
                base_risk = 5 if match.similarity > 0.9 else 15
    else:
        lines.append("| KNOWN PERSON MATCH: None (unknown individual)")

    # Format vehicle matches
    if vehicle_matches:
        for match in vehicle_matches:
            lines.append(f"| REGISTERED VEHICLE: {match.vehicle_description}")
            # Vehicle match caps base risk at 10 (takes minimum)
            base_risk = min(base_risk, 10)

    lines.append(bottom_border)
    lines.append(f"-> Calculated base risk: {base_risk}")

    return "\n".join(lines)


# ==============================================================================
# Conditional Section Building (NEM-3020)
# ==============================================================================
# These functions build prompt sections conditionally, only including sections
# that have actual meaningful data. Empty or unhelpful sections like
# "Violence analysis: Not performed" are NOT included.


class EnrichmentResultLike(Protocol):
    """Protocol for EnrichmentResult-like objects used by build_enrichment_sections.

    This protocol allows the function to work with both the actual EnrichmentResult
    class and mock objects in tests.
    """

    violence_detection: Any | None
    clothing_classifications: dict[str, Any]
    clothing_segmentation: dict[str, Any] | None
    pose_results: dict[str, Any]
    vehicle_damage: dict[str, Any]
    pet_classifications: dict[str, Any]


def _format_violence_section(violence_result: Any) -> str | None:
    """Format violence section ONLY if violence is detected.

    Returns None if violence is not detected (avoids unhelpful "No violence detected").

    Args:
        violence_result: ViolenceDetectionResult or mock with is_violent attribute

    Returns:
        Formatted violence alert string, or None if no violence detected
    """
    if violence_result is None:
        return None

    if not getattr(violence_result, "is_violent", False):
        return None

    # Violence detected - format the alert
    confidence = getattr(violence_result, "confidence", 0.0)
    violent_score = getattr(violence_result, "violent_score", 0.0)
    non_violent_score = getattr(violence_result, "non_violent_score", 0.0)

    return (
        f"**VIOLENCE DETECTED** (confidence: {confidence:.0%})\n"
        f"  Violent score: {violent_score:.0%}\n"
        f"  Non-violent score: {non_violent_score:.0%}\n"
        f"  ACTION REQUIRED: Immediate review recommended"
    )


def _format_clothing_section(
    clothing_classifications: dict[str, Any],
    clothing_segmentation: dict[str, Any] | None = None,
) -> str | None:
    """Format clothing section ONLY if there's meaningful data.

    Returns None if no clothing classifications exist.

    Args:
        clothing_classifications: Dict of clothing classifications
        clothing_segmentation: Optional dict of segmentation results

    Returns:
        Formatted clothing analysis string, or None if no data
    """
    if not clothing_classifications:
        return None

    # Use the existing format function, which handles all the formatting logic
    result = format_clothing_analysis_context(clothing_classifications, clothing_segmentation)

    # Check if the result is just the "no data" placeholder
    if result == "Clothing analysis: No person detections analyzed":
        return None
    if result == "Clothing analysis: No results":
        return None

    return result


def _format_pose_section(pose_results: dict[str, Any]) -> str | None:
    """Format pose section ONLY if high confidence poses exist (> 0.7).

    Returns None if no poses or all poses are low confidence.

    Args:
        pose_results: Dict mapping detection_id to PoseResult-like objects

    Returns:
        Formatted pose analysis string, or None if no high-confidence poses
    """
    if not pose_results:
        return None

    # Filter to only high-confidence poses
    high_conf_poses: dict[str, dict[str, Any]] = {}
    for det_id, pose in pose_results.items():
        # Handle both PoseResult objects and dict representations
        if hasattr(pose, "pose_confidence"):
            confidence = pose.pose_confidence
            pose_class = pose.pose_class
        else:
            confidence = pose.get("confidence", 0.0) if isinstance(pose, dict) else 0.0
            pose_class = (
                pose.get("classification", str(pose)) if isinstance(pose, dict) else str(pose)
            )

        if confidence > 0.7:
            high_conf_poses[det_id] = {"classification": pose_class, "confidence": confidence}

    if not high_conf_poses:
        return None

    # Use existing format function with filtered poses
    return format_pose_analysis_context(high_conf_poses)


def _format_vehicle_damage_section(
    vehicle_damage: dict[str, Any],
    time_of_day: str | None = None,
) -> str | None:
    """Format vehicle damage section ONLY if damage is detected.

    Returns None if no vehicles have damage.

    Args:
        vehicle_damage: Dict mapping detection_id to VehicleDamageResult-like objects
        time_of_day: Optional time context for risk assessment

    Returns:
        Formatted vehicle damage string, or None if no damage
    """
    if not vehicle_damage:
        return None

    # Filter to only vehicles with actual damage
    damaged = {k: v for k, v in vehicle_damage.items() if getattr(v, "has_damage", False)}

    if not damaged:
        return None

    # Use existing format function with only damaged vehicles
    return format_vehicle_damage_context(damaged, time_of_day)


def _format_pet_section(pet_classifications: dict[str, Any]) -> str | None:
    """Format pet section ONLY if high-confidence pets are detected (> 85%).

    High-confidence pets help reduce false positives by informing the LLM
    that the detection may be a household pet rather than a threat.

    Args:
        pet_classifications: Dict mapping detection_id to PetClassificationResult-like objects

    Returns:
        Formatted pet detection string, or None if no high-confidence pets
    """
    if not pet_classifications:
        return None

    # Filter to only high-confidence pets (> 85%)
    high_conf_pets = {
        k: v for k, v in pet_classifications.items() if getattr(v, "confidence", 0.0) > 0.85
    }

    if not high_conf_pets:
        return None

    # Use existing format function with only high-confidence pets
    return format_pet_classification_context(high_conf_pets)


def build_enrichment_sections(enrichment_result: EnrichmentResultLike) -> str:
    """Build enrichment sections, ONLY including those with actual data.

    This function conditionally includes prompt sections based on whether
    meaningful data exists. Empty or unhelpful sections like "Violence analysis:
    Not performed" are NOT included, reducing prompt noise.

    Section Inclusion Rules:
    - Violence: Only if is_violent=True
    - Clothing: Only if classifications exist
    - Pose: Only if confidence > 0.7
    - Vehicle damage: Only if has_damage=True
    - Pets: Only if confidence > 85% (helps reduce FPs)

    DON'T include:
    - "Violence analysis: Not performed"
    - "Vehicle classification: No vehicles analyzed"
    - Empty pose/action sections
    - Low confidence data

    Args:
        enrichment_result: EnrichmentResult or mock object with the required attributes

    Returns:
        Formatted string with sections separated by double newlines,
        or empty string if no meaningful data exists.

    Example:
        >>> result = build_enrichment_sections(enrichment_with_violence)
        >>> "VIOLENCE DETECTED" in result
        True
        >>> result = build_enrichment_sections(empty_enrichment)
        >>> result == ""
        True
    """
    sections: list[str] = []

    # Violence - only if detected
    violence_section = _format_violence_section(enrichment_result.violence_detection)
    if violence_section:
        sections.append(violence_section)

    # Clothing - only if meaningful results
    clothing_section = _format_clothing_section(
        enrichment_result.clothing_classifications,
        getattr(enrichment_result, "clothing_segmentation", None),
    )
    if clothing_section:
        sections.append(clothing_section)

    # Pose - only if high confidence
    pose_section = _format_pose_section(enrichment_result.pose_results)
    if pose_section:
        sections.append(pose_section)

    # Vehicle damage - only if detected
    vehicle_damage_section = _format_vehicle_damage_section(enrichment_result.vehicle_damage)
    if vehicle_damage_section:
        sections.append(vehicle_damage_section)

    # Pet detection - always include if high confidence pet found (helps reduce FPs)
    pet_section = _format_pet_section(enrichment_result.pet_classifications)
    if pet_section:
        sections.append(pet_section)

    return "\n\n".join(sections) if sections else ""


# ==============================================================================
# On-Demand Model Enrichment Context (NEM-3041)
# ==============================================================================
# These functions format new enrichment types from the model zoo for the
# Nemotron prompt: pose estimation, threat detection, demographics,
# re-identification embeddings, and action recognition.


@dataclass
class ThreatInfo:
    """Information about a detected threat.

    Attributes:
        threat_type: Type of threat (e.g., "gun", "knife", "weapon")
        severity: Severity level ("low", "medium", "high", "critical")
        confidence: Confidence score (0-1)
    """

    threat_type: str
    severity: str
    confidence: float


class ThreatResultLike(Protocol):
    """Protocol for threat detection result-like objects.

    This protocol allows the formatting functions to work with both
    the actual ThreatDetectionResult class and mock objects in tests.
    """

    has_threat: bool
    threats: list[dict[str, Any]]


class DemographicsResultLike(Protocol):
    """Protocol for demographics result-like objects."""

    age_range: str
    gender: str
    confidence: float


class ActionResultLike(Protocol):
    """Protocol for action recognition result-like objects."""

    action: str
    confidence: float
    is_suspicious: bool


class VehicleAttributesLike(Protocol):
    """Protocol for vehicle attributes from enrichment."""

    color: str | None
    make: str | None
    model: str | None
    vehicle_type: str
    confidence: float


class OnDemandEnrichmentLike(Protocol):
    """Protocol for on-demand enrichment result-like objects.

    This protocol defines the interface for enrichment results that include
    the new model zoo enrichments: pose, threat, demographics, action, reid.
    """

    pose: Any | None
    clothing: Any | None
    demographics: DemographicsResultLike | None
    action: dict[str, Any] | None
    reid_embedding: list[float] | None
    threat: ThreatResultLike | None
    vehicle: VehicleAttributesLike | None


def build_person_analysis_section(enrichment: OnDemandEnrichmentLike) -> str:
    """Build person analysis section for prompt.

    Combines pose, clothing, demographics, action recognition, and re-ID
    data into a structured section for Nemotron analysis.

    Args:
        enrichment: OnDemandEnrichmentLike object containing person enrichment data

    Returns:
        Formatted string for prompt inclusion, or "No person analysis available."
        if no data exists.

    Example:
        >>> result = build_person_analysis_section(enrichment_with_pose)
        >>> "### Pose & Posture" in result
        True
    """
    sections: list[str] = []

    # Pose & Posture
    if enrichment.pose is not None:
        pose = enrichment.pose
        # Handle both PoseResult objects and dict representations
        if hasattr(pose, "pose_class"):
            pose_class = pose.pose_class
            pose_confidence = pose.pose_confidence
            pose_suspicious = pose_class.lower() in ("crouching", "crawling", "lying")
        else:
            pose_class = pose.get("pose_class", pose.get("classification", "unknown"))
            pose_confidence = pose.get("pose_confidence", pose.get("confidence", 0.0))
            pose_suspicious = pose_class.lower() in ("crouching", "crawling", "lying")

        pose_text = f"""### Pose & Posture
- Detected pose: {pose_class}
- Confidence: {pose_confidence:.1%}
- Suspicious posture: {"YES" if pose_suspicious else "No"}"""
        sections.append(pose_text)

    # Appearance/Clothing
    if enrichment.clothing is not None:
        clothing = enrichment.clothing
        # Handle both ClothingClassification objects and dict representations
        if hasattr(clothing, "categories"):
            categories = (
                clothing.categories[:3] if hasattr(clothing.categories, "__getitem__") else []
            )
            categories_str = ", ".join(
                [f"{c.get('category', c)} ({c.get('confidence', 0):.0%})" for c in categories]
            )
            clothing_suspicious = getattr(clothing, "is_suspicious", False)
        elif hasattr(clothing, "raw_description"):
            categories_str = clothing.raw_description
            clothing_suspicious = getattr(clothing, "is_suspicious", False)
        elif isinstance(clothing, dict):
            categories = clothing.get("categories", [])[:3]
            if categories and isinstance(categories[0], dict):
                categories_str = ", ".join(
                    [
                        f"{c.get('category', str(c))} ({c.get('confidence', 0):.0%})"
                        for c in categories
                    ]
                )
            else:
                categories_str = ", ".join(str(c) for c in categories) if categories else "unknown"
            clothing_suspicious = clothing.get("is_suspicious", False)
        else:
            categories_str = str(clothing)
            clothing_suspicious = False

        clothing_text = f"""### Appearance
- Clothing: {categories_str}
- Suspicious attire: {"YES" if clothing_suspicious else "No"}"""
        sections.append(clothing_text)

    # Demographics
    if enrichment.demographics is not None:
        demo = enrichment.demographics
        # Handle both DemographicsResult objects and dict representations
        age_range: str
        gender: str
        if hasattr(demo, "age_range"):
            age_range = demo.age_range
            gender = demo.gender
        elif isinstance(demo, dict):
            age_range = str(demo.get("age_range") or demo.get("age_group") or "unknown")
            gender = str(demo.get("gender") or "unknown")
        else:
            age_range = "unknown"
            gender = "unknown"

        demo_text = f"""### Demographics
- Estimated age: {age_range}
- Gender: {gender}"""
        sections.append(demo_text)

    # Action Recognition
    if enrichment.action is not None:
        action = enrichment.action
        # Handle both ActionResult objects and dict representations
        action_name: str
        confidence: float
        is_suspicious: bool
        if hasattr(action, "action") and hasattr(action, "confidence"):
            action_name = str(action.action)
            confidence = float(action.confidence)
            is_suspicious = bool(getattr(action, "is_suspicious", False))
        elif isinstance(action, dict):
            action_name = str(action.get("action") or action.get("top_action") or "unknown")
            confidence = float(action.get("confidence") or 0.0)
            is_suspicious = bool(action.get("is_suspicious", False))
        else:
            action_name = str(action)
            confidence = 0.0
            is_suspicious = False

        action_text = f"""### Behavior
- Detected action: {action_name}
- Confidence: {confidence:.1%}
- Suspicious behavior: {"YES" if is_suspicious else "No"}"""
        sections.append(action_text)

    # Re-ID
    if enrichment.reid_embedding is not None:
        reid_text = """### Identity
- Re-ID embedding extracted for tracking"""
        sections.append(reid_text)

    if not sections:
        return "No person analysis available."

    return "\n\n".join(sections)


def build_threat_section(enrichment: OnDemandEnrichmentLike) -> str:
    """Build threat detection section for prompt.

    Formats weapon/threat detection results with severity and confidence.

    Args:
        enrichment: OnDemandEnrichmentLike object containing threat detection data

    Returns:
        Formatted string for prompt inclusion, or "No threats detected."
        if no threats are present.

    Example:
        >>> result = build_threat_section(enrichment_with_weapon)
        >>> "THREATS DETECTED" in result
        True
    """
    if enrichment.threat is None:
        return "No threats detected."

    threat = enrichment.threat

    # Handle ThreatResultLike protocol
    has_threat: bool
    threats: list[dict[str, Any]]
    if hasattr(threat, "has_threat"):
        has_threat = bool(threat.has_threat)
        threats = threat.threats if hasattr(threat, "threats") else []
    elif isinstance(threat, dict):
        has_threat = bool(threat.get("has_threat") or threat.get("threats_detected", False))
        threats = threat.get("threats", [])
    else:
        return "No threats detected."

    if not has_threat:
        return "No threats detected."

    threat_lines = ["**THREATS DETECTED:**"]
    for t in threats:
        threat_type: str
        severity: str
        t_confidence: float
        if isinstance(t, dict):
            threat_type = str(t.get("threat_type") or t.get("type") or "unknown")
            severity = str(t.get("severity") or "high")
            t_confidence = float(t.get("confidence") or 0.0)
        else:
            threat_type = str(getattr(t, "threat_type", "unknown"))
            severity = str(getattr(t, "severity", "high"))
            t_confidence = float(getattr(t, "confidence", 0.0))

        threat_lines.append(
            f"- {threat_type.upper()} (severity: {severity}, confidence: {t_confidence:.0%})"
        )

    return "\n".join(threat_lines)


def build_vehicle_section(enrichment: OnDemandEnrichmentLike) -> str:
    """Build vehicle analysis section for prompt.

    Formats vehicle classification data including color, make, model, and type.

    Args:
        enrichment: OnDemandEnrichmentLike object containing vehicle classification data

    Returns:
        Formatted string for prompt inclusion, or "No vehicle detected."
        if no vehicle data exists.

    Example:
        >>> result = build_vehicle_section(enrichment_with_vehicle)
        >>> "Vehicle:" in result
        True
    """
    if enrichment.vehicle is None:
        return "No vehicle detected."

    v = enrichment.vehicle

    # Handle VehicleAttributesLike protocol
    color: str | None
    make: str | None
    model: str | None
    vehicle_type: str
    v_confidence: float
    if hasattr(v, "vehicle_type"):
        color = getattr(v, "color", None)
        make = getattr(v, "make", None)
        model = getattr(v, "model", None)
        vehicle_type = str(v.vehicle_type)
        v_confidence = float(getattr(v, "confidence", 0.0))
    elif isinstance(v, dict):
        color = v.get("color")
        make = v.get("make")
        model = v.get("model")
        vehicle_type = str(v.get("vehicle_type") or v.get("type") or "vehicle")
        v_confidence = float(v.get("confidence") or 0.0)
    else:
        return "No vehicle detected."

    parts: list[str] = []
    if color:
        parts.append(color)
    if make:
        parts.append(make)
    if model:
        parts.append(model)
    parts.append(vehicle_type)

    return f"Vehicle: {' '.join(parts)} (confidence: {v_confidence:.0%})"


def format_ondemand_enrichment_context(enrichment: OnDemandEnrichmentLike) -> str:
    """Format on-demand model enrichment for Nemotron.

    Creates a comprehensive context string combining all on-demand model
    results: threat detection, pose analysis, demographics, action recognition,
    re-identification, and vehicle analysis.

    This is the main entry point for formatting new model zoo enrichments
    into the Nemotron prompt.

    Args:
        enrichment: OnDemandEnrichmentLike object containing all enrichment data

    Returns:
        Formatted string with all enrichment sections, or empty string if
        no meaningful data exists.

    Example:
        >>> result = format_ondemand_enrichment_context(full_enrichment)
        >>> "### Pose & Posture" in result
        True
    """
    sections: list[str] = []

    # Threat detection (CRITICAL - always first if present)
    threat_section = build_threat_section(enrichment)
    if threat_section != "No threats detected.":
        # Add prominent header for threats
        sections.append(f"### THREAT DETECTION\n{threat_section}")

    # Person analysis (pose, clothing, demographics, action, reid)
    person_section = build_person_analysis_section(enrichment)
    if person_section != "No person analysis available.":
        sections.append(f"## Person Analysis\n{person_section}")

    # Vehicle analysis
    vehicle_section = build_vehicle_section(enrichment)
    if vehicle_section != "No vehicle detected.":
        sections.append(f"### Vehicle Analysis\n{vehicle_section}")

    return "\n\n".join(sections) if sections else ""


def format_enhanced_clothing_context(clothing_result: dict[str, Any] | None) -> str:
    """Format enhanced clothing analysis for Nemotron.

    Provides detailed clothing context including suspicious attire detection,
    service uniform identification, and carried items.

    Args:
        clothing_result: Dictionary containing enhanced clothing analysis results
            with keys like "suspicious", "delivery", "utility", "carrying", "casual"

    Returns:
        Formatted string for prompt inclusion, or empty string if no data.

    Example:
        >>> result = format_enhanced_clothing_context({"suspicious": {"confidence": 0.8, ...}})
        >>> "ALERT" in result
        True
    """
    if not clothing_result:
        return ""

    lines = ["### Person Appearance Analysis"]

    # Primary classification - suspicious attire
    if clothing_result.get("suspicious"):
        susp = clothing_result["suspicious"]
        confidence = (
            susp.get("confidence", 0.0)
            if isinstance(susp, dict)
            else getattr(susp, "confidence", 0.0)
        )
        top_match = (
            susp.get("top_match", "suspicious attire") if isinstance(susp, dict) else str(susp)
        )
        if confidence > 0.6:
            lines.append(f"- **ALERT**: {top_match} (confidence: {confidence:.0%})")

    # Service uniform detection
    if clothing_result.get("delivery"):
        deliv = clothing_result["delivery"]
        confidence = (
            deliv.get("confidence", 0.0)
            if isinstance(deliv, dict)
            else getattr(deliv, "confidence", 0.0)
        )
        top_match = (
            deliv.get("top_match", "delivery uniform") if isinstance(deliv, dict) else str(deliv)
        )
        if confidence > 0.5:
            lines.append(f"- Service worker identified: {top_match} ({confidence:.0%})")

    # Utility workers
    if clothing_result.get("utility"):
        util = clothing_result["utility"]
        confidence = (
            util.get("confidence", 0.0)
            if isinstance(util, dict)
            else getattr(util, "confidence", 0.0)
        )
        top_match = util.get("top_match", "utility worker") if isinstance(util, dict) else str(util)
        if confidence > 0.5:
            lines.append(f"- Utility worker identified: {top_match} ({confidence:.0%})")

    # Carrying items - critical for risk assessment
    if clothing_result.get("carrying"):
        carry = clothing_result["carrying"]
        confidence = (
            carry.get("confidence", 0.0)
            if isinstance(carry, dict)
            else getattr(carry, "confidence", 0.0)
        )
        top_match = (
            carry.get("top_match", "carrying item") if isinstance(carry, dict) else str(carry)
        )
        lines.append(f"- Carrying: {top_match} ({confidence:.0%})")

    # General attire
    if clothing_result.get("casual"):
        casual = clothing_result["casual"]
        top_match = (
            casual.get("top_match", "casual attire") if isinstance(casual, dict) else str(casual)
        )
        lines.append(f"- General attire: {top_match}")

    if len(lines) == 1:  # Only header, no content
        return ""

    return "\n".join(lines)


def format_florence_scene_context(florence_result: dict[str, Any] | None) -> str:
    """Format Florence-2 enhanced extraction for Nemotron.

    Provides detailed scene context from Florence-2 including scene description,
    security-relevant objects, and detected text.

    Args:
        florence_result: Dictionary containing Florence-2 extraction results
            with keys like "scene", "security_objects", "text_regions"

    Returns:
        Formatted string for prompt inclusion, or empty string if no data.

    Example:
        >>> result = format_florence_scene_context({"scene": "A person walking...", ...})
        >>> "Scene Analysis" in result
        True
    """
    if not florence_result:
        return ""

    lines = ["### Scene Analysis (Florence-2)"]

    # Detailed scene description
    if florence_result.get("scene"):
        lines.append(f"\n**Scene Description:**\n{florence_result['scene']}")

    # Security-relevant objects detected
    if florence_result.get("security_objects"):
        objects = florence_result["security_objects"]
        labels = objects.get("labels", []) if isinstance(objects, dict) else []
        if labels:
            lines.append(f"\n**Objects Detected:** {', '.join(labels)}")

            # Flag high-risk objects
            high_risk = {"weapon", "knife", "crowbar", "tool", "gun"}
            detected_risks = [o for o in labels if any(r in o.lower() for r in high_risk)]
            if detected_risks:
                lines.append(f"- **HIGH RISK OBJECTS**: {', '.join(detected_risks)}")

    # Text/plates found
    if florence_result.get("text_regions"):
        texts = florence_result["text_regions"]
        labels = texts.get("labels", []) if isinstance(texts, dict) else []
        if labels:
            lines.append(f"\n**Visible Text:** {', '.join(labels)}")

    if len(lines) == 1:  # Only header, no content
        return ""

    return "\n".join(lines)


# ==============================================================================
# Rubric-Based Scoring (NEM-3728)
# ==============================================================================
# For explicit rubric-based risk scoring using the LLM-as-a-Judge pattern,
# see the risk_rubrics module which provides:
# - RUBRIC_ENHANCED_PROMPT: Prompt template with embedded rubric definitions
# - RubricScores: Pydantic model for validating rubric-based LLM output
# - calculate_risk_score: Function to compute risk from rubric scores
# - Predefined rubrics: THREAT_LEVEL_RUBRIC, INTENT_RUBRIC, TIME_CONTEXT_RUBRIC
#
# Import from backend.services.risk_rubrics for rubric-based scoring.
