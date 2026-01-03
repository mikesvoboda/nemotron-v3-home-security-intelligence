"""Unit tests for Log model."""

from backend.models.log import Log


class TestLogModel:
    """Tests for Log SQLAlchemy model."""

    def test_log_creation(self):
        """Test creating a log entry."""
        log = Log(
            level="INFO",
            component="test",
            message="Test message",
            source="backend",
        )
        assert log.level == "INFO"
        assert log.component == "test"
        assert log.message == "Test message"
        assert log.source == "backend"

    def test_log_with_metadata(self):
        """Test log with optional metadata fields."""
        log = Log(
            level="ERROR",
            component="file_watcher",
            message="File not found",
            camera_id="front_door",
            request_id="abc-123",
            duration_ms=45,
            extra={"file_path": "/export/foscam/test.jpg"},
        )
        assert log.camera_id == "front_door"
        assert log.request_id == "abc-123"
        assert log.duration_ms == 45
        assert log.extra == {"file_path": "/export/foscam/test.jpg"}

    def test_log_repr(self):
        """Test string representation."""
        log = Log(
            id=1,
            level="WARNING",
            component="api",
            message="Slow query detected in database operation",
        )
        repr_str = repr(log)
        assert "WARNING" in repr_str
        assert "api" in repr_str
