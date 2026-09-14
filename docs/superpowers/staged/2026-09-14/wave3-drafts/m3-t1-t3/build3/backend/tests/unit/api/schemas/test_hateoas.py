"""Unit tests for HATEOAS (Hypermedia as the Engine of Application State) schemas.

These tests verify the Link schema and link generation functions work correctly
to provide API discoverability through hypermedia links.
"""

from unittest.mock import MagicMock

import pytest

from backend.api.schemas.hateoas import (
    Link,
    LinkRel,
    build_camera_links,
    build_detection_links,
    build_detection_video_links,
    build_event_links,
    build_link,
)


class TestLinkSchema:
    """Tests for the Link Pydantic schema."""

    def test_link_creation_with_defaults(self) -> None:
        """Test creating a Link with default method (GET)."""
        link = Link(href="/api/cameras/front_door", rel="self")

        assert link.href == "/api/cameras/front_door"
        assert link.rel == "self"
        assert link.method == "GET"

    def test_link_creation_with_custom_method(self) -> None:
        """Test creating a Link with a custom HTTP method."""
        link = Link(href="/api/cameras/front_door", rel="update", method="PATCH")

        assert link.href == "/api/cameras/front_door"
        assert link.rel == "update"
        assert link.method == "PATCH"

    def test_link_creation_with_delete_method(self) -> None:
        """Test creating a Link with DELETE method."""
        link = Link(href="/api/cameras/front_door", rel="delete", method="DELETE")

        assert link.method == "DELETE"

    def test_link_creation_with_post_method(self) -> None:
        """Test creating a Link with POST method."""
        link = Link(href="/api/events", rel="create", method="POST")

        assert link.method == "POST"

    def test_link_creation_with_put_method(self) -> None:
        """Test creating a Link with PUT method."""
        link = Link(href="/api/cameras/front_door", rel="replace", method="PUT")

        assert link.method == "PUT"

    def test_link_serialization(self) -> None:
        """Test that Link serializes correctly to dict."""
        link = Link(href="/api/cameras/front_door", rel="self", method="GET")
        link_dict = link.model_dump()

        assert link_dict == {
            "href": "/api/cameras/front_door",
            "rel": "self",
            "method": "GET",
        }

    def test_link_json_serialization(self) -> None:
        """Test that Link serializes correctly to JSON."""
        link = Link(href="/api/cameras/front_door", rel="self")
        json_str = link.model_dump_json()

        assert '"href":"/api/cameras/front_door"' in json_str
        assert '"rel":"self"' in json_str
        assert '"method":"GET"' in json_str


class TestLinkRelConstants:
    """Tests for LinkRel constants."""

    def test_standard_rels(self) -> None:
        """Test standard link relationship constants."""
        assert LinkRel.SELF == "self"
        assert LinkRel.COLLECTION == "collection"
        assert LinkRel.NEXT == "next"
        assert LinkRel.PREV == "prev"
        assert LinkRel.FIRST == "first"
        assert LinkRel.LAST == "last"

    def test_domain_specific_rels(self) -> None:
        """Test domain-specific link relationship constants."""
        assert LinkRel.CAMERA == "camera"
        assert LinkRel.CAMERAS == "cameras"
        assert LinkRel.EVENT == "event"
        assert LinkRel.EVENTS == "events"
        assert LinkRel.DETECTION == "detection"
        assert LinkRel.DETECTIONS == "detections"
        assert LinkRel.SNAPSHOT == "snapshot"
        assert LinkRel.IMAGE == "image"
        assert LinkRel.THUMBNAIL == "thumbnail"
        assert LinkRel.VIDEO == "video"
        assert LinkRel.ENRICHMENT == "enrichment"
        assert LinkRel.UPDATE == "update"
        assert LinkRel.DELETE == "delete"


