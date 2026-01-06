"""
Prompt parsing utilities for smart insertion of suggestions.

This module provides utilities to parse system prompts and identify optimal
insertion points for suggestions based on section headers and variable patterns.
"""

import re
from collections.abc import Callable
from inspect import signature as _mutmut_signature
from typing import Annotated, ClassVar

MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg=None):
    """Forward call to original or mutated function, depending on the environment"""
    import os

    mutant_under_test = os.environ["MUTANT_UNDER_TEST"]
    if mutant_under_test == "fail":
        from mutmut.__main__ import MutmutProgrammaticFailException

        raise MutmutProgrammaticFailException("Failed programmatically")
    elif mutant_under_test == "stats":
        from mutmut.__main__ import record_trampoline_hit

        record_trampoline_hit(orig.__module__ + "." + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + "." + orig.__name__ + "__mutmut_"
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition(".")[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result


def x_find_insertion_point__mutmut_orig(
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
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_1(
    prompt: str, target_section: str, insertion_point: str = "XXappendXX"
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
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_2(
    prompt: str, target_section: str, insertion_point: str = "APPEND"
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
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_3(
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
    escaped_section = None

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
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_4(
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
    escaped_section = re.escape(None)

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
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_5(
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
    section_pattern = None
    section_match = re.search(section_pattern, prompt, re.DOTALL | re.IGNORECASE)

    if section_match:
        if insertion_point == "prepend":
            return section_match.start(1), "section_start"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_6(
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
    section_match = None

    if section_match:
        if insertion_point == "prepend":
            return section_match.start(1), "section_start"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_7(
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
    section_match = re.search(None, prompt, re.DOTALL | re.IGNORECASE)

    if section_match:
        if insertion_point == "prepend":
            return section_match.start(1), "section_start"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_8(
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
    section_match = re.search(section_pattern, None, re.DOTALL | re.IGNORECASE)

    if section_match:
        if insertion_point == "prepend":
            return section_match.start(1), "section_start"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_9(
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
    section_match = re.search(section_pattern, prompt, None)

    if section_match:
        if insertion_point == "prepend":
            return section_match.start(1), "section_start"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_10(
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
    section_match = re.search(prompt, re.DOTALL | re.IGNORECASE)

    if section_match:
        if insertion_point == "prepend":
            return section_match.start(1), "section_start"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_11(
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
    section_match = re.search(section_pattern, re.DOTALL | re.IGNORECASE)

    if section_match:
        if insertion_point == "prepend":
            return section_match.start(1), "section_start"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_12(
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
    section_match = re.search(
        section_pattern,
        prompt,
    )

    if section_match:
        if insertion_point == "prepend":
            return section_match.start(1), "section_start"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_13(
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
    section_match = re.search(section_pattern, prompt, re.DOTALL & re.IGNORECASE)

    if section_match:
        if insertion_point == "prepend":
            return section_match.start(1), "section_start"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_14(
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
        if insertion_point != "prepend":
            return section_match.start(1), "section_start"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_15(
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
        if insertion_point == "XXprependXX":
            return section_match.start(1), "section_start"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_16(
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
        if insertion_point == "PREPEND":
            return section_match.start(1), "section_start"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_17(
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
            return section_match.start(None), "section_start"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_18(
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
            return section_match.start(2), "section_start"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_19(
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
            return section_match.start(1), "XXsection_startXX"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_20(
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
            return section_match.start(1), "SECTION_START"
        else:  # append (default)
            return section_match.end(1), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_21(
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
            return section_match.end(None), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_22(
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
            return section_match.end(2), "section_end"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_23(
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
            return section_match.end(1), "XXsection_endXX"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_24(
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
            return section_match.end(1), "SECTION_END"

    # Fallback: append to end
    return len(prompt), "fallback"


def x_find_insertion_point__mutmut_25(
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
    return len(prompt), "XXfallbackXX"


def x_find_insertion_point__mutmut_26(
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
    return len(prompt), "FALLBACK"


x_find_insertion_point__mutmut_mutants: ClassVar[MutantDict] = {
    "x_find_insertion_point__mutmut_1": x_find_insertion_point__mutmut_1,
    "x_find_insertion_point__mutmut_2": x_find_insertion_point__mutmut_2,
    "x_find_insertion_point__mutmut_3": x_find_insertion_point__mutmut_3,
    "x_find_insertion_point__mutmut_4": x_find_insertion_point__mutmut_4,
    "x_find_insertion_point__mutmut_5": x_find_insertion_point__mutmut_5,
    "x_find_insertion_point__mutmut_6": x_find_insertion_point__mutmut_6,
    "x_find_insertion_point__mutmut_7": x_find_insertion_point__mutmut_7,
    "x_find_insertion_point__mutmut_8": x_find_insertion_point__mutmut_8,
    "x_find_insertion_point__mutmut_9": x_find_insertion_point__mutmut_9,
    "x_find_insertion_point__mutmut_10": x_find_insertion_point__mutmut_10,
    "x_find_insertion_point__mutmut_11": x_find_insertion_point__mutmut_11,
    "x_find_insertion_point__mutmut_12": x_find_insertion_point__mutmut_12,
    "x_find_insertion_point__mutmut_13": x_find_insertion_point__mutmut_13,
    "x_find_insertion_point__mutmut_14": x_find_insertion_point__mutmut_14,
    "x_find_insertion_point__mutmut_15": x_find_insertion_point__mutmut_15,
    "x_find_insertion_point__mutmut_16": x_find_insertion_point__mutmut_16,
    "x_find_insertion_point__mutmut_17": x_find_insertion_point__mutmut_17,
    "x_find_insertion_point__mutmut_18": x_find_insertion_point__mutmut_18,
    "x_find_insertion_point__mutmut_19": x_find_insertion_point__mutmut_19,
    "x_find_insertion_point__mutmut_20": x_find_insertion_point__mutmut_20,
    "x_find_insertion_point__mutmut_21": x_find_insertion_point__mutmut_21,
    "x_find_insertion_point__mutmut_22": x_find_insertion_point__mutmut_22,
    "x_find_insertion_point__mutmut_23": x_find_insertion_point__mutmut_23,
    "x_find_insertion_point__mutmut_24": x_find_insertion_point__mutmut_24,
    "x_find_insertion_point__mutmut_25": x_find_insertion_point__mutmut_25,
    "x_find_insertion_point__mutmut_26": x_find_insertion_point__mutmut_26,
}


def find_insertion_point(*args, **kwargs):
    result = _mutmut_trampoline(
        x_find_insertion_point__mutmut_orig, x_find_insertion_point__mutmut_mutants, args, kwargs
    )
    return result


find_insertion_point.__signature__ = _mutmut_signature(x_find_insertion_point__mutmut_orig)
x_find_insertion_point__mutmut_orig.__name__ = "x_find_insertion_point"


def x_detect_variable_style__mutmut_orig(prompt: str) -> dict[str, str]:
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


def x_detect_variable_style__mutmut_1(prompt: str) -> dict[str, str]:
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
    result: dict[str, str] = None

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


def x_detect_variable_style__mutmut_2(prompt: str) -> dict[str, str]:
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
    result: dict[str, str] = {"XXformatXX": "none", "label_style": "none", "indentation": ""}

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


def x_detect_variable_style__mutmut_3(prompt: str) -> dict[str, str]:
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
    result: dict[str, str] = {"FORMAT": "none", "label_style": "none", "indentation": ""}

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


def x_detect_variable_style__mutmut_4(prompt: str) -> dict[str, str]:
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
    result: dict[str, str] = {"format": "XXnoneXX", "label_style": "none", "indentation": ""}

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


def x_detect_variable_style__mutmut_5(prompt: str) -> dict[str, str]:
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
    result: dict[str, str] = {"format": "NONE", "label_style": "none", "indentation": ""}

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


def x_detect_variable_style__mutmut_6(prompt: str) -> dict[str, str]:
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
    result: dict[str, str] = {"format": "none", "XXlabel_styleXX": "none", "indentation": ""}

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


def x_detect_variable_style__mutmut_7(prompt: str) -> dict[str, str]:
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
    result: dict[str, str] = {"format": "none", "LABEL_STYLE": "none", "indentation": ""}

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


def x_detect_variable_style__mutmut_8(prompt: str) -> dict[str, str]:
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
    result: dict[str, str] = {"format": "none", "label_style": "XXnoneXX", "indentation": ""}

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


def x_detect_variable_style__mutmut_9(prompt: str) -> dict[str, str]:
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
    result: dict[str, str] = {"format": "none", "label_style": "NONE", "indentation": ""}

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


def x_detect_variable_style__mutmut_10(prompt: str) -> dict[str, str]:
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
    result: dict[str, str] = {"format": "none", "label_style": "none", "XXindentationXX": ""}

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


def x_detect_variable_style__mutmut_11(prompt: str) -> dict[str, str]:
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
    result: dict[str, str] = {"format": "none", "label_style": "none", "INDENTATION": ""}

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


def x_detect_variable_style__mutmut_12(prompt: str) -> dict[str, str]:
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
    result: dict[str, str] = {"format": "none", "label_style": "none", "indentation": "XXXX"}

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


def x_detect_variable_style__mutmut_13(prompt: str) -> dict[str, str]:
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
    if re.search(None, prompt):
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


def x_detect_variable_style__mutmut_14(prompt: str) -> dict[str, str]:
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
    if re.search(r"\{[a-z_]+\}", None):
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


def x_detect_variable_style__mutmut_15(prompt: str) -> dict[str, str]:
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
    if re.search(prompt):
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


def x_detect_variable_style__mutmut_16(prompt: str) -> dict[str, str]:
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
    if re.search(
        r"\{[a-z_]+\}",
    ):
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


def x_detect_variable_style__mutmut_17(prompt: str) -> dict[str, str]:
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
    if re.search(r"XX\{[a-z_]+\}XX", prompt):
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


def x_detect_variable_style__mutmut_18(prompt: str) -> dict[str, str]:
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
    if re.search(r"\{[A-Z_]+\}", prompt):
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


def x_detect_variable_style__mutmut_19(prompt: str) -> dict[str, str]:
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
        result["format"] = None
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


def x_detect_variable_style__mutmut_20(prompt: str) -> dict[str, str]:
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
        result["XXformatXX"] = "curly"
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


def x_detect_variable_style__mutmut_21(prompt: str) -> dict[str, str]:
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
        result["FORMAT"] = "curly"
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


def x_detect_variable_style__mutmut_22(prompt: str) -> dict[str, str]:
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
        result["format"] = "XXcurlyXX"
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


def x_detect_variable_style__mutmut_23(prompt: str) -> dict[str, str]:
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
        result["format"] = "CURLY"
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


def x_detect_variable_style__mutmut_24(prompt: str) -> dict[str, str]:
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
    elif re.search(None, prompt):
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


def x_detect_variable_style__mutmut_25(prompt: str) -> dict[str, str]:
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
    elif re.search(r"<[a-z_]+>", None):
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


def x_detect_variable_style__mutmut_26(prompt: str) -> dict[str, str]:
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
    elif re.search(prompt):
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


def x_detect_variable_style__mutmut_27(prompt: str) -> dict[str, str]:
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
    elif re.search(
        r"<[a-z_]+>",
    ):
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


def x_detect_variable_style__mutmut_28(prompt: str) -> dict[str, str]:
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
    elif re.search(r"XX<[a-z_]+>XX", prompt):
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


def x_detect_variable_style__mutmut_29(prompt: str) -> dict[str, str]:
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
    elif re.search(r"<[A-Z_]+>", prompt):
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


def x_detect_variable_style__mutmut_30(prompt: str) -> dict[str, str]:
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
        result["format"] = None
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


def x_detect_variable_style__mutmut_31(prompt: str) -> dict[str, str]:
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
        result["XXformatXX"] = "angle"
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


def x_detect_variable_style__mutmut_32(prompt: str) -> dict[str, str]:
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
        result["FORMAT"] = "angle"
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


def x_detect_variable_style__mutmut_33(prompt: str) -> dict[str, str]:
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
        result["format"] = "XXangleXX"
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


def x_detect_variable_style__mutmut_34(prompt: str) -> dict[str, str]:
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
        result["format"] = "ANGLE"
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


def x_detect_variable_style__mutmut_35(prompt: str) -> dict[str, str]:
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
    elif re.search(None, prompt):
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


def x_detect_variable_style__mutmut_36(prompt: str) -> dict[str, str]:
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
    elif re.search(r"\$[a-z_]+", None):
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


def x_detect_variable_style__mutmut_37(prompt: str) -> dict[str, str]:
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
    elif re.search(prompt):
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


def x_detect_variable_style__mutmut_38(prompt: str) -> dict[str, str]:
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
    elif re.search(
        r"\$[a-z_]+",
    ):
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


def x_detect_variable_style__mutmut_39(prompt: str) -> dict[str, str]:
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
    elif re.search(r"XX\$[a-z_]+XX", prompt):
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


def x_detect_variable_style__mutmut_40(prompt: str) -> dict[str, str]:
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
    elif re.search(r"\$[A-Z_]+", prompt):
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


def x_detect_variable_style__mutmut_41(prompt: str) -> dict[str, str]:
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
        result["format"] = None

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


def x_detect_variable_style__mutmut_42(prompt: str) -> dict[str, str]:
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
        result["XXformatXX"] = "dollar"

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


def x_detect_variable_style__mutmut_43(prompt: str) -> dict[str, str]:
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
        result["FORMAT"] = "dollar"

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


def x_detect_variable_style__mutmut_44(prompt: str) -> dict[str, str]:
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
        result["format"] = "XXdollarXX"

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


def x_detect_variable_style__mutmut_45(prompt: str) -> dict[str, str]:
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
        result["format"] = "DOLLAR"

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


def x_detect_variable_style__mutmut_46(prompt: str) -> dict[str, str]:
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
    if re.search(None, prompt):
        result["label_style"] = "colon"
    # Check label style - "Label={var}" pattern
    elif re.search(r"[A-Z][a-z]+=[\{\<\$]", prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_47(prompt: str) -> dict[str, str]:
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
    if re.search(r"[A-Z][a-z]+:\s*[\{\<\$]", None):
        result["label_style"] = "colon"
    # Check label style - "Label={var}" pattern
    elif re.search(r"[A-Z][a-z]+=[\{\<\$]", prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_48(prompt: str) -> dict[str, str]:
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
    if re.search(prompt):
        result["label_style"] = "colon"
    # Check label style - "Label={var}" pattern
    elif re.search(r"[A-Z][a-z]+=[\{\<\$]", prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_49(prompt: str) -> dict[str, str]:
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
    if re.search(
        r"[A-Z][a-z]+:\s*[\{\<\$]",
    ):
        result["label_style"] = "colon"
    # Check label style - "Label={var}" pattern
    elif re.search(r"[A-Z][a-z]+=[\{\<\$]", prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_50(prompt: str) -> dict[str, str]:
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
    if re.search(r"XX[A-Z][a-z]+:\s*[\{\<\$]XX", prompt):
        result["label_style"] = "colon"
    # Check label style - "Label={var}" pattern
    elif re.search(r"[A-Z][a-z]+=[\{\<\$]", prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_51(prompt: str) -> dict[str, str]:
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
    if re.search(r"[a-z][a-z]+:\s*[\{\<\$]", prompt):
        result["label_style"] = "colon"
    # Check label style - "Label={var}" pattern
    elif re.search(r"[A-Z][a-z]+=[\{\<\$]", prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_52(prompt: str) -> dict[str, str]:
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
    if re.search(r"[A-Z][A-Z]+:\s*[\{\<\$]", prompt):
        result["label_style"] = "colon"
    # Check label style - "Label={var}" pattern
    elif re.search(r"[A-Z][a-z]+=[\{\<\$]", prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_53(prompt: str) -> dict[str, str]:
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
        result["label_style"] = None
    # Check label style - "Label={var}" pattern
    elif re.search(r"[A-Z][a-z]+=[\{\<\$]", prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_54(prompt: str) -> dict[str, str]:
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
        result["XXlabel_styleXX"] = "colon"
    # Check label style - "Label={var}" pattern
    elif re.search(r"[A-Z][a-z]+=[\{\<\$]", prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_55(prompt: str) -> dict[str, str]:
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
        result["LABEL_STYLE"] = "colon"
    # Check label style - "Label={var}" pattern
    elif re.search(r"[A-Z][a-z]+=[\{\<\$]", prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_56(prompt: str) -> dict[str, str]:
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
        result["label_style"] = "XXcolonXX"
    # Check label style - "Label={var}" pattern
    elif re.search(r"[A-Z][a-z]+=[\{\<\$]", prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_57(prompt: str) -> dict[str, str]:
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
        result["label_style"] = "COLON"
    # Check label style - "Label={var}" pattern
    elif re.search(r"[A-Z][a-z]+=[\{\<\$]", prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_58(prompt: str) -> dict[str, str]:
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
    elif re.search(None, prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_59(prompt: str) -> dict[str, str]:
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
    elif re.search(r"[A-Z][a-z]+=[\{\<\$]", None):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_60(prompt: str) -> dict[str, str]:
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
    elif re.search(prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_61(prompt: str) -> dict[str, str]:
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
    elif re.search(
        r"[A-Z][a-z]+=[\{\<\$]",
    ):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_62(prompt: str) -> dict[str, str]:
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
    elif re.search(r"XX[A-Z][a-z]+=[\{\<\$]XX", prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_63(prompt: str) -> dict[str, str]:
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
    elif re.search(r"[a-z][a-z]+=[\{\<\$]", prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_64(prompt: str) -> dict[str, str]:
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
    elif re.search(r"[A-Z][A-Z]+=[\{\<\$]", prompt):
        result["label_style"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_65(prompt: str) -> dict[str, str]:
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
        result["label_style"] = None

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_66(prompt: str) -> dict[str, str]:
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
        result["XXlabel_styleXX"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_67(prompt: str) -> dict[str, str]:
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
        result["LABEL_STYLE"] = "equals"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_68(prompt: str) -> dict[str, str]:
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
        result["label_style"] = "XXequalsXX"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_69(prompt: str) -> dict[str, str]:
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
        result["label_style"] = "EQUALS"

    # Detect indentation by looking for lines starting with whitespace followed by uppercase
    indent_match = re.search(r"\n([ \t]+)[A-Z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_70(prompt: str) -> dict[str, str]:
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
    indent_match = None
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_71(prompt: str) -> dict[str, str]:
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
    indent_match = re.search(None, prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_72(prompt: str) -> dict[str, str]:
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
    indent_match = re.search(r"\n([ \t]+)[A-Z]", None)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_73(prompt: str) -> dict[str, str]:
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
    indent_match = re.search(prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_74(prompt: str) -> dict[str, str]:
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
    indent_match = re.search(
        r"\n([ \t]+)[A-Z]",
    )
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_75(prompt: str) -> dict[str, str]:
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
    indent_match = re.search(r"XX\n([ \t]+)[A-Z]XX", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_76(prompt: str) -> dict[str, str]:
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
    indent_match = re.search(r"\n([ \t]+)[a-z]", prompt)
    if indent_match:
        result["indentation"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_77(prompt: str) -> dict[str, str]:
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
        result["indentation"] = None

    return result


def x_detect_variable_style__mutmut_78(prompt: str) -> dict[str, str]:
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
        result["XXindentationXX"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_79(prompt: str) -> dict[str, str]:
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
        result["INDENTATION"] = indent_match.group(1)

    return result


def x_detect_variable_style__mutmut_80(prompt: str) -> dict[str, str]:
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
        result["indentation"] = indent_match.group(None)

    return result


def x_detect_variable_style__mutmut_81(prompt: str) -> dict[str, str]:
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
        result["indentation"] = indent_match.group(2)

    return result


x_detect_variable_style__mutmut_mutants: ClassVar[MutantDict] = {
    "x_detect_variable_style__mutmut_1": x_detect_variable_style__mutmut_1,
    "x_detect_variable_style__mutmut_2": x_detect_variable_style__mutmut_2,
    "x_detect_variable_style__mutmut_3": x_detect_variable_style__mutmut_3,
    "x_detect_variable_style__mutmut_4": x_detect_variable_style__mutmut_4,
    "x_detect_variable_style__mutmut_5": x_detect_variable_style__mutmut_5,
    "x_detect_variable_style__mutmut_6": x_detect_variable_style__mutmut_6,
    "x_detect_variable_style__mutmut_7": x_detect_variable_style__mutmut_7,
    "x_detect_variable_style__mutmut_8": x_detect_variable_style__mutmut_8,
    "x_detect_variable_style__mutmut_9": x_detect_variable_style__mutmut_9,
    "x_detect_variable_style__mutmut_10": x_detect_variable_style__mutmut_10,
    "x_detect_variable_style__mutmut_11": x_detect_variable_style__mutmut_11,
    "x_detect_variable_style__mutmut_12": x_detect_variable_style__mutmut_12,
    "x_detect_variable_style__mutmut_13": x_detect_variable_style__mutmut_13,
    "x_detect_variable_style__mutmut_14": x_detect_variable_style__mutmut_14,
    "x_detect_variable_style__mutmut_15": x_detect_variable_style__mutmut_15,
    "x_detect_variable_style__mutmut_16": x_detect_variable_style__mutmut_16,
    "x_detect_variable_style__mutmut_17": x_detect_variable_style__mutmut_17,
    "x_detect_variable_style__mutmut_18": x_detect_variable_style__mutmut_18,
    "x_detect_variable_style__mutmut_19": x_detect_variable_style__mutmut_19,
    "x_detect_variable_style__mutmut_20": x_detect_variable_style__mutmut_20,
    "x_detect_variable_style__mutmut_21": x_detect_variable_style__mutmut_21,
    "x_detect_variable_style__mutmut_22": x_detect_variable_style__mutmut_22,
    "x_detect_variable_style__mutmut_23": x_detect_variable_style__mutmut_23,
    "x_detect_variable_style__mutmut_24": x_detect_variable_style__mutmut_24,
    "x_detect_variable_style__mutmut_25": x_detect_variable_style__mutmut_25,
    "x_detect_variable_style__mutmut_26": x_detect_variable_style__mutmut_26,
    "x_detect_variable_style__mutmut_27": x_detect_variable_style__mutmut_27,
    "x_detect_variable_style__mutmut_28": x_detect_variable_style__mutmut_28,
    "x_detect_variable_style__mutmut_29": x_detect_variable_style__mutmut_29,
    "x_detect_variable_style__mutmut_30": x_detect_variable_style__mutmut_30,
    "x_detect_variable_style__mutmut_31": x_detect_variable_style__mutmut_31,
    "x_detect_variable_style__mutmut_32": x_detect_variable_style__mutmut_32,
    "x_detect_variable_style__mutmut_33": x_detect_variable_style__mutmut_33,
    "x_detect_variable_style__mutmut_34": x_detect_variable_style__mutmut_34,
    "x_detect_variable_style__mutmut_35": x_detect_variable_style__mutmut_35,
    "x_detect_variable_style__mutmut_36": x_detect_variable_style__mutmut_36,
    "x_detect_variable_style__mutmut_37": x_detect_variable_style__mutmut_37,
    "x_detect_variable_style__mutmut_38": x_detect_variable_style__mutmut_38,
    "x_detect_variable_style__mutmut_39": x_detect_variable_style__mutmut_39,
    "x_detect_variable_style__mutmut_40": x_detect_variable_style__mutmut_40,
    "x_detect_variable_style__mutmut_41": x_detect_variable_style__mutmut_41,
    "x_detect_variable_style__mutmut_42": x_detect_variable_style__mutmut_42,
    "x_detect_variable_style__mutmut_43": x_detect_variable_style__mutmut_43,
    "x_detect_variable_style__mutmut_44": x_detect_variable_style__mutmut_44,
    "x_detect_variable_style__mutmut_45": x_detect_variable_style__mutmut_45,
    "x_detect_variable_style__mutmut_46": x_detect_variable_style__mutmut_46,
    "x_detect_variable_style__mutmut_47": x_detect_variable_style__mutmut_47,
    "x_detect_variable_style__mutmut_48": x_detect_variable_style__mutmut_48,
    "x_detect_variable_style__mutmut_49": x_detect_variable_style__mutmut_49,
    "x_detect_variable_style__mutmut_50": x_detect_variable_style__mutmut_50,
    "x_detect_variable_style__mutmut_51": x_detect_variable_style__mutmut_51,
    "x_detect_variable_style__mutmut_52": x_detect_variable_style__mutmut_52,
    "x_detect_variable_style__mutmut_53": x_detect_variable_style__mutmut_53,
    "x_detect_variable_style__mutmut_54": x_detect_variable_style__mutmut_54,
    "x_detect_variable_style__mutmut_55": x_detect_variable_style__mutmut_55,
    "x_detect_variable_style__mutmut_56": x_detect_variable_style__mutmut_56,
    "x_detect_variable_style__mutmut_57": x_detect_variable_style__mutmut_57,
    "x_detect_variable_style__mutmut_58": x_detect_variable_style__mutmut_58,
    "x_detect_variable_style__mutmut_59": x_detect_variable_style__mutmut_59,
    "x_detect_variable_style__mutmut_60": x_detect_variable_style__mutmut_60,
    "x_detect_variable_style__mutmut_61": x_detect_variable_style__mutmut_61,
    "x_detect_variable_style__mutmut_62": x_detect_variable_style__mutmut_62,
    "x_detect_variable_style__mutmut_63": x_detect_variable_style__mutmut_63,
    "x_detect_variable_style__mutmut_64": x_detect_variable_style__mutmut_64,
    "x_detect_variable_style__mutmut_65": x_detect_variable_style__mutmut_65,
    "x_detect_variable_style__mutmut_66": x_detect_variable_style__mutmut_66,
    "x_detect_variable_style__mutmut_67": x_detect_variable_style__mutmut_67,
    "x_detect_variable_style__mutmut_68": x_detect_variable_style__mutmut_68,
    "x_detect_variable_style__mutmut_69": x_detect_variable_style__mutmut_69,
    "x_detect_variable_style__mutmut_70": x_detect_variable_style__mutmut_70,
    "x_detect_variable_style__mutmut_71": x_detect_variable_style__mutmut_71,
    "x_detect_variable_style__mutmut_72": x_detect_variable_style__mutmut_72,
    "x_detect_variable_style__mutmut_73": x_detect_variable_style__mutmut_73,
    "x_detect_variable_style__mutmut_74": x_detect_variable_style__mutmut_74,
    "x_detect_variable_style__mutmut_75": x_detect_variable_style__mutmut_75,
    "x_detect_variable_style__mutmut_76": x_detect_variable_style__mutmut_76,
    "x_detect_variable_style__mutmut_77": x_detect_variable_style__mutmut_77,
    "x_detect_variable_style__mutmut_78": x_detect_variable_style__mutmut_78,
    "x_detect_variable_style__mutmut_79": x_detect_variable_style__mutmut_79,
    "x_detect_variable_style__mutmut_80": x_detect_variable_style__mutmut_80,
    "x_detect_variable_style__mutmut_81": x_detect_variable_style__mutmut_81,
}


def detect_variable_style(*args, **kwargs):
    result = _mutmut_trampoline(
        x_detect_variable_style__mutmut_orig, x_detect_variable_style__mutmut_mutants, args, kwargs
    )
    return result


detect_variable_style.__signature__ = _mutmut_signature(x_detect_variable_style__mutmut_orig)
x_detect_variable_style__mutmut_orig.__name__ = "x_detect_variable_style"


def x_generate_insertion_text__mutmut_orig(
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


def x_generate_insertion_text__mutmut_1(
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
    indent = None
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


def x_generate_insertion_text__mutmut_2(
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
    indent = style.get(None, "")
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


def x_generate_insertion_text__mutmut_3(
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
    indent = style.get("indentation")
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


def x_generate_insertion_text__mutmut_4(
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
    indent = style.get("")
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


def x_generate_insertion_text__mutmut_5(
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
    indent = style.get(
        "indentation",
    )
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


def x_generate_insertion_text__mutmut_6(
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
    indent = style.get("XXindentationXX", "")
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


def x_generate_insertion_text__mutmut_7(
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
    indent = style.get("INDENTATION", "")
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


def x_generate_insertion_text__mutmut_8(
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
    indent = style.get("indentation", "XXXX")
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


def x_generate_insertion_text__mutmut_9(
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
    var_format = None
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


def x_generate_insertion_text__mutmut_10(
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
    var_format = style.get(None, "curly")
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


def x_generate_insertion_text__mutmut_11(
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
    var_format = style.get("format")
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


def x_generate_insertion_text__mutmut_12(
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
    var_format = style.get("curly")
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


def x_generate_insertion_text__mutmut_13(
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
    var_format = style.get(
        "format",
    )
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


def x_generate_insertion_text__mutmut_14(
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
    var_format = style.get("XXformatXX", "curly")
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


def x_generate_insertion_text__mutmut_15(
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
    var_format = style.get("FORMAT", "curly")
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


def x_generate_insertion_text__mutmut_16(
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
    var_format = style.get("format", "XXcurlyXX")
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


def x_generate_insertion_text__mutmut_17(
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
    var_format = style.get("format", "CURLY")
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


def x_generate_insertion_text__mutmut_18(
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
    label_style = None

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


def x_generate_insertion_text__mutmut_19(
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
    label_style = style.get(None, "colon")

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


def x_generate_insertion_text__mutmut_20(
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
    label_style = style.get("label_style")

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


def x_generate_insertion_text__mutmut_21(
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
    label_style = style.get("colon")

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


def x_generate_insertion_text__mutmut_22(
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
    label_style = style.get(
        "label_style",
    )

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


def x_generate_insertion_text__mutmut_23(
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
    label_style = style.get("XXlabel_styleXX", "colon")

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


def x_generate_insertion_text__mutmut_24(
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
    label_style = style.get("LABEL_STYLE", "colon")

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


def x_generate_insertion_text__mutmut_25(
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
    label_style = style.get("label_style", "XXcolonXX")

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


def x_generate_insertion_text__mutmut_26(
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
    label_style = style.get("label_style", "COLON")

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


def x_generate_insertion_text__mutmut_27(
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
    if var_format != "curly":
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


def x_generate_insertion_text__mutmut_28(
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
    if var_format == "XXcurlyXX":
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


def x_generate_insertion_text__mutmut_29(
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
    if var_format == "CURLY":
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


def x_generate_insertion_text__mutmut_30(
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
        var = None
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


def x_generate_insertion_text__mutmut_31(
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
    elif var_format != "angle":
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


def x_generate_insertion_text__mutmut_32(
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
    elif var_format == "XXangleXX":
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


def x_generate_insertion_text__mutmut_33(
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
    elif var_format == "ANGLE":
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


def x_generate_insertion_text__mutmut_34(
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
        var = None
    elif var_format == "dollar":
        var = f"${proposed_variable}"
    else:
        var = f"{{{proposed_variable}}}"  # default to curly

    # Format with label based on detected style
    if label_style == "equals":
        return f"{indent}{proposed_label}={var}\n"
    else:  # colon is default
        return f"{indent}{proposed_label}: {var}\n"


def x_generate_insertion_text__mutmut_35(
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
    elif var_format != "dollar":
        var = f"${proposed_variable}"
    else:
        var = f"{{{proposed_variable}}}"  # default to curly

    # Format with label based on detected style
    if label_style == "equals":
        return f"{indent}{proposed_label}={var}\n"
    else:  # colon is default
        return f"{indent}{proposed_label}: {var}\n"


def x_generate_insertion_text__mutmut_36(
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
    elif var_format == "XXdollarXX":
        var = f"${proposed_variable}"
    else:
        var = f"{{{proposed_variable}}}"  # default to curly

    # Format with label based on detected style
    if label_style == "equals":
        return f"{indent}{proposed_label}={var}\n"
    else:  # colon is default
        return f"{indent}{proposed_label}: {var}\n"


def x_generate_insertion_text__mutmut_37(
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
    elif var_format == "DOLLAR":
        var = f"${proposed_variable}"
    else:
        var = f"{{{proposed_variable}}}"  # default to curly

    # Format with label based on detected style
    if label_style == "equals":
        return f"{indent}{proposed_label}={var}\n"
    else:  # colon is default
        return f"{indent}{proposed_label}: {var}\n"


def x_generate_insertion_text__mutmut_38(
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
        var = None
    else:
        var = f"{{{proposed_variable}}}"  # default to curly

    # Format with label based on detected style
    if label_style == "equals":
        return f"{indent}{proposed_label}={var}\n"
    else:  # colon is default
        return f"{indent}{proposed_label}: {var}\n"


def x_generate_insertion_text__mutmut_39(
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
        var = None  # default to curly

    # Format with label based on detected style
    if label_style == "equals":
        return f"{indent}{proposed_label}={var}\n"
    else:  # colon is default
        return f"{indent}{proposed_label}: {var}\n"


def x_generate_insertion_text__mutmut_40(
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
    if label_style != "equals":
        return f"{indent}{proposed_label}={var}\n"
    else:  # colon is default
        return f"{indent}{proposed_label}: {var}\n"


def x_generate_insertion_text__mutmut_41(
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
    if label_style == "XXequalsXX":
        return f"{indent}{proposed_label}={var}\n"
    else:  # colon is default
        return f"{indent}{proposed_label}: {var}\n"


def x_generate_insertion_text__mutmut_42(
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
    if label_style == "EQUALS":
        return f"{indent}{proposed_label}={var}\n"
    else:  # colon is default
        return f"{indent}{proposed_label}: {var}\n"


x_generate_insertion_text__mutmut_mutants: ClassVar[MutantDict] = {
    "x_generate_insertion_text__mutmut_1": x_generate_insertion_text__mutmut_1,
    "x_generate_insertion_text__mutmut_2": x_generate_insertion_text__mutmut_2,
    "x_generate_insertion_text__mutmut_3": x_generate_insertion_text__mutmut_3,
    "x_generate_insertion_text__mutmut_4": x_generate_insertion_text__mutmut_4,
    "x_generate_insertion_text__mutmut_5": x_generate_insertion_text__mutmut_5,
    "x_generate_insertion_text__mutmut_6": x_generate_insertion_text__mutmut_6,
    "x_generate_insertion_text__mutmut_7": x_generate_insertion_text__mutmut_7,
    "x_generate_insertion_text__mutmut_8": x_generate_insertion_text__mutmut_8,
    "x_generate_insertion_text__mutmut_9": x_generate_insertion_text__mutmut_9,
    "x_generate_insertion_text__mutmut_10": x_generate_insertion_text__mutmut_10,
    "x_generate_insertion_text__mutmut_11": x_generate_insertion_text__mutmut_11,
    "x_generate_insertion_text__mutmut_12": x_generate_insertion_text__mutmut_12,
    "x_generate_insertion_text__mutmut_13": x_generate_insertion_text__mutmut_13,
    "x_generate_insertion_text__mutmut_14": x_generate_insertion_text__mutmut_14,
    "x_generate_insertion_text__mutmut_15": x_generate_insertion_text__mutmut_15,
    "x_generate_insertion_text__mutmut_16": x_generate_insertion_text__mutmut_16,
    "x_generate_insertion_text__mutmut_17": x_generate_insertion_text__mutmut_17,
    "x_generate_insertion_text__mutmut_18": x_generate_insertion_text__mutmut_18,
    "x_generate_insertion_text__mutmut_19": x_generate_insertion_text__mutmut_19,
    "x_generate_insertion_text__mutmut_20": x_generate_insertion_text__mutmut_20,
    "x_generate_insertion_text__mutmut_21": x_generate_insertion_text__mutmut_21,
    "x_generate_insertion_text__mutmut_22": x_generate_insertion_text__mutmut_22,
    "x_generate_insertion_text__mutmut_23": x_generate_insertion_text__mutmut_23,
    "x_generate_insertion_text__mutmut_24": x_generate_insertion_text__mutmut_24,
    "x_generate_insertion_text__mutmut_25": x_generate_insertion_text__mutmut_25,
    "x_generate_insertion_text__mutmut_26": x_generate_insertion_text__mutmut_26,
    "x_generate_insertion_text__mutmut_27": x_generate_insertion_text__mutmut_27,
    "x_generate_insertion_text__mutmut_28": x_generate_insertion_text__mutmut_28,
    "x_generate_insertion_text__mutmut_29": x_generate_insertion_text__mutmut_29,
    "x_generate_insertion_text__mutmut_30": x_generate_insertion_text__mutmut_30,
    "x_generate_insertion_text__mutmut_31": x_generate_insertion_text__mutmut_31,
    "x_generate_insertion_text__mutmut_32": x_generate_insertion_text__mutmut_32,
    "x_generate_insertion_text__mutmut_33": x_generate_insertion_text__mutmut_33,
    "x_generate_insertion_text__mutmut_34": x_generate_insertion_text__mutmut_34,
    "x_generate_insertion_text__mutmut_35": x_generate_insertion_text__mutmut_35,
    "x_generate_insertion_text__mutmut_36": x_generate_insertion_text__mutmut_36,
    "x_generate_insertion_text__mutmut_37": x_generate_insertion_text__mutmut_37,
    "x_generate_insertion_text__mutmut_38": x_generate_insertion_text__mutmut_38,
    "x_generate_insertion_text__mutmut_39": x_generate_insertion_text__mutmut_39,
    "x_generate_insertion_text__mutmut_40": x_generate_insertion_text__mutmut_40,
    "x_generate_insertion_text__mutmut_41": x_generate_insertion_text__mutmut_41,
    "x_generate_insertion_text__mutmut_42": x_generate_insertion_text__mutmut_42,
}


def generate_insertion_text(*args, **kwargs):
    result = _mutmut_trampoline(
        x_generate_insertion_text__mutmut_orig,
        x_generate_insertion_text__mutmut_mutants,
        args,
        kwargs,
    )
    return result


generate_insertion_text.__signature__ = _mutmut_signature(x_generate_insertion_text__mutmut_orig)
x_generate_insertion_text__mutmut_orig.__name__ = "x_generate_insertion_text"


def x_validate_prompt_syntax__mutmut_orig(prompt: str) -> list[str]:
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


def x_validate_prompt_syntax__mutmut_1(prompt: str) -> list[str]:
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
    warnings: list[str] = None

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


def x_validate_prompt_syntax__mutmut_2(prompt: str) -> list[str]:
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
    open_braces = None
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


def x_validate_prompt_syntax__mutmut_3(prompt: str) -> list[str]:
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
    open_braces = prompt.count(None)
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


def x_validate_prompt_syntax__mutmut_4(prompt: str) -> list[str]:
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
    open_braces = prompt.count("XX{XX")
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


def x_validate_prompt_syntax__mutmut_5(prompt: str) -> list[str]:
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
    close_braces = None
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


def x_validate_prompt_syntax__mutmut_6(prompt: str) -> list[str]:
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
    close_braces = prompt.count(None)
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


def x_validate_prompt_syntax__mutmut_7(prompt: str) -> list[str]:
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
    close_braces = prompt.count("XX}XX")
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


def x_validate_prompt_syntax__mutmut_8(prompt: str) -> list[str]:
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
    if open_braces == close_braces:
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


def x_validate_prompt_syntax__mutmut_9(prompt: str) -> list[str]:
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
        warnings.append(None)

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


def x_validate_prompt_syntax__mutmut_10(prompt: str) -> list[str]:
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
    variables = None
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


def x_validate_prompt_syntax__mutmut_11(prompt: str) -> list[str]:
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
    variables = re.findall(None, prompt)
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


def x_validate_prompt_syntax__mutmut_12(prompt: str) -> list[str]:
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
    variables = re.findall(r"\{([a-z_]+)\}", None)
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


def x_validate_prompt_syntax__mutmut_13(prompt: str) -> list[str]:
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
    variables = re.findall(prompt)
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


def x_validate_prompt_syntax__mutmut_14(prompt: str) -> list[str]:
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
    variables = re.findall(
        r"\{([a-z_]+)\}",
    )
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


def x_validate_prompt_syntax__mutmut_15(prompt: str) -> list[str]:
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
    variables = re.findall(r"XX\{([a-z_]+)\}XX", prompt)
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


def x_validate_prompt_syntax__mutmut_16(prompt: str) -> list[str]:
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
    variables = re.findall(r"\{([A-Z_]+)\}", prompt)
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


def x_validate_prompt_syntax__mutmut_17(prompt: str) -> list[str]:
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
    seen: set[str] = None
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


def x_validate_prompt_syntax__mutmut_18(prompt: str) -> list[str]:
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
    duplicates: set[str] = None
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


def x_validate_prompt_syntax__mutmut_19(prompt: str) -> list[str]:
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
        if var not in seen:
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


def x_validate_prompt_syntax__mutmut_20(prompt: str) -> list[str]:
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
            duplicates.add(None)
        seen.add(var)
    if duplicates:
        warnings.append(f"Duplicate variables: {', '.join(sorted(duplicates))}")

    # Check for unclosed angle brackets
    open_angles = prompt.count("<")
    close_angles = prompt.count(">")
    if open_angles != close_angles:
        warnings.append(f"Unbalanced angle brackets: {open_angles} open, {close_angles} close")

    return warnings


def x_validate_prompt_syntax__mutmut_21(prompt: str) -> list[str]:
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
        seen.add(None)
    if duplicates:
        warnings.append(f"Duplicate variables: {', '.join(sorted(duplicates))}")

    # Check for unclosed angle brackets
    open_angles = prompt.count("<")
    close_angles = prompt.count(">")
    if open_angles != close_angles:
        warnings.append(f"Unbalanced angle brackets: {open_angles} open, {close_angles} close")

    return warnings


def x_validate_prompt_syntax__mutmut_22(prompt: str) -> list[str]:
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
        warnings.append(None)

    # Check for unclosed angle brackets
    open_angles = prompt.count("<")
    close_angles = prompt.count(">")
    if open_angles != close_angles:
        warnings.append(f"Unbalanced angle brackets: {open_angles} open, {close_angles} close")

    return warnings


def x_validate_prompt_syntax__mutmut_23(prompt: str) -> list[str]:
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
        warnings.append(f"Duplicate variables: {', '.join(None)}")

    # Check for unclosed angle brackets
    open_angles = prompt.count("<")
    close_angles = prompt.count(">")
    if open_angles != close_angles:
        warnings.append(f"Unbalanced angle brackets: {open_angles} open, {close_angles} close")

    return warnings


def x_validate_prompt_syntax__mutmut_24(prompt: str) -> list[str]:
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
        warnings.append(f"Duplicate variables: {'XX, XX'.join(sorted(duplicates))}")

    # Check for unclosed angle brackets
    open_angles = prompt.count("<")
    close_angles = prompt.count(">")
    if open_angles != close_angles:
        warnings.append(f"Unbalanced angle brackets: {open_angles} open, {close_angles} close")

    return warnings


def x_validate_prompt_syntax__mutmut_25(prompt: str) -> list[str]:
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
        warnings.append(f"Duplicate variables: {', '.join(sorted(None))}")

    # Check for unclosed angle brackets
    open_angles = prompt.count("<")
    close_angles = prompt.count(">")
    if open_angles != close_angles:
        warnings.append(f"Unbalanced angle brackets: {open_angles} open, {close_angles} close")

    return warnings


def x_validate_prompt_syntax__mutmut_26(prompt: str) -> list[str]:
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
    open_angles = None
    close_angles = prompt.count(">")
    if open_angles != close_angles:
        warnings.append(f"Unbalanced angle brackets: {open_angles} open, {close_angles} close")

    return warnings


def x_validate_prompt_syntax__mutmut_27(prompt: str) -> list[str]:
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
    open_angles = prompt.count(None)
    close_angles = prompt.count(">")
    if open_angles != close_angles:
        warnings.append(f"Unbalanced angle brackets: {open_angles} open, {close_angles} close")

    return warnings


def x_validate_prompt_syntax__mutmut_28(prompt: str) -> list[str]:
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
    open_angles = prompt.count("XX<XX")
    close_angles = prompt.count(">")
    if open_angles != close_angles:
        warnings.append(f"Unbalanced angle brackets: {open_angles} open, {close_angles} close")

    return warnings


def x_validate_prompt_syntax__mutmut_29(prompt: str) -> list[str]:
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
    close_angles = None
    if open_angles != close_angles:
        warnings.append(f"Unbalanced angle brackets: {open_angles} open, {close_angles} close")

    return warnings


def x_validate_prompt_syntax__mutmut_30(prompt: str) -> list[str]:
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
    close_angles = prompt.count(None)
    if open_angles != close_angles:
        warnings.append(f"Unbalanced angle brackets: {open_angles} open, {close_angles} close")

    return warnings


def x_validate_prompt_syntax__mutmut_31(prompt: str) -> list[str]:
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
    close_angles = prompt.count("XX>XX")
    if open_angles != close_angles:
        warnings.append(f"Unbalanced angle brackets: {open_angles} open, {close_angles} close")

    return warnings


def x_validate_prompt_syntax__mutmut_32(prompt: str) -> list[str]:
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
    if open_angles == close_angles:
        warnings.append(f"Unbalanced angle brackets: {open_angles} open, {close_angles} close")

    return warnings


def x_validate_prompt_syntax__mutmut_33(prompt: str) -> list[str]:
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
        warnings.append(None)

    return warnings


x_validate_prompt_syntax__mutmut_mutants: ClassVar[MutantDict] = {
    "x_validate_prompt_syntax__mutmut_1": x_validate_prompt_syntax__mutmut_1,
    "x_validate_prompt_syntax__mutmut_2": x_validate_prompt_syntax__mutmut_2,
    "x_validate_prompt_syntax__mutmut_3": x_validate_prompt_syntax__mutmut_3,
    "x_validate_prompt_syntax__mutmut_4": x_validate_prompt_syntax__mutmut_4,
    "x_validate_prompt_syntax__mutmut_5": x_validate_prompt_syntax__mutmut_5,
    "x_validate_prompt_syntax__mutmut_6": x_validate_prompt_syntax__mutmut_6,
    "x_validate_prompt_syntax__mutmut_7": x_validate_prompt_syntax__mutmut_7,
    "x_validate_prompt_syntax__mutmut_8": x_validate_prompt_syntax__mutmut_8,
    "x_validate_prompt_syntax__mutmut_9": x_validate_prompt_syntax__mutmut_9,
    "x_validate_prompt_syntax__mutmut_10": x_validate_prompt_syntax__mutmut_10,
    "x_validate_prompt_syntax__mutmut_11": x_validate_prompt_syntax__mutmut_11,
    "x_validate_prompt_syntax__mutmut_12": x_validate_prompt_syntax__mutmut_12,
    "x_validate_prompt_syntax__mutmut_13": x_validate_prompt_syntax__mutmut_13,
    "x_validate_prompt_syntax__mutmut_14": x_validate_prompt_syntax__mutmut_14,
    "x_validate_prompt_syntax__mutmut_15": x_validate_prompt_syntax__mutmut_15,
    "x_validate_prompt_syntax__mutmut_16": x_validate_prompt_syntax__mutmut_16,
    "x_validate_prompt_syntax__mutmut_17": x_validate_prompt_syntax__mutmut_17,
    "x_validate_prompt_syntax__mutmut_18": x_validate_prompt_syntax__mutmut_18,
    "x_validate_prompt_syntax__mutmut_19": x_validate_prompt_syntax__mutmut_19,
    "x_validate_prompt_syntax__mutmut_20": x_validate_prompt_syntax__mutmut_20,
    "x_validate_prompt_syntax__mutmut_21": x_validate_prompt_syntax__mutmut_21,
    "x_validate_prompt_syntax__mutmut_22": x_validate_prompt_syntax__mutmut_22,
    "x_validate_prompt_syntax__mutmut_23": x_validate_prompt_syntax__mutmut_23,
    "x_validate_prompt_syntax__mutmut_24": x_validate_prompt_syntax__mutmut_24,
    "x_validate_prompt_syntax__mutmut_25": x_validate_prompt_syntax__mutmut_25,
    "x_validate_prompt_syntax__mutmut_26": x_validate_prompt_syntax__mutmut_26,
    "x_validate_prompt_syntax__mutmut_27": x_validate_prompt_syntax__mutmut_27,
    "x_validate_prompt_syntax__mutmut_28": x_validate_prompt_syntax__mutmut_28,
    "x_validate_prompt_syntax__mutmut_29": x_validate_prompt_syntax__mutmut_29,
    "x_validate_prompt_syntax__mutmut_30": x_validate_prompt_syntax__mutmut_30,
    "x_validate_prompt_syntax__mutmut_31": x_validate_prompt_syntax__mutmut_31,
    "x_validate_prompt_syntax__mutmut_32": x_validate_prompt_syntax__mutmut_32,
    "x_validate_prompt_syntax__mutmut_33": x_validate_prompt_syntax__mutmut_33,
}


def validate_prompt_syntax(*args, **kwargs):
    result = _mutmut_trampoline(
        x_validate_prompt_syntax__mutmut_orig,
        x_validate_prompt_syntax__mutmut_mutants,
        args,
        kwargs,
    )
    return result


validate_prompt_syntax.__signature__ = _mutmut_signature(x_validate_prompt_syntax__mutmut_orig)
x_validate_prompt_syntax__mutmut_orig.__name__ = "x_validate_prompt_syntax"


def x_apply_suggestion_to_prompt__mutmut_orig(
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


def x_apply_suggestion_to_prompt__mutmut_1(
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
    style = None
    insert_idx, _insert_type = find_insertion_point(prompt, target_section, insertion_point)
    new_text = generate_insertion_text(proposed_label, proposed_variable, style)

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_2(
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
    style = detect_variable_style(None)
    insert_idx, _insert_type = find_insertion_point(prompt, target_section, insertion_point)
    new_text = generate_insertion_text(proposed_label, proposed_variable, style)

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_3(
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
    insert_idx, _insert_type = None
    new_text = generate_insertion_text(proposed_label, proposed_variable, style)

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_4(
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
    insert_idx, _insert_type = find_insertion_point(None, target_section, insertion_point)
    new_text = generate_insertion_text(proposed_label, proposed_variable, style)

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_5(
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
    insert_idx, _insert_type = find_insertion_point(prompt, None, insertion_point)
    new_text = generate_insertion_text(proposed_label, proposed_variable, style)

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_6(
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
    insert_idx, _insert_type = find_insertion_point(prompt, target_section, None)
    new_text = generate_insertion_text(proposed_label, proposed_variable, style)

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_7(
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
    insert_idx, _insert_type = find_insertion_point(target_section, insertion_point)
    new_text = generate_insertion_text(proposed_label, proposed_variable, style)

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_8(
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
    insert_idx, _insert_type = find_insertion_point(prompt, insertion_point)
    new_text = generate_insertion_text(proposed_label, proposed_variable, style)

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_9(
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
    insert_idx, _insert_type = find_insertion_point(
        prompt,
        target_section,
    )
    new_text = generate_insertion_text(proposed_label, proposed_variable, style)

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_10(
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
    new_text = None

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_11(
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
    new_text = generate_insertion_text(None, proposed_variable, style)

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_12(
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
    new_text = generate_insertion_text(proposed_label, None, style)

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_13(
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
    new_text = generate_insertion_text(proposed_label, proposed_variable, None)

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_14(
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
    new_text = generate_insertion_text(proposed_variable, style)

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_15(
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
    new_text = generate_insertion_text(proposed_label, style)

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_16(
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
    new_text = generate_insertion_text(
        proposed_label,
        proposed_variable,
    )

    return prompt[:insert_idx] + new_text + prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_17(
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

    return prompt[:insert_idx] + new_text - prompt[insert_idx:]


def x_apply_suggestion_to_prompt__mutmut_18(
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

    return prompt[:insert_idx] - new_text + prompt[insert_idx:]


x_apply_suggestion_to_prompt__mutmut_mutants: ClassVar[MutantDict] = {
    "x_apply_suggestion_to_prompt__mutmut_1": x_apply_suggestion_to_prompt__mutmut_1,
    "x_apply_suggestion_to_prompt__mutmut_2": x_apply_suggestion_to_prompt__mutmut_2,
    "x_apply_suggestion_to_prompt__mutmut_3": x_apply_suggestion_to_prompt__mutmut_3,
    "x_apply_suggestion_to_prompt__mutmut_4": x_apply_suggestion_to_prompt__mutmut_4,
    "x_apply_suggestion_to_prompt__mutmut_5": x_apply_suggestion_to_prompt__mutmut_5,
    "x_apply_suggestion_to_prompt__mutmut_6": x_apply_suggestion_to_prompt__mutmut_6,
    "x_apply_suggestion_to_prompt__mutmut_7": x_apply_suggestion_to_prompt__mutmut_7,
    "x_apply_suggestion_to_prompt__mutmut_8": x_apply_suggestion_to_prompt__mutmut_8,
    "x_apply_suggestion_to_prompt__mutmut_9": x_apply_suggestion_to_prompt__mutmut_9,
    "x_apply_suggestion_to_prompt__mutmut_10": x_apply_suggestion_to_prompt__mutmut_10,
    "x_apply_suggestion_to_prompt__mutmut_11": x_apply_suggestion_to_prompt__mutmut_11,
    "x_apply_suggestion_to_prompt__mutmut_12": x_apply_suggestion_to_prompt__mutmut_12,
    "x_apply_suggestion_to_prompt__mutmut_13": x_apply_suggestion_to_prompt__mutmut_13,
    "x_apply_suggestion_to_prompt__mutmut_14": x_apply_suggestion_to_prompt__mutmut_14,
    "x_apply_suggestion_to_prompt__mutmut_15": x_apply_suggestion_to_prompt__mutmut_15,
    "x_apply_suggestion_to_prompt__mutmut_16": x_apply_suggestion_to_prompt__mutmut_16,
    "x_apply_suggestion_to_prompt__mutmut_17": x_apply_suggestion_to_prompt__mutmut_17,
    "x_apply_suggestion_to_prompt__mutmut_18": x_apply_suggestion_to_prompt__mutmut_18,
}


def apply_suggestion_to_prompt(*args, **kwargs):
    result = _mutmut_trampoline(
        x_apply_suggestion_to_prompt__mutmut_orig,
        x_apply_suggestion_to_prompt__mutmut_mutants,
        args,
        kwargs,
    )
    return result


apply_suggestion_to_prompt.__signature__ = _mutmut_signature(
    x_apply_suggestion_to_prompt__mutmut_orig
)
x_apply_suggestion_to_prompt__mutmut_orig.__name__ = "x_apply_suggestion_to_prompt"
