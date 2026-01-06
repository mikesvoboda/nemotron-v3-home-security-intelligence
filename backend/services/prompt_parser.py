"""
Prompt parsing utilities for smart insertion of suggestions.

This module provides utilities to parse system prompts and identify optimal
insertion points for suggestions based on section headers and variable patterns.
"""

import logging
import re

logger = logging.getLogger(__name__)


def find_insertion_point(
    prompt: str, target_section: str, insertion_point: str = "append"
) -> tuple[int, str]:
    """
    Determine where to insert the suggestion based on:
    1. Target section header (e.g., "## Camera & Time Context")
    2. Insertion point type (append, prepend, replace)

    Args:
        prompt: The full prompt text to analyze
        target_section: The section header to find (without ## prefix)
        insertion_point: Where to insert ('append', 'prepend', or 'replace')

    Returns:
        tuple[int, str]: (insertion_index, insertion_type)
        insertion_type is one of: 'section_end', 'section_start', 'fallback'
    """
    # Escape special regex characters in the target section
    escaped_section = re.escape(target_section)

    # Find target section using regex - match ## followed by section name
    # The pattern captures everything until the next ## section or end of string
    section_pattern = rf"##\s*{escaped_section}[^\n]*\n(.*?)(?=\n##|\Z)"
    section_match = re.search(section_pattern, prompt, re.DOTALL | re.IGNORECASE)

    if section_match:
        if insertion_point == "prepend":
            return section_match.start(1), "section_start"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    logger.warning(
        "Section '%s' not found in prompt, falling back to end insertion",
        target_section,
        extra={"target_section": target_section, "prompt_length": len(prompt)},
    )
    return len(prompt), "fallback"


def detect_variable_style(prompt: str) -> dict[str, str]:
    """
    Analyze existing variable patterns in prompt.

    Args:
        prompt: The prompt text to analyze

    Returns:
        dict with:
        - 'format': 'curly' | 'angle' | 'dollar' | 'none'
        - 'label_style': 'colon' | 'equals' | 'none'
        - 'indentation': detected indentation (spaces/tabs)
    """
    result: dict[str, str] = {"format": "none", "label_style": "none", "indentation": ""}

    # Check for {variable} pattern (curly braces)
    if re.search(r"\{[a-z_]+\}", prompt):
        result["format"] = "curly"
    # Check for <variable> pattern (angle brackets)
    elif re.search(r"<[a-z_]+>", prompt):
        result["format"] = "angle"
    # Check for $variable pattern (dollar sign)
    elif re.search(r"\$[a-z_]+", prompt):
        result["format"] = "dollar"

    # Check label style - "Label: {var}" pattern
    if re.search(r"[A-Z][a-z]+:\s*[\{\<\$]", prompt):
        result["label_style"] = "colon"
    # Check label style - "Label={var}" pattern
    elif re.search(r"[A-Z][a-z]+=[\{\<\$]", prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def generate_insertion_text(
    proposed_label: str, proposed_variable: str, style: dict[str, str]
) -> str:
    """
    Generate the text to insert based on suggestion and detected style.

    Args:
        proposed_label: The label for the variable (e.g., "Time Since Last Event")
        proposed_variable: The variable name (e.g., "time_since_last_event")
        style: The detected style dict from detect_variable_style

    Returns:
        Formatted insertion text, e.g., "Time Since Last Event: {time_since_last_event}\n"
    """
    indent = style.get("indentation", "")
    var_format = style.get("format", "curly")
    label_style = style.get("label_style", "colon")

    # Format variable based on detected style
    if var_format == "curly":
        var = f"{{{proposed_variable}}}"
    elif var_format == "angle":
        var = f"<{proposed_variable}>"
    elif var_format == "dollar":
        var = f"${proposed_variable}"
    else:
        var = f"{{{proposed_variable}}}"  # default to curly

    # Format with label based on detected style
    if label_style == "equals":
        return f"{indent}{proposed_label}={var}\n"
    else:  # colon is default
        return f"{indent}{proposed_label}: {var}\n"


def validate_prompt_syntax(prompt: str) -> list[str]:
    """
    Check for common prompt issues:
    - Unclosed brackets
    - Duplicate variables
    - Missing section headers

    Args:
        prompt: The prompt text to validate

    Returns:
        list of warning messages (empty if valid)
    """
    warnings: list[str] = []

    # Check for unclosed curly braces
    open_braces = prompt.count("{")
    close_braces = prompt.count("}")
    if open_braces != close_braces:
        warnings.append(f"Unbalanced curly braces: {open_braces} open, {close_braces} close")

    # Check for duplicate variables (curly brace style)
    variables = re.findall(r"\{([a-z_]+)\}", prompt)
    seen: set[str] = set()
    duplicates: set[str] = set()
    for var in variables:
        if var in seen:
            duplicates.add(var)
        seen.add(var)
    if duplicates:
        warnings.append(f"Duplicate variables: {', '.join(sorted(duplicates))}")

    # Check for unclosed angle brackets
    open_angles = prompt.count("<")
    close_angles = prompt.count(">")
    if open_angles != close_angles:
        warnings.append(f"Unbalanced angle brackets: {open_angles} open, {close_angles} close")

    return warnings


def apply_suggestion_to_prompt(
    prompt: str,
    target_section: str,
    insertion_point: str,
    proposed_label: str,
    proposed_variable: str,
) -> str:
    """
    Apply a suggestion to a prompt, returning the modified prompt.

    Convenience function that combines find_insertion_point,
    detect_variable_style, and generate_insertion_text.

    Args:
        prompt: The original prompt text
        target_section: The section to insert into (e.g., "Camera & Time Context")
        insertion_point: Where to insert ('append' or 'prepend')
        proposed_label: The label for the new variable
        proposed_variable: The variable name

    Returns:
        The modified prompt with the suggestion applied
    """
    style = detect_variable_style(prompt)
    insert_idx, _insert_type = find_insertion_point(prompt, target_section, insertion_point)
    new_text = generate_insertion_text(proposed_label, proposed_variable, style)

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]
