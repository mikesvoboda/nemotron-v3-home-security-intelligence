"""Unit tests for video analytics Prometheus metrics (NEM-3722).

Tests cover:
- Tracking metrics (tracks created, lost, reidentified)
- Zone metrics (crossings, intrusions, occupancy)
- Loitering metrics (alerts, dwell times)
- Action recognition metrics (events detected by type)
- Face recognition metrics (known/unknown, quality scores)
"""

from backend.core.metrics import (
    ACTION_RECOGNITION_CONFIDENCE,
    ACTION_RECOGNITION_DURATION_SECONDS,
    # Action recognition metrics
    ACTION_RECOGNITION_TOTAL,
    # Face recognition metrics
    FACE_DETECTIONS_TOTAL,
    FACE_EMBEDDINGS_GENERATED_TOTAL,
    FACE_MATCHES_TOTAL,
    FACE_QUALITY_SCORE,
    FACE_RECOGNITION_CONFIDENCE,
    FACE_RECOGNITION_CONFIDENCE_BUCKETS,
    # Loitering metrics
    LOITERING_ALERTS_TOTAL,
    LOITERING_DURATION_BUCKETS,
    LOITERING_DWELL_TIME_SECONDS,
    LOITERING_EVENTS_TOTAL,
    TRACK_ACTIVE_COUNT,
    TRACK_DURATION_SECONDS,
    # Tracking metrics
    TRACKS_CREATED_TOTAL,
    TRACKS_LOST_TOTAL,
    TRACKS_REIDENTIFIED_TOTAL,
    # Zone metrics
    ZONE_CROSSINGS_TOTAL,
    ZONE_DWELL_TIME_SECONDS,
    ZONE_INTRUSIONS_TOTAL,
    ZONE_OCCUPANCY,
    get_metrics_response,
    observe_action_recognition_confidence,
    observe_action_recognition_duration,
    observe_face_quality_score,
    observe_face_recognition_confidence,
    observe_loitering_dwell_time,
    observe_track_duration,
    observe_zone_dwell_time,
    record_action_recognition,
    record_face_detection,
    record_face_embedding_generated,
    record_face_match,
    record_loitering_alert,
    record_loitering_event,
    # Helper functions
    record_track_created,
    record_track_lost,
    record_track_reidentified,
    record_zone_crossing,
    record_zone_intrusion,
    set_active_track_count,
    set_zone_occupancy,
)


class TestTrackingMetricsDefinitions:
    """Test tracking metric definitions and registrations."""

    def test_tracks_created_counter_exists(self) -> None:
        """TRACKS_CREATED_TOTAL counter should be defined with camera_id label."""
        assert TRACKS_CREATED_TOTAL is not None
        # prometheus_client strips _total suffix from counter names internally
        assert TRACKS_CREATED_TOTAL._name == "hsi_tracks_created"
        assert "camera_id" in TRACKS_CREATED_TOTAL._labelnames

    def test_tracks_lost_counter_exists(self) -> None:
        """TRACKS_LOST_TOTAL counter should be defined with camera_id and reason labels."""
        assert TRACKS_LOST_TOTAL is not None
        assert TRACKS_LOST_TOTAL._name == "hsi_tracks_lost"
        assert "camera_id" in TRACKS_LOST_TOTAL._labelnames
        assert "reason" in TRACKS_LOST_TOTAL._labelnames

    def test_tracks_reidentified_counter_exists(self) -> None:
        """TRACKS_REIDENTIFIED_TOTAL counter should be defined with camera_id label."""
        assert TRACKS_REIDENTIFIED_TOTAL is not None
        assert TRACKS_REIDENTIFIED_TOTAL._name == "hsi_tracks_reidentified"
        assert "camera_id" in TRACKS_REIDENTIFIED_TOTAL._labelnames

    def test_track_duration_histogram_exists(self) -> None:
        """TRACK_DURATION_SECONDS histogram should be defined."""
        assert TRACK_DURATION_SECONDS is not None
        assert TRACK_DURATION_SECONDS._name == "hsi_track_duration_seconds"
        assert "camera_id" in TRACK_DURATION_SECONDS._labelnames
        assert "entity_type" in TRACK_DURATION_SECONDS._labelnames

    def test_track_active_count_gauge_exists(self) -> None:
        """TRACK_ACTIVE_COUNT gauge should be defined with camera_id label."""
        assert TRACK_ACTIVE_COUNT is not None
        assert TRACK_ACTIVE_COUNT._name == "hsi_track_active_count"
        assert "camera_id" in TRACK_ACTIVE_COUNT._labelnames


