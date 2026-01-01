"""Prompt templates for AI analysis services.

This module contains prompt templates used by the Nemotron analyzer
to generate risk assessments from security camera detections.

Nemotron-3-Nano uses ChatML format with <|im_start|> and <|im_end|> tags.
The model outputs <think>...</think> reasoning blocks before the response.
"""

RISK_ANALYSIS_PROMPT = """<|im_start|>system
You are a home security risk analyzer. Output valid JSON only.<|im_end|>
<|im_start|>user
Analyze these detections and output a JSON risk assessment.

Camera: {camera_name}
Time: {start_time} to {end_time}
Detections:
{detections_list}

Risk levels: low (0-29), medium (30-59), high (60-84), critical (85-100)

Output format: {{"risk_score": N, "risk_level": "level", "summary": "text", "reasoning": "text"}}<|im_end|>
<|im_start|>assistant
"""
