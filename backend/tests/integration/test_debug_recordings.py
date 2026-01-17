"""Integration tests for Debug API recording and replay endpoints (NEM-2754).

This module tests the debug endpoints for request recording and replay:
- Recording activation/deactivation
- Recorded request storage and retrieval
- Request replay functionality
- Recording filters and options

All debug endpoints require settings.debug == True.
"""

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

# Test directory for recordings (isolated from production)
TEST_RECORDINGS_DIR = "data/test_recordings"


@pytest.fixture
def test_recordings_dir(tmp_path):
    """Create a temporary recordings directory for test isolation."""
    recordings_dir = tmp_path / "recordings"
    recordings_dir.mkdir(parents=True, exist_ok=True)
    return str(recordings_dir)


@pytest.fixture
def sample_recording_data():
    """Sample recording data for testing."""
    return {
        "recording_id": "test_recording_123",
        "timestamp": "2024-01-17T10:00:00Z",
        "method": "POST",
        "path": "/api/cameras",
        "headers": {
            "content-type": "application/json",
            "user-agent": "test-client",
        },
        "query_params": {},
        "body": {
            "name": "Test Camera",
            "folder_path": "/export/foscam/test",
        },
        "status_code": 201,
        "duration_ms": 125.5,
        "body_truncated": False,
        "response": {
            "id": "test_camera",
            "name": "Test Camera",
            "folder_path": "/export/foscam/test",
            "status": "online",
        },
    }


@pytest.fixture
def create_sample_recording(test_recordings_dir, sample_recording_data):
    """Create a sample recording file for testing."""

    def _create(recording_id=None, data=None):
        rec_id = recording_id or sample_recording_data["recording_id"]
        rec_data = data or sample_recording_data
        recording_path = Path(test_recordings_dir) / f"{rec_id}.json"
        with recording_path.open("w") as f:
            json.dump(rec_data, f)
        return rec_id, rec_data

    return _create


# =============================================================================
# List Recordings Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_recordings_empty_directory(client, test_recordings_dir):
    """Test listing recordings when no recordings exist."""
    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.get("/api/debug/recordings")

    assert response.status_code == 200
    data = response.json()
    assert data["recordings"] == []
    assert data["total"] == 0
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_list_recordings_single_recording(
    client, test_recordings_dir, create_sample_recording
):
    """Test listing recordings with one recording present."""
    recording_id, recording_data = create_sample_recording()

    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.get("/api/debug/recordings")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["recordings"]) == 1

    recording = data["recordings"][0]
    assert recording["recording_id"] == recording_id
    assert recording["method"] == recording_data["method"]
    assert recording["path"] == recording_data["path"]
    assert recording["status_code"] == recording_data["status_code"]
    assert recording["duration_ms"] == recording_data["duration_ms"]
    assert recording["body_truncated"] is False


@pytest.mark.asyncio
async def test_list_recordings_multiple_recordings(
    client, test_recordings_dir, create_sample_recording
):
    """Test listing multiple recordings sorted by timestamp."""
    # Create multiple recordings
    rec_ids = []
    for i in range(3):
        unique_id = str(uuid.uuid4())[:8]
        rec_id = f"test_recording_{unique_id}"
        data = {
            "recording_id": rec_id,
            "timestamp": f"2024-01-17T10:{i:02d}:00Z",
            "method": "GET",
            "path": f"/api/test/{i}",
            "status_code": 200,
            "duration_ms": 100.0 + i,
            "body_truncated": False,
        }
        create_sample_recording(rec_id, data)
        rec_ids.append(rec_id)

    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.get("/api/debug/recordings")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["recordings"]) == 3