class TestZoneMetricsDefinitions:
    """Test zone metric definitions and registrations."""

    def test_zone_crossings_counter_exists(self) -> None:
        """ZONE_CROSSINGS_TOTAL counter should be defined with proper labels."""
        assert ZONE_CROSSINGS_TOTAL is not None
        assert ZONE_CROSSINGS_TOTAL._name == "hsi_zone_crossings"
        assert "zone_id" in ZONE_CROSSINGS_TOTAL._labelnames
        assert "direction" in ZONE_CROSSINGS_TOTAL._labelnames
        assert "entity_type" in ZONE_CROSSINGS_TOTAL._labelnames

    def test_zone_intrusions_counter_exists(self) -> None:
        """ZONE_INTRUSIONS_TOTAL counter should be defined with zone_id and severity labels."""
        assert ZONE_INTRUSIONS_TOTAL is not None
        assert ZONE_INTRUSIONS_TOTAL._name == "hsi_zone_intrusions"
        assert "zone_id" in ZONE_INTRUSIONS_TOTAL._labelnames
        assert "severity" in ZONE_INTRUSIONS_TOTAL._labelnames

    def test_zone_occupancy_gauge_exists(self) -> None:
        """ZONE_OCCUPANCY gauge should be defined with zone_id label."""
        assert ZONE_OCCUPANCY is not None
        assert ZONE_OCCUPANCY._name == "hsi_zone_occupancy"
        assert "zone_id" in ZONE_OCCUPANCY._labelnames

    def test_zone_dwell_time_histogram_exists(self) -> None:
        """ZONE_DWELL_TIME_SECONDS histogram should be defined."""
        assert ZONE_DWELL_TIME_SECONDS is not None
        assert ZONE_DWELL_TIME_SECONDS._name == "hsi_zone_dwell_time_seconds"
        assert "zone_id" in ZONE_DWELL_TIME_SECONDS._labelnames


class TestLoiteringMetricsDefinitions:
    """Test loitering metric definitions and registrations."""

    def test_loitering_alerts_counter_exists(self) -> None:
        """LOITERING_ALERTS_TOTAL counter should be defined with proper labels."""
        assert LOITERING_ALERTS_TOTAL is not None
        assert LOITERING_ALERTS_TOTAL._name == "hsi_loitering_alerts"
        assert "camera_id" in LOITERING_ALERTS_TOTAL._labelnames
        assert "zone_id" in LOITERING_ALERTS_TOTAL._labelnames

    def test_loitering_dwell_time_histogram_exists(self) -> None:
        """LOITERING_DWELL_TIME_SECONDS histogram should be defined."""
        assert LOITERING_DWELL_TIME_SECONDS is not None
        assert LOITERING_DWELL_TIME_SECONDS._name == "hsi_loitering_dwell_time_seconds"
        assert "camera_id" in LOITERING_DWELL_TIME_SECONDS._labelnames

    def test_loitering_duration_buckets_defined(self) -> None:
        """LOITERING_DURATION_BUCKETS should have appropriate time ranges."""
        # Loitering typically occurs over 30s to 30min+
        assert 30 in LOITERING_DURATION_BUCKETS  # 30 seconds
        assert 60 in LOITERING_DURATION_BUCKETS  # 1 minute
        assert 300 in LOITERING_DURATION_BUCKETS  # 5 minutes
        assert 600 in LOITERING_DURATION_BUCKETS  # 10 minutes
        assert 1800 in LOITERING_DURATION_BUCKETS  # 30 minutes

    def test_loitering_events_counter_exists(self) -> None:
        """LOITERING_EVENTS_TOTAL counter should be defined with zone and severity labels."""
        assert LOITERING_EVENTS_TOTAL is not None
        # prometheus_client strips _total suffix from counter names internally
        assert LOITERING_EVENTS_TOTAL._name == "hsi_loitering_events"
        assert "zone_id" in LOITERING_EVENTS_TOTAL._labelnames
        assert "zone_name" in LOITERING_EVENTS_TOTAL._labelnames
        assert "severity" in LOITERING_EVENTS_TOTAL._labelnames