class TestBuildLink:
    """Tests for the build_link function."""

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        """Create a mock FastAPI Request object."""
        request = MagicMock()
        request.url.scheme = "http"
        request.url.netloc = "localhost:8000"
        return request

    def test_build_link_with_defaults(self, mock_request: MagicMock) -> None:
        """Test building a link with default GET method."""
        link = build_link(mock_request, "/api/cameras/front_door", "self")

        assert link.href == "/api/cameras/front_door"
        assert link.rel == "self"
        assert link.method == "GET"

    def test_build_link_with_custom_method(self, mock_request: MagicMock) -> None:
        """Test building a link with a custom method."""
        link = build_link(mock_request, "/api/cameras/front_door", "update", "PATCH")

        assert link.href == "/api/cameras/front_door"
        assert link.rel == "update"
        assert link.method == "PATCH"


class TestBuildCameraLinks:
    """Tests for the build_camera_links function."""

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        """Create a mock FastAPI Request object."""
        request = MagicMock()
        return request

    def test_build_camera_links_structure(self, mock_request: MagicMock) -> None:
        """Test that camera links contain all expected relationships."""
        links = build_camera_links(mock_request, "front_door")

        # Extract rel values for easier assertions
        rels = {link.rel for link in links}

        assert "self" in rels
        assert "collection" in rels
        assert "snapshot" in rels
        assert "zones" in rels
        assert "baseline" in rels
        assert "scene_changes" in rels
        assert "update" in rels
        assert "delete" in rels
        assert "events" in rels
        assert "detections" in rels

    def test_build_camera_links_self_href(self, mock_request: MagicMock) -> None:
        """Test that self link points to the camera resource."""
        links = build_camera_links(mock_request, "front_door")
        self_link = next(link for link in links if link.rel == "self")

        assert self_link.href == "/api/cameras/front_door"
        assert self_link.method == "GET"

    def test_build_camera_links_events_href(self, mock_request: MagicMock) -> None:
        """Test that events link filters by camera_id."""
        links = build_camera_links(mock_request, "front_door")
        events_link = next(link for link in links if link.rel == "events")

        assert events_link.href == "/api/events?camera_id=front_door"
        assert events_link.method == "GET"

    def test_build_camera_links_detections_href(self, mock_request: MagicMock) -> None:
        """Test that detections link filters by camera_id."""
        links = build_camera_links(mock_request, "front_door")
        detections_link = next(link for link in links if link.rel == "detections")

        assert detections_link.href == "/api/detections?camera_id=front_door"
        assert detections_link.method == "GET"

    def test_build_camera_links_update_method(self, mock_request: MagicMock) -> None:
        """Test that update link uses PATCH method."""
        links = build_camera_links(mock_request, "front_door")
        update_link = next(link for link in links if link.rel == "update")

        assert update_link.href == "/api/cameras/front_door"
        assert update_link.method == "PATCH"

    def test_build_camera_links_delete_method(self, mock_request: MagicMock) -> None:
        """Test that delete link uses DELETE method."""
        links = build_camera_links(mock_request, "front_door")
        delete_link = next(link for link in links if link.rel == "delete")

        assert delete_link.href == "/api/cameras/front_door"
        assert delete_link.method == "DELETE"


class TestBuildEventLinks:
    """Tests for the build_event_links function."""

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        """Create a mock FastAPI Request object."""
        return MagicMock()

    def test_build_event_links_structure(self, mock_request: MagicMock) -> None:
        """Test that event links contain all expected relationships."""
        links = build_event_links(mock_request, 123, "front_door")

        rels = {link.rel for link in links}

        assert "self" in rels
        assert "collection" in rels
        assert "camera" in rels
        assert "detections" in rels
        assert "enrichment" in rels
        assert "clip" in rels
        assert "update" in rels

    def test_build_event_links_self_href(self, mock_request: MagicMock) -> None:
        """Test that self link points to the event resource."""
        links = build_event_links(mock_request, 123, "front_door")
        self_link = next(link for link in links if link.rel == "self")

        assert self_link.href == "/api/events/123"
        assert self_link.method == "GET"

    def test_build_event_links_camera_href(self, mock_request: MagicMock) -> None:
        """Test that camera link points to the associated camera."""
        links = build_event_links(mock_request, 123, "front_door")
        camera_link = next(link for link in links if link.rel == "camera")

        assert camera_link.href == "/api/cameras/front_door"
        assert camera_link.method == "GET"

    def test_build_event_links_detections_href(self, mock_request: MagicMock) -> None:
        """Test that detections link points to event detections."""
        links = build_event_links(mock_request, 123, "front_door")
        detections_link = next(link for link in links if link.rel == "detections")

        assert detections_link.href == "/api/events/123/detections"
        assert detections_link.method == "GET"


