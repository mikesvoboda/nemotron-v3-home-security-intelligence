"""OpenAPI documentation helpers and examples for API endpoints.

This module provides:
- Sparse fieldsets documentation and examples (NEM-1434)
- Response examples for common endpoint patterns
- OpenAPI schema enrichment utilities

Usage in routes:
    from backend.api.schemas.openapi_docs import (
        SPARSE_FIELDSETS_DESCRIPTION,
        get_sparse_fieldsets_example,
    )

    @router.get(
        "/events",
        description=f"List events with optional filtering.\\n\\n{SPARSE_FIELDSETS_DESCRIPTION}",
    )
    async def list_events(...):
        ...
"""

from typing import Any

# =============================================================================
# Sparse Fieldsets Documentation (NEM-1434, NEM-2002)
# =============================================================================

SPARSE_FIELDSETS_DESCRIPTION = """
## Sparse Fieldsets

Use the `fields` query parameter to request only specific fields in the response,
reducing payload size and improving performance. Field names are case-insensitive.

### Syntax

```
?fields=field1,field2,field3
```

### Examples

Request only event IDs and risk levels:
```
GET /api/events?fields=id,risk_level
```

Request event summary with camera information:
```
GET /api/events?fields=id,camera_id,summary,reviewed,detection_count
```

### Response Format

When `fields` is specified, the response contains only the requested fields:

```json
{
  "items": [
    {"id": 123, "risk_level": "high"},
    {"id": 124, "risk_level": "medium"}
  ],
  "pagination": {...}
}
```

### Available Fields by Endpoint

**Events** (`/api/events`):
- `id`, `camera_id`, `started_at`, `ended_at`
- `risk_score`, `risk_level`, `summary`, `reasoning`
- `reviewed`, `detection_count`, `detection_ids`, `thumbnail_url`

**Cameras** (`/api/cameras`):
- `id`, `name`, `folder_path`, `status`
- `created_at`, `last_seen_at`

**Detections** (`/api/detections`):
- `id`, `camera_id`, `file_path`, `file_type`, `detected_at`
- `object_type`, `confidence`, `thumbnail_path`
- `bbox_x`, `bbox_y`, `bbox_width`, `bbox_height`
- `media_type`, `duration`, `video_codec`, `video_width`, `video_height`
- `enrichment_data`

### Error Handling

Invalid field names return a 400 Bad Request:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid field(s) requested: invalid_field. Valid fields are: id, camera_id, ..."
  }
}
```
"""

SPARSE_FIELDSETS_QUERY_PARAM_DOCS = {
    "description": (
        "Comma-separated list of fields to include in response (sparse fieldsets). "
        "Reduces payload size by returning only requested fields. "
        "See endpoint documentation for available fields."
    ),
    "example": "id,camera_id,risk_level,summary,reviewed",
}


def get_sparse_fieldsets_example(
    valid_fields: list[str],
    example_selection: list[str],
) -> dict[str, Any]:
    """Generate OpenAPI example for sparse fieldsets parameter.

    Args:
        valid_fields: List of all valid field names for the endpoint
        example_selection: Subset of fields to show in the example

    Returns:
        Dictionary with OpenAPI schema extras for the fields parameter
    """
    return {
        "description": (
            f"Comma-separated list of fields to include in response (sparse fieldsets). "
            f"Valid fields: {', '.join(sorted(valid_fields))}"
        ),
        "example": ",".join(example_selection),
    }


# =============================================================================
# Response Examples for Common Patterns
# =============================================================================

# Event list response example with all fields
EVENT_LIST_RESPONSE_EXAMPLE: dict[str, Any] = {
    "items": [
        {
            "id": 12345,
            "camera_id": "front_door",
            "started_at": "2024-01-15T10:30:00Z",
            "ended_at": "2024-01-15T10:31:30Z",
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Person detected at front door during unusual hours",
            "reasoning": "Detection occurred at 3:30 AM when household is typically asleep",
            "reviewed": False,
            "detection_count": 5,
            "detection_ids": [101, 102, 103, 104, 105],
            "thumbnail_url": "/api/media/detections/101",
        },
        {
            "id": 12344,
            "camera_id": "backyard",
            "started_at": "2024-01-15T09:15:00Z",
            "ended_at": "2024-01-15T09:16:00Z",
            "risk_score": 25,
            "risk_level": "low",
            "summary": "Dog detected in backyard",
            "reasoning": "Household pet detected during normal hours",
            "reviewed": True,
            "detection_count": 2,
            "detection_ids": [99, 100],
            "thumbnail_url": "/api/media/detections/99",
        },
    ],
    "pagination": {
        "total": 150,
        "limit": 50,
        "offset": None,
        "cursor": None,
        "next_cursor": "eyJpZCI6MTIzNDQsImNyZWF0ZWRfYXQiOiIyMDI0LTAxLTE1VDA5OjE1OjAwWiJ9",  # pragma: allowlist secret
        "has_more": True,
    },
}

