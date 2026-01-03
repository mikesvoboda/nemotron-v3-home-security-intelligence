"""JSON parsing utilities for LLM responses.

This module provides robust JSON extraction from potentially malformed LLM outputs,
handling common issues like:
- Markdown code blocks (```json ... ```)
- Extra text before/after JSON
- Missing commas between object properties
- Trailing commas
- Single quotes instead of double quotes
- Incomplete/truncated JSON
- <think>...</think> blocks from reasoning models
"""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_from_llm_response(text: str) -> dict[str, Any]:
    """Extract and parse JSON from an LLM response.

    Handles common LLM JSON output issues including markdown code blocks,
    reasoning blocks, malformed JSON with missing commas, and other syntax errors.

    Args:
        text: Raw LLM response text that may contain JSON

    Returns:
        Parsed dictionary from the JSON

    Raises:
        ValueError: If no valid JSON can be extracted or parsed
    """
    if not text or not text.strip():
        raise ValueError("Empty LLM response")

    # Step 1: Clean the response
    cleaned = _clean_llm_response(text)

    # Step 2: Try to find and extract JSON
    json_str = _find_json_in_text(cleaned)
    if not json_str:
        # Fallback: try the original text in case cleaning removed important content
        json_str = _find_json_in_text(text)
        if not json_str:
            raise ValueError(f"No JSON found in LLM response: {text[:200]}")

    # Step 3: Try to parse the JSON, with repairs if needed
    return _parse_json_with_fallbacks(json_str, text)


def _clean_llm_response(text: str) -> str:
    """Clean common LLM response artifacts.

    Removes:
    - <think>...</think> reasoning blocks
    - Markdown code blocks (```json ... ```)
    - Leading/trailing whitespace
    """
    cleaned = text

    # Remove <think>...</think> reasoning blocks (complete)
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL)

    # Handle incomplete <think> blocks (no closing tag)
    if "<think>" in cleaned:
        # Try to find JSON after the think block
        think_start = cleaned.find("<think>")
        json_start = cleaned.find("{", think_start)
        if json_start > think_start:
            cleaned = cleaned[json_start:]

    # Remove markdown code blocks
    # Handle ```json ... ``` format
    cleaned = re.sub(r"```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"```\s*$", "", cleaned)

    return cleaned.strip()


def _find_json_in_text(text: str) -> str | None:
    """Find and extract a JSON object from text.

    Uses bracket matching to handle nested objects properly.

    Args:
        text: Text that may contain a JSON object

    Returns:
        The JSON string if found, None otherwise
    """
    # Find the first opening brace
    start = text.find("{")
    if start == -1:
        return None

    # Use bracket matching to find the complete JSON object
    brace_count = 0
    in_string = False
    escape_next = False
    end = start

    for i, char in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                return text[start:end]

    # If we get here, we have unbalanced braces - try to extract anyway
    # Find the last closing brace
    last_brace = text.rfind("}")
    if last_brace > start:
        return text[start : last_brace + 1]

    return None


def _try_parse_json(json_str: str) -> dict[str, Any] | None:
    """Attempt to parse a JSON string, returning None on failure."""
    try:
        result = json.loads(json_str)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass
    return None


def _parse_json_with_fallbacks(json_str: str, original_text: str) -> dict[str, Any]:
    """Parse JSON with multiple fallback strategies.

    Tries:
    1. Direct parsing
    2. Repair missing commas
    3. Fix trailing commas
    4. Replace single quotes
    5. Multiple repairs combined
    6. Aggressive regex extraction

    Args:
        json_str: The extracted JSON string to parse
        original_text: Original text (for error messages)

    Returns:
        Parsed dictionary

    Raises:
        ValueError: If all parsing strategies fail
    """
    # Strategy 1: Direct parse
    if (result := _try_parse_json(json_str)) is not None:
        return result

    # Strategy 2: Fix missing commas between properties
    if (result := _try_parse_json(_fix_missing_commas(json_str))) is not None:
        return result

    # Strategy 3: Fix trailing commas
    if (result := _try_parse_json(_fix_trailing_commas(json_str))) is not None:
        return result

    # Strategy 4: Replace single quotes with double quotes
    if (result := _try_parse_json(_fix_single_quotes(json_str))) is not None:
        return result

    # Strategy 5: Combined repairs
    combined = _fix_missing_commas(_fix_trailing_commas(_fix_single_quotes(json_str)))
    if (result := _try_parse_json(combined)) is not None:
        return result

    # Strategy 6: Try aggressive extraction with regex for simple objects
    simple_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", json_str, re.DOTALL)
    if simple_match:
        repaired = _fix_missing_commas(simple_match.group())
        if (result := _try_parse_json(repaired)) is not None:
            return result

    raise ValueError(f"Could not parse JSON from LLM response: {original_text[:200]}")


def _fix_missing_commas(json_str: str) -> str:
    """Fix missing commas between JSON object properties.

    Handles cases like:
    - "key1": "value1"
      "key2": "value2"   <- missing comma after value1

    - "key1": 42
      "key2": "value"    <- missing comma after 42

    - "key1": true
      "key2": false      <- missing comma after true
    """
    # Pattern: value followed by newline/whitespace then key
    # Match: string value, number, true, false, null followed by whitespace and a quote
    patterns = [
        # String value followed by key (missing comma)
        (r'("\s*)\n\s*(")', r"\1,\n\2"),
        # Number followed by key
        (r'(\d)\s*\n\s*(")', r"\1,\n\2"),
        # Boolean/null followed by key
        (r'(true|false|null)\s*\n\s*(")', r"\1,\n\2"),
        # Closing brace/bracket followed by key (for nested structures)
        (r'([}\]])\s*\n\s*(")', r"\1,\n\2"),
    ]

    result = json_str
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    return result


def _fix_trailing_commas(json_str: str) -> str:
    """Remove trailing commas before closing braces/brackets.

    Handles cases like:
    - {"key": "value",}
    - ["item1", "item2",]
    """
    # Remove comma before closing brace/bracket, allowing for whitespace
    result = re.sub(r",\s*}", "}", json_str)
    result = re.sub(r",\s*\]", "]", result)
    return result


def _fix_single_quotes(json_str: str) -> str:
    """Replace single quotes with double quotes for JSON compatibility.

    Note: This is a simple replacement and may not handle all edge cases
    (e.g., escaped quotes within strings). Use with caution.
    """
    # Simple replacement - may not work for all cases
    # But LLMs rarely produce escaped quotes in their JSON output
    return json_str.replace("'", '"')


def extract_json_field(
    text: str,
    field_name: str,
    default: Any = None,
) -> Any:
    """Extract a specific field from JSON in LLM response.

    Convenience function that extracts JSON and returns a specific field.

    Args:
        text: Raw LLM response text
        field_name: Name of the field to extract
        default: Default value if field not found or extraction fails

    Returns:
        The field value, or default if not found
    """
    try:
        data = extract_json_from_llm_response(text)
        return data.get(field_name, default)
    except ValueError:
        return default
