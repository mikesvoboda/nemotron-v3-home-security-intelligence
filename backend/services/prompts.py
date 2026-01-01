"""Prompt templates for AI analysis services.

This module contains prompt templates used by the Nemotron analyzer
to generate risk assessments from security camera detections.

Nemotron-3-Nano uses ChatML format with <|im_start|> and <|im_end|> tags.
The model outputs <think>...</think> reasoning blocks before the response.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.services.enrichment_pipeline import EnrichmentResult
    from backend.services.fashion_clip_loader import ClothingClassification
    from backend.services.image_quality_loader import ImageQualityResult
    from backend.services.pet_classifier_loader import PetClassificationResult
    from backend.services.segformer_loader import ClothingSegmentationResult
    from backend.services.vehicle_classifier_loader import VehicleClassificationResult
    from backend.services.vehicle_damage_loader import VehicleDamageResult
    from backend.services.violence_loader import ViolenceDetectionResult
    from backend.services.vision_extractor import BatchExtractionResult
    from backend.services.weather_loader import WeatherResult

# Basic prompt template (legacy, used as fallback)
RISK_ANALYSIS_PROMPT = """<|im_start|>system
You are a home security risk analyzer. Provide detailed reasoning. Output valid JSON only.<|im_end|>
<|im_start|>user
Analyze these detections and output a JSON risk assessment.

Camera: {camera_name}
Time: {start_time} to {end_time}
Detections:
{detections_list}

Consider in your analysis:
- Time of day context (late night activity is more concerning)
- Object combinations (person + vehicle vs person alone)
- Detection confidence levels
- Number and frequency of detections
- Potential benign explanations (delivery, neighbor, wildlife)

Risk levels: low (0-29), medium (30-59), high (60-84), critical (85-100)

Output JSON with detailed reasoning that explains your risk assessment:
{{"risk_score": N, "risk_level": "level", "summary": "1-2 sentence summary", "reasoning": "detailed multi-sentence explanation of factors considered and why this risk level was assigned"}}<|im_end|>
<|im_start|>assistant
"""

# Enhanced prompt template with context enrichment
ENRICHED_RISK_ANALYSIS_PROMPT = """<|im_start|>system
You are a home security risk analyzer. Output valid JSON only.<|im_end|>
<|im_start|>user
Analyze these detections and output a JSON risk assessment.

## Camera Context
Camera: {camera_name}
Time: {start_time} to {end_time}
Day: {day_of_week}

## Zone Analysis
{zone_analysis}

## Baseline Comparison
Expected activity for {hour}:00 on {day_of_week}:
{baseline_comparison}

Deviation score: {deviation_score} (0=normal, 1=highly unusual)

## Cross-Camera Activity
{cross_camera_summary}

## Detections
{detections_list}

## Risk Interpretation Guide
- entry_point detections: Higher concern, especially unknown persons
- Baseline deviation > 0.5: Unusual activity pattern
- Cross-camera correlation: May indicate coordinated movement
- Time of day: Late night activity more concerning

## Risk Levels
- low (0-29): Normal activity, no action needed
- medium (30-59): Notable activity, worth reviewing
- high (60-84): Suspicious activity, recommend alert
- critical (85-100): Immediate threat, urgent action

Output format: {{"risk_score": N, "risk_level": "level", "summary": "text", "reasoning": "text", "recommended_action": "text"}}<|im_end|>
<|im_start|>assistant
"""

# Full enriched prompt with vision enrichment (plates, faces, OCR)
# Used when both context enrichment and enrichment pipeline are available
FULL_ENRICHED_RISK_ANALYSIS_PROMPT = """<|im_start|>system
You are a home security risk analyzer. Output valid JSON only.<|im_end|>
<|im_start|>user
Analyze these detections and output a JSON risk assessment.

## Camera Context
Camera: {camera_name}
Time: {start_time} to {end_time}
Day: {day_of_week}

## Zone Analysis
{zone_analysis}

## Baseline Comparison
Expected activity for {hour}:00 on {day_of_week}:
{baseline_comparison}

Deviation score: {deviation_score} (0=normal, 1=highly unusual)

## Cross-Camera Activity
{cross_camera_summary}

## Vision Enrichment
{enrichment_context}

## Detections
{detections_list}

## Risk Interpretation Guide
- entry_point detections: Higher concern, especially unknown persons
- Baseline deviation > 0.5: Unusual activity pattern
- Cross-camera correlation: May indicate coordinated movement
- Time of day: Late night activity more concerning
- License plates: Known vs unknown vehicles, partial plates may indicate evasion
- Faces detected: Presence of faces helps identify individuals for review

## Risk Levels
- low (0-29): Normal activity, no action needed
- medium (30-59): Notable activity, worth reviewing
- high (60-84): Suspicious activity, recommend alert
- critical (85-100): Immediate threat, urgent action

Output format: {{"risk_score": N, "risk_level": "level", "summary": "text", "reasoning": "text", "recommended_action": "text"}}<|im_end|>
<|im_start|>assistant
"""

# Vision-enhanced prompt with Florence-2 attributes, re-identification, and scene analysis
# Used when full vision extraction pipeline is available
VISION_ENHANCED_RISK_ANALYSIS_PROMPT = """<|im_start|>system
You are a home security risk analyzer. Provide detailed reasoning. Output valid JSON only.<|im_end|>
<|im_start|>user
Analyze this security event and provide a risk assessment.