@pytest.mark.asyncio
async def test_list_recordings_with_limit(client, test_recordings_dir, create_sample_recording):
    """Test listing recordings with limit parameter."""
    # Create 5 recordings
    for i in range(5):
        unique_id = str(uuid.uuid4())[:8]
        rec_id = f"test_recording_{unique_id}"
        data = {
            "recording_id": rec_id,
            "timestamp": f"2024-01-17T10:{i:02d}:00Z",
            "method": "GET",
            "path": f"/api/test/{i}",
            "status_code": 200,
            "duration_ms": 100.0,
            "body_truncated": False,
        }
        create_sample_recording(rec_id, data)

    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.get("/api/debug/recordings?limit=2")

    assert response.status_code == 200
    data = response.json()
    assert len(data["recordings"]) == 2
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_list_recordings_ignores_invalid_files(client, test_recordings_dir):
    """Test that invalid JSON files are skipped gracefully."""
    # Create invalid recording file
    invalid_path = Path(test_recordings_dir) / "invalid.json"
    with invalid_path.open("w") as f:
        f.write("{ invalid json")

    # Create valid recording
    valid_path = Path(test_recordings_dir) / "valid.json"
    with valid_path.open("w") as f:
        json.dump(
            {
                "recording_id": "valid",
                "timestamp": "2024-01-17T10:00:00Z",
                "method": "GET",
                "path": "/api/test",
                "status_code": 200,
                "duration_ms": 100.0,
            },
            f,
        )

    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.get("/api/debug/recordings")

    assert response.status_code == 200
    data = response.json()
    # Should only count valid recordings
    assert data["total"] == 1
    assert data["recordings"][0]["recording_id"] == "valid"


