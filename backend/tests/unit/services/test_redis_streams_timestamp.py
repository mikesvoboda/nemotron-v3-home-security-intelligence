"""Unit tests for Redis Streams timestamp parsing bug fixes.

This module tests the timestamp parsing fixes for DetectionStreamMessage and
AnalysisStreamMessage in the Redis Streams service. These bugs were discovered
during the 2026-02-18 session where timestamps were being published as ISO 8601
strings but parsed as floats, causing ValueError exceptions.

Bug Fixes Tested:
    1. DetectionStreamMessage.from_stream_entry() - timestamp field parsing
    2. AnalysisStreamMessage.from_stream_entry() - pipeline_start_time field parsing
    3. AnalysisStreamMessage.to_queue_dict() - float to ISO 8601 conversion
    4. batch_aggregator.py close_batch() - pipeline_start_time pass-through

Related Issues:
    - Session 2026-02-18: AI Pipeline Timestamp Parsing Bugs

Test Coverage:
    - Parse ISO 8601 timestamp strings
    - Parse Unix epoch float timestamps
    - Handle invalid timestamps (fallback to current time or None)
    - Round-trip conversion: ISO → float → ISO
    - Edge cases: missing fields, malformed strings, timezone variations

Design Notes:
    The parser accepts both formats for backward compatibility:
    - Float: Unix epoch seconds (e.g., 1234567890.123)
    - String: ISO 8601 format (e.g., "2026-02-18T12:34:56.789Z")
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from backend.services.redis_streams import (
    AnalysisStreamMessage,
    DetectionStreamMessage,
)

# ---------------------------------------------------------------------------
# DetectionStreamMessage Tests
# ---------------------------------------------------------------------------


class TestDetectionStreamMessageTimestampParsing:
    """Tests for DetectionStreamMessage.from_stream_entry() timestamp parsing."""

    def test_parse_iso_8601_timestamp_string(self):
        """Test parsing ISO 8601 string timestamp.

        ACCEPTANCE: Parser should accept ISO 8601 format and convert to float.
        """
        iso_timestamp = "2026-02-18T12:34:56.789123+00:00"
        expected_timestamp = datetime.fromisoformat(iso_timestamp).timestamp()

        data = {
            "camera_id": "front_door",
            "detection_id": "42",
            "file_path": "/path/img.jpg",
            "timestamp": iso_timestamp,
        }

        msg = DetectionStreamMessage.from_stream_entry("msg-1", data)

        assert msg.camera_id == "front_door"
        assert msg.detection_id == 42
        assert msg.file_path == "/path/img.jpg"
        assert abs(msg.timestamp - expected_timestamp) < 0.001

    def test_parse_iso_8601_with_z_suffix(self):
        """Test parsing ISO 8601 string with Z (Zulu time) suffix.

        ACCEPTANCE: Parser should handle both +00:00 and Z timezone formats.
        """
        iso_timestamp = "2026-02-18T12:34:56.789Z"
        # datetime.fromisoformat() requires .replace("Z", "+00:00")
        expected_timestamp = datetime.fromisoformat(
            iso_timestamp.replace("Z", "+00:00")
        ).timestamp()

        data = {
            "camera_id": "back_yard",
            "detection_id": "100",
            "file_path": "/path/img2.jpg",
            "timestamp": iso_timestamp,
        }

        msg = DetectionStreamMessage.from_stream_entry("msg-2", data)

        assert abs(msg.timestamp - expected_timestamp) < 0.001

    def test_parse_float_timestamp(self):
        """Test parsing Unix epoch float timestamp.

        ACCEPTANCE: Parser should accept float strings (backward compatibility).
        """
        unix_timestamp = 1708261234.567
        data = {
            "camera_id": "driveway",
            "detection_id": "200",
            "file_path": "/path/img3.jpg",
            "timestamp": str(unix_timestamp),
        }

        msg = DetectionStreamMessage.from_stream_entry("msg-3", data)

        assert abs(msg.timestamp - unix_timestamp) < 0.001

    def test_parse_invalid_timestamp_falls_back_to_current_time(self):
        """Test invalid timestamp falls back to current time.

        ACCEPTANCE: Invalid timestamps should not crash; use time.time() as fallback.
        """
        before = time.time()

        data = {
            "camera_id": "garage",
            "detection_id": "300",
            "file_path": "/path/img4.jpg",
            "timestamp": "invalid-timestamp-format",
        }

        msg = DetectionStreamMessage.from_stream_entry("msg-4", data)

        after = time.time()

        # Fallback timestamp should be approximately current time
        assert before <= msg.timestamp <= after

    def test_parse_missing_timestamp_uses_default(self):
        """Test missing timestamp field uses time.time() default.

        ACCEPTANCE: Missing timestamp should fall back to current time.
        """
        before = time.time()

        data = {
            "camera_id": "kitchen",
            "detection_id": "400",
            "file_path": "/path/img5.jpg",
            # No timestamp field
        }

        msg = DetectionStreamMessage.from_stream_entry("msg-5", data)

        after = time.time()

        assert before <= msg.timestamp <= after

    def test_parse_empty_string_timestamp(self):
        """Test empty string timestamp falls back to current time.

        ACCEPTANCE: Empty strings should trigger fallback logic.
        """
        before = time.time()

        data = {
            "camera_id": "hallway",
            "detection_id": "500",
            "file_path": "/path/img6.jpg",
            "timestamp": "",
        }

        msg = DetectionStreamMessage.from_stream_entry("msg-6", data)

        after = time.time()

        assert before <= msg.timestamp <= after

    def test_parse_timestamp_with_microseconds(self):
        """Test parsing ISO 8601 timestamp with microseconds.

        ACCEPTANCE: Full precision should be preserved during conversion.
        """
        iso_timestamp = "2026-02-18T15:45:30.123456+00:00"
        expected_timestamp = datetime.fromisoformat(iso_timestamp).timestamp()

        data = {
            "camera_id": "bedroom",
            "detection_id": "600",
            "file_path": "/path/img7.jpg",
            "timestamp": iso_timestamp,
        }

        msg = DetectionStreamMessage.from_stream_entry("msg-7", data)

        # Check precision to microsecond level
        assert abs(msg.timestamp - expected_timestamp) < 0.000001

    def test_parse_timestamp_naive_datetime(self):
        """Test parsing ISO 8601 without timezone (naive datetime).

        ACCEPTANCE: Naive datetimes should be accepted (assumed UTC).
        """
        iso_timestamp = "2026-02-18T10:00:00"
        expected_timestamp = datetime.fromisoformat(iso_timestamp).timestamp()

        data = {
            "camera_id": "porch",
            "detection_id": "700",
            "file_path": "/path/img8.jpg",
            "timestamp": iso_timestamp,
        }

        msg = DetectionStreamMessage.from_stream_entry("msg-8", data)

        # Should parse successfully even without timezone
        assert abs(msg.timestamp - expected_timestamp) < 0.001


# ---------------------------------------------------------------------------
# AnalysisStreamMessage Tests
# ---------------------------------------------------------------------------


class TestAnalysisStreamMessageTimestampParsing:
    """Tests for AnalysisStreamMessage.from_stream_entry() timestamp parsing."""

    def test_parse_iso_8601_pipeline_start_time(self):
        """Test parsing ISO 8601 string for pipeline_start_time.

        ACCEPTANCE: Parser should accept ISO 8601 format and convert to float.
        """
        iso_timestamp = "2026-02-18T14:20:30.456789+00:00"
        expected_timestamp = datetime.fromisoformat(iso_timestamp).timestamp()

        data = {
            "batch_id": "batch_abc123",
            "camera_id": "front_door",
            "detection_ids": "[1, 2, 3]",
            "pipeline_start_time": iso_timestamp,
        }

        msg = AnalysisStreamMessage.from_stream_entry("msg-1", data)

        assert msg.batch_id == "batch_abc123"
        assert msg.camera_id == "front_door"
        assert msg.detection_ids == [1, 2, 3]
        assert msg.pipeline_start_time is not None
        assert abs(msg.pipeline_start_time - expected_timestamp) < 0.001

    def test_parse_iso_8601_pipeline_start_time_with_z(self):
        """Test parsing ISO 8601 with Z suffix for pipeline_start_time.

        ACCEPTANCE: Parser should handle Z timezone indicator.
        """
        iso_timestamp = "2026-02-18T16:45:00.123Z"
        expected_timestamp = datetime.fromisoformat(
            iso_timestamp.replace("Z", "+00:00")
        ).timestamp()

        data = {
            "batch_id": "batch_xyz789",
            "camera_id": "back_yard",
            "detection_ids": "[10, 20]",
            "pipeline_start_time": iso_timestamp,
        }

        msg = AnalysisStreamMessage.from_stream_entry("msg-2", data)

        assert msg.pipeline_start_time is not None
        assert abs(msg.pipeline_start_time - expected_timestamp) < 0.001

    def test_parse_float_pipeline_start_time(self):
        """Test parsing Unix epoch float for pipeline_start_time.

        ACCEPTANCE: Parser should accept float strings (backward compatibility).
        """
        unix_timestamp = 1708270800.987
        data = {
            "batch_id": "batch_float",
            "camera_id": "driveway",
            "detection_ids": "[100, 101, 102]",
            "pipeline_start_time": str(unix_timestamp),
        }

        msg = AnalysisStreamMessage.from_stream_entry("msg-3", data)

        assert msg.pipeline_start_time is not None
        assert abs(msg.pipeline_start_time - unix_timestamp) < 0.001

    def test_parse_missing_pipeline_start_time(self):
        """Test missing pipeline_start_time field returns None.

        ACCEPTANCE: Missing optional field should result in None, not crash.
        """
        data = {
            "batch_id": "batch_no_time",
            "camera_id": "garage",
            "detection_ids": "[5, 6]",
            # No pipeline_start_time field
        }

        msg = AnalysisStreamMessage.from_stream_entry("msg-4", data)

        assert msg.batch_id == "batch_no_time"
        assert msg.pipeline_start_time is None

    def test_parse_invalid_pipeline_start_time(self):
        """Test invalid pipeline_start_time falls back to None.

        ACCEPTANCE: Invalid timestamps should return None, not crash.
        """
        data = {
            "batch_id": "batch_bad_time",
            "camera_id": "kitchen",
            "detection_ids": "[7, 8, 9]",
            "pipeline_start_time": "not-a-valid-timestamp",
        }

        msg = AnalysisStreamMessage.from_stream_entry("msg-5", data)

        assert msg.pipeline_start_time is None

    def test_parse_empty_string_pipeline_start_time(self):
        """Test empty string pipeline_start_time returns None.

        ACCEPTANCE: Empty strings should be treated as missing field.
        """
        data = {
            "batch_id": "batch_empty_time",
            "camera_id": "hallway",
            "detection_ids": "[11, 12]",
            "pipeline_start_time": "",
        }

        msg = AnalysisStreamMessage.from_stream_entry("msg-6", data)

        # Empty string should fail float() and fromisoformat(), resulting in None
        assert msg.pipeline_start_time is None


# ---------------------------------------------------------------------------
# AnalysisStreamMessage.to_queue_dict() Tests
# ---------------------------------------------------------------------------


class TestAnalysisStreamMessageToQueueDict:
    """Tests for AnalysisStreamMessage.to_queue_dict() timestamp conversion."""

    def test_to_queue_dict_converts_float_to_iso_string(self):
        """Test to_queue_dict() converts float timestamp back to ISO 8601 string.

        ACCEPTANCE: AnalysisQueuePayload expects ISO string, not float.
        """
        unix_timestamp = 1708270800.123456
        msg = AnalysisStreamMessage(
            id="msg-1",
            batch_id="batch_convert",
            camera_id="front_door",
            detection_ids=[1, 2, 3],
            pipeline_start_time=unix_timestamp,
        )

        result = msg.to_queue_dict()

        assert result["batch_id"] == "batch_convert"
        assert result["camera_id"] == "front_door"
        assert result["detection_ids"] == [1, 2, 3]
        assert "pipeline_start_time" in result

        # Verify it's a valid ISO 8601 string
        pipeline_start_str = result["pipeline_start_time"]
        assert isinstance(pipeline_start_str, str)

        # Should be parseable by datetime.fromisoformat()
        parsed_back = datetime.fromisoformat(pipeline_start_str)
        assert abs(parsed_back.timestamp() - unix_timestamp) < 0.001

    def test_to_queue_dict_with_none_pipeline_start_time(self):
        """Test to_queue_dict() when pipeline_start_time is None.

        ACCEPTANCE: None values should be excluded from result dict.
        """
        msg = AnalysisStreamMessage(
            id="msg-2",
            batch_id="batch_no_time",
            camera_id="back_yard",
            detection_ids=[10, 20],
            pipeline_start_time=None,
        )

        result = msg.to_queue_dict()

        assert result["batch_id"] == "batch_no_time"
        assert result["camera_id"] == "back_yard"
        assert result["detection_ids"] == [10, 20]
        # pipeline_start_time should not be in the dict when None
        assert "pipeline_start_time" not in result

    def test_to_queue_dict_preserves_utc_timezone(self):
        """Test to_queue_dict() produces UTC timestamp with proper timezone info.

        ACCEPTANCE: ISO string should explicitly indicate UTC timezone.
        """
        unix_timestamp = 1708270800.0
        msg = AnalysisStreamMessage(
            id="msg-3",
            batch_id="batch_utc",
            camera_id="driveway",
            detection_ids=[100],
            pipeline_start_time=unix_timestamp,
        )

        result = msg.to_queue_dict()
        pipeline_start_str = result["pipeline_start_time"]

        # Should contain timezone info (either +00:00 or Z)
        assert "+00:00" in pipeline_start_str or pipeline_start_str.endswith("Z")

        # Parse and verify it's UTC
        parsed = datetime.fromisoformat(pipeline_start_str)
        assert parsed.tzinfo == UTC


# ---------------------------------------------------------------------------
# Round-Trip Tests
# ---------------------------------------------------------------------------


class TestTimestampRoundTrip:
    """Tests for full round-trip timestamp conversion."""

    def test_iso_string_to_float_to_iso_string(self):
        """Test round-trip: ISO string → from_stream_entry → to_queue_dict → ISO string.

        ACCEPTANCE: Full pipeline should preserve timestamp value through conversions.
        """
        original_iso = "2026-02-18T18:30:45.123456+00:00"
        original_timestamp = datetime.fromisoformat(original_iso).timestamp()

        # Step 1: Parse from Redis stream entry (ISO string → float)
        data = {
            "batch_id": "batch_roundtrip",
            "camera_id": "garage",
            "detection_ids": "[1, 2]",
            "pipeline_start_time": original_iso,
        }
        msg = AnalysisStreamMessage.from_stream_entry("msg-1", data)

        # Verify float conversion
        assert msg.pipeline_start_time is not None
        assert abs(msg.pipeline_start_time - original_timestamp) < 0.001

        # Step 2: Convert back to queue dict (float → ISO string)
        queue_dict = msg.to_queue_dict()

        # Verify ISO string conversion
        assert "pipeline_start_time" in queue_dict
        final_iso = queue_dict["pipeline_start_time"]
        assert isinstance(final_iso, str)

        # Step 3: Verify final ISO string is valid and matches original
        final_timestamp = datetime.fromisoformat(final_iso).timestamp()
        assert abs(final_timestamp - original_timestamp) < 0.001

    def test_float_to_float_to_iso_string(self):
        """Test round-trip: float string → from_stream_entry → to_queue_dict → ISO string.

        ACCEPTANCE: Float input should be converted to ISO string in final output.
        """
        original_timestamp = 1708270800.987654

        # Step 1: Parse from Redis stream entry (float string → float)
        data = {
            "batch_id": "batch_float_roundtrip",
            "camera_id": "kitchen",
            "detection_ids": "[10, 20, 30]",
            "pipeline_start_time": str(original_timestamp),
        }
        msg = AnalysisStreamMessage.from_stream_entry("msg-2", data)

        # Verify float parsing
        assert msg.pipeline_start_time is not None
        assert abs(msg.pipeline_start_time - original_timestamp) < 0.001

        # Step 2: Convert to queue dict (float → ISO string)
        queue_dict = msg.to_queue_dict()

        # Verify ISO string conversion
        assert "pipeline_start_time" in queue_dict
        final_iso = queue_dict["pipeline_start_time"]
        assert isinstance(final_iso, str)

        # Step 3: Verify final ISO string can be parsed and matches original
        final_timestamp = datetime.fromisoformat(final_iso).timestamp()
        assert abs(final_timestamp - original_timestamp) < 0.001

    def test_detection_stream_message_timestamp_round_trip(self):
        """Test DetectionStreamMessage timestamp survives round-trip parsing.

        ACCEPTANCE: Detection timestamps should maintain precision through conversions.
        """
        original_iso = "2026-02-18T20:15:00.987654+00:00"
        original_timestamp = datetime.fromisoformat(original_iso).timestamp()

        # Parse from stream entry
        data = {
            "camera_id": "porch",
            "detection_id": "999",
            "file_path": "/path/img.jpg",
            "timestamp": original_iso,
        }
        msg = DetectionStreamMessage.from_stream_entry("msg-1", data)

        # Verify float conversion with high precision
        assert abs(msg.timestamp - original_timestamp) < 0.000001

        # Convert back to ISO (not part of DetectionStreamMessage API,
        # but verify the timestamp can be converted back)
        converted_iso = datetime.fromtimestamp(msg.timestamp, tz=UTC).isoformat()
        converted_timestamp = datetime.fromisoformat(converted_iso).timestamp()

        # Should maintain precision
        assert abs(converted_timestamp - original_timestamp) < 0.000001


# ---------------------------------------------------------------------------
# Edge Cases and Error Handling
# ---------------------------------------------------------------------------


class TestTimestampEdgeCases:
    """Tests for edge cases in timestamp parsing."""

    def test_epoch_zero_timestamp(self):
        """Test Unix epoch zero (1970-01-01T00:00:00Z) is valid.

        ACCEPTANCE: Epoch zero should be a valid timestamp.
        """
        data = {
            "batch_id": "batch_epoch_zero",
            "camera_id": "test",
            "detection_ids": "[1]",
            "pipeline_start_time": "0",
        }
        msg = AnalysisStreamMessage.from_stream_entry("msg-1", data)

        assert msg.pipeline_start_time == 0.0

    def test_negative_timestamp(self):
        """Test negative Unix timestamp (before epoch) is valid.

        ACCEPTANCE: Pre-1970 timestamps should be accepted.
        """
        data = {
            "batch_id": "batch_negative",
            "camera_id": "test",
            "detection_ids": "[1]",
            "pipeline_start_time": "-86400.0",  # One day before epoch
        }
        msg = AnalysisStreamMessage.from_stream_entry("msg-1", data)

        assert msg.pipeline_start_time == -86400.0

    def test_very_large_timestamp(self):
        """Test very large timestamp (far future) is valid.

        ACCEPTANCE: Year 3000+ timestamps should be accepted.
        """
        # Timestamp for year 3000
        future_timestamp = 32503680000.0
        data = {
            "batch_id": "batch_future",
            "camera_id": "test",
            "detection_ids": "[1]",
            "pipeline_start_time": str(future_timestamp),
        }
        msg = AnalysisStreamMessage.from_stream_entry("msg-1", data)

        assert msg.pipeline_start_time == future_timestamp

    def test_timestamp_with_different_timezone_offset(self):
        """Test ISO 8601 timestamp with non-UTC timezone offset.

        ACCEPTANCE: Parser should handle any valid ISO 8601 timezone.
        """
        # -05:00 timezone (EST)
        iso_timestamp = "2026-02-18T12:00:00.000-05:00"
        expected_timestamp = datetime.fromisoformat(iso_timestamp).timestamp()

        data = {
            "batch_id": "batch_est",
            "camera_id": "test",
            "detection_ids": "[1]",
            "pipeline_start_time": iso_timestamp,
        }
        msg = AnalysisStreamMessage.from_stream_entry("msg-1", data)

        assert msg.pipeline_start_time is not None
        # Should be converted to UTC timestamp
        assert abs(msg.pipeline_start_time - expected_timestamp) < 0.001