## Camera & Time
Camera: {camera_name}
Time: {timestamp}
Day: {day_of_week}
Lighting: {time_of_day}

## Detections with Attributes
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
- Service workers: Usually lower risk (delivery, utility)
- Unusual objects: Tools, abandoned items increase risk
- Time context: Late night + artificial light = concerning
- Behavioral cues: Crouching, loitering, repeated passes

## Risk Levels
- low (0-29): Normal activity
- medium (30-59): Notable, worth reviewing
- high (60-84): Suspicious, recommend alert
- critical (85-100): Immediate threat

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
You are an advanced home security risk analyzer with access to comprehensive AI-enriched detection data. Provide detailed reasoning. Output valid JSON only.<|im_end|>
<|im_start|>user
Analyze this security event with full AI enrichment and provide a detailed risk assessment.

## Camera & Time Context
Camera: {camera_name}
Time: {timestamp}
Day: {day_of_week}
Lighting: {time_of_day}

## Environmental Context
{weather_context}
{image_quality_context}

## Detections with Full Enrichment
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
- High-visibility vest or delivery uniform = likely service worker (lower risk)
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

### Image Quality
- Sudden quality drop = possible camera obstruction/tampering
- Motion blur + person = fast movement (running)
- Consistent low quality = camera maintenance needed

### Time Context
- Late night (11pm-5am) + artificial light = concerning
- Business hours + service uniform = normal activity
- Weekend + unknown vehicle = note but lower concern

### Risk Levels
- low (0-29): Normal activity, no action needed
- medium (30-59): Notable activity, worth reviewing
- high (60-84): Suspicious activity, recommend alert
- critical (85-100): Immediate threat, urgent action required

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
                person_lines.append(f"  Clothing items: {', '.join(seg.clothing_items)}")
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
    depth_results: dict[str, Any] | None = None,
) -> str:
    """Format depth estimation results for prompt context.

    Args:
        depth_results: Dict with depth analysis results, or None

    Returns:
        Formatted string for prompt inclusion
    """
    if depth_results is None:
        return "Depth analysis: Not available"

    lines = ["Spatial depth analysis:"]

    # Process per-detection depth
    detections = depth_results.get("detections", {})
    for det_id, depth_info in detections.items():
        distance = depth_info.get("relative_distance", "unknown")
        confidence = depth_info.get("confidence", 0.0)

        # Risk notes based on distance and movement
        risk_note = ""
        if distance == "foreground":
            risk_note = " [Close to camera - high visibility]"
        elif distance == "approaching":
            risk_note = " [Moving toward camera - monitor closely]"

        lines.append(f"  Detection {det_id}: {distance} ({confidence:.0%}){risk_note}")

    # Movement patterns if available
    if "movement_pattern" in depth_results:
        pattern = depth_results["movement_pattern"]
        lines.append(f"  Movement pattern: {pattern}")

    return "\n".join(lines) if len(lines) > 1 else "Depth analysis: No depth data available"


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


def format_detections_with_all_enrichment(  # noqa: PLR0912
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
    """
    if not detections:
        return "No detections in this batch."

    lines = []

    for det in detections:
        det_id = str(det.get("detection_id", det.get("id", "")))
        class_name = det.get("class_name", det.get("object_type", "unknown"))
        confidence = det.get("confidence", 0.0)
        bbox = det.get("bbox", [])

        # Base detection info
        bbox_str = f"[{', '.join(str(int(b)) for b in bbox)}]" if bbox else "[]"
        base_line = f"### {class_name.upper()} (ID: {det_id})"
        lines.append(base_line)
        lines.append(f"Confidence: {confidence:.0%}, Location: {bbox_str}")

        # Add Florence-2 vision attributes if available
        if vision_extraction:
            if det_id in vision_extraction.vehicle_attributes:
                v_attrs = vision_extraction.vehicle_attributes[det_id]
                attr_parts = []
                if v_attrs.color:
                    attr_parts.append(f"Color: {v_attrs.color}")
                if v_attrs.vehicle_type:
                    attr_parts.append(f"Type: {v_attrs.vehicle_type}")
                if v_attrs.is_commercial:
                    commercial = "Commercial vehicle"
                    if v_attrs.commercial_text:
                        commercial += f" ({v_attrs.commercial_text})"
                    attr_parts.append(commercial)
                if attr_parts:
                    lines.append(f"Florence-2: {', '.join(attr_parts)}")
                if v_attrs.caption:
                    lines.append(f"Description: {v_attrs.caption}")

            elif det_id in vision_extraction.person_attributes:
                p_attrs = vision_extraction.person_attributes[det_id]
                attr_parts = []
                if p_attrs.clothing:
                    attr_parts.append(f"Wearing: {p_attrs.clothing}")
                if p_attrs.carrying:
                    attr_parts.append(f"Carrying: {p_attrs.carrying}")
                if p_attrs.action:
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
                    lines.append(f"Clothing items: {', '.join(seg.clothing_items)}")
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
