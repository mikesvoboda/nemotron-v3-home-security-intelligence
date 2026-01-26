"""Eager loading utilities for SQLAlchemy ORM (NEM-3758).

This module provides utilities for applying eager loading strategies to
SQLAlchemy queries to prevent N+1 query problems.

Eager Loading Strategies:
    - joinedload: Best for single related objects (many-to-one, one-to-one)
    - selectinload: Best for collections with reasonable size
    - subqueryload: Best for large collections or complex queries

Usage:
    from backend.core.eager_loading import apply_eager_loading

    stmt = select(Event)
    stmt = apply_eager_loading(stmt, Event, ["camera"])

    # Or use the helper functions
    from backend.core.eager_loading import with_camera, with_entities

    stmt = select(Event).options(with_camera())
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy.orm import joinedload, selectinload

if TYPE_CHECKING:
    from sqlalchemy.sql import Select


# =============================================================================
# Strategy Selection
# =============================================================================

LoadingStrategy = Literal["joinedload", "selectinload", "subqueryload", "noload"]


def get_loading_strategy(
    relationship_type: Literal["many_to_one", "one_to_one", "one_to_many", "many_to_many"],
    expected_count: Literal["single", "multiple", "large"] = "multiple",
) -> LoadingStrategy:
    """Determine the optimal eager loading strategy for a relationship.

    Args:
        relationship_type: Type of SQLAlchemy relationship
        expected_count: Expected number of related objects

    Returns:
        Recommended loading strategy name

    Strategy Selection Guide:
        - many_to_one / one_to_one: Always use joinedload (single JOIN, no extra queries)
        - one_to_many (few items): Use selectinload (single IN query)
        - one_to_many (many items): Use subqueryload (separate query, better for large sets)
        - many_to_many: Use selectinload or subqueryload depending on size
    """
    if relationship_type in ("many_to_one", "one_to_one"):
        return "joinedload"

    if relationship_type in ("one_to_many", "many_to_many"):
        if expected_count == "large":
            return "subqueryload"
        return "selectinload"

    # Default to selectinload for unknown relationship types
    return "selectinload"


# =============================================================================
# Eager Loading Application
# =============================================================================


def apply_eager_loading(
    stmt: Select[Any],
    model: type,
    relationships: list[str],
) -> Select[Any]:
    """Apply eager loading options to a SQLAlchemy select statement.

    Automatically determines the best loading strategy based on relationship type.

    Args:
        stmt: SQLAlchemy Select statement
        model: The model class being queried
        relationships: List of relationship attribute names to eager load

    Returns:
        The statement with eager loading options applied

    Example:
        stmt = select(Event)
        stmt = apply_eager_loading(stmt, Event, ["camera", "detections"])
    """
    if not relationships:
        return stmt

    options = []

    for rel_name in relationships:
        if not hasattr(model, rel_name):
            continue

        rel_attr = getattr(model, rel_name)

        # Determine relationship type from the attribute
        if hasattr(rel_attr, "property") and hasattr(rel_attr.property, "uselist"):
            is_collection = rel_attr.property.uselist
        else:
            # Default assumption based on common patterns
            is_collection = rel_name.endswith("s") or rel_name in ("entities", "detections")

        if is_collection:
            # Use selectinload for collections
            options.append(selectinload(rel_attr))
        else:
            # Use joinedload for single objects
            options.append(joinedload(rel_attr))

    if options:
        return stmt.options(*options)

    return stmt


# =============================================================================
# Pre-built Loading Options
# =============================================================================


def with_camera() -> Any:
    """Create a joinedload option for the camera relationship.

    Usage:
        stmt = select(Event).options(with_camera())

    Returns:
        joinedload option for camera relationship
    """
    from backend.models import Event

    return joinedload(Event.camera)


def with_camera_for_detection() -> Any:
    """Create a joinedload option for camera on Detection model.

    Returns:
        joinedload option for Detection.camera
    """
    from backend.models import Detection

    return joinedload(Detection.camera)


def with_event_records_for_detection() -> Any:
    """Create a selectinload option for event_records on Detection model.

    Returns:
        selectinload option for Detection.event_records
    """
    from backend.models import Detection

    return selectinload(Detection.event_records)


def with_primary_detection() -> Any:
    """Create a selectinload option for primary_detection on Entity model.

    Returns:
        selectinload option for Entity.primary_detection
    """
    from backend.models import Entity

    return selectinload(Entity.primary_detection)


def with_pose_result_for_detection() -> Any:
    """Create a joinedload option for pose_result on Detection model.

    Returns:
        joinedload option for Detection.pose_result
    """
    from backend.models import Detection

    return joinedload(Detection.pose_result)


# =============================================================================
# Relationship Configuration Hints
# =============================================================================

# Mapping of model.relationship to recommended loading strategy
LOADING_RECOMMENDATIONS: dict[str, dict[str, LoadingStrategy]] = {
    "Event": {
        "camera": "joinedload",
    },
    "Detection": {
        "camera": "joinedload",
        "entities": "selectinload",
        "event": "joinedload",
    },
    "Entity": {
        "primary_detection": "selectinload",
        "detections": "selectinload",
    },
    "Camera": {
        "events": "selectinload",
        "detections": "selectinload",
    },
}


def get_recommended_loading(model_name: str, relationship_name: str) -> LoadingStrategy:
    """Get the recommended loading strategy for a model relationship.

    Args:
        model_name: Name of the model class
        relationship_name: Name of the relationship attribute

    Returns:
        Recommended loading strategy
    """
    model_recommendations = LOADING_RECOMMENDATIONS.get(model_name, {})
    return model_recommendations.get(relationship_name, "selectinload")