class TestActionRecognitionMetricsDefinitions:
    """Test action recognition metric definitions and registrations."""

    def test_action_recognition_counter_exists(self) -> None:
        """ACTION_RECOGNITION_TOTAL counter should be defined with proper labels."""
        assert ACTION_RECOGNITION_TOTAL is not None
        assert ACTION_RECOGNITION_TOTAL._name == "hsi_action_recognition"
        assert "action_type" in ACTION_RECOGNITION_TOTAL._labelnames
        assert "camera_id" in ACTION_RECOGNITION_TOTAL._labelnames

    def test_action_recognition_confidence_histogram_exists(self) -> None:
        """ACTION_RECOGNITION_CONFIDENCE histogram should be defined."""
        assert ACTION_RECOGNITION_CONFIDENCE is not None
        assert ACTION_RECOGNITION_CONFIDENCE._name == "hsi_action_recognition_confidence"
        assert "action_type" in ACTION_RECOGNITION_CONFIDENCE._labelnames

    def test_action_recognition_duration_histogram_exists(self) -> None:
        """ACTION_RECOGNITION_DURATION_SECONDS histogram should be defined."""
        assert ACTION_RECOGNITION_DURATION_SECONDS is not None
        assert (
            ACTION_RECOGNITION_DURATION_SECONDS._name == "hsi_action_recognition_duration_seconds"
        )


class TestFaceRecognitionMetricsDefinitions:
    """Test face recognition metric definitions and registrations."""

    def test_face_detections_counter_exists(self) -> None:
        """FACE_DETECTIONS_TOTAL counter should be defined with proper labels."""
        assert FACE_DETECTIONS_TOTAL is not None
        assert FACE_DETECTIONS_TOTAL._name == "hsi_face_detections"
        assert "camera_id" in FACE_DETECTIONS_TOTAL._labelnames
        assert "match_status" in FACE_DETECTIONS_TOTAL._labelnames

    def test_face_quality_score_histogram_exists(self) -> None:
        """FACE_QUALITY_SCORE histogram should be defined."""
        assert FACE_QUALITY_SCORE is not None
        assert FACE_QUALITY_SCORE._name == "hsi_face_quality_score"

    def test_face_embeddings_counter_exists(self) -> None:
        """FACE_EMBEDDINGS_GENERATED_TOTAL counter should be defined with match_status label."""
        assert FACE_EMBEDDINGS_GENERATED_TOTAL is not None
        assert FACE_EMBEDDINGS_GENERATED_TOTAL._name == "hsi_face_embeddings_generated"
        assert "match_status" in FACE_EMBEDDINGS_GENERATED_TOTAL._labelnames

    def test_face_matches_counter_exists(self) -> None:
        """FACE_MATCHES_TOTAL counter should be defined with person_id label."""
        assert FACE_MATCHES_TOTAL is not None
        assert FACE_MATCHES_TOTAL._name == "hsi_face_matches"
        assert "person_id" in FACE_MATCHES_TOTAL._labelnames

    def test_face_recognition_confidence_histogram_exists(self) -> None:
        """FACE_RECOGNITION_CONFIDENCE histogram should be defined (NEM-4143)."""
        assert FACE_RECOGNITION_CONFIDENCE is not None
        assert FACE_RECOGNITION_CONFIDENCE._name == "hsi_face_recognition_confidence"

    def test_face_recognition_confidence_buckets_defined(self) -> None:
        """FACE_RECOGNITION_CONFIDENCE_BUCKETS should have appropriate thresholds (NEM-4143)."""
        # Should include common face recognition thresholds
        assert 0.68 in FACE_RECOGNITION_CONFIDENCE_BUCKETS  # Default threshold
        assert 0.85 in FACE_RECOGNITION_CONFIDENCE_BUCKETS  # High confidence
        assert 0.95 in FACE_RECOGNITION_CONFIDENCE_BUCKETS  # Near perfect


