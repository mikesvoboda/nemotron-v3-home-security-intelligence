"""Utilities for constructing Pydantic models from trusted data (NEM-3430).

This module provides utilities for bypassing Pydantic validation when
constructing models from trusted internal data sources (e.g., database records).

Using model_construct() instead of regular model instantiation can provide
significant performance improvements when:
1. Data comes from a trusted source (database, cache, internal service)
2. Data has already been validated at write time
3. High-throughput scenarios where validation overhead is noticeable

WARNING: Only use these utilities with data from trusted sources. Using
model_construct() with untrusted/external data bypasses all validation,
which could lead to invalid model state or security issues.

Example usage:
    >>> from backend.api.schemas.trusted import from_db_record
    >>> from backend.api.schemas.camera import CameraResponse
    >>>
    >>> # Database record is trusted data - validation already happened at write time
    >>> camera = await db.get(Camera, camera_id)
    >>> response = from_db_record(CameraResponse, camera)
"""

from collections.abc import Mapping
from typing import Any, TypeVar

from pydantic import BaseModel

# Generic type variable for Pydantic models
ModelT = TypeVar("ModelT", bound=BaseModel)


def from_db_record(
    model_class: type[ModelT],
    record: Any,
    *,
    update: Mapping[str, Any] | None = None,
    include_none: bool = False,
) -> ModelT:
    """Construct a Pydantic model from a trusted database record without validation.

    This function uses Pydantic's model_construct() to create model instances
    from trusted data sources (e.g., SQLAlchemy ORM objects) without running
    validators. This provides a performance boost for internal data that has
    already been validated at write time.

    Args:
        model_class: The Pydantic model class to instantiate
        record: A SQLAlchemy ORM object or dict with attribute values
        update: Optional dict of additional/override values to include
        include_none: If False (default), None values from update are excluded

    Returns:
        An instance of model_class constructed without validation

    Example:
        >>> from backend.models import Camera
        >>> from backend.api.schemas.camera import CameraResponse
        >>>
        >>> # Fetch from database
        >>> camera = await session.get(Camera, "front_door")
        >>>
        >>> # Construct response without validation (trusted data)
        >>> response = from_db_record(CameraResponse, camera)
        >>>
        >>> # With additional computed fields
        >>> response = from_db_record(
        ...     CameraResponse,
        ...     camera,
        ...     update={"thumbnail_url": f"/api/cameras/{camera.id}/thumbnail"}
        ... )

    Performance notes:
        - Approximately 2-5x faster than regular model instantiation for simple models
        - More significant gains for models with complex validators
        - Use selectively for high-throughput code paths
    """
    # Get field names from the model
    field_names = set(model_class.model_fields.keys())

    # Extract values from the record
    if isinstance(record, Mapping):
        values = {k: record[k] for k in field_names if k in record}
    else:
        # Assume it's an ORM object with attributes
        values = {}
        for field_name in field_names:
            if hasattr(record, field_name):
                values[field_name] = getattr(record, field_name)

    # Apply updates if provided
    if update:
        for key, value in update.items():
            if key in field_names:
                if include_none or value is not None:
                    values[key] = value

    # Construct without validation
    return model_class.model_construct(**values)


def from_dict(
    model_class: type[ModelT],
    data: Mapping[str, Any],
    *,
    _fields_set: set[str] | None = None,
) -> ModelT:
    """Construct a Pydantic model from a trusted dictionary without validation.

    This function uses Pydantic's model_construct() to create model instances
    from trusted dictionaries (e.g., cached data, internal API responses)
    without running validators.

    Args:
        model_class: The Pydantic model class to instantiate
        data: Dictionary with field values
        _fields_set: Optional set of field names that were explicitly set
                    (used by Pydantic for serialization with exclude_unset)

    Returns:
        An instance of model_class constructed without validation

    Example:
        >>> from backend.api.schemas.camera import CameraResponse
        >>>
        >>> # Data from Redis cache (already validated when stored)
        >>> cached_data = await redis.get("camera:front_door")
        >>> camera = from_dict(CameraResponse, cached_data)

    Warning:
        Only use with trusted data sources. External/user input should
        always use regular model instantiation for validation.
    """
    return model_class.model_construct(_fields_set=_fields_set, **data)


def from_db_records(
    model_class: type[ModelT],
    records: list[Any],
    *,
    update_fn: Any | None = None,
) -> list[ModelT]:
    """Construct multiple Pydantic models from trusted database records.

    Batch version of from_db_record() for efficiently processing multiple
    records without validation overhead.

    Args:
        model_class: The Pydantic model class to instantiate
        records: List of SQLAlchemy ORM objects or dicts
        update_fn: Optional function that takes a record and returns
                  additional/override values as a dict

    Returns:
        List of model instances constructed without validation

    Example:
        >>> from backend.models import Detection
        >>> from backend.api.schemas.detections import DetectionResponse
        >>>
        >>> # Fetch many records from database
        >>> detections = await session.scalars(select(Detection).limit(100))
        >>>
        >>> # Construct all responses without validation
        >>> responses = from_db_records(
        ...     DetectionResponse,
        ...     list(detections),
        ...     update_fn=lambda d: {"thumbnail_url": f"/api/detections/{d.id}/image"}
        ... )

    Performance notes:
        - For 100 records, this can be 100-500ms faster than validated construction
        - Gains are proportional to model complexity and record count
    """
    if update_fn is None:
        return [from_db_record(model_class, record) for record in records]

    return [from_db_record(model_class, record, update=update_fn(record)) for record in records]