# Event list with sparse fieldsets
EVENT_LIST_SPARSE_RESPONSE_EXAMPLE: dict[str, Any] = {
    "items": [
        {"id": 12345, "risk_level": "high", "reviewed": False},
        {"id": 12344, "risk_level": "low", "reviewed": True},
    ],
    "pagination": {
        "total": 150,
        "limit": 50,
        "offset": None,
        "cursor": None,
        "next_cursor": "eyJpZCI6MTIzNDQsImNyZWF0ZWRfYXQiOiIyMDI0LTAxLTE1VDA5OjE1OjAwWiJ9",  # pragma: allowlist secret
        "has_more": True,
    },
}

# Camera list response example
CAMERA_LIST_RESPONSE_EXAMPLE: dict[str, Any] = {
    "items": [
        {
            "id": "front_door",
            "name": "Front Door Camera",
            "folder_path": "/export/foscam/front_door",
            "status": "online",
            "created_at": "2024-01-01T00:00:00Z",
            "last_seen_at": "2024-01-15T10:30:00Z",
        },
        {
            "id": "backyard",
            "name": "Backyard Camera",
            "folder_path": "/export/foscam/backyard",
            "status": "online",
            "created_at": "2024-01-01T00:00:00Z",
            "last_seen_at": "2024-01-15T10:29:00Z",
        },
    ],
    "pagination": {
        "total": 2,
        "limit": 1000,
        "offset": None,
        "cursor": None,
        "next_cursor": None,
        "has_more": False,
    },
}

# Detection list response example
DETECTION_LIST_RESPONSE_EXAMPLE: dict[str, Any] = {
    "items": [
        {
            "id": 101,
            "camera_id": "front_door",
            "file_path": "/export/foscam/front_door/2024-01-15/image_001.jpg",
            "file_type": "image/jpeg",
            "detected_at": "2024-01-15T10:30:00Z",
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 150,
            "bbox_y": 200,
            "bbox_width": 100,
            "bbox_height": 250,
            "thumbnail_path": "/data/thumbnails/detection_101.jpg",
            "media_type": "image",
            "duration": None,
            "video_codec": None,
            "video_width": None,
            "video_height": None,
            "enrichment_data": {
                "clothing_classifications": {
                    "1": {
                        "raw_description": "dark jacket, blue jeans",
                        "is_suspicious": False,
                    }
                }
            },
        }
    ],
    "pagination": {
        "total": 500,
        "limit": 50,
        "offset": None,
        "cursor": None,
        "next_cursor": "eyJpZCI6MTAxLCJjcmVhdGVkX2F0IjoiMjAyNC0wMS0xNVQxMDozMDowMFoifQ==",  # pragma: allowlist secret
        "has_more": True,
    },
}

# Event stats response example
EVENT_STATS_RESPONSE_EXAMPLE: dict[str, Any] = {
    "total_events": 1500,
    "events_by_risk_level": {
        "critical": 25,
        "high": 150,
        "medium": 450,
        "low": 875,
    },
    "events_by_camera": [
        {"camera_id": "front_door", "camera_name": "Front Door Camera", "event_count": 650},
        {"camera_id": "backyard", "camera_name": "Backyard Camera", "event_count": 450},
        {"camera_id": "driveway", "camera_name": "Driveway Camera", "event_count": 400},
    ],
}

# Detection stats response example
DETECTION_STATS_RESPONSE_EXAMPLE: dict[str, Any] = {
    "total_detections": 25000,
    "detections_by_class": {
        "person": 12000,
        "car": 5000,
        "truck": 2000,
        "dog": 1500,
        "cat": 1000,
        "bird": 800,
        "bicycle": 500,
        "motorcycle": 200,
    },
    "average_confidence": 0.87,
}

# Single event response example
EVENT_RESPONSE_EXAMPLE: dict[str, Any] = {
    "id": 12345,
    "camera_id": "front_door",
    "started_at": "2024-01-15T10:30:00Z",
    "ended_at": "2024-01-15T10:31:30Z",
    "risk_score": 75,
    "risk_level": "high",
    "summary": "Person detected at front door during unusual hours",
    "reasoning": "Detection occurred at 3:30 AM when household is typically asleep. "
    "Individual appeared to be examining door lock area.",
    "reviewed": False,
    "notes": None,
    "detection_count": 5,
    "detection_ids": [101, 102, 103, 104, 105],
    "thumbnail_url": "/api/media/detections/101",
    "links": {
        "self": "/api/events/12345",
        "camera": "/api/cameras/front_door",
        "detections": "/api/events/12345/detections",
        "review": "/api/events/12345",
    },
}

# Single camera response example
CAMERA_RESPONSE_EXAMPLE: dict[str, Any] = {
    "id": "front_door",
    "name": "Front Door Camera",
    "folder_path": "/export/foscam/front_door",
    "status": "online",
    "created_at": "2024-01-01T00:00:00Z",
    "last_seen_at": "2024-01-15T10:30:00Z",
}

