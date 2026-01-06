"""Full-text search service for events.

This module provides PostgreSQL full-text search capabilities for events,
supporting:
- Basic text search across summary, reasoning, object types, and camera names
- Phrase search using double quotes (e.g., "suspicious person")
- Boolean operators (AND, OR, NOT)
- Filtering by time range, camera IDs, severity levels, and object types
- Relevance-ranked results with scores
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Float, and_, cast, func, or_, select, text
from sqlalchemy.dialects.postgresql import REGCONFIG

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import escape_ilike_pattern
from backend.core.logging import get_logger
from backend.models.camera import Camera
from backend.models.event import Event

logger = get_logger(__name__)
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


@dataclass
class SearchFilters:
    """Filters for event search."""

    start_date: datetime | None = None
    end_date: datetime | None = None
    camera_ids: list[str] = field(default_factory=list)
    severity: list[str] = field(
        default_factory=list
    )  # risk_level values: low, medium, high, critical
    object_types: list[str] = field(default_factory=list)
    reviewed: bool | None = None


@dataclass
class SearchResult:
    """A single search result with relevance score."""

    id: int
    camera_id: str
    camera_name: str | None
    started_at: datetime
    ended_at: datetime | None
    risk_score: int | None
    risk_level: str | None
    summary: str | None
    reasoning: str | None
    reviewed: bool
    detection_count: int
    detection_ids: list[int]
    object_types: str | None
    relevance_score: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "summary": self.summary,
            "reasoning": self.reasoning,
            "reviewed": self.reviewed,
            "detection_count": self.detection_count,
            "detection_ids": self.detection_ids,
            "object_types": self.object_types,
            "relevance_score": self.relevance_score,
        }


@dataclass
class SearchResponse:
    """Response from search_events containing results and pagination info."""

    results: list[SearchResult]
    total_count: int
    limit: int
    offset: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "results": [r.to_dict() for r in self.results],
            "total_count": self.total_count,
            "limit": self.limit,
            "offset": self.offset,
        }


def x__parse_detection_ids__mutmut_orig(detection_ids_str: str | None) -> list[int]:
    """Parse detection IDs stored as JSON array to list of integers.

    Args:
        detection_ids_str: JSON array string of detection IDs (e.g., "[1, 2, 3]")
                          or None/empty string

    Returns:
        List of integer detection IDs. Empty list if input is None or empty.
    """
    if not detection_ids_str:
        return []
    try:
        ids = json.loads(detection_ids_str)
        if isinstance(ids, list):
            return [int(d) for d in ids]
        return []
    except (json.JSONDecodeError, ValueError):
        # Fallback for legacy comma-separated format
        return [int(d.strip()) for d in detection_ids_str.split(",") if d.strip()]


def x__parse_detection_ids__mutmut_1(detection_ids_str: str | None) -> list[int]:
    """Parse detection IDs stored as JSON array to list of integers.

    Args:
        detection_ids_str: JSON array string of detection IDs (e.g., "[1, 2, 3]")
                          or None/empty string

    Returns:
        List of integer detection IDs. Empty list if input is None or empty.
    """
    if detection_ids_str:
        return []
    try:
        ids = json.loads(detection_ids_str)
        if isinstance(ids, list):
            return [int(d) for d in ids]
        return []
    except (json.JSONDecodeError, ValueError):
        # Fallback for legacy comma-separated format
        return [int(d.strip()) for d in detection_ids_str.split(",") if d.strip()]


def x__parse_detection_ids__mutmut_2(detection_ids_str: str | None) -> list[int]:
    """Parse detection IDs stored as JSON array to list of integers.

    Args:
        detection_ids_str: JSON array string of detection IDs (e.g., "[1, 2, 3]")
                          or None/empty string

    Returns:
        List of integer detection IDs. Empty list if input is None or empty.
    """
    if not detection_ids_str:
        return []
    try:
        ids = None
        if isinstance(ids, list):
            return [int(d) for d in ids]
        return []
    except (json.JSONDecodeError, ValueError):
        # Fallback for legacy comma-separated format
        return [int(d.strip()) for d in detection_ids_str.split(",") if d.strip()]


def x__parse_detection_ids__mutmut_3(detection_ids_str: str | None) -> list[int]:
    """Parse detection IDs stored as JSON array to list of integers.

    Args:
        detection_ids_str: JSON array string of detection IDs (e.g., "[1, 2, 3]")
                          or None/empty string

    Returns:
        List of integer detection IDs. Empty list if input is None or empty.
    """
    if not detection_ids_str:
        return []
    try:
        ids = json.loads(None)
        if isinstance(ids, list):
            return [int(d) for d in ids]
        return []
    except (json.JSONDecodeError, ValueError):
        # Fallback for legacy comma-separated format
        return [int(d.strip()) for d in detection_ids_str.split(",") if d.strip()]


def x__parse_detection_ids__mutmut_4(detection_ids_str: str | None) -> list[int]:
    """Parse detection IDs stored as JSON array to list of integers.

    Args:
        detection_ids_str: JSON array string of detection IDs (e.g., "[1, 2, 3]")
                          or None/empty string

    Returns:
        List of integer detection IDs. Empty list if input is None or empty.
    """
    if not detection_ids_str:
        return []
    try:
        ids = json.loads(detection_ids_str)
        if isinstance(ids, list):
            return [int(None) for d in ids]
        return []
    except (json.JSONDecodeError, ValueError):
        # Fallback for legacy comma-separated format
        return [int(d.strip()) for d in detection_ids_str.split(",") if d.strip()]


def x__parse_detection_ids__mutmut_5(detection_ids_str: str | None) -> list[int]:
    """Parse detection IDs stored as JSON array to list of integers.

    Args:
        detection_ids_str: JSON array string of detection IDs (e.g., "[1, 2, 3]")
                          or None/empty string

    Returns:
        List of integer detection IDs. Empty list if input is None or empty.
    """
    if not detection_ids_str:
        return []
    try:
        ids = json.loads(detection_ids_str)
        if isinstance(ids, list):
            return [int(d) for d in ids]
        return []
    except (json.JSONDecodeError, ValueError):
        # Fallback for legacy comma-separated format
        return [int(None) for d in detection_ids_str.split(",") if d.strip()]


def x__parse_detection_ids__mutmut_6(detection_ids_str: str | None) -> list[int]:
    """Parse detection IDs stored as JSON array to list of integers.

    Args:
        detection_ids_str: JSON array string of detection IDs (e.g., "[1, 2, 3]")
                          or None/empty string

    Returns:
        List of integer detection IDs. Empty list if input is None or empty.
    """
    if not detection_ids_str:
        return []
    try:
        ids = json.loads(detection_ids_str)
        if isinstance(ids, list):
            return [int(d) for d in ids]
        return []
    except (json.JSONDecodeError, ValueError):
        # Fallback for legacy comma-separated format
        return [int(d.strip()) for d in detection_ids_str.split(None) if d.strip()]


def x__parse_detection_ids__mutmut_7(detection_ids_str: str | None) -> list[int]:
    """Parse detection IDs stored as JSON array to list of integers.

    Args:
        detection_ids_str: JSON array string of detection IDs (e.g., "[1, 2, 3]")
                          or None/empty string

    Returns:
        List of integer detection IDs. Empty list if input is None or empty.
    """
    if not detection_ids_str:
        return []
    try:
        ids = json.loads(detection_ids_str)
        if isinstance(ids, list):
            return [int(d) for d in ids]
        return []
    except (json.JSONDecodeError, ValueError):
        # Fallback for legacy comma-separated format
        return [int(d.strip()) for d in detection_ids_str.split("XX,XX") if d.strip()]


x__parse_detection_ids__mutmut_mutants: ClassVar[MutantDict] = {
    "x__parse_detection_ids__mutmut_1": x__parse_detection_ids__mutmut_1,
    "x__parse_detection_ids__mutmut_2": x__parse_detection_ids__mutmut_2,
    "x__parse_detection_ids__mutmut_3": x__parse_detection_ids__mutmut_3,
    "x__parse_detection_ids__mutmut_4": x__parse_detection_ids__mutmut_4,
    "x__parse_detection_ids__mutmut_5": x__parse_detection_ids__mutmut_5,
    "x__parse_detection_ids__mutmut_6": x__parse_detection_ids__mutmut_6,
    "x__parse_detection_ids__mutmut_7": x__parse_detection_ids__mutmut_7,
}


def _parse_detection_ids(*args, **kwargs):
    result = _mutmut_trampoline(
        x__parse_detection_ids__mutmut_orig, x__parse_detection_ids__mutmut_mutants, args, kwargs
    )
    return result


_parse_detection_ids.__signature__ = _mutmut_signature(x__parse_detection_ids__mutmut_orig)
x__parse_detection_ids__mutmut_orig.__name__ = "x__parse_detection_ids"


def x__process_phrase_token__mutmut_orig(
    phrase_idx: int, phrases: list[str], result_parts: list[str]
) -> int:
    """Process a phrase placeholder token."""
    if phrase_idx < len(phrases):
        phrase_words = phrases[phrase_idx].split()
        if phrase_words:
            phrase_tsquery = " <-> ".join(phrase_words)
            result_parts.append(f"({phrase_tsquery})")
        return phrase_idx + 1
    return phrase_idx


def x__process_phrase_token__mutmut_1(
    phrase_idx: int, phrases: list[str], result_parts: list[str]
) -> int:
    """Process a phrase placeholder token."""
    if phrase_idx <= len(phrases):
        phrase_words = phrases[phrase_idx].split()
        if phrase_words:
            phrase_tsquery = " <-> ".join(phrase_words)
            result_parts.append(f"({phrase_tsquery})")
        return phrase_idx + 1
    return phrase_idx


def x__process_phrase_token__mutmut_2(
    phrase_idx: int, phrases: list[str], result_parts: list[str]
) -> int:
    """Process a phrase placeholder token."""
    if phrase_idx < len(phrases):
        phrase_words = None
        if phrase_words:
            phrase_tsquery = " <-> ".join(phrase_words)
            result_parts.append(f"({phrase_tsquery})")
        return phrase_idx + 1
    return phrase_idx


def x__process_phrase_token__mutmut_3(
    phrase_idx: int, phrases: list[str], result_parts: list[str]
) -> int:
    """Process a phrase placeholder token."""
    if phrase_idx < len(phrases):
        phrase_words = phrases[phrase_idx].split()
        if phrase_words:
            phrase_tsquery = None
            result_parts.append(f"({phrase_tsquery})")
        return phrase_idx + 1
    return phrase_idx


def x__process_phrase_token__mutmut_4(
    phrase_idx: int, phrases: list[str], result_parts: list[str]
) -> int:
    """Process a phrase placeholder token."""
    if phrase_idx < len(phrases):
        phrase_words = phrases[phrase_idx].split()
        if phrase_words:
            phrase_tsquery = " <-> ".join(None)
            result_parts.append(f"({phrase_tsquery})")
        return phrase_idx + 1
    return phrase_idx


def x__process_phrase_token__mutmut_5(
    phrase_idx: int, phrases: list[str], result_parts: list[str]
) -> int:
    """Process a phrase placeholder token."""
    if phrase_idx < len(phrases):
        phrase_words = phrases[phrase_idx].split()
        if phrase_words:
            phrase_tsquery = "XX <-> XX".join(phrase_words)
            result_parts.append(f"({phrase_tsquery})")
        return phrase_idx + 1
    return phrase_idx


def x__process_phrase_token__mutmut_6(
    phrase_idx: int, phrases: list[str], result_parts: list[str]
) -> int:
    """Process a phrase placeholder token."""
    if phrase_idx < len(phrases):
        phrase_words = phrases[phrase_idx].split()
        if phrase_words:
            phrase_tsquery = " <-> ".join(phrase_words)
            result_parts.append(None)
        return phrase_idx + 1
    return phrase_idx


def x__process_phrase_token__mutmut_7(
    phrase_idx: int, phrases: list[str], result_parts: list[str]
) -> int:
    """Process a phrase placeholder token."""
    if phrase_idx < len(phrases):
        phrase_words = phrases[phrase_idx].split()
        if phrase_words:
            phrase_tsquery = " <-> ".join(phrase_words)
            result_parts.append(f"({phrase_tsquery})")
        return phrase_idx - 1
    return phrase_idx


def x__process_phrase_token__mutmut_8(
    phrase_idx: int, phrases: list[str], result_parts: list[str]
) -> int:
    """Process a phrase placeholder token."""
    if phrase_idx < len(phrases):
        phrase_words = phrases[phrase_idx].split()
        if phrase_words:
            phrase_tsquery = " <-> ".join(phrase_words)
            result_parts.append(f"({phrase_tsquery})")
        return phrase_idx + 2
    return phrase_idx


x__process_phrase_token__mutmut_mutants: ClassVar[MutantDict] = {
    "x__process_phrase_token__mutmut_1": x__process_phrase_token__mutmut_1,
    "x__process_phrase_token__mutmut_2": x__process_phrase_token__mutmut_2,
    "x__process_phrase_token__mutmut_3": x__process_phrase_token__mutmut_3,
    "x__process_phrase_token__mutmut_4": x__process_phrase_token__mutmut_4,
    "x__process_phrase_token__mutmut_5": x__process_phrase_token__mutmut_5,
    "x__process_phrase_token__mutmut_6": x__process_phrase_token__mutmut_6,
    "x__process_phrase_token__mutmut_7": x__process_phrase_token__mutmut_7,
    "x__process_phrase_token__mutmut_8": x__process_phrase_token__mutmut_8,
}


def _process_phrase_token(*args, **kwargs):
    result = _mutmut_trampoline(
        x__process_phrase_token__mutmut_orig, x__process_phrase_token__mutmut_mutants, args, kwargs
    )
    return result


_process_phrase_token.__signature__ = _mutmut_signature(x__process_phrase_token__mutmut_orig)
x__process_phrase_token__mutmut_orig.__name__ = "x__process_phrase_token"


def x__process_not_token__mutmut_orig(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_1(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx - 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_2(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 2 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_3(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 <= len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_4(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = None
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_5(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx - 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_6(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 2].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_7(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = None
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_8(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" - "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_9(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "XXPHRASE_XX" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_10(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "phrase_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_11(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "XXPLACEHOLDERXX"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_12(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "placeholder"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_13(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token or next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_14(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.lower() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_15(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_16(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("XXANDXX", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_17(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("and", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_18(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "XXORXX", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_19(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "or", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_20(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "XXNOTXX", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_21(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "not", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_22(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(None)
            return idx + 2, True
    return idx + 1, False


def x__process_not_token__mutmut_23(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx - 2, True
    return idx + 1, False


def x__process_not_token__mutmut_24(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 3, True
    return idx + 1, False


def x__process_not_token__mutmut_25(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, False
    return idx + 1, False


def x__process_not_token__mutmut_26(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx - 1, False


def x__process_not_token__mutmut_27(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 2, False


def x__process_not_token__mutmut_28(
    idx: int, tokens: list[str], result_parts: list[str]
) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, True


x__process_not_token__mutmut_mutants: ClassVar[MutantDict] = {
    "x__process_not_token__mutmut_1": x__process_not_token__mutmut_1,
    "x__process_not_token__mutmut_2": x__process_not_token__mutmut_2,
    "x__process_not_token__mutmut_3": x__process_not_token__mutmut_3,
    "x__process_not_token__mutmut_4": x__process_not_token__mutmut_4,
    "x__process_not_token__mutmut_5": x__process_not_token__mutmut_5,
    "x__process_not_token__mutmut_6": x__process_not_token__mutmut_6,
    "x__process_not_token__mutmut_7": x__process_not_token__mutmut_7,
    "x__process_not_token__mutmut_8": x__process_not_token__mutmut_8,
    "x__process_not_token__mutmut_9": x__process_not_token__mutmut_9,
    "x__process_not_token__mutmut_10": x__process_not_token__mutmut_10,
    "x__process_not_token__mutmut_11": x__process_not_token__mutmut_11,
    "x__process_not_token__mutmut_12": x__process_not_token__mutmut_12,
    "x__process_not_token__mutmut_13": x__process_not_token__mutmut_13,
    "x__process_not_token__mutmut_14": x__process_not_token__mutmut_14,
    "x__process_not_token__mutmut_15": x__process_not_token__mutmut_15,
    "x__process_not_token__mutmut_16": x__process_not_token__mutmut_16,
    "x__process_not_token__mutmut_17": x__process_not_token__mutmut_17,
    "x__process_not_token__mutmut_18": x__process_not_token__mutmut_18,
    "x__process_not_token__mutmut_19": x__process_not_token__mutmut_19,
    "x__process_not_token__mutmut_20": x__process_not_token__mutmut_20,
    "x__process_not_token__mutmut_21": x__process_not_token__mutmut_21,
    "x__process_not_token__mutmut_22": x__process_not_token__mutmut_22,
    "x__process_not_token__mutmut_23": x__process_not_token__mutmut_23,
    "x__process_not_token__mutmut_24": x__process_not_token__mutmut_24,
    "x__process_not_token__mutmut_25": x__process_not_token__mutmut_25,
    "x__process_not_token__mutmut_26": x__process_not_token__mutmut_26,
    "x__process_not_token__mutmut_27": x__process_not_token__mutmut_27,
    "x__process_not_token__mutmut_28": x__process_not_token__mutmut_28,
}


def _process_not_token(*args, **kwargs):
    result = _mutmut_trampoline(
        x__process_not_token__mutmut_orig, x__process_not_token__mutmut_mutants, args, kwargs
    )
    return result


_process_not_token.__signature__ = _mutmut_signature(x__process_not_token__mutmut_orig)
x__process_not_token__mutmut_orig.__name__ = "x__process_not_token"


def x__process_regular_token__mutmut_orig(token: str, result_parts: list[str]) -> None:
    """Process a regular word token."""
    clean_token = re.sub(r"[^\w]", "", token)
    if clean_token:
        result_parts.append(clean_token)


def x__process_regular_token__mutmut_1(token: str, result_parts: list[str]) -> None:
    """Process a regular word token."""
    clean_token = None
    if clean_token:
        result_parts.append(clean_token)


def x__process_regular_token__mutmut_2(token: str, result_parts: list[str]) -> None:
    """Process a regular word token."""
    clean_token = re.sub(None, "", token)
    if clean_token:
        result_parts.append(clean_token)


def x__process_regular_token__mutmut_3(token: str, result_parts: list[str]) -> None:
    """Process a regular word token."""
    clean_token = re.sub(r"[^\w]", None, token)
    if clean_token:
        result_parts.append(clean_token)


def x__process_regular_token__mutmut_4(token: str, result_parts: list[str]) -> None:
    """Process a regular word token."""
    clean_token = re.sub(r"[^\w]", "", None)
    if clean_token:
        result_parts.append(clean_token)


def x__process_regular_token__mutmut_5(token: str, result_parts: list[str]) -> None:
    """Process a regular word token."""
    clean_token = re.sub("", token)
    if clean_token:
        result_parts.append(clean_token)


def x__process_regular_token__mutmut_6(token: str, result_parts: list[str]) -> None:
    """Process a regular word token."""
    clean_token = re.sub(r"[^\w]", token)
    if clean_token:
        result_parts.append(clean_token)


def x__process_regular_token__mutmut_7(token: str, result_parts: list[str]) -> None:
    """Process a regular word token."""
    clean_token = re.sub(
        r"[^\w]",
        "",
    )
    if clean_token:
        result_parts.append(clean_token)


def x__process_regular_token__mutmut_8(token: str, result_parts: list[str]) -> None:
    """Process a regular word token."""
    clean_token = re.sub(r"XX[^\w]XX", "", token)
    if clean_token:
        result_parts.append(clean_token)


def x__process_regular_token__mutmut_9(token: str, result_parts: list[str]) -> None:
    """Process a regular word token."""
    clean_token = re.sub(r"[^\w]", "XXXX", token)
    if clean_token:
        result_parts.append(clean_token)


def x__process_regular_token__mutmut_10(token: str, result_parts: list[str]) -> None:
    """Process a regular word token."""
    clean_token = re.sub(r"[^\w]", "", token)
    if clean_token:
        result_parts.append(None)


x__process_regular_token__mutmut_mutants: ClassVar[MutantDict] = {
    "x__process_regular_token__mutmut_1": x__process_regular_token__mutmut_1,
    "x__process_regular_token__mutmut_2": x__process_regular_token__mutmut_2,
    "x__process_regular_token__mutmut_3": x__process_regular_token__mutmut_3,
    "x__process_regular_token__mutmut_4": x__process_regular_token__mutmut_4,
    "x__process_regular_token__mutmut_5": x__process_regular_token__mutmut_5,
    "x__process_regular_token__mutmut_6": x__process_regular_token__mutmut_6,
    "x__process_regular_token__mutmut_7": x__process_regular_token__mutmut_7,
    "x__process_regular_token__mutmut_8": x__process_regular_token__mutmut_8,
    "x__process_regular_token__mutmut_9": x__process_regular_token__mutmut_9,
    "x__process_regular_token__mutmut_10": x__process_regular_token__mutmut_10,
}


def _process_regular_token(*args, **kwargs):
    result = _mutmut_trampoline(
        x__process_regular_token__mutmut_orig,
        x__process_regular_token__mutmut_mutants,
        args,
        kwargs,
    )
    return result


_process_regular_token.__signature__ = _mutmut_signature(x__process_regular_token__mutmut_orig)
x__process_regular_token__mutmut_orig.__name__ = "x__process_regular_token"


def x__process_token__mutmut_orig(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_1(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = None

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_2(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.lower()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_3(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token != placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_4(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = None
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_5(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(None, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_6(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, None, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_7(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, None)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_8(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_9(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_10(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(
            phrase_idx,
            phrases,
        )
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_11(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx - 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_12(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 2, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_13(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = None
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_14(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" - "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_15(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "XXANXX" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_16(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "an" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_17(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "XXDXX"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_18(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "d"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_19(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = None
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_20(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" - "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_21(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "XXOXX" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_22(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "o" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_23(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "XXRXX"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_24(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "r"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_25(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = None

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_26(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" - "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_27(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "XXNOXX" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_28(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "no" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_29(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "XXTXX"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_30(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "t"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_31(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper != and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_32(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx - 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_33(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 2, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_34(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper != or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_35(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append(None)
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_36(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("XX|XX")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_37(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx - 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_38(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 2, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_39(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper != not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_40(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = None
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_41(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(None, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_42(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, None, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_43(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, None)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_44(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_45(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_46(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(
            idx,
            tokens,
        )
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_47(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(None, result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_48(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, None)
    return idx + 1, phrase_idx


def x__process_token__mutmut_49(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(result_parts)
    return idx + 1, phrase_idx


def x__process_token__mutmut_50(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(
        token,
    )
    return idx + 1, phrase_idx


def x__process_token__mutmut_51(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx - 1, phrase_idx


def x__process_token__mutmut_52(
    token: str,
    idx: int,
    tokens: list[str],
    phrases: list[str],
    phrase_idx: int,
    result_parts: list[str],
    placeholder: str,
) -> tuple[int, int]:
    """Process a single token in the query. Returns (new_idx, new_phrase_idx)."""
    upper = token.upper()

    if token == placeholder:
        new_phrase_idx = _process_phrase_token(phrase_idx, phrases, result_parts)
        return idx + 1, new_phrase_idx

    # Use string concat to avoid S105 false positives for boolean operators
    and_op = "AN" + "D"
    or_op = "O" + "R"
    not_op = "NO" + "T"

    if upper == and_op:
        return idx + 1, phrase_idx  # AND is implicit, skip

    if upper == or_op:
        if result_parts:
            result_parts.append("|")
        return idx + 1, phrase_idx

    if upper == not_op:
        new_idx, _ = _process_not_token(idx, tokens, result_parts)
        return new_idx, phrase_idx

    _process_regular_token(token, result_parts)
    return idx + 2, phrase_idx


x__process_token__mutmut_mutants: ClassVar[MutantDict] = {
    "x__process_token__mutmut_1": x__process_token__mutmut_1,
    "x__process_token__mutmut_2": x__process_token__mutmut_2,
    "x__process_token__mutmut_3": x__process_token__mutmut_3,
    "x__process_token__mutmut_4": x__process_token__mutmut_4,
    "x__process_token__mutmut_5": x__process_token__mutmut_5,
    "x__process_token__mutmut_6": x__process_token__mutmut_6,
    "x__process_token__mutmut_7": x__process_token__mutmut_7,
    "x__process_token__mutmut_8": x__process_token__mutmut_8,
    "x__process_token__mutmut_9": x__process_token__mutmut_9,
    "x__process_token__mutmut_10": x__process_token__mutmut_10,
    "x__process_token__mutmut_11": x__process_token__mutmut_11,
    "x__process_token__mutmut_12": x__process_token__mutmut_12,
    "x__process_token__mutmut_13": x__process_token__mutmut_13,
    "x__process_token__mutmut_14": x__process_token__mutmut_14,
    "x__process_token__mutmut_15": x__process_token__mutmut_15,
    "x__process_token__mutmut_16": x__process_token__mutmut_16,
    "x__process_token__mutmut_17": x__process_token__mutmut_17,
    "x__process_token__mutmut_18": x__process_token__mutmut_18,
    "x__process_token__mutmut_19": x__process_token__mutmut_19,
    "x__process_token__mutmut_20": x__process_token__mutmut_20,
    "x__process_token__mutmut_21": x__process_token__mutmut_21,
    "x__process_token__mutmut_22": x__process_token__mutmut_22,
    "x__process_token__mutmut_23": x__process_token__mutmut_23,
    "x__process_token__mutmut_24": x__process_token__mutmut_24,
    "x__process_token__mutmut_25": x__process_token__mutmut_25,
    "x__process_token__mutmut_26": x__process_token__mutmut_26,
    "x__process_token__mutmut_27": x__process_token__mutmut_27,
    "x__process_token__mutmut_28": x__process_token__mutmut_28,
    "x__process_token__mutmut_29": x__process_token__mutmut_29,
    "x__process_token__mutmut_30": x__process_token__mutmut_30,
    "x__process_token__mutmut_31": x__process_token__mutmut_31,
    "x__process_token__mutmut_32": x__process_token__mutmut_32,
    "x__process_token__mutmut_33": x__process_token__mutmut_33,
    "x__process_token__mutmut_34": x__process_token__mutmut_34,
    "x__process_token__mutmut_35": x__process_token__mutmut_35,
    "x__process_token__mutmut_36": x__process_token__mutmut_36,
    "x__process_token__mutmut_37": x__process_token__mutmut_37,
    "x__process_token__mutmut_38": x__process_token__mutmut_38,
    "x__process_token__mutmut_39": x__process_token__mutmut_39,
    "x__process_token__mutmut_40": x__process_token__mutmut_40,
    "x__process_token__mutmut_41": x__process_token__mutmut_41,
    "x__process_token__mutmut_42": x__process_token__mutmut_42,
    "x__process_token__mutmut_43": x__process_token__mutmut_43,
    "x__process_token__mutmut_44": x__process_token__mutmut_44,
    "x__process_token__mutmut_45": x__process_token__mutmut_45,
    "x__process_token__mutmut_46": x__process_token__mutmut_46,
    "x__process_token__mutmut_47": x__process_token__mutmut_47,
    "x__process_token__mutmut_48": x__process_token__mutmut_48,
    "x__process_token__mutmut_49": x__process_token__mutmut_49,
    "x__process_token__mutmut_50": x__process_token__mutmut_50,
    "x__process_token__mutmut_51": x__process_token__mutmut_51,
    "x__process_token__mutmut_52": x__process_token__mutmut_52,
}


def _process_token(*args, **kwargs):
    result = _mutmut_trampoline(
        x__process_token__mutmut_orig, x__process_token__mutmut_mutants, args, kwargs
    )
    return result


_process_token.__signature__ = _mutmut_signature(x__process_token__mutmut_orig)
x__process_token__mutmut_orig.__name__ = "x__process_token"


def x__convert_query_to_tsquery__mutmut_orig(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_1(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query and not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_2(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_3(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_4(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return "XXXX"

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_5(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = None
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_6(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'XX"([^"]+)"XX'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_7(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = None
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_8(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(None, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_9(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, None)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_10(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_11(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(
        phrase_pattern,
    )
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_12(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = None
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_13(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" - "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_14(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "XXPHRASE_XX" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_15(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "phrase_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_16(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "XXPLACEHOLDERXX"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_17(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "placeholder"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_18(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = None

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_19(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(None, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_20(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, None, query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_21(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", None)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_22(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_23(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_24(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(
        phrase_pattern,
        f" {placeholder} ",
    )

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_25(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = None
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_26(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = None
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_27(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = None
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_28(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 1
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_29(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = None

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_30(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 1

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_31(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx <= len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_32(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = None
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_33(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_34(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx = 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_35(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx -= 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_36(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 2
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_37(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            break
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_38(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = None

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_39(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            None, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_40(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, None, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_41(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, None, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_42(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, None, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_43(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, None, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_44(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(token, idx, tokens, phrases, phrase_idx, None, placeholder)

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_45(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, None
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_46(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_47(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_48(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(token, idx, phrases, phrase_idx, result_parts, placeholder)

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_49(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(token, idx, tokens, phrase_idx, result_parts, placeholder)

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_50(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(token, idx, tokens, phrases, result_parts, placeholder)

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_51(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(token, idx, tokens, phrases, phrase_idx, placeholder)

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_52(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token,
            idx,
            tokens,
            phrases,
            phrase_idx,
            result_parts,
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_53(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_54(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return "XXXX"

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(result_parts)


def x__convert_query_to_tsquery__mutmut_55(query: str) -> str:
    """Convert user search query to PostgreSQL tsquery format.

    Supports:
    - Phrase search: "suspicious person" -> 'suspicious <-> person'
    - Boolean AND: person AND vehicle -> person & vehicle
    - Boolean OR: person OR vehicle -> person | vehicle
    - Boolean NOT: NOT person -> !person
    - Plain words: person vehicle -> person & vehicle (default AND)

    Args:
        query: User's search query string

    Returns:
        PostgreSQL tsquery-compatible string
    """
    if not query or not query.strip():
        return ""

    # Handle phrases in double quotes - convert to proximity search
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, query)
    # Use constant for placeholder to avoid S105 warning
    placeholder = "PHRASE_" + "PLACEHOLDER"
    remaining_query = re.sub(phrase_pattern, f" {placeholder} ", query)

    tokens = remaining_query.split()
    result_parts: list[str] = []
    phrase_idx = 0
    idx = 0

    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        idx, phrase_idx = _process_token(
            token, idx, tokens, phrases, phrase_idx, result_parts, placeholder
        )

    if not result_parts:
        return ""

    # Build the final query joining with & (AND) for non-OR parts
    return _join_query_parts(None)


x__convert_query_to_tsquery__mutmut_mutants: ClassVar[MutantDict] = {
    "x__convert_query_to_tsquery__mutmut_1": x__convert_query_to_tsquery__mutmut_1,
    "x__convert_query_to_tsquery__mutmut_2": x__convert_query_to_tsquery__mutmut_2,
    "x__convert_query_to_tsquery__mutmut_3": x__convert_query_to_tsquery__mutmut_3,
    "x__convert_query_to_tsquery__mutmut_4": x__convert_query_to_tsquery__mutmut_4,
    "x__convert_query_to_tsquery__mutmut_5": x__convert_query_to_tsquery__mutmut_5,
    "x__convert_query_to_tsquery__mutmut_6": x__convert_query_to_tsquery__mutmut_6,
    "x__convert_query_to_tsquery__mutmut_7": x__convert_query_to_tsquery__mutmut_7,
    "x__convert_query_to_tsquery__mutmut_8": x__convert_query_to_tsquery__mutmut_8,
    "x__convert_query_to_tsquery__mutmut_9": x__convert_query_to_tsquery__mutmut_9,
    "x__convert_query_to_tsquery__mutmut_10": x__convert_query_to_tsquery__mutmut_10,
    "x__convert_query_to_tsquery__mutmut_11": x__convert_query_to_tsquery__mutmut_11,
    "x__convert_query_to_tsquery__mutmut_12": x__convert_query_to_tsquery__mutmut_12,
    "x__convert_query_to_tsquery__mutmut_13": x__convert_query_to_tsquery__mutmut_13,
    "x__convert_query_to_tsquery__mutmut_14": x__convert_query_to_tsquery__mutmut_14,
    "x__convert_query_to_tsquery__mutmut_15": x__convert_query_to_tsquery__mutmut_15,
    "x__convert_query_to_tsquery__mutmut_16": x__convert_query_to_tsquery__mutmut_16,
    "x__convert_query_to_tsquery__mutmut_17": x__convert_query_to_tsquery__mutmut_17,
    "x__convert_query_to_tsquery__mutmut_18": x__convert_query_to_tsquery__mutmut_18,
    "x__convert_query_to_tsquery__mutmut_19": x__convert_query_to_tsquery__mutmut_19,
    "x__convert_query_to_tsquery__mutmut_20": x__convert_query_to_tsquery__mutmut_20,
    "x__convert_query_to_tsquery__mutmut_21": x__convert_query_to_tsquery__mutmut_21,
    "x__convert_query_to_tsquery__mutmut_22": x__convert_query_to_tsquery__mutmut_22,
    "x__convert_query_to_tsquery__mutmut_23": x__convert_query_to_tsquery__mutmut_23,
    "x__convert_query_to_tsquery__mutmut_24": x__convert_query_to_tsquery__mutmut_24,
    "x__convert_query_to_tsquery__mutmut_25": x__convert_query_to_tsquery__mutmut_25,
    "x__convert_query_to_tsquery__mutmut_26": x__convert_query_to_tsquery__mutmut_26,
    "x__convert_query_to_tsquery__mutmut_27": x__convert_query_to_tsquery__mutmut_27,
    "x__convert_query_to_tsquery__mutmut_28": x__convert_query_to_tsquery__mutmut_28,
    "x__convert_query_to_tsquery__mutmut_29": x__convert_query_to_tsquery__mutmut_29,
    "x__convert_query_to_tsquery__mutmut_30": x__convert_query_to_tsquery__mutmut_30,
    "x__convert_query_to_tsquery__mutmut_31": x__convert_query_to_tsquery__mutmut_31,
    "x__convert_query_to_tsquery__mutmut_32": x__convert_query_to_tsquery__mutmut_32,
    "x__convert_query_to_tsquery__mutmut_33": x__convert_query_to_tsquery__mutmut_33,
    "x__convert_query_to_tsquery__mutmut_34": x__convert_query_to_tsquery__mutmut_34,
    "x__convert_query_to_tsquery__mutmut_35": x__convert_query_to_tsquery__mutmut_35,
    "x__convert_query_to_tsquery__mutmut_36": x__convert_query_to_tsquery__mutmut_36,
    "x__convert_query_to_tsquery__mutmut_37": x__convert_query_to_tsquery__mutmut_37,
    "x__convert_query_to_tsquery__mutmut_38": x__convert_query_to_tsquery__mutmut_38,
    "x__convert_query_to_tsquery__mutmut_39": x__convert_query_to_tsquery__mutmut_39,
    "x__convert_query_to_tsquery__mutmut_40": x__convert_query_to_tsquery__mutmut_40,
    "x__convert_query_to_tsquery__mutmut_41": x__convert_query_to_tsquery__mutmut_41,
    "x__convert_query_to_tsquery__mutmut_42": x__convert_query_to_tsquery__mutmut_42,
    "x__convert_query_to_tsquery__mutmut_43": x__convert_query_to_tsquery__mutmut_43,
    "x__convert_query_to_tsquery__mutmut_44": x__convert_query_to_tsquery__mutmut_44,
    "x__convert_query_to_tsquery__mutmut_45": x__convert_query_to_tsquery__mutmut_45,
    "x__convert_query_to_tsquery__mutmut_46": x__convert_query_to_tsquery__mutmut_46,
    "x__convert_query_to_tsquery__mutmut_47": x__convert_query_to_tsquery__mutmut_47,
    "x__convert_query_to_tsquery__mutmut_48": x__convert_query_to_tsquery__mutmut_48,
    "x__convert_query_to_tsquery__mutmut_49": x__convert_query_to_tsquery__mutmut_49,
    "x__convert_query_to_tsquery__mutmut_50": x__convert_query_to_tsquery__mutmut_50,
    "x__convert_query_to_tsquery__mutmut_51": x__convert_query_to_tsquery__mutmut_51,
    "x__convert_query_to_tsquery__mutmut_52": x__convert_query_to_tsquery__mutmut_52,
    "x__convert_query_to_tsquery__mutmut_53": x__convert_query_to_tsquery__mutmut_53,
    "x__convert_query_to_tsquery__mutmut_54": x__convert_query_to_tsquery__mutmut_54,
    "x__convert_query_to_tsquery__mutmut_55": x__convert_query_to_tsquery__mutmut_55,
}


def _convert_query_to_tsquery(*args, **kwargs):
    result = _mutmut_trampoline(
        x__convert_query_to_tsquery__mutmut_orig,
        x__convert_query_to_tsquery__mutmut_mutants,
        args,
        kwargs,
    )
    return result


_convert_query_to_tsquery.__signature__ = _mutmut_signature(
    x__convert_query_to_tsquery__mutmut_orig
)
x__convert_query_to_tsquery__mutmut_orig.__name__ = "x__convert_query_to_tsquery"


def x__join_query_parts__mutmut_orig(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[-1] + " |"
        else:
            if final_parts and not final_parts[-1].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_1(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = None
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[-1] + " |"
        else:
            if final_parts and not final_parts[-1].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_2(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part != "|":
            if final_parts:
                final_parts[-1] = final_parts[-1] + " |"
        else:
            if final_parts and not final_parts[-1].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_3(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "XX|XX":
            if final_parts:
                final_parts[-1] = final_parts[-1] + " |"
        else:
            if final_parts and not final_parts[-1].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_4(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = None
        else:
            if final_parts and not final_parts[-1].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_5(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[+1] = final_parts[-1] + " |"
        else:
            if final_parts and not final_parts[-1].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_6(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-2] = final_parts[-1] + " |"
        else:
            if final_parts and not final_parts[-1].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_7(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[-1] - " |"
        else:
            if final_parts and not final_parts[-1].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_8(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[+1] + " |"
        else:
            if final_parts and not final_parts[-1].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_9(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[-2] + " |"
        else:
            if final_parts and not final_parts[-1].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_10(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[-1] + "XX |XX"
        else:
            if final_parts and not final_parts[-1].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_11(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[-1] + " |"
        else:
            if final_parts or not final_parts[-1].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_12(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[-1] + " |"
        else:
            if final_parts and final_parts[-1].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_13(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[-1] + " |"
        else:
            if final_parts and not final_parts[-1].endswith(None):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_14(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[-1] + " |"
        else:
            if final_parts and not final_parts[+1].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_15(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[-1] + " |"
        else:
            if final_parts and not final_parts[-2].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_16(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[-1] + " |"
        else:
            if final_parts and not final_parts[-1].endswith("XX|XX"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_17(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[-1] + " |"
        else:
            if final_parts and not final_parts[-1].endswith("|"):
                final_parts.append(None)
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_18(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[-1] + " |"
        else:
            if final_parts and not final_parts[-1].endswith("|"):
                final_parts.append("XX&XX")
            final_parts.append(part)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_19(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[-1] + " |"
        else:
            if final_parts and not final_parts[-1].endswith("|"):
                final_parts.append("&")
            final_parts.append(None)
    return " ".join(final_parts)


def x__join_query_parts__mutmut_20(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[-1] + " |"
        else:
            if final_parts and not final_parts[-1].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return " ".join(None)


def x__join_query_parts__mutmut_21(result_parts: list[str]) -> str:
    """Join query parts with AND (&) operators, respecting OR (|) operators."""
    final_parts: list[str] = []
    for part in result_parts:
        if part == "|":
            if final_parts:
                final_parts[-1] = final_parts[-1] + " |"
        else:
            if final_parts and not final_parts[-1].endswith("|"):
                final_parts.append("&")
            final_parts.append(part)
    return "XX XX".join(final_parts)


x__join_query_parts__mutmut_mutants: ClassVar[MutantDict] = {
    "x__join_query_parts__mutmut_1": x__join_query_parts__mutmut_1,
    "x__join_query_parts__mutmut_2": x__join_query_parts__mutmut_2,
    "x__join_query_parts__mutmut_3": x__join_query_parts__mutmut_3,
    "x__join_query_parts__mutmut_4": x__join_query_parts__mutmut_4,
    "x__join_query_parts__mutmut_5": x__join_query_parts__mutmut_5,
    "x__join_query_parts__mutmut_6": x__join_query_parts__mutmut_6,
    "x__join_query_parts__mutmut_7": x__join_query_parts__mutmut_7,
    "x__join_query_parts__mutmut_8": x__join_query_parts__mutmut_8,
    "x__join_query_parts__mutmut_9": x__join_query_parts__mutmut_9,
    "x__join_query_parts__mutmut_10": x__join_query_parts__mutmut_10,
    "x__join_query_parts__mutmut_11": x__join_query_parts__mutmut_11,
    "x__join_query_parts__mutmut_12": x__join_query_parts__mutmut_12,
    "x__join_query_parts__mutmut_13": x__join_query_parts__mutmut_13,
    "x__join_query_parts__mutmut_14": x__join_query_parts__mutmut_14,
    "x__join_query_parts__mutmut_15": x__join_query_parts__mutmut_15,
    "x__join_query_parts__mutmut_16": x__join_query_parts__mutmut_16,
    "x__join_query_parts__mutmut_17": x__join_query_parts__mutmut_17,
    "x__join_query_parts__mutmut_18": x__join_query_parts__mutmut_18,
    "x__join_query_parts__mutmut_19": x__join_query_parts__mutmut_19,
    "x__join_query_parts__mutmut_20": x__join_query_parts__mutmut_20,
    "x__join_query_parts__mutmut_21": x__join_query_parts__mutmut_21,
}


def _join_query_parts(*args, **kwargs):
    result = _mutmut_trampoline(
        x__join_query_parts__mutmut_orig, x__join_query_parts__mutmut_mutants, args, kwargs
    )
    return result


_join_query_parts.__signature__ = _mutmut_signature(x__join_query_parts__mutmut_orig)
x__join_query_parts__mutmut_orig.__name__ = "x__join_query_parts"


def x__build_search_query__mutmut_orig(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_1(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = None
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_2(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(None)
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_3(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op not in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_4(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["XX&XX", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_5(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "XX|XX", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_6(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "XX!XX", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_7(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "XX<->XX"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_8(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = None
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_9(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(None, tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_10(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), None)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_11(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_12(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(
                cast("english", REGCONFIG),
            )
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_13(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast(None, REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_14(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", None), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_15(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast(REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_16(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(
                cast(
                    "english",
                ),
                tsquery_str,
            )
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_17(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("XXenglishXX", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_18(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("ENGLISH", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_19(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = None

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_20(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(None, query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_21(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), None)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_22(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_23(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(
                cast("english", REGCONFIG),
            )

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_24(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast(None, REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_25(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", None), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_26(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast(REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_27(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(
                cast(
                    "english",
                ),
                query,
            )

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_28(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("XXenglishXX", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_29(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("ENGLISH", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_30(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = None
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_31(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(None, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_32(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, None)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_33(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_34(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(
            Event.search_vector,
        )
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_35(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = None

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_36(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(None, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_37(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, None)

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_38(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_39(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(
            raw_rank * 10,
        )

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_40(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank / 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_41(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 11, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_42(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(None, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_43(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, None))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_44(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_45(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(
            raw_rank * 10,
            cast(
                1.0,
            ),
        )

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_46(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(2.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_47(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = None

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_48(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(None)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_49(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = None

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_50(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            None,
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_51(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            None,
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_52(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_53(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_54(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(None),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_55(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op(None)(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_56(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("XX@@XX")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_57(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                None,
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_58(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                None,
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_59(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_60(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_61(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    None,
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_62(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    None,
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_63(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    None,
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_64(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_65(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_66(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_67(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(None),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_68(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(None),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_69(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(None),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_70(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(None),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_71(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(None, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_72(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, None)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_73(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_74(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(
                Camera,
            )
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_75(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(None, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_76(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, None, Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_77(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), None)
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_78(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_79(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_80(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(
                Event,
                rank.label("relevance_score"),
            )
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_81(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label(None), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_82(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("XXrelevance_scoreXX"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_83(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("RELEVANCE_SCORE"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_84(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label(None))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_85(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("XXcamera_nameXX"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_86(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("CAMERA_NAME"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_87(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id != Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_88(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            False,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_89(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(None, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_90(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, None),
            False,
        )


def x__build_search_query__mutmut_91(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_92(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(
                Camera,
            ),
            False,
        )


def x__build_search_query__mutmut_93(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                None,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_94(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                None,
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_95(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                None,
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_96(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_97(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_98(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_99(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label(None),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_100(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(None, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_101(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, None).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_102(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_103(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(
                    0.0,
                ).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_104(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(1.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_105(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("XXrelevance_scoreXX"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_106(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("RELEVANCE_SCORE"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_107(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label(None),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_108(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("XXcamera_nameXX"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_109(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("CAMERA_NAME"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            False,
        )


def x__build_search_query__mutmut_110(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id != Camera.id),
            False,
        )


def x__build_search_query__mutmut_111(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking.

    The query includes an ILIKE fallback for events with NULL search_vector.
    This handles events created before the FTS trigger was added, or events
    that were never updated after the trigger was created.
    """
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        # ts_rank returns values typically in range 0.0-0.1
        # Normalize to 0.0-1.0 range for frontend percentage display
        # Multiply by 10 and cap at 1.0: ts_rank 0.1 -> 1.0 (100%), 0.05 -> 0.5 (50%)
        raw_rank = func.ts_rank(Event.search_vector, tsquery)
        rank = func.least(raw_rank * 10, cast(1.0, Float))

        # Escape the query for ILIKE pattern matching to prevent injection
        safe_query = escape_ilike_pattern(query)

        # Build search condition with ILIKE fallback for NULL search_vector
        # This handles events created before the FTS trigger was added
        search_condition = or_(
            Event.search_vector.op("@@")(tsquery),
            and_(
                Event.search_vector.is_(None),
                or_(
                    Event.summary.ilike(f"%{safe_query}%"),
                    Event.reasoning.ilike(f"%{safe_query}%"),
                    Event.object_types.ilike(f"%{safe_query}%"),
                ),
            ),
        )

        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(search_condition),
            True,
        )
    else:
        return (
            select(
                Event,
                cast(0.0, Float).label("relevance_score"),
                Camera.name.label("camera_name"),
            ).outerjoin(Camera, Event.camera_id == Camera.id),
            True,
        )


