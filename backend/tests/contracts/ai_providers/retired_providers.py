# Evidence-only module: the retired tier's frozen source, kept for
# characterization pins. NOT SHIPPED CODE.
#
# Nothing under backend/services or backend/api imports this file, and pytest
# never collects it (no test_ prefix - a module of frozen code, not a test).
# Its only readers are the characterization pins in
# test_conformance_semantics.py::TestS5ThinkTagStripping.
#
# Why this file exists (R8 S2, 2026-09-29): the two think-tag strip sites the
# D1-D6 Tier-A defect characterization is pinned against -
# backend/services/nemotron_analyzer.py (pattern defs :164-165, sub sites :270
# and :4664) and backend/services/summary_generator.py (:440) - were deleted
# with the legacy LLM tier. Those pins are the adjudicated evidence record for
# the swap-readiness defect set (plan 2026-09-19-swap-readiness-72h; the golden
# list in scripts/check-ai-provider-parity.py). If the pins quietly disappear
# the contract tier goes silent about a defect set that was ruled real, so the
# frozen source keeps them assertable. Three retarget options were weighed and
# rejected:
#
#   * delete the pins       - un-pins adjudicated evidence with no visible
#                             tombstone;
#   * pytest.skip           - a skip IS a suppression: it needs a registry
#                             entry and a ratchet category, and it stops
#                             asserting anything;
#   * git show at test time - CI checkouts are shallow clones, so the deleted
#                             blob is not guaranteed present and the pin would
#                             be un-runnable in CI.
#
# Everything below the marker is copied VERBATIM from commit 0ba90d5f (the S2a
# parent - the last commit that carried the analyzer): the pattern defs at
# source :164-165, extract_reasoning_and_response at :214-276 (docstring
# examples included, since the analyzer itself contained them), and the second
# strip site at :4663-4675 dedented by 8 (it lived inside a method). No line
# was edited; s5a reads the pattern literals and s5b executes the function
# exactly as they read/executed the deleted originals, and the file greps
# clean of both absence spellings s5a pins.

from __future__ import annotations

import re

# ---- verbatim from backend/services/nemotron_analyzer.py ----
_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)
_THINK_EXTRACT_PATTERN = re.compile(r"<think>(.*?)</think>", re.DOTALL)


def extract_reasoning_and_response(text: str) -> tuple[str, str]:
    """Extract chain-of-thought reasoning and final JSON response from LLM output.

    Nemotron models with 'detailed thinking on' enabled output reasoning in
    <think>...</think> tags before the JSON response. This function separates
    the reasoning from the response for structured storage and analysis.

    Args:
        text: Raw LLM completion text that may contain <think>...</think> blocks
            followed by JSON response.

    Returns:
        A tuple of (reasoning, json_response) where:
        - reasoning: The content extracted from <think>...</think> tags,
            or empty string if no think block is present
        - json_response: The remaining text after removing think blocks,
            which should contain the JSON response

    Examples:
        >>> text = "<think>Analyzing the scene...</think>{\"risk_score\": 25}"
        >>> reasoning, response = extract_reasoning_and_response(text)
        >>> reasoning
        'Analyzing the scene...'
        >>> response
        '{"risk_score": 25}'

        >>> # Text without think blocks
        >>> text = '{"risk_score": 25, "risk_level": "low"}'
        >>> reasoning, response = extract_reasoning_and_response(text)
        >>> reasoning
        ''
        >>> response
        '{"risk_score": 25, "risk_level": "low"}'

        >>> # Handles malformed/incomplete tags gracefully
        >>> text = "<think>Incomplete reasoning"
        >>> reasoning, response = extract_reasoning_and_response(text)
        >>> reasoning
        ''  # No closing tag, so no reasoning extracted
        >>> response
        '<think>Incomplete reasoning'

    Note:
        This function is designed to work with Nemotron's chain-of-thought
        reasoning feature (NEM-3727). The reasoning content can be stored
        separately for debugging, auditing, and model improvement.
    """
    # Try to extract content from <think>...</think> blocks
    think_match = _THINK_EXTRACT_PATTERN.search(text)

    if think_match:
        # Extract reasoning content (strip whitespace for cleaner output)
        reasoning = think_match.group(1).strip()

        # Remove all think blocks from text to get the response
        # Uses the existing _THINK_PATTERN for consistency
        json_response = _THINK_PATTERN.sub("", text).strip()

        return reasoning, json_response

    # No think block found - return empty reasoning and original text
    return "", text.strip()


# The analyzer's SECOND strip site (nemotron_analyzer.py:4663-4675, inside its
# risk-response parse method), verbatim but dedented by 8 and wrapped in a
# module-level function so it is legal at this scope. Same _THINK_PATTERN
# object, a second .sub() call: "two strip sites, one regex object" (s5c)
# counts 1 + 1 here exactly as it counted 2 in the analyzer.
def _frozen_second_strip_site(text: str) -> str:
    # Strip <think>...</think> reasoning blocks (Nemotron-3-Nano format)
    cleaned_text = _THINK_PATTERN.sub("", text).strip()

    # Handle incomplete think blocks (model may not close the tag)
    if "<think>" in cleaned_text:
        parts = cleaned_text.split("</think>")
        if len(parts) > 1:
            cleaned_text = parts[-1].strip()
        else:
            think_start = cleaned_text.find("<think>")
            json_start = cleaned_text.find("{", think_start)
            if json_start != -1:
                cleaned_text = cleaned_text[json_start:]