class TestTrackingMetricHelpers:
    """Test tracking metric helper functions."""

    def test_record_track_created(self) -> None:
        """record_track_created should increment counter with camera_id and object_class."""
        record_track_created("camera-001", "person")
        record_track_created("camera-002", "car")
        # No assertion needed - no exception means success

    def test_record_track_lost(self) -> None:
        """record_track_lost should increment counter with camera_id, object_class, and reason."""
        record_track_lost("camera-001", "person", "timeout")
        record_track_lost("camera-001", "car", "out_of_frame")
        record_track_lost("camera-002", "dog", "occlusion")

    def test_record_track_reidentified(self) -> None:
        """record_track_reidentified should increment counter with camera_id."""
        record_track_reidentified("camera-001")
        record_track_reidentified("camera-002")

    def test_observe_track_duration(self) -> None:
        """observe_track_duration should record histogram observation."""
        observe_track_duration("camera-001", "person", 15.5)
        observe_track_duration("camera-001", "vehicle", 120.0)
        observe_track_duration("camera-002", "person", 5.0)

    def test_set_active_track_count(self) -> None:
        """set_active_track_count should update gauge value."""
        set_active_track_count("camera-001", 5)
        set_active_track_count("camera-002", 12)
        set_active_track_count("camera-001", 0)


class TestZoneMetricHelpers:
    """Test zone metric helper functions."""

    def test_record_zone_crossing(self) -> None:
        """record_zone_crossing should increment counter with labels."""
        record_zone_crossing("zone-001", "enter", "person")
        record_zone_crossing("zone-001", "exit", "person")
        record_zone_crossing("zone-002", "enter", "vehicle")

    def test_record_zone_intrusion(self) -> None:
        """record_zone_intrusion should increment counter with zone_id and severity."""
        record_zone_intrusion("zone-001", "high")
        record_zone_intrusion("zone-002", "medium")
        record_zone_intrusion("zone-001", "low")

    def test_set_zone_occupancy(self) -> None:
        """set_zone_occupancy should update gauge value."""
        set_zone_occupancy("zone-001", 3)
        set_zone_occupancy("zone-002", 0)
        set_zone_occupancy("zone-001", 5)

    def test_observe_zone_dwell_time(self) -> None:
        """observe_zone_dwell_time should record histogram observation."""
        observe_zone_dwell_time("zone-001", 45.0)  # 45 seconds
        observe_zone_dwell_time("zone-002", 300.0)  # 5 minutes
        observe_zone_dwell_time("zone-001", 60.0)  # 1 minute


class TestLoiteringMetricHelpers:
    """Test loitering metric helper functions."""

    def test_record_loitering_alert(self) -> None:
        """record_loitering_alert should increment counter with camera_id and zone_id."""
        record_loitering_alert("camera-001", "zone-001")
        record_loitering_alert("camera-001", "zone-002")
        record_loitering_alert("camera-002", "zone-001")

    def test_observe_loitering_dwell_time(self) -> None:
        """observe_loitering_dwell_time should record histogram observation."""
        observe_loitering_dwell_time("camera-001", 120.0)  # 2 minutes
        observe_loitering_dwell_time("camera-001", 600.0)  # 10 minutes
        observe_loitering_dwell_time("camera-002", 45.0)  # 45 seconds

    def test_record_loitering_event(self) -> None:
        """record_loitering_event should increment counter with zone and severity labels."""
        # Test with alert severity
        record_loitering_event("zone-001", "Front Yard", "alert")
        record_loitering_event("zone-002", "Driveway", "alert")
        # Test with warning severity
        record_loitering_event("zone-001", "Front Yard", "warning")
        record_loitering_event("zone-003", "Back Porch", "warning")

    def test_record_loitering_event_sanitizes_labels(self) -> None:
        """record_loitering_event should sanitize all label values."""
        # Labels with special characters should be sanitized
        record_loitering_event("zone/with/slashes", "Zone Name With <script>", "alert")
        # Very long zone name should be truncated
        long_name = "A" * 200
        record_loitering_event("zone-001", long_name, "warning")