x__build_search_query__mutmut_mutants: ClassVar[MutantDict] = {
    "x__build_search_query__mutmut_1": x__build_search_query__mutmut_1,
    "x__build_search_query__mutmut_2": x__build_search_query__mutmut_2,
    "x__build_search_query__mutmut_3": x__build_search_query__mutmut_3,
    "x__build_search_query__mutmut_4": x__build_search_query__mutmut_4,
    "x__build_search_query__mutmut_5": x__build_search_query__mutmut_5,
    "x__build_search_query__mutmut_6": x__build_search_query__mutmut_6,
    "x__build_search_query__mutmut_7": x__build_search_query__mutmut_7,
    "x__build_search_query__mutmut_8": x__build_search_query__mutmut_8,
    "x__build_search_query__mutmut_9": x__build_search_query__mutmut_9,
    "x__build_search_query__mutmut_10": x__build_search_query__mutmut_10,
    "x__build_search_query__mutmut_11": x__build_search_query__mutmut_11,
    "x__build_search_query__mutmut_12": x__build_search_query__mutmut_12,
    "x__build_search_query__mutmut_13": x__build_search_query__mutmut_13,
    "x__build_search_query__mutmut_14": x__build_search_query__mutmut_14,
    "x__build_search_query__mutmut_15": x__build_search_query__mutmut_15,
    "x__build_search_query__mutmut_16": x__build_search_query__mutmut_16,
    "x__build_search_query__mutmut_17": x__build_search_query__mutmut_17,
    "x__build_search_query__mutmut_18": x__build_search_query__mutmut_18,
    "x__build_search_query__mutmut_19": x__build_search_query__mutmut_19,
    "x__build_search_query__mutmut_20": x__build_search_query__mutmut_20,
    "x__build_search_query__mutmut_21": x__build_search_query__mutmut_21,
    "x__build_search_query__mutmut_22": x__build_search_query__mutmut_22,
    "x__build_search_query__mutmut_23": x__build_search_query__mutmut_23,
    "x__build_search_query__mutmut_24": x__build_search_query__mutmut_24,
    "x__build_search_query__mutmut_25": x__build_search_query__mutmut_25,
    "x__build_search_query__mutmut_26": x__build_search_query__mutmut_26,
    "x__build_search_query__mutmut_27": x__build_search_query__mutmut_27,
    "x__build_search_query__mutmut_28": x__build_search_query__mutmut_28,
    "x__build_search_query__mutmut_29": x__build_search_query__mutmut_29,
    "x__build_search_query__mutmut_30": x__build_search_query__mutmut_30,
    "x__build_search_query__mutmut_31": x__build_search_query__mutmut_31,
    "x__build_search_query__mutmut_32": x__build_search_query__mutmut_32,
    "x__build_search_query__mutmut_33": x__build_search_query__mutmut_33,
    "x__build_search_query__mutmut_34": x__build_search_query__mutmut_34,
    "x__build_search_query__mutmut_35": x__build_search_query__mutmut_35,
    "x__build_search_query__mutmut_36": x__build_search_query__mutmut_36,
    "x__build_search_query__mutmut_37": x__build_search_query__mutmut_37,
    "x__build_search_query__mutmut_38": x__build_search_query__mutmut_38,
    "x__build_search_query__mutmut_39": x__build_search_query__mutmut_39,
    "x__build_search_query__mutmut_40": x__build_search_query__mutmut_40,
    "x__build_search_query__mutmut_41": x__build_search_query__mutmut_41,
    "x__build_search_query__mutmut_42": x__build_search_query__mutmut_42,
    "x__build_search_query__mutmut_43": x__build_search_query__mutmut_43,
    "x__build_search_query__mutmut_44": x__build_search_query__mutmut_44,
    "x__build_search_query__mutmut_45": x__build_search_query__mutmut_45,
    "x__build_search_query__mutmut_46": x__build_search_query__mutmut_46,
    "x__build_search_query__mutmut_47": x__build_search_query__mutmut_47,
    "x__build_search_query__mutmut_48": x__build_search_query__mutmut_48,
    "x__build_search_query__mutmut_49": x__build_search_query__mutmut_49,
    "x__build_search_query__mutmut_50": x__build_search_query__mutmut_50,
    "x__build_search_query__mutmut_51": x__build_search_query__mutmut_51,
    "x__build_search_query__mutmut_52": x__build_search_query__mutmut_52,
    "x__build_search_query__mutmut_53": x__build_search_query__mutmut_53,
    "x__build_search_query__mutmut_54": x__build_search_query__mutmut_54,
    "x__build_search_query__mutmut_55": x__build_search_query__mutmut_55,
    "x__build_search_query__mutmut_56": x__build_search_query__mutmut_56,
    "x__build_search_query__mutmut_57": x__build_search_query__mutmut_57,
    "x__build_search_query__mutmut_58": x__build_search_query__mutmut_58,
    "x__build_search_query__mutmut_59": x__build_search_query__mutmut_59,
    "x__build_search_query__mutmut_60": x__build_search_query__mutmut_60,
    "x__build_search_query__mutmut_61": x__build_search_query__mutmut_61,
    "x__build_search_query__mutmut_62": x__build_search_query__mutmut_62,
    "x__build_search_query__mutmut_63": x__build_search_query__mutmut_63,
    "x__build_search_query__mutmut_64": x__build_search_query__mutmut_64,
    "x__build_search_query__mutmut_65": x__build_search_query__mutmut_65,
    "x__build_search_query__mutmut_66": x__build_search_query__mutmut_66,
    "x__build_search_query__mutmut_67": x__build_search_query__mutmut_67,
    "x__build_search_query__mutmut_68": x__build_search_query__mutmut_68,
    "x__build_search_query__mutmut_69": x__build_search_query__mutmut_69,
    "x__build_search_query__mutmut_70": x__build_search_query__mutmut_70,
    "x__build_search_query__mutmut_71": x__build_search_query__mutmut_71,
    "x__build_search_query__mutmut_72": x__build_search_query__mutmut_72,
    "x__build_search_query__mutmut_73": x__build_search_query__mutmut_73,
    "x__build_search_query__mutmut_74": x__build_search_query__mutmut_74,
    "x__build_search_query__mutmut_75": x__build_search_query__mutmut_75,
    "x__build_search_query__mutmut_76": x__build_search_query__mutmut_76,
    "x__build_search_query__mutmut_77": x__build_search_query__mutmut_77,
    "x__build_search_query__mutmut_78": x__build_search_query__mutmut_78,
    "x__build_search_query__mutmut_79": x__build_search_query__mutmut_79,
    "x__build_search_query__mutmut_80": x__build_search_query__mutmut_80,
    "x__build_search_query__mutmut_81": x__build_search_query__mutmut_81,
    "x__build_search_query__mutmut_82": x__build_search_query__mutmut_82,
    "x__build_search_query__mutmut_83": x__build_search_query__mutmut_83,
    "x__build_search_query__mutmut_84": x__build_search_query__mutmut_84,
    "x__build_search_query__mutmut_85": x__build_search_query__mutmut_85,
    "x__build_search_query__mutmut_86": x__build_search_query__mutmut_86,
    "x__build_search_query__mutmut_87": x__build_search_query__mutmut_87,
    "x__build_search_query__mutmut_88": x__build_search_query__mutmut_88,
    "x__build_search_query__mutmut_89": x__build_search_query__mutmut_89,
    "x__build_search_query__mutmut_90": x__build_search_query__mutmut_90,
    "x__build_search_query__mutmut_91": x__build_search_query__mutmut_91,
    "x__build_search_query__mutmut_92": x__build_search_query__mutmut_92,
    "x__build_search_query__mutmut_93": x__build_search_query__mutmut_93,
    "x__build_search_query__mutmut_94": x__build_search_query__mutmut_94,
    "x__build_search_query__mutmut_95": x__build_search_query__mutmut_95,
    "x__build_search_query__mutmut_96": x__build_search_query__mutmut_96,
    "x__build_search_query__mutmut_97": x__build_search_query__mutmut_97,
    "x__build_search_query__mutmut_98": x__build_search_query__mutmut_98,
    "x__build_search_query__mutmut_99": x__build_search_query__mutmut_99,
    "x__build_search_query__mutmut_100": x__build_search_query__mutmut_100,
    "x__build_search_query__mutmut_101": x__build_search_query__mutmut_101,
    "x__build_search_query__mutmut_102": x__build_search_query__mutmut_102,
    "x__build_search_query__mutmut_103": x__build_search_query__mutmut_103,
    "x__build_search_query__mutmut_104": x__build_search_query__mutmut_104,
    "x__build_search_query__mutmut_105": x__build_search_query__mutmut_105,
    "x__build_search_query__mutmut_106": x__build_search_query__mutmut_106,
    "x__build_search_query__mutmut_107": x__build_search_query__mutmut_107,
    "x__build_search_query__mutmut_108": x__build_search_query__mutmut_108,
    "x__build_search_query__mutmut_109": x__build_search_query__mutmut_109,
    "x__build_search_query__mutmut_110": x__build_search_query__mutmut_110,
    "x__build_search_query__mutmut_111": x__build_search_query__mutmut_111,
}


