"""HATEOAS (Hypermedia as the Engine of Application State) schemas for API discoverability.

This module provides base schemas for adding hypermedia links to API responses,
enabling clients to discover related resources and available actions dynamically.

HATEOAS is a REST architectural constraint that makes APIs self-documenting by
including links in responses that describe what actions are available and how
to navigate to related resources.

Example response with HATEOAS links:
{
    "id": "front_door",
    "name": "Front Door Camera",
    "status": "online",
    "links": [
        {"href": "/api/cameras/front_door", "rel": "self", "method": "GET"},
        {"href": "/api/cameras/front_door/events", "rel": "events", "method": "GET"},
        {"href": "/api/cameras/front_door/detections", "rel": "detections", "method": "GET"},
        {"href": "/api/cameras/front_door/snapshot", "rel": "snapshot", "method": "GET"}
    ]
}
"""

from typing import Literal

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field


class Link(BaseModel):
    """HATEOAS link representing a related resource or action.

    Links follow the standard web linking format with href, rel, and method.
    The 'rel' attribute describes the relationship between the current resource
    and the linked resource.

    Common rel values:
    - self: The canonical link to this resource
    - collection: Link to the parent collection
    - next/prev: Pagination links
    - related: Generic related resource
    - Custom rels for domain-specific relationships (events, detections, camera)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "href": "/api/cameras/front_door",
                "rel": "self",
                "method": "GET",
            }
        }
    )

    href: str = Field(
        ...,
        description="The URL of the linked resource (relative or absolute)",
    )
    rel: str = Field(
        ...,
        description="The relationship type between the current resource and the link target",
    )
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = Field(
        default="GET",
        description="The HTTP method to use when accessing the linked resource",
    )


def build_link(
    _request: Request,
    path: str,
    rel: str,
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET",
) -> Link:
    """Build a HATEOAS link with a URL path.

    This function creates Link objects with relative URLs for consistency.
    Relative URLs are preferred because they work regardless of the hostname
    or port the API is accessed through.

    Args:
        _request: FastAPI Request object (reserved for future absolute URL building)
        path: The URL path for the link (e.g., "/api/cameras/front_door")
        rel: The relationship type (e.g., "self", "events", "detections")
        method: The HTTP method for the link (default: GET)

    Returns:
        Link object with the specified href, rel, and method
    """
    return Link(href=path, rel=rel, method=method)


# Link relationship constants for consistency across the API
class LinkRel:
    """Standard link relationship types used throughout the API.

    Using constants ensures consistency in link relationships and makes
    it easier for clients to understand and process links programmatically.
    """

    SELF = "self"
    COLLECTION = "collection"
    NEXT = "next"
    PREV = "prev"
    FIRST = "first"
    LAST = "last"

    # Domain-specific relationships
    CAMERA = "camera"
    CAMERAS = "cameras"
    EVENT = "event"
    EVENTS = "events"
    DETECTION = "detection"
    DETECTIONS = "detections"
    SNAPSHOT = "snapshot"
    IMAGE = "image"
    THUMBNAIL = "thumbnail"
    VIDEO = "video"
    ENRICHMENT = "enrichment"
    CLIP = "clip"
    ZONES = "zones"
    BASELINE = "baseline"
    SCENE_CHANGES = "scene_changes"
    UPDATE = "update"
    DELETE = "delete"


def build_camera_links(request: Request, camera_id: str) -> list[Link]:
    """Build standard HATEOAS links for a camera resource.

    Args:
        request: FastAPI Request object
        camera_id: The camera ID

    Returns:
        List of Link objects for camera-related resources
    """
    return [
        build_link(request, f"/api/cameras/{camera_id}", LinkRel.SELF, "GET"),
        build_link(request, "/api/cameras", LinkRel.COLLECTION, "GET"),
        build_link(request, f"/api/cameras/{camera_id}/snapshot", LinkRel.SNAPSHOT, "GET"),
        build_link(request, f"/api/cameras/{camera_id}/zones", LinkRel.ZONES, "GET"),
        build_link(request, f"/api/cameras/{camera_id}/baseline", LinkRel.BASELINE, "GET"),
        build_link(
            request, f"/api/cameras/{camera_id}/scene-changes", LinkRel.SCENE_CHANGES, "GET"
        ),
        build_link(request, f"/api/cameras/{camera_id}", LinkRel.UPDATE, "PATCH"),
        build_link(request, f"/api/cameras/{camera_id}", LinkRel.DELETE, "DELETE"),
        build_link(request, f"/api/events?camera_id={camera_id}", LinkRel.EVENTS, "GET"),
        build_link(request, f"/api/detections?camera_id={camera_id}", LinkRel.DETECTIONS, "GET"),
    ]


def build_event_links(request: Request, event_id: int, camera_id: str) -> list[Link]:
    """Build standard HATEOAS links for an event resource.

    Args:
        request: FastAPI Request object
        event_id: The event ID
        camera_id: The camera ID associated with the event

    Returns:
        List of Link objects for event-related resources
    """
    return [
        build_link(request, f"/api/events/{event_id}", LinkRel.SELF, "GET"),
        build_link(request, "/api/events", LinkRel.COLLECTION, "GET"),
        build_link(request, f"/api/cameras/{camera_id}", LinkRel.CAMERA, "GET"),
        build_link(request, f"/api/events/{event_id}/detections", LinkRel.DETECTIONS, "GET"),
        build_link(request, f"/api/events/{event_id}/enrichments", LinkRel.ENRICHMENT, "GET"),
        build_link(request, f"/api/events/{event_id}/clip", LinkRel.CLIP, "GET"),
        build_link(request, f"/api/events/{event_id}", LinkRel.UPDATE, "PATCH"),
    ]


def build_detection_links(
    request: Request, detection_id: int, camera_id: str, event_id: int | None = None
) -> list[Link]:
    """Build standard HATEOAS links for a detection resource.

    Args:
        request: FastAPI Request object
        detection_id: The detection ID
        camera_id: The camera ID associated with the detection
        event_id: Optional event ID if detection is associated with an event

    Returns:
        List of Link objects for detection-related resources
    """
    links = [
        build_link(request, f"/api/detections/{detection_id}", LinkRel.SELF, "GET"),
        build_link(request, "/api/detections", LinkRel.COLLECTION, "GET"),
        build_link(request, f"/api/cameras/{camera_id}", LinkRel.CAMERA, "GET"),
        build_link(request, f"/api/detections/{detection_id}/image", LinkRel.IMAGE, "GET"),
        build_link(
            request, f"/api/detections/{detection_id}/enrichment", LinkRel.ENRICHMENT, "GET"
        ),
    ]

    if event_id is not None:
        links.append(build_link(request, f"/api/events/{event_id}", LinkRel.EVENT, "GET"))

    return links


def build_detection_video_links(
    request: Request, detection_id: int, camera_id: str, event_id: int | None = None
) -> list[Link]:
    """Build HATEOAS links for a video detection resource.

    Extends the standard detection links with video-specific links.

    Args:
        request: FastAPI Request object
        detection_id: The detection ID
        camera_id: The camera ID associated with the detection
        event_id: Optional event ID if detection is associated with an event

    Returns:
        List of Link objects for video detection resources
    """
    links = build_detection_links(request, detection_id, camera_id, event_id)
    links.extend(
        [
            build_link(request, f"/api/detections/{detection_id}/video", LinkRel.VIDEO, "GET"),
            build_link(
                request, f"/api/detections/{detection_id}/video/thumbnail", LinkRel.THUMBNAIL, "GET"
            ),
        ]
    )
    return links