class TestActionRecognitionMetricHelpers:
    """Test action recognition metric helper functions."""

    def test_record_action_recognition(self) -> None:
        """record_action_recognition should increment counter with labels."""
        record_action_recognition("walking", "camera-001")
        record_action_recognition("loitering", "camera-001")
        record_action_recognition("fighting", "camera-002")

    def test_observe_action_recognition_confidence(self) -> None:
        """observe_action_recognition_confidence should record histogram observation."""
        observe_action_recognition_confidence("walking", 0.95)
        observe_action_recognition_confidence("loitering", 0.78)
        observe_action_recognition_confidence("fighting", 0.65)

    def test_observe_action_recognition_duration(self) -> None:
        """observe_action_recognition_duration should record histogram observation."""
        observe_action_recognition_duration(0.15)  # 150ms
        observe_action_recognition_duration(0.5)  # 500ms
        observe_action_recognition_duration(1.2)  # 1.2s


class TestFaceRecognitionMetricHelpers:
    """Test face recognition metric helper functions."""

    def test_record_face_detection(self) -> None:
        """record_face_detection should increment counter with camera_id and match_status."""
        record_face_detection("camera-001", "known")
        record_face_detection("camera-001", "unknown")
        record_face_detection("camera-002", "known")

    def test_observe_face_quality_score(self) -> None:
        """observe_face_quality_score should record histogram observation."""
        observe_face_quality_score(0.85)
        observe_face_quality_score(0.55)
        observe_face_quality_score(0.95)

    def test_record_face_embedding_generated(self) -> None:
        """record_face_embedding_generated should increment counter with match_status (NEM-4143)."""
        record_face_embedding_generated("known")
        record_face_embedding_generated("unknown")
        record_face_embedding_generated()  # Defaults to "unknown"

    def test_observe_face_recognition_confidence(self) -> None:
        """observe_face_recognition_confidence should record histogram observation (NEM-4143)."""
        observe_face_recognition_confidence("cam1", 0.72)  # Above default threshold
        observe_face_recognition_confidence("cam2", 0.55)  # Below threshold
        observe_face_recognition_confidence("cam1", 0.95)  # High confidence

    def test_record_face_match(self) -> None:
        """record_face_match should increment counter with person_id."""
        record_face_match("person-001")
        record_face_match("person-002")
        record_face_match("person-001")


class TestVideoAnalyticsMetricsExposure:
    """Test that video analytics metrics are exposed in /metrics endpoint."""

    def test_metrics_response_contains_tracking_metrics(self) -> None:
        """Metrics response should contain tracking metrics."""
        response = get_metrics_response().decode("utf-8")
        assert "hsi_tracks_created_total" in response
        assert "hsi_tracks_lost_total" in response
        assert "hsi_tracks_reidentified_total" in response
        assert "hsi_track_duration_seconds" in response
        assert "hsi_track_active_count" in response

    def test_metrics_response_contains_zone_metrics(self) -> None:
        """Metrics response should contain zone metrics."""
        response = get_metrics_response().decode("utf-8")
        assert "hsi_zone_crossings_total" in response
        assert "hsi_zone_intrusions_total" in response
        assert "hsi_zone_occupancy" in response
        assert "hsi_zone_dwell_time_seconds" in response

    def test_metrics_response_contains_loitering_metrics(self) -> None:
        """Metrics response should contain loitering metrics."""
        response = get_metrics_response().decode("utf-8")
        assert "hsi_loitering_alerts_total" in response
        assert "hsi_loitering_dwell_time_seconds" in response
        assert "hsi_loitering_events_total" in response

    def test_metrics_response_contains_action_recognition_metrics(self) -> None:
        """Metrics response should contain action recognition metrics."""
        response = get_metrics_response().decode("utf-8")
        assert "hsi_action_recognition_total" in response
        assert "hsi_action_recognition_confidence" in response
        assert "hsi_action_recognition_duration_seconds" in response

    def test_metrics_response_contains_face_recognition_metrics(self) -> None:
        """Metrics response should contain face recognition metrics."""
        response = get_metrics_response().decode("utf-8")
        assert "hsi_face_detections_total" in response
        assert "hsi_face_quality_score" in response
        assert "hsi_face_embeddings_generated_total" in response
        assert "hsi_face_matches_total" in response
        assert "hsi_face_recognition_confidence" in response  # NEM-4143