def _build_search_query(*args, **kwargs):
    result = _mutmut_trampoline(
        x__build_search_query__mutmut_orig, x__build_search_query__mutmut_mutants, args, kwargs
    )
    return result


_build_search_query.__signature__ = _mutmut_signature(x__build_search_query__mutmut_orig)
x__build_search_query__mutmut_orig.__name__ = "x__build_search_query"


def x__build_filter_conditions__mutmut_orig(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = []

    if filters.start_date:
        conditions.append(Event.started_at >= filters.start_date)
    if filters.end_date:
        conditions.append(Event.started_at <= filters.end_date)
    if filters.camera_ids:
        conditions.append(Event.camera_id.in_(filters.camera_ids))
    if filters.severity:
        conditions.append(Event.risk_level.in_(filters.severity))
    if filters.reviewed is not None:
        conditions.append(Event.reviewed == filters.reviewed)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = [
            Event.object_types.ilike(f"%{escape_ilike_pattern(t)}%") for t in filters.object_types
        ]
        conditions.append(or_(*obj_conditions))

    return conditions


def x__build_filter_conditions__mutmut_1(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = None

    if filters.start_date:
        conditions.append(Event.started_at >= filters.start_date)
    if filters.end_date:
        conditions.append(Event.started_at <= filters.end_date)
    if filters.camera_ids:
        conditions.append(Event.camera_id.in_(filters.camera_ids))
    if filters.severity:
        conditions.append(Event.risk_level.in_(filters.severity))
    if filters.reviewed is not None:
        conditions.append(Event.reviewed == filters.reviewed)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = [
            Event.object_types.ilike(f"%{escape_ilike_pattern(t)}%") for t in filters.object_types
        ]
        conditions.append(or_(*obj_conditions))

    return conditions


def x__build_filter_conditions__mutmut_2(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = []

    if filters.start_date:
        conditions.append(None)
    if filters.end_date:
        conditions.append(Event.started_at <= filters.end_date)
    if filters.camera_ids:
        conditions.append(Event.camera_id.in_(filters.camera_ids))
    if filters.severity:
        conditions.append(Event.risk_level.in_(filters.severity))
    if filters.reviewed is not None:
        conditions.append(Event.reviewed == filters.reviewed)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = [
            Event.object_types.ilike(f"%{escape_ilike_pattern(t)}%") for t in filters.object_types
        ]
        conditions.append(or_(*obj_conditions))

    return conditions


def x__build_filter_conditions__mutmut_3(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = []

    if filters.start_date:
        conditions.append(Event.started_at > filters.start_date)
    if filters.end_date:
        conditions.append(Event.started_at <= filters.end_date)
    if filters.camera_ids:
        conditions.append(Event.camera_id.in_(filters.camera_ids))
    if filters.severity:
        conditions.append(Event.risk_level.in_(filters.severity))
    if filters.reviewed is not None:
        conditions.append(Event.reviewed == filters.reviewed)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = [
            Event.object_types.ilike(f"%{escape_ilike_pattern(t)}%") for t in filters.object_types
        ]
        conditions.append(or_(*obj_conditions))

    return conditions


def x__build_filter_conditions__mutmut_4(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = []

    if filters.start_date:
        conditions.append(Event.started_at >= filters.start_date)
    if filters.end_date:
        conditions.append(None)
    if filters.camera_ids:
        conditions.append(Event.camera_id.in_(filters.camera_ids))
    if filters.severity:
        conditions.append(Event.risk_level.in_(filters.severity))
    if filters.reviewed is not None:
        conditions.append(Event.reviewed == filters.reviewed)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = [
            Event.object_types.ilike(f"%{escape_ilike_pattern(t)}%") for t in filters.object_types
        ]
        conditions.append(or_(*obj_conditions))

    return conditions


def x__build_filter_conditions__mutmut_5(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = []

    if filters.start_date:
        conditions.append(Event.started_at >= filters.start_date)
    if filters.end_date:
        conditions.append(Event.started_at < filters.end_date)
    if filters.camera_ids:
        conditions.append(Event.camera_id.in_(filters.camera_ids))
    if filters.severity:
        conditions.append(Event.risk_level.in_(filters.severity))
    if filters.reviewed is not None:
        conditions.append(Event.reviewed == filters.reviewed)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = [
            Event.object_types.ilike(f"%{escape_ilike_pattern(t)}%") for t in filters.object_types
        ]
        conditions.append(or_(*obj_conditions))

    return conditions


def x__build_filter_conditions__mutmut_6(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = []

    if filters.start_date:
        conditions.append(Event.started_at >= filters.start_date)
    if filters.end_date:
        conditions.append(Event.started_at <= filters.end_date)
    if filters.camera_ids:
        conditions.append(None)
    if filters.severity:
        conditions.append(Event.risk_level.in_(filters.severity))
    if filters.reviewed is not None:
        conditions.append(Event.reviewed == filters.reviewed)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = [
            Event.object_types.ilike(f"%{escape_ilike_pattern(t)}%") for t in filters.object_types
        ]
        conditions.append(or_(*obj_conditions))

    return conditions


def x__build_filter_conditions__mutmut_7(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = []

    if filters.start_date:
        conditions.append(Event.started_at >= filters.start_date)
    if filters.end_date:
        conditions.append(Event.started_at <= filters.end_date)
    if filters.camera_ids:
        conditions.append(Event.camera_id.in_(None))
    if filters.severity:
        conditions.append(Event.risk_level.in_(filters.severity))
    if filters.reviewed is not None:
        conditions.append(Event.reviewed == filters.reviewed)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = [
            Event.object_types.ilike(f"%{escape_ilike_pattern(t)}%") for t in filters.object_types
        ]
        conditions.append(or_(*obj_conditions))

    return conditions


def x__build_filter_conditions__mutmut_8(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = []

    if filters.start_date:
        conditions.append(Event.started_at >= filters.start_date)
    if filters.end_date:
        conditions.append(Event.started_at <= filters.end_date)
    if filters.camera_ids:
        conditions.append(Event.camera_id.in_(filters.camera_ids))
    if filters.severity:
        conditions.append(None)
    if filters.reviewed is not None:
        conditions.append(Event.reviewed == filters.reviewed)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = [
            Event.object_types.ilike(f"%{escape_ilike_pattern(t)}%") for t in filters.object_types
        ]
        conditions.append(or_(*obj_conditions))

    return conditions


def x__build_filter_conditions__mutmut_9(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = []

    if filters.start_date:
        conditions.append(Event.started_at >= filters.start_date)
    if filters.end_date:
        conditions.append(Event.started_at <= filters.end_date)
    if filters.camera_ids:
        conditions.append(Event.camera_id.in_(filters.camera_ids))
    if filters.severity:
        conditions.append(Event.risk_level.in_(None))
    if filters.reviewed is not None:
        conditions.append(Event.reviewed == filters.reviewed)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = [
            Event.object_types.ilike(f"%{escape_ilike_pattern(t)}%") for t in filters.object_types
        ]
        conditions.append(or_(*obj_conditions))

    return conditions


def x__build_filter_conditions__mutmut_10(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = []

    if filters.start_date:
        conditions.append(Event.started_at >= filters.start_date)
    if filters.end_date:
        conditions.append(Event.started_at <= filters.end_date)
    if filters.camera_ids:
        conditions.append(Event.camera_id.in_(filters.camera_ids))
    if filters.severity:
        conditions.append(Event.risk_level.in_(filters.severity))
    if filters.reviewed is None:
        conditions.append(Event.reviewed == filters.reviewed)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = [
            Event.object_types.ilike(f"%{escape_ilike_pattern(t)}%") for t in filters.object_types
        ]
        conditions.append(or_(*obj_conditions))

    return conditions


def x__build_filter_conditions__mutmut_11(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = []

    if filters.start_date:
        conditions.append(Event.started_at >= filters.start_date)
    if filters.end_date:
        conditions.append(Event.started_at <= filters.end_date)
    if filters.camera_ids:
        conditions.append(Event.camera_id.in_(filters.camera_ids))
    if filters.severity:
        conditions.append(Event.risk_level.in_(filters.severity))
    if filters.reviewed is not None:
        conditions.append(None)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = [
            Event.object_types.ilike(f"%{escape_ilike_pattern(t)}%") for t in filters.object_types
        ]
        conditions.append(or_(*obj_conditions))

    return conditions


def x__build_filter_conditions__mutmut_12(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = []

    if filters.start_date:
        conditions.append(Event.started_at >= filters.start_date)
    if filters.end_date:
        conditions.append(Event.started_at <= filters.end_date)
    if filters.camera_ids:
        conditions.append(Event.camera_id.in_(filters.camera_ids))
    if filters.severity:
        conditions.append(Event.risk_level.in_(filters.severity))
    if filters.reviewed is not None:
        conditions.append(Event.reviewed != filters.reviewed)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = [
            Event.object_types.ilike(f"%{escape_ilike_pattern(t)}%") for t in filters.object_types
        ]
        conditions.append(or_(*obj_conditions))

    return conditions


def x__build_filter_conditions__mutmut_13(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = []

    if filters.start_date:
        conditions.append(Event.started_at >= filters.start_date)
    if filters.end_date:
        conditions.append(Event.started_at <= filters.end_date)
    if filters.camera_ids:
        conditions.append(Event.camera_id.in_(filters.camera_ids))
    if filters.severity:
        conditions.append(Event.risk_level.in_(filters.severity))
    if filters.reviewed is not None:
        conditions.append(Event.reviewed == filters.reviewed)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = None
        conditions.append(or_(*obj_conditions))

    return conditions


def x__build_filter_conditions__mutmut_14(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = []

    if filters.start_date:
        conditions.append(Event.started_at >= filters.start_date)
    if filters.end_date:
        conditions.append(Event.started_at <= filters.end_date)
    if filters.camera_ids:
        conditions.append(Event.camera_id.in_(filters.camera_ids))
    if filters.severity:
        conditions.append(Event.risk_level.in_(filters.severity))
    if filters.reviewed is not None:
        conditions.append(Event.reviewed == filters.reviewed)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = [Event.object_types.ilike(None) for t in filters.object_types]
        conditions.append(or_(*obj_conditions))

    return conditions


def x__build_filter_conditions__mutmut_15(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = []

    if filters.start_date:
        conditions.append(Event.started_at >= filters.start_date)
    if filters.end_date:
        conditions.append(Event.started_at <= filters.end_date)
    if filters.camera_ids:
        conditions.append(Event.camera_id.in_(filters.camera_ids))
    if filters.severity:
        conditions.append(Event.risk_level.in_(filters.severity))
    if filters.reviewed is not None:
        conditions.append(Event.reviewed == filters.reviewed)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = [
            Event.object_types.ilike(f"%{escape_ilike_pattern(None)}%")
            for t in filters.object_types
        ]
        conditions.append(or_(*obj_conditions))

    return conditions


def x__build_filter_conditions__mutmut_16(filters: SearchFilters) -> list:
    """Build filter conditions from SearchFilters."""
    conditions = []

    if filters.start_date:
        conditions.append(Event.started_at >= filters.start_date)
    if filters.end_date:
        conditions.append(Event.started_at <= filters.end_date)
    if filters.camera_ids:
        conditions.append(Event.camera_id.in_(filters.camera_ids))
    if filters.severity:
        conditions.append(Event.risk_level.in_(filters.severity))
    if filters.reviewed is not None:
        conditions.append(Event.reviewed == filters.reviewed)
    if filters.object_types:
        # Escape ILIKE special characters to prevent pattern injection
        obj_conditions = [
            Event.object_types.ilike(f"%{escape_ilike_pattern(t)}%") for t in filters.object_types
        ]
        conditions.append(None)

    return conditions


x__build_filter_conditions__mutmut_mutants: ClassVar[MutantDict] = {
    "x__build_filter_conditions__mutmut_1": x__build_filter_conditions__mutmut_1,
    "x__build_filter_conditions__mutmut_2": x__build_filter_conditions__mutmut_2,
    "x__build_filter_conditions__mutmut_3": x__build_filter_conditions__mutmut_3,
    "x__build_filter_conditions__mutmut_4": x__build_filter_conditions__mutmut_4,
    "x__build_filter_conditions__mutmut_5": x__build_filter_conditions__mutmut_5,
    "x__build_filter_conditions__mutmut_6": x__build_filter_conditions__mutmut_6,
    "x__build_filter_conditions__mutmut_7": x__build_filter_conditions__mutmut_7,
    "x__build_filter_conditions__mutmut_8": x__build_filter_conditions__mutmut_8,
    "x__build_filter_conditions__mutmut_9": x__build_filter_conditions__mutmut_9,
    "x__build_filter_conditions__mutmut_10": x__build_filter_conditions__mutmut_10,
    "x__build_filter_conditions__mutmut_11": x__build_filter_conditions__mutmut_11,
    "x__build_filter_conditions__mutmut_12": x__build_filter_conditions__mutmut_12,
    "x__build_filter_conditions__mutmut_13": x__build_filter_conditions__mutmut_13,
    "x__build_filter_conditions__mutmut_14": x__build_filter_conditions__mutmut_14,
    "x__build_filter_conditions__mutmut_15": x__build_filter_conditions__mutmut_15,
    "x__build_filter_conditions__mutmut_16": x__build_filter_conditions__mutmut_16,
}


def _build_filter_conditions(*args, **kwargs):
    result = _mutmut_trampoline(
        x__build_filter_conditions__mutmut_orig,
        x__build_filter_conditions__mutmut_mutants,
        args,
        kwargs,
    )
    return result


_build_filter_conditions.__signature__ = _mutmut_signature(x__build_filter_conditions__mutmut_orig)
x__build_filter_conditions__mutmut_orig.__name__ = "x__build_filter_conditions"


def x__row_to_search_result__mutmut_orig(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_1(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = None
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_2(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[1]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_3(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = None
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_4(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[2]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_5(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = None
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_6(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[3]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_7(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = None

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_8(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(None)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_9(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=None,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_10(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=None,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_11(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=None,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_12(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=None,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_13(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=None,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_14(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=None,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_15(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=None,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_16(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=None,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_17(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=None,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_18(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=None,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_19(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=None,
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_20(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=None,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_21(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=None,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_22(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=None,
    )


def x__row_to_search_result__mutmut_23(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_24(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_25(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_26(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_27(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_28(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_29(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_30(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_31(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_32(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_33(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_34(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_35(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        relevance_score=float(relevance_score) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_36(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
    )


def x__row_to_search_result__mutmut_37(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(None) if relevance_score else 0.0,
    )


def x__row_to_search_result__mutmut_38(row: Any) -> SearchResult:
    """Convert a database row to SearchResult."""
    event = row[0]
    relevance_score = row[1]
    camera_name = row[2]
    detection_ids = _parse_detection_ids(event.detection_ids)

    return SearchResult(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        detection_count=len(detection_ids),
        detection_ids=detection_ids,
        object_types=event.object_types,
        relevance_score=float(relevance_score) if relevance_score else 1.0,
    )


x__row_to_search_result__mutmut_mutants: ClassVar[MutantDict] = {
    "x__row_to_search_result__mutmut_1": x__row_to_search_result__mutmut_1,
    "x__row_to_search_result__mutmut_2": x__row_to_search_result__mutmut_2,
    "x__row_to_search_result__mutmut_3": x__row_to_search_result__mutmut_3,
    "x__row_to_search_result__mutmut_4": x__row_to_search_result__mutmut_4,
    "x__row_to_search_result__mutmut_5": x__row_to_search_result__mutmut_5,
    "x__row_to_search_result__mutmut_6": x__row_to_search_result__mutmut_6,
    "x__row_to_search_result__mutmut_7": x__row_to_search_result__mutmut_7,
    "x__row_to_search_result__mutmut_8": x__row_to_search_result__mutmut_8,
    "x__row_to_search_result__mutmut_9": x__row_to_search_result__mutmut_9,
    "x__row_to_search_result__mutmut_10": x__row_to_search_result__mutmut_10,
    "x__row_to_search_result__mutmut_11": x__row_to_search_result__mutmut_11,
    "x__row_to_search_result__mutmut_12": x__row_to_search_result__mutmut_12,
    "x__row_to_search_result__mutmut_13": x__row_to_search_result__mutmut_13,
    "x__row_to_search_result__mutmut_14": x__row_to_search_result__mutmut_14,
    "x__row_to_search_result__mutmut_15": x__row_to_search_result__mutmut_15,
    "x__row_to_search_result__mutmut_16": x__row_to_search_result__mutmut_16,
    "x__row_to_search_result__mutmut_17": x__row_to_search_result__mutmut_17,
    "x__row_to_search_result__mutmut_18": x__row_to_search_result__mutmut_18,
    "x__row_to_search_result__mutmut_19": x__row_to_search_result__mutmut_19,
    "x__row_to_search_result__mutmut_20": x__row_to_search_result__mutmut_20,
    "x__row_to_search_result__mutmut_21": x__row_to_search_result__mutmut_21,
    "x__row_to_search_result__mutmut_22": x__row_to_search_result__mutmut_22,
    "x__row_to_search_result__mutmut_23": x__row_to_search_result__mutmut_23,
    "x__row_to_search_result__mutmut_24": x__row_to_search_result__mutmut_24,
    "x__row_to_search_result__mutmut_25": x__row_to_search_result__mutmut_25,
    "x__row_to_search_result__mutmut_26": x__row_to_search_result__mutmut_26,
    "x__row_to_search_result__mutmut_27": x__row_to_search_result__mutmut_27,
    "x__row_to_search_result__mutmut_28": x__row_to_search_result__mutmut_28,
    "x__row_to_search_result__mutmut_29": x__row_to_search_result__mutmut_29,
    "x__row_to_search_result__mutmut_30": x__row_to_search_result__mutmut_30,
    "x__row_to_search_result__mutmut_31": x__row_to_search_result__mutmut_31,
    "x__row_to_search_result__mutmut_32": x__row_to_search_result__mutmut_32,
    "x__row_to_search_result__mutmut_33": x__row_to_search_result__mutmut_33,
    "x__row_to_search_result__mutmut_34": x__row_to_search_result__mutmut_34,
    "x__row_to_search_result__mutmut_35": x__row_to_search_result__mutmut_35,
    "x__row_to_search_result__mutmut_36": x__row_to_search_result__mutmut_36,
    "x__row_to_search_result__mutmut_37": x__row_to_search_result__mutmut_37,
    "x__row_to_search_result__mutmut_38": x__row_to_search_result__mutmut_38,
}


def _row_to_search_result(*args, **kwargs):
    result = _mutmut_trampoline(
        x__row_to_search_result__mutmut_orig, x__row_to_search_result__mutmut_mutants, args, kwargs
    )
    return result


_row_to_search_result.__signature__ = _mutmut_signature(x__row_to_search_result__mutmut_orig)
x__row_to_search_result__mutmut_orig.__name__ = "x__row_to_search_result"


async def x_search_events__mutmut_orig(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_1(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 51,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_2(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 1,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_3(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is not None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_4(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = None

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_5(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = None
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_6(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(None)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_7(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = None

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_8(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(None, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_9(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, None)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_10(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_11(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(
        tsquery_str,
    )

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_12(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = None
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_13(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(None)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_14(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = None

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_15(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(None)

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_16(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = None
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_17(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(None)
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_18(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(None).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_19(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = None
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_20(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(None)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_21(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = None

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_22(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() and 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_23(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 1

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_24(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = None
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_25(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(None, Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_26(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), None)
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_27(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_28(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(
            text("relevance_score DESC"),
        )
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_29(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text(None), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_30(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("XXrelevance_score DESCXX"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_31(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score desc"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_32(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("RELEVANCE_SCORE DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_33(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = None

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_34(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(None)

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_35(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = None
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_36(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(None)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_37(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(None).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_38(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = None
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_39(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(None)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_40(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = None

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_41(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=None,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_42(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=None,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_43(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=None,
        offset=offset,
    )


async def x_search_events__mutmut_44(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=None,
    )


async def x_search_events__mutmut_45(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_46(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        limit=limit,
        offset=offset,
    )


async def x_search_events__mutmut_47(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        offset=offset,
    )


async def x_search_events__mutmut_48(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(row) for row in rows],
        total_count=total_count,
        limit=limit,
    )


async def x_search_events__mutmut_49(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SearchResponse:
    """Search events using PostgreSQL full-text search.

    Args:
        db: Database session
        query: Search query string. Supports:
            - Basic words: person vehicle (implicit AND)
            - Phrases: "suspicious person"
            - Boolean: person AND vehicle, person OR animal, NOT cat
        filters: Optional filters for time range, cameras, severity, object types
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        SearchResponse with ranked results and pagination info
    """
    if filters is None:
        filters = SearchFilters()

    tsquery_str = _convert_query_to_tsquery(query)
    base_query, has_search = _build_search_query(tsquery_str, query)

    # Apply filter conditions
    conditions = _build_filter_conditions(filters)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply ordering
    if has_search:
        base_query = base_query.order_by(text("relevance_score DESC"), Event.started_at.desc())
    else:
        base_query = base_query.order_by(Event.started_at.desc())

    # Apply pagination and execute
    base_query = base_query.limit(limit).offset(offset)
    result = await db.execute(base_query)
    rows = result.all()

    return SearchResponse(
        results=[_row_to_search_result(None) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


x_search_events__mutmut_mutants: ClassVar[MutantDict] = {
    "x_search_events__mutmut_1": x_search_events__mutmut_1,
    "x_search_events__mutmut_2": x_search_events__mutmut_2,
    "x_search_events__mutmut_3": x_search_events__mutmut_3,
    "x_search_events__mutmut_4": x_search_events__mutmut_4,
    "x_search_events__mutmut_5": x_search_events__mutmut_5,
    "x_search_events__mutmut_6": x_search_events__mutmut_6,
    "x_search_events__mutmut_7": x_search_events__mutmut_7,
    "x_search_events__mutmut_8": x_search_events__mutmut_8,
    "x_search_events__mutmut_9": x_search_events__mutmut_9,
    "x_search_events__mutmut_10": x_search_events__mutmut_10,
    "x_search_events__mutmut_11": x_search_events__mutmut_11,
    "x_search_events__mutmut_12": x_search_events__mutmut_12,
    "x_search_events__mutmut_13": x_search_events__mutmut_13,
    "x_search_events__mutmut_14": x_search_events__mutmut_14,
    "x_search_events__mutmut_15": x_search_events__mutmut_15,
    "x_search_events__mutmut_16": x_search_events__mutmut_16,
    "x_search_events__mutmut_17": x_search_events__mutmut_17,
    "x_search_events__mutmut_18": x_search_events__mutmut_18,
    "x_search_events__mutmut_19": x_search_events__mutmut_19,
    "x_search_events__mutmut_20": x_search_events__mutmut_20,
    "x_search_events__mutmut_21": x_search_events__mutmut_21,
    "x_search_events__mutmut_22": x_search_events__mutmut_22,
    "x_search_events__mutmut_23": x_search_events__mutmut_23,
    "x_search_events__mutmut_24": x_search_events__mutmut_24,
    "x_search_events__mutmut_25": x_search_events__mutmut_25,
    "x_search_events__mutmut_26": x_search_events__mutmut_26,
    "x_search_events__mutmut_27": x_search_events__mutmut_27,
    "x_search_events__mutmut_28": x_search_events__mutmut_28,
    "x_search_events__mutmut_29": x_search_events__mutmut_29,
    "x_search_events__mutmut_30": x_search_events__mutmut_30,
    "x_search_events__mutmut_31": x_search_events__mutmut_31,
    "x_search_events__mutmut_32": x_search_events__mutmut_32,
    "x_search_events__mutmut_33": x_search_events__mutmut_33,
    "x_search_events__mutmut_34": x_search_events__mutmut_34,
    "x_search_events__mutmut_35": x_search_events__mutmut_35,
    "x_search_events__mutmut_36": x_search_events__mutmut_36,
    "x_search_events__mutmut_37": x_search_events__mutmut_37,
    "x_search_events__mutmut_38": x_search_events__mutmut_38,
    "x_search_events__mutmut_39": x_search_events__mutmut_39,
    "x_search_events__mutmut_40": x_search_events__mutmut_40,
    "x_search_events__mutmut_41": x_search_events__mutmut_41,
    "x_search_events__mutmut_42": x_search_events__mutmut_42,
    "x_search_events__mutmut_43": x_search_events__mutmut_43,
    "x_search_events__mutmut_44": x_search_events__mutmut_44,
    "x_search_events__mutmut_45": x_search_events__mutmut_45,
    "x_search_events__mutmut_46": x_search_events__mutmut_46,
    "x_search_events__mutmut_47": x_search_events__mutmut_47,
    "x_search_events__mutmut_48": x_search_events__mutmut_48,
    "x_search_events__mutmut_49": x_search_events__mutmut_49,
}


def search_events(*args, **kwargs):
    result = _mutmut_trampoline(
        x_search_events__mutmut_orig, x_search_events__mutmut_mutants, args, kwargs
    )
    return result


search_events.__signature__ = _mutmut_signature(x_search_events__mutmut_orig)
x_search_events__mutmut_orig.__name__ = "x_search_events"


async def x_refresh_event_search_vector__mutmut_orig(db: AsyncSession, event_id: int) -> None:
    """Manually refresh the search vector for a specific event.

    This is useful when updating an event's object_types after batch aggregation.

    Args:
        db: Database session
        event_id: ID of the event to refresh
    """
    # The trigger handles this automatically, but we can force a refresh
    # by updating the event (even with no changes, the trigger fires)
    # Uses UPDATE...FROM JOIN pattern for better performance (avoids correlated subquery)
    await db.execute(
        text(
            """
            UPDATE events e SET
                search_vector = to_tsvector('english',
                    COALESCE(e.summary, '') || ' ' ||
                    COALESCE(e.reasoning, '') || ' ' ||
                    COALESCE(e.object_types, '') || ' ' ||
                    COALESCE(c.name, '')
                )
            FROM cameras c
            WHERE e.camera_id = c.id AND e.id = :event_id
        """
        ),
        {"event_id": event_id},
    )
    await db.commit()


async def x_refresh_event_search_vector__mutmut_1(db: AsyncSession, event_id: int) -> None:
    """Manually refresh the search vector for a specific event.

    This is useful when updating an event's object_types after batch aggregation.

    Args:
        db: Database session
        event_id: ID of the event to refresh
    """
    # The trigger handles this automatically, but we can force a refresh
    # by updating the event (even with no changes, the trigger fires)
    # Uses UPDATE...FROM JOIN pattern for better performance (avoids correlated subquery)
    await db.execute(
        None,
        {"event_id": event_id},
    )
    await db.commit()


async def x_refresh_event_search_vector__mutmut_2(db: AsyncSession, event_id: int) -> None:
    """Manually refresh the search vector for a specific event.

    This is useful when updating an event's object_types after batch aggregation.

    Args:
        db: Database session
        event_id: ID of the event to refresh
    """
    # The trigger handles this automatically, but we can force a refresh
    # by updating the event (even with no changes, the trigger fires)
    # Uses UPDATE...FROM JOIN pattern for better performance (avoids correlated subquery)
    await db.execute(
        text(
            """
            UPDATE events e SET
                search_vector = to_tsvector('english',
                    COALESCE(e.summary, '') || ' ' ||
                    COALESCE(e.reasoning, '') || ' ' ||
                    COALESCE(e.object_types, '') || ' ' ||
                    COALESCE(c.name, '')
                )
            FROM cameras c
            WHERE e.camera_id = c.id AND e.id = :event_id
        """
        ),
        None,
    )
    await db.commit()


async def x_refresh_event_search_vector__mutmut_3(db: AsyncSession, event_id: int) -> None:
    """Manually refresh the search vector for a specific event.

    This is useful when updating an event's object_types after batch aggregation.

    Args:
        db: Database session
        event_id: ID of the event to refresh
    """
    # The trigger handles this automatically, but we can force a refresh
    # by updating the event (even with no changes, the trigger fires)
    # Uses UPDATE...FROM JOIN pattern for better performance (avoids correlated subquery)
    await db.execute(
        {"event_id": event_id},
    )
    await db.commit()


async def x_refresh_event_search_vector__mutmut_4(db: AsyncSession, event_id: int) -> None:
    """Manually refresh the search vector for a specific event.

    This is useful when updating an event's object_types after batch aggregation.

    Args:
        db: Database session
        event_id: ID of the event to refresh
    """
    # The trigger handles this automatically, but we can force a refresh
    # by updating the event (even with no changes, the trigger fires)
    # Uses UPDATE...FROM JOIN pattern for better performance (avoids correlated subquery)
    await db.execute(
        text(
            """
            UPDATE events e SET
                search_vector = to_tsvector('english',
                    COALESCE(e.summary, '') || ' ' ||
                    COALESCE(e.reasoning, '') || ' ' ||
                    COALESCE(e.object_types, '') || ' ' ||
                    COALESCE(c.name, '')
                )
            FROM cameras c
            WHERE e.camera_id = c.id AND e.id = :event_id
        """
        ),
    )
    await db.commit()


async def x_refresh_event_search_vector__mutmut_5(db: AsyncSession, event_id: int) -> None:
    """Manually refresh the search vector for a specific event.

    This is useful when updating an event's object_types after batch aggregation.

    Args:
        db: Database session
        event_id: ID of the event to refresh
    """
    # The trigger handles this automatically, but we can force a refresh
    # by updating the event (even with no changes, the trigger fires)
    # Uses UPDATE...FROM JOIN pattern for better performance (avoids correlated subquery)
    await db.execute(
        text(None),
        {"event_id": event_id},
    )
    await db.commit()


async def x_refresh_event_search_vector__mutmut_6(db: AsyncSession, event_id: int) -> None:
    """Manually refresh the search vector for a specific event.

    This is useful when updating an event's object_types after batch aggregation.

    Args:
        db: Database session
        event_id: ID of the event to refresh
    """
    # The trigger handles this automatically, but we can force a refresh
    # by updating the event (even with no changes, the trigger fires)
    # Uses UPDATE...FROM JOIN pattern for better performance (avoids correlated subquery)
    await db.execute(
        text(
            """
            UPDATE events e SET
                search_vector = to_tsvector('english',
                    COALESCE(e.summary, '') || ' ' ||
                    COALESCE(e.reasoning, '') || ' ' ||
                    COALESCE(e.object_types, '') || ' ' ||
                    COALESCE(c.name, '')
                )
            FROM cameras c
            WHERE e.camera_id = c.id AND e.id = :event_id
        """
        ),
        {"XXevent_idXX": event_id},
    )
    await db.commit()


async def x_refresh_event_search_vector__mutmut_7(db: AsyncSession, event_id: int) -> None:
    """Manually refresh the search vector for a specific event.

    This is useful when updating an event's object_types after batch aggregation.

    Args:
        db: Database session
        event_id: ID of the event to refresh
    """
    # The trigger handles this automatically, but we can force a refresh
    # by updating the event (even with no changes, the trigger fires)
    # Uses UPDATE...FROM JOIN pattern for better performance (avoids correlated subquery)
    await db.execute(
        text(
            """
            UPDATE events e SET
                search_vector = to_tsvector('english',
                    COALESCE(e.summary, '') || ' ' ||
                    COALESCE(e.reasoning, '') || ' ' ||
                    COALESCE(e.object_types, '') || ' ' ||
                    COALESCE(c.name, '')
                )
            FROM cameras c
            WHERE e.camera_id = c.id AND e.id = :event_id
        """
        ),
        {"EVENT_ID": event_id},
    )
    await db.commit()


x_refresh_event_search_vector__mutmut_mutants: ClassVar[MutantDict] = {
    "x_refresh_event_search_vector__mutmut_1": x_refresh_event_search_vector__mutmut_1,
    "x_refresh_event_search_vector__mutmut_2": x_refresh_event_search_vector__mutmut_2,
    "x_refresh_event_search_vector__mutmut_3": x_refresh_event_search_vector__mutmut_3,
    "x_refresh_event_search_vector__mutmut_4": x_refresh_event_search_vector__mutmut_4,
    "x_refresh_event_search_vector__mutmut_5": x_refresh_event_search_vector__mutmut_5,
    "x_refresh_event_search_vector__mutmut_6": x_refresh_event_search_vector__mutmut_6,
    "x_refresh_event_search_vector__mutmut_7": x_refresh_event_search_vector__mutmut_7,
}


def refresh_event_search_vector(*args, **kwargs):
    result = _mutmut_trampoline(
        x_refresh_event_search_vector__mutmut_orig,
        x_refresh_event_search_vector__mutmut_mutants,
        args,
        kwargs,
    )
    return result


refresh_event_search_vector.__signature__ = _mutmut_signature(
    x_refresh_event_search_vector__mutmut_orig
)
x_refresh_event_search_vector__mutmut_orig.__name__ = "x_refresh_event_search_vector"


async def x_update_event_object_types__mutmut_orig(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = ", ".join(sorted(set(object_types))) if object_types else None

    await db.execute(
        text("UPDATE events SET object_types = :object_types WHERE id = :event_id"),
        {"object_types": object_types_str, "event_id": event_id},
    )
    await db.commit()


async def x_update_event_object_types__mutmut_1(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = None

    await db.execute(
        text("UPDATE events SET object_types = :object_types WHERE id = :event_id"),
        {"object_types": object_types_str, "event_id": event_id},
    )
    await db.commit()


async def x_update_event_object_types__mutmut_2(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = ", ".join(None) if object_types else None

    await db.execute(
        text("UPDATE events SET object_types = :object_types WHERE id = :event_id"),
        {"object_types": object_types_str, "event_id": event_id},
    )
    await db.commit()


async def x_update_event_object_types__mutmut_3(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = "XX, XX".join(sorted(set(object_types))) if object_types else None

    await db.execute(
        text("UPDATE events SET object_types = :object_types WHERE id = :event_id"),
        {"object_types": object_types_str, "event_id": event_id},
    )
    await db.commit()


async def x_update_event_object_types__mutmut_4(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = ", ".join(sorted(None)) if object_types else None

    await db.execute(
        text("UPDATE events SET object_types = :object_types WHERE id = :event_id"),
        {"object_types": object_types_str, "event_id": event_id},
    )
    await db.commit()


async def x_update_event_object_types__mutmut_5(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = ", ".join(sorted(set(None))) if object_types else None

    await db.execute(
        text("UPDATE events SET object_types = :object_types WHERE id = :event_id"),
        {"object_types": object_types_str, "event_id": event_id},
    )
    await db.commit()


async def x_update_event_object_types__mutmut_6(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = ", ".join(sorted(set(object_types))) if object_types else None

    await db.execute(
        None,
        {"object_types": object_types_str, "event_id": event_id},
    )
    await db.commit()


async def x_update_event_object_types__mutmut_7(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = ", ".join(sorted(set(object_types))) if object_types else None

    await db.execute(
        text("UPDATE events SET object_types = :object_types WHERE id = :event_id"),
        None,
    )
    await db.commit()


async def x_update_event_object_types__mutmut_8(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = ", ".join(sorted(set(object_types))) if object_types else None

    await db.execute(
        {"object_types": object_types_str, "event_id": event_id},
    )
    await db.commit()


async def x_update_event_object_types__mutmut_9(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = ", ".join(sorted(set(object_types))) if object_types else None

    await db.execute(
        text("UPDATE events SET object_types = :object_types WHERE id = :event_id"),
    )
    await db.commit()


async def x_update_event_object_types__mutmut_10(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = ", ".join(sorted(set(object_types))) if object_types else None

    await db.execute(
        text(None),
        {"object_types": object_types_str, "event_id": event_id},
    )
    await db.commit()


async def x_update_event_object_types__mutmut_11(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = ", ".join(sorted(set(object_types))) if object_types else None

    await db.execute(
        text("XXUPDATE events SET object_types = :object_types WHERE id = :event_idXX"),
        {"object_types": object_types_str, "event_id": event_id},
    )
    await db.commit()


async def x_update_event_object_types__mutmut_12(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = ", ".join(sorted(set(object_types))) if object_types else None

    await db.execute(
        text("update events set object_types = :object_types where id = :event_id"),
        {"object_types": object_types_str, "event_id": event_id},
    )
    await db.commit()


async def x_update_event_object_types__mutmut_13(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = ", ".join(sorted(set(object_types))) if object_types else None

    await db.execute(
        text("UPDATE EVENTS SET OBJECT_TYPES = :OBJECT_TYPES WHERE ID = :EVENT_ID"),
        {"object_types": object_types_str, "event_id": event_id},
    )
    await db.commit()


async def x_update_event_object_types__mutmut_14(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = ", ".join(sorted(set(object_types))) if object_types else None

    await db.execute(
        text("UPDATE events SET object_types = :object_types WHERE id = :event_id"),
        {"XXobject_typesXX": object_types_str, "event_id": event_id},
    )
    await db.commit()


async def x_update_event_object_types__mutmut_15(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = ", ".join(sorted(set(object_types))) if object_types else None

    await db.execute(
        text("UPDATE events SET object_types = :object_types WHERE id = :event_id"),
        {"OBJECT_TYPES": object_types_str, "event_id": event_id},
    )
    await db.commit()


async def x_update_event_object_types__mutmut_16(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = ", ".join(sorted(set(object_types))) if object_types else None

    await db.execute(
        text("UPDATE events SET object_types = :object_types WHERE id = :event_id"),
        {"object_types": object_types_str, "XXevent_idXX": event_id},
    )
    await db.commit()


async def x_update_event_object_types__mutmut_17(
    db: AsyncSession,
    event_id: int,
    object_types: list[str],
) -> None:
    """Update the cached object_types for an event.

    This should be called by the batch aggregator when creating/updating events.
    The search_vector trigger will automatically update the search index.

    Args:
        db: Database session
        event_id: ID of the event to update
        object_types: List of detected object types (e.g., ["person", "vehicle"])
    """
    # Convert list to comma-separated string for storage
    object_types_str = ", ".join(sorted(set(object_types))) if object_types else None

    await db.execute(
        text("UPDATE events SET object_types = :object_types WHERE id = :event_id"),
        {"object_types": object_types_str, "EVENT_ID": event_id},
    )
    await db.commit()


x_update_event_object_types__mutmut_mutants: ClassVar[MutantDict] = {
    "x_update_event_object_types__mutmut_1": x_update_event_object_types__mutmut_1,
    "x_update_event_object_types__mutmut_2": x_update_event_object_types__mutmut_2,
    "x_update_event_object_types__mutmut_3": x_update_event_object_types__mutmut_3,
    "x_update_event_object_types__mutmut_4": x_update_event_object_types__mutmut_4,
    "x_update_event_object_types__mutmut_5": x_update_event_object_types__mutmut_5,
    "x_update_event_object_types__mutmut_6": x_update_event_object_types__mutmut_6,
    "x_update_event_object_types__mutmut_7": x_update_event_object_types__mutmut_7,
    "x_update_event_object_types__mutmut_8": x_update_event_object_types__mutmut_8,
    "x_update_event_object_types__mutmut_9": x_update_event_object_types__mutmut_9,
    "x_update_event_object_types__mutmut_10": x_update_event_object_types__mutmut_10,
    "x_update_event_object_types__mutmut_11": x_update_event_object_types__mutmut_11,
    "x_update_event_object_types__mutmut_12": x_update_event_object_types__mutmut_12,
    "x_update_event_object_types__mutmut_13": x_update_event_object_types__mutmut_13,
    "x_update_event_object_types__mutmut_14": x_update_event_object_types__mutmut_14,
    "x_update_event_object_types__mutmut_15": x_update_event_object_types__mutmut_15,
    "x_update_event_object_types__mutmut_16": x_update_event_object_types__mutmut_16,
    "x_update_event_object_types__mutmut_17": x_update_event_object_types__mutmut_17,
}


def update_event_object_types(*args, **kwargs):
    result = _mutmut_trampoline(
        x_update_event_object_types__mutmut_orig,
        x_update_event_object_types__mutmut_mutants,
        args,
        kwargs,
    )
    return result


update_event_object_types.__signature__ = _mutmut_signature(
    x_update_event_object_types__mutmut_orig
)
x_update_event_object_types__mutmut_orig.__name__ = "x_update_event_object_types"