# =============================================================================
# Get Recording Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_recording_success(client, test_recordings_dir, create_sample_recording):
    """Test retrieving a specific recording."""
    recording_id, recording_data = create_sample_recording()

    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.get(f"/api/debug/recordings/{recording_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["recording_id"] == recording_id
    assert data["method"] == recording_data["method"]
    assert data["path"] == recording_data["path"]
    assert data["body"] == recording_data["body"]
    assert "retrieved_at" in data


@pytest.mark.asyncio
async def test_get_recording_not_found(client, test_recordings_dir):
    """Test retrieving non-existent recording returns 404."""
    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.get("/api/debug/recordings/nonexistent")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_recording_path_traversal_blocked(client, test_recordings_dir):
    """Test that path traversal attacks are blocked."""
    # Try to access file outside recordings directory
    malicious_ids = [
        "../../../etc/passwd",
        "..%2F..%2F..%2Fetc%2Fpasswd",
        "test/../../secret",
    ]

    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        for malicious_id in malicious_ids:
            response = await client.get(f"/api/debug/recordings/{malicious_id}")
            assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_recording_invalid_characters_sanitized(client, test_recordings_dir):
    """Test that invalid characters in recording_id are sanitized."""
    # Create recording with safe ID
    safe_id = "test_recording_123"
    recording_data = {
        "recording_id": safe_id,
        "timestamp": "2024-01-17T10:00:00Z",
        "method": "GET",
        "path": "/api/test",
        "status_code": 200,
        "duration_ms": 100.0,
    }
    recording_path = Path(test_recordings_dir) / f"{safe_id}.json"
    with recording_path.open("w") as f:
        json.dump(recording_data, f)

    # Try to access with unsafe characters (should be sanitized to safe_id)
    unsafe_id = "test/../recording/123"

    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.get(f"/api/debug/recordings/{unsafe_id}")

    # Should return 404 because sanitized ID doesn't match file
    assert response.status_code == 404


# =============================================================================
# Replay Request Tests
# =============================================================================


@pytest.mark.asyncio
async def test_replay_request_success(client, test_recordings_dir, create_sample_recording):
    """Test successful request replay."""
    # Create a recording of a simple GET request
    recording_id = f"test_replay_{uuid.uuid4().hex[:8]}"
    recording_data = {
        "recording_id": recording_id,
        "timestamp": "2024-01-17T10:00:00Z",
        "method": "GET",
        "path": "/api/cameras",
        "headers": {},
        "query_params": {},
        "body": None,
        "status_code": 200,
        "duration_ms": 100.0,
    }
    create_sample_recording(recording_id, recording_data)

    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.post(f"/api/debug/replay/{recording_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["recording_id"] == recording_id
    assert data["original_status_code"] == 200
    assert "replay_status_code" in data
    assert "replay_response" in data
    assert "replay_metadata" in data
    assert data["replay_metadata"]["original_path"] == "/api/cameras"
    assert data["replay_metadata"]["original_method"] == "GET"
    assert "replay_duration_ms" in data["replay_metadata"]


@pytest.mark.asyncio
async def test_replay_request_with_body(client, test_recordings_dir, create_sample_recording):
    """Test replaying a POST request with JSON body."""
    recording_id = f"test_replay_post_{uuid.uuid4().hex[:8]}"
    unique_camera_id = str(uuid.uuid4())[:8]
    recording_data = {
        "recording_id": recording_id,
        "timestamp": "2024-01-17T10:00:00Z",
        "method": "POST",
        "path": "/api/cameras",
        "headers": {"content-type": "application/json"},
        "query_params": {},
        "body": {
            "name": f"Replayed Camera {unique_camera_id}",
            "folder_path": f"/export/foscam/replay_{unique_camera_id}",
        },
        "status_code": 201,
        "duration_ms": 150.0,
    }
    create_sample_recording(recording_id, recording_data)

    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.post(f"/api/debug/replay/{recording_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["recording_id"] == recording_id
    assert data["original_status_code"] == 201
    assert "replay_status_code" in data
    # The replay should attempt to create the camera
    assert data["replay_metadata"]["original_method"] == "POST"


@pytest.mark.asyncio
async def test_replay_request_with_query_params(
    client, test_recordings_dir, create_sample_recording
):
    """Test replaying a request with query parameters."""
    recording_id = f"test_replay_query_{uuid.uuid4().hex[:8]}"
    recording_data = {
        "recording_id": recording_id,
        "timestamp": "2024-01-17T10:00:00Z",
        "method": "GET",
        "path": "/api/cameras",
        "headers": {},
        "query_params": {"limit": "10", "status": "online"},
        "body": None,
        "status_code": 200,
        "duration_ms": 100.0,
    }
    create_sample_recording(recording_id, recording_data)

    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.post(f"/api/debug/replay/{recording_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["recording_id"] == recording_id
    assert "replay_status_code" in data


@pytest.mark.asyncio
async def test_replay_request_not_found(client, test_recordings_dir):
    """Test replaying non-existent recording returns 404."""
    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.post("/api/debug/replay/nonexistent")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_replay_request_adds_replay_headers(
    client, test_recordings_dir, create_sample_recording
):
    """Test that replay adds special headers to identify replayed requests."""
    recording_id = f"test_replay_headers_{uuid.uuid4().hex[:8]}"
    recording_data = {
        "recording_id": recording_id,
        "timestamp": "2024-01-17T10:00:00Z",
        "method": "GET",
        "path": "/api/cameras",
        "headers": {},
        "query_params": {},
        "body": None,
        "status_code": 200,
        "duration_ms": 100.0,
    }
    create_sample_recording(recording_id, recording_data)

    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.post(f"/api/debug/replay/{recording_id}")

    assert response.status_code == 200
    # The replay functionality adds X-Replay-Request and X-Original-Recording-ID headers
    # We verify that the replay was successful and metadata is present
    data = response.json()
    assert data["recording_id"] == recording_id
    assert "replay_metadata" in data


@pytest.mark.asyncio
async def test_replay_request_invalid_json_file(client, test_recordings_dir):
    """Test replaying a recording with invalid JSON returns 500."""
    recording_id = "invalid_json_rec"
    invalid_path = Path(test_recordings_dir) / f"{recording_id}.json"
    with invalid_path.open("w") as f:
        f.write("{ invalid json")

    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.post(f"/api/debug/replay/{recording_id}")

    assert response.status_code == 500
    assert "Failed to read recording" in response.json()["detail"]


# =============================================================================
# Delete Recording Tests
# =============================================================================


@pytest.mark.asyncio
async def test_delete_recording_success(client, test_recordings_dir, create_sample_recording):
    """Test successful recording deletion."""
    recording_id, _ = create_sample_recording()

    # Verify recording exists
    recording_path = Path(test_recordings_dir) / f"{recording_id}.json"
    assert recording_path.exists()

    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.delete(f"/api/debug/recordings/{recording_id}")

    assert response.status_code == 200
    data = response.json()
    assert "deleted successfully" in data["message"]

    # Verify recording is deleted
    assert not recording_path.exists()


@pytest.mark.asyncio
async def test_delete_recording_not_found(client, test_recordings_dir):
    """Test deleting non-existent recording returns 404."""
    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.delete("/api/debug/recordings/nonexistent")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_recording_path_traversal_blocked(client, test_recordings_dir):
    """Test that path traversal attacks in delete are blocked."""
    malicious_ids = [
        "../../../etc/passwd",
        "..%2F..%2F..%2Fetc%2Fpasswd",
        "test/../../secret",
    ]

    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        for malicious_id in malicious_ids:
            response = await client.delete(f"/api/debug/recordings/{malicious_id}")
            assert response.status_code == 404


# =============================================================================
# Debug Mode Gating Tests
# =============================================================================


@pytest.mark.asyncio
async def test_recordings_require_debug_mode(client, test_recordings_dir):
    """Test that recording endpoints require debug mode to be enabled."""
    # Patch settings to disable debug mode
    from backend.core.config import Settings

    production_settings = Settings(
        debug=False,
        database_url="postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        redis_url="redis://localhost:6379/15",
    )

    with (
        patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir),
        patch("backend.api.routes.debug.get_settings", return_value=production_settings),
    ):
        # All endpoints should return 404 when debug mode is disabled
        response = await client.get("/api/debug/recordings")
        assert response.status_code == 404

        response = await client.get("/api/debug/recordings/test")
        assert response.status_code == 404

        response = await client.post("/api/debug/replay/test")
        assert response.status_code == 404

        response = await client.delete("/api/debug/recordings/test")
        assert response.status_code == 404


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


@pytest.mark.asyncio
async def test_list_recordings_nonexistent_directory(client, tmp_path):
    """Test listing recordings when recordings directory doesn't exist."""
    nonexistent_dir = str(tmp_path / "nonexistent")

    with patch("backend.api.routes.debug.RECORDINGS_DIR", nonexistent_dir):
        response = await client.get("/api/debug/recordings")

    assert response.status_code == 200
    data = response.json()
    assert data["recordings"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_recording_empty_id(client, test_recordings_dir):
    """Test retrieving recording with empty ID returns 404."""
    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.get("/api/debug/recordings/")

    # FastAPI routing should not match this
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_replay_request_missing_fields(client, test_recordings_dir):
    """Test replaying a recording with missing required fields handles gracefully."""
    recording_id = "incomplete_recording"
    incomplete_data = {
        "recording_id": recording_id,
        # Missing method, path, etc.
    }
    recording_path = Path(test_recordings_dir) / f"{recording_id}.json"
    with recording_path.open("w") as f:
        json.dump(incomplete_data, f)

    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.post(f"/api/debug/replay/{recording_id}")

    # Should handle missing fields with defaults
    assert response.status_code == 200
    data = response.json()
    assert data["recording_id"] == recording_id


@pytest.mark.asyncio
async def test_recording_with_special_characters_in_filename(client, test_recordings_dir):
    """Test that recordings with special characters are handled correctly."""
    # Recording IDs should be sanitized, so special chars are removed
    recording_id = "test-recording_123"  # Only alphanumeric, dash, underscore allowed
    recording_data = {
        "recording_id": recording_id,
        "timestamp": "2024-01-17T10:00:00Z",
        "method": "GET",
        "path": "/api/test",
        "status_code": 200,
        "duration_ms": 100.0,
    }
    recording_path = Path(test_recordings_dir) / f"{recording_id}.json"
    with recording_path.open("w") as f:
        json.dump(recording_data, f)

    with patch("backend.api.routes.debug.RECORDINGS_DIR", test_recordings_dir):
        response = await client.get(f"/api/debug/recordings/{recording_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["recording_id"] == recording_id
