"""Prompt templates for AI analysis services.

This module contains prompt templates used by the Nemotron analyzer
to generate risk assessments from security camera detections.

Nemotron-3-Nano uses ChatML format with <|im_start|> and <|im_end|> tags.
The model outputs <think>...</think> reasoning blocks before the response.
"""

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
