"""Prompt templates for AI analysis services.

This module contains prompt templates used by the Nemotron analyzer
to generate risk assessments from security camera detections.

Nemotron-3-Nano uses ChatML format with <|im_start|> and <|im_end|> tags.
The model outputs <think>...</think> reasoning blocks before the response.
"""

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