class TestBuildDetectionLinks:
    """Tests for the build_detection_links function."""

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        """Create a mock FastAPI Request object."""
        return MagicMock()

    def test_build_detection_links_structure(self, mock_request: MagicMock) -> None:
        """Test that detection links contain all expected relationships."""
        links = build_detection_links(mock_request, 456, "front_door")

        rels = {link.rel for link in links}

        assert "self" in rels
        assert "collection" in rels
        assert "camera" in rels
        assert "image" in rels
        assert "enrichment" in rels

    def test_build_detection_links_without_event(self, mock_request: MagicMock) -> None:
        """Test that detection links without event_id don't include event link."""
        links = build_detection_links(mock_request, 456, "front_door", event_id=None)

        rels = {link.rel for link in links}

        assert "event" not in rels

    def test_build_detection_links_with_event(self, mock_request: MagicMock) -> None:
        """Test that detection links with event_id include event link."""
        links = build_detection_links(mock_request, 456, "front_door", event_id=123)

        event_link = next((link for link in links if link.rel == "event"), None)

        assert event_link is not None
        assert event_link.href == "/api/events/123"
        assert event_link.method == "GET"

    def test_build_detection_links_self_href(self, mock_request: MagicMock) -> None:
        """Test that self link points to the detection resource."""
        links = build_detection_links(mock_request, 456, "front_door")
        self_link = next(link for link in links if link.rel == "self")

        assert self_link.href == "/api/detections/456"
        assert self_link.method == "GET"


class TestBuildDetectionVideoLinks:
    """Tests for the build_detection_video_links function."""

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        """Create a mock FastAPI Request object."""
        return MagicMock()

    def test_build_video_detection_links_includes_base_links(self, mock_request: MagicMock) -> None:
        """Test that video detection links include all base detection links."""
        links = build_detection_video_links(mock_request, 456, "front_door")

        rels = {link.rel for link in links}

        # Base detection links
        assert "self" in rels
        assert "collection" in rels
        assert "camera" in rels
        assert "image" in rels
        assert "enrichment" in rels

    def test_build_video_detection_links_includes_video_specific(
        self, mock_request: MagicMock
    ) -> None:
        """Test that video detection links include video-specific links."""
        links = build_detection_video_links(mock_request, 456, "front_door")

        rels = {link.rel for link in links}

        assert "video" in rels
        assert "thumbnail" in rels

    def test_build_video_detection_links_video_href(self, mock_request: MagicMock) -> None:
        """Test video link href."""
        links = build_detection_video_links(mock_request, 456, "front_door")
        video_link = next(link for link in links if link.rel == "video")

        assert video_link.href == "/api/detections/456/video"
        assert video_link.method == "GET"

    def test_build_video_detection_links_thumbnail_href(self, mock_request: MagicMock) -> None:
        """Test thumbnail link href."""
        links = build_detection_video_links(mock_request, 456, "front_door")
        thumbnail_link = next(link for link in links if link.rel == "thumbnail")

        assert thumbnail_link.href == "/api/detections/456/video/thumbnail"
        assert thumbnail_link.method == "GET"

    def test_build_video_detection_links_with_event(self, mock_request: MagicMock) -> None:
        """Test that video detection links include event link when provided."""
        links = build_detection_video_links(mock_request, 456, "front_door", event_id=123)

        event_link = next((link for link in links if link.rel == "event"), None)

        assert event_link is not None
        assert event_link.href == "/api/events/123"
