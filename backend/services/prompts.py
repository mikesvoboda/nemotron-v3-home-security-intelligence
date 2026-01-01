"""Prompt templates for AI analysis services.

This module contains prompt templates used by the Nemotron analyzer
to generate risk assessments from security camera detections.
"""

RISK_ANALYSIS_PROMPT = """You are a home security AI analyst. Analyze the following detections from security cameras and provide a risk assessment.

Camera: {camera_name}
Time Window: {start_time} to {end_time}
Detections:
{detections_list}

Respond in JSON format:
{{
  "risk_score": <0-100>,
  "risk_level": "<low|medium|high|critical>",
  "summary": "<brief 1-2 sentence summary>",
  "reasoning": "<detailed explanation>"
}}

Risk guidelines:
- Low (0-29): Normal activity (pets, known vehicles, delivery persons)
- Medium (30-59): Unusual but not alarming (unknown person during day, unfamiliar vehicle)
- High (60-84): Concerning activity (person at odd hours, multiple unknowns, loitering)
- Critical (85-100): Immediate attention (forced entry attempt, multiple persons at night, suspicious behavior)
"""
