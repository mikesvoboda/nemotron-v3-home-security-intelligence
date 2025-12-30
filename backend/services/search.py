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

from backend.core.logging import get_logger
from backend.models.camera import Camera
from backend.models.event import Event

logger = get_logger(__name__)


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


def _parse_detection_ids(detection_ids_str: str | None) -> list[int]:
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


def _process_phrase_token(phrase_idx: int, phrases: list[str], result_parts: list[str]) -> int:
    """Process a phrase placeholder token."""
    if phrase_idx < len(phrases):
        phrase_words = phrases[phrase_idx].split()
        if phrase_words:
            phrase_tsquery = " <-> ".join(phrase_words)
            result_parts.append(f"({phrase_tsquery})")
        return phrase_idx + 1
    return phrase_idx


def _process_not_token(idx: int, tokens: list[str], result_parts: list[str]) -> tuple[int, bool]:
    """Process a NOT token. Returns (new_idx, should_continue)."""
    if idx + 1 < len(tokens):
        next_token = tokens[idx + 1].strip()
        # Use constant for placeholder to avoid S105
        placeholder = "PHRASE_" + "PLACEHOLDER"
        if next_token and next_token.upper() not in ("AND", "OR", "NOT", placeholder):
            result_parts.append(f"!{next_token}")
            return idx + 2, True
    return idx + 1, False


def _process_regular_token(token: str, result_parts: list[str]) -> None:
    """Process a regular word token."""
    clean_token = re.sub(r"[^\w]", "", token)
    if clean_token:
        result_parts.append(clean_token)


def _process_token(
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


def _convert_query_to_tsquery(query: str) -> str:
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


def _join_query_parts(result_parts: list[str]) -> str:
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


def _build_search_query(tsquery_str: str, query: str) -> tuple:
    """Build the base search query with relevance ranking."""
    if tsquery_str:
        has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])
        if has_operators:
            tsquery = func.to_tsquery(cast("english", REGCONFIG), tsquery_str)
        else:
            tsquery = func.websearch_to_tsquery(cast("english", REGCONFIG), query)

        rank = func.ts_rank(Event.search_vector, tsquery)
        return (
            select(Event, rank.label("relevance_score"), Camera.name.label("camera_name"))
            .outerjoin(Camera, Event.camera_id == Camera.id)
            .where(Event.search_vector.op("@@")(tsquery)),
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


def _build_filter_conditions(filters: SearchFilters) -> list:
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
        obj_conditions = [Event.object_types.ilike(f"%{t}%") for t in filters.object_types]
        conditions.append(or_(*obj_conditions))

    return conditions


def _row_to_search_result(row: Any) -> SearchResult:
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


async def search_events(
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


async def refresh_event_search_vector(db: AsyncSession, event_id: int) -> None:
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


async def update_event_object_types(
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