# Single detection response example
DETECTION_RESPONSE_EXAMPLE: dict[str, Any] = {
    "id": 101,
    "camera_id": "front_door",
    "file_path": "/export/foscam/front_door/2024-01-15/image_001.jpg",
    "file_type": "image/jpeg",
    "detected_at": "2024-01-15T10:30:00Z",
    "object_type": "person",
    "confidence": 0.95,
    "bbox_x": 150,
    "bbox_y": 200,
    "bbox_width": 100,
    "bbox_height": 250,
    "thumbnail_path": "/data/thumbnails/detection_101.jpg",
    "media_type": "image",
    "duration": None,
    "video_codec": None,
    "video_width": None,
    "video_height": None,
    "enrichment_data": {
        "clothing_classifications": {
            "1": {
                "raw_description": "dark jacket, blue jeans",
                "is_suspicious": False,
            }
        }
    },
}


# =============================================================================
# OpenAPI Response Builders
# =============================================================================


def build_list_responses(
    success_example: dict[str, Any],
    sparse_example: dict[str, Any] | None = None,
) -> dict[int, dict[str, Any]]:
    """Build OpenAPI responses for list endpoints.

    Args:
        success_example: Example for full response
        sparse_example: Example for sparse fieldsets response (optional)

    Returns:
        Dictionary of OpenAPI response specifications
    """
    from backend.api.schemas.errors import COMMON_ERROR_RESPONSES

    responses: dict[int, dict[str, Any]] = {
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "examples": {
                        "full_response": {
                            "summary": "Full response with all fields",
                            "value": success_example,
                        },
                    }
                }
            },
        },
        400: COMMON_ERROR_RESPONSES[400],
        429: COMMON_ERROR_RESPONSES[429],
        500: COMMON_ERROR_RESPONSES[500],
    }

    if sparse_example:
        responses[200]["content"]["application/json"]["examples"]["sparse_response"] = {
            "summary": "Sparse response with selected fields",
            "description": "Response when using ?fields=id,risk_level,reviewed",
            "value": sparse_example,
        }

    return responses


def build_detail_responses(success_example: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Build OpenAPI responses for detail (GET by ID) endpoints.

    Args:
        success_example: Example for successful response

    Returns:
        Dictionary of OpenAPI response specifications
    """
    from backend.api.schemas.errors import COMMON_ERROR_RESPONSES

    return {
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "example": success_example,
                }
            },
        },
        404: COMMON_ERROR_RESPONSES[404],
        429: COMMON_ERROR_RESPONSES[429],
        500: COMMON_ERROR_RESPONSES[500],
    }


def build_create_responses(success_example: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Build OpenAPI responses for create (POST) endpoints.

    Args:
        success_example: Example for successful response

    Returns:
        Dictionary of OpenAPI response specifications
    """
    from backend.api.schemas.errors import COMMON_ERROR_RESPONSES

    return {
        201: {
            "description": "Resource created successfully",
            "content": {
                "application/json": {
                    "example": success_example,
                }
            },
        },
        400: COMMON_ERROR_RESPONSES[400],
        409: COMMON_ERROR_RESPONSES[409],
        422: {
            "description": "Validation error",
            "model": "ValidationErrorResponse",
        },
        429: COMMON_ERROR_RESPONSES[429],
        500: COMMON_ERROR_RESPONSES[500],
    }


def build_update_responses(success_example: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Build OpenAPI responses for update (PATCH/PUT) endpoints.

    Args:
        success_example: Example for successful response

    Returns:
        Dictionary of OpenAPI response specifications
    """
    from backend.api.schemas.errors import COMMON_ERROR_RESPONSES

    return {
        200: {
            "description": "Resource updated successfully",
            "content": {
                "application/json": {
                    "example": success_example,
                }
            },
        },
        400: COMMON_ERROR_RESPONSES[400],
        404: COMMON_ERROR_RESPONSES[404],
        422: {
            "description": "Validation error",
            "model": "ValidationErrorResponse",
        },
        429: COMMON_ERROR_RESPONSES[429],
        500: COMMON_ERROR_RESPONSES[500],
    }


def build_delete_responses() -> dict[int, dict[str, Any]]:
    """Build OpenAPI responses for delete endpoints.

    Returns:
        Dictionary of OpenAPI response specifications
    """
    from backend.api.schemas.errors import COMMON_ERROR_RESPONSES

    return {
        204: {
            "description": "Resource deleted successfully",
        },
        404: COMMON_ERROR_RESPONSES[404],
        409: COMMON_ERROR_RESPONSES[409],
        429: COMMON_ERROR_RESPONSES[429],
        500: COMMON_ERROR_RESPONSES[500],
    }


def build_ai_endpoint_responses(success_example: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Build OpenAPI responses for AI-powered endpoints.

    Args:
        success_example: Example for successful response

    Returns:
        Dictionary of OpenAPI response specifications including 502/503 for AI services
    """
    from backend.api.schemas.errors import COMMON_ERROR_RESPONSES

    return {
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "example": success_example,
                }
            },
        },
        400: COMMON_ERROR_RESPONSES[400],
        404: COMMON_ERROR_RESPONSES[404],
        429: COMMON_ERROR_RESPONSES[429],
        500: COMMON_ERROR_RESPONSES[500],
        502: COMMON_ERROR_RESPONSES[502],
        503: COMMON_ERROR_RESPONSES[503],
    }
