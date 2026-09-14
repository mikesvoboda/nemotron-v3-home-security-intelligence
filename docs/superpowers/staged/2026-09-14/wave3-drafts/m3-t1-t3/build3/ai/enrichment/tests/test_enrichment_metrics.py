"""Unit tests for AI enrichment service video analytics metrics (NEM-3722).

Tests cover:
- Action recognition metrics
- Pose estimation metrics
- Re-identification (ReID) metrics
- Threat detection metrics
- Demographics metrics
- Face quality metrics
- OCR metrics (PaddleOCR license plate text recognition)

Note: VRAM and model loading metrics are already defined in model_manager.py
and tested separately.
"""

# Add parent directory to path for imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from metrics import (
    ACTION_RECOGNITION_CONFIDENCE,
    ACTION_RECOGNITION_FRAMES_PROCESSED,
    ACTION_RECOGNITION_INFERENCE_LATENCY,
    # Action recognition metrics
    ACTION_RECOGNITION_INFERENCES_TOTAL,
    DEMOGRAPHICS_INFERENCE_LATENCY,
    # Demographics metrics
    DEMOGRAPHICS_INFERENCES_TOTAL,
    # Face quality metrics
    FACE_QUALITY_ASSESSMENTS_TOTAL,
    FACE_QUALITY_SCORES,
    # OCR metrics
    OCR_BLURRY_IMAGES_TOTAL,
    OCR_CONFIDENCE,
    OCR_ENHANCED_IMAGES_TOTAL,
    OCR_ERRORS_TOTAL,
    OCR_IMAGE_QUALITY,
    OCR_INFERENCE_SECONDS,
    OCR_REQUESTS_TOTAL,
    OCR_TEXTS_PER_IMAGE,
    POSE_ESTIMATION_INFERENCE_LATENCY,
    # Pose estimation metrics
    POSE_ESTIMATION_INFERENCES_TOTAL,
    POSE_KEYPOINTS_DETECTED,
    POSE_SUSPICIOUS_ALERTS_TOTAL,
    REID_EMBEDDING_LATENCY,
    # ReID metrics
    REID_EMBEDDINGS_GENERATED_TOTAL,
    REID_MATCH_SIMILARITY,
    REID_MATCHES_TOTAL,
    THREAT_ALERTS_TOTAL,
    THREAT_DETECTION_INFERENCE_LATENCY,
    # Threat detection metrics
    THREAT_DETECTION_INFERENCES_TOTAL,
    get_metrics,
    record_action_recognition_frames,
    # Helper functions
    record_action_recognition_inference,
    record_demographics_inference,
    record_face_quality_assessment,
    record_ocr_error,
    record_ocr_inference,
    record_pose_estimation_inference,
    record_reid_embedding_generated,
    record_reid_match,
    record_threat_detection_inference,
)


class TestActionRecognitionMetricsDefinitions:
    """Test action recognition metric definitions."""

    def test_action_recognition_inferences_counter_exists(self) -> None:
        """ACTION_RECOGNITION_INFERENCES_TOTAL counter should be defined."""
        assert ACTION_RECOGNITION_INFERENCES_TOTAL is not None
        assert "action_type" in ACTION_RECOGNITION_INFERENCES_TOTAL._labelnames
        assert "is_suspicious" in ACTION_RECOGNITION_INFERENCES_TOTAL._labelnames

    def test_action_recognition_inference_latency_exists(self) -> None:
        """ACTION_RECOGNITION_INFERENCE_LATENCY histogram should be defined."""
        assert ACTION_RECOGNITION_INFERENCE_LATENCY is not None

    def test_action_recognition_confidence_exists(self) -> None:
        """ACTION_RECOGNITION_CONFIDENCE histogram should be defined."""
        assert ACTION_RECOGNITION_CONFIDENCE is not None
        assert "action_type" in ACTION_RECOGNITION_CONFIDENCE._labelnames

    def test_action_recognition_frames_counter_exists(self) -> None:
        """ACTION_RECOGNITION_FRAMES_PROCESSED counter should be defined."""
        assert ACTION_RECOGNITION_FRAMES_PROCESSED is not None


class TestPoseEstimationMetricsDefinitions:
    """Test pose estimation metric definitions."""

    def test_pose_estimation_inferences_counter_exists(self) -> None:
        """POSE_ESTIMATION_INFERENCES_TOTAL counter should be defined."""
        assert POSE_ESTIMATION_INFERENCES_TOTAL is not None
        assert "posture" in POSE_ESTIMATION_INFERENCES_TOTAL._labelnames
        assert "is_suspicious" in POSE_ESTIMATION_INFERENCES_TOTAL._labelnames

    def test_pose_estimation_inference_latency_exists(self) -> None:
        """POSE_ESTIMATION_INFERENCE_LATENCY histogram should be defined."""
        assert POSE_ESTIMATION_INFERENCE_LATENCY is not None

    def test_pose_keypoints_detected_exists(self) -> None:
        """POSE_KEYPOINTS_DETECTED histogram should be defined."""
        assert POSE_KEYPOINTS_DETECTED is not None

    def test_pose_suspicious_alerts_counter_exists(self) -> None:
        """POSE_SUSPICIOUS_ALERTS_TOTAL counter should be defined."""
        assert POSE_SUSPICIOUS_ALERTS_TOTAL is not None
        assert "posture_type" in POSE_SUSPICIOUS_ALERTS_TOTAL._labelnames


class TestReIDMetricsDefinitions:
    """Test re-identification metric definitions."""

    def test_reid_embeddings_counter_exists(self) -> None:
        """REID_EMBEDDINGS_GENERATED_TOTAL counter should be defined."""
        assert REID_EMBEDDINGS_GENERATED_TOTAL is not None

    def test_reid_embedding_latency_exists(self) -> None:
        """REID_EMBEDDING_LATENCY histogram should be defined."""
        assert REID_EMBEDDING_LATENCY is not None

    def test_reid_matches_counter_exists(self) -> None:
        """REID_MATCHES_TOTAL counter should be defined."""
        assert REID_MATCHES_TOTAL is not None
        assert "match_type" in REID_MATCHES_TOTAL._labelnames

    def test_reid_match_similarity_exists(self) -> None:
        """REID_MATCH_SIMILARITY histogram should be defined."""
        assert REID_MATCH_SIMILARITY is not None


class TestThreatDetectionMetricsDefinitions:
    """Test threat detection metric definitions."""

    def test_threat_detection_inferences_counter_exists(self) -> None:
        """THREAT_DETECTION_INFERENCES_TOTAL counter should be defined."""
        assert THREAT_DETECTION_INFERENCES_TOTAL is not None
        assert "threat_type" in THREAT_DETECTION_INFERENCES_TOTAL._labelnames
        assert "severity" in THREAT_DETECTION_INFERENCES_TOTAL._labelnames

    def test_threat_detection_latency_exists(self) -> None:
        """THREAT_DETECTION_INFERENCE_LATENCY histogram should be defined."""
        assert THREAT_DETECTION_INFERENCE_LATENCY is not None

    def test_threat_alerts_counter_exists(self) -> None:
        """THREAT_ALERTS_TOTAL counter should be defined."""
        assert THREAT_ALERTS_TOTAL is not None
        assert "threat_type" in THREAT_ALERTS_TOTAL._labelnames


class TestDemographicsMetricsDefinitions:
    """Test demographics metric definitions."""

    def test_demographics_inferences_counter_exists(self) -> None:
        """DEMOGRAPHICS_INFERENCES_TOTAL counter should be defined."""
        assert DEMOGRAPHICS_INFERENCES_TOTAL is not None
        assert "age_range" in DEMOGRAPHICS_INFERENCES_TOTAL._labelnames
        assert "gender" in DEMOGRAPHICS_INFERENCES_TOTAL._labelnames

    def test_demographics_latency_exists(self) -> None:
        """DEMOGRAPHICS_INFERENCE_LATENCY histogram should be defined."""
        assert DEMOGRAPHICS_INFERENCE_LATENCY is not None


class TestFaceQualityMetricsDefinitions:
    """Test face quality metric definitions."""

    def test_face_quality_assessments_counter_exists(self) -> None:
        """FACE_QUALITY_ASSESSMENTS_TOTAL counter should be defined."""
        assert FACE_QUALITY_ASSESSMENTS_TOTAL is not None
        assert "quality_tier" in FACE_QUALITY_ASSESSMENTS_TOTAL._labelnames

    def test_face_quality_scores_histogram_exists(self) -> None:
        """FACE_QUALITY_SCORES histogram should be defined."""
        assert FACE_QUALITY_SCORES is not None


class TestActionRecognitionMetricHelpers:
    """Test action recognition metric helper functions."""

    def test_record_action_recognition_inference(self) -> None:
        """record_action_recognition_inference should record metrics."""
        record_action_recognition_inference("walking", 0.95, 0.5)
        record_action_recognition_inference("loitering", 0.78, 1.2, is_suspicious=True)
        # No exception means success

    def test_record_action_recognition_frames(self) -> None:
        """record_action_recognition_frames should increment counter."""
        record_action_recognition_frames(8)
        record_action_recognition_frames(16)


class TestPoseEstimationMetricHelpers:
    """Test pose estimation metric helper functions."""

    def test_record_pose_estimation_inference(self) -> None:
        """record_pose_estimation_inference should record metrics."""
        record_pose_estimation_inference("standing", False, 0.025, 17)
        record_pose_estimation_inference("crouching", True, 0.030, 15)

    def test_suspicious_pose_increments_alert_counter(self) -> None:
        """Suspicious pose should increment alert counter."""
        record_pose_estimation_inference("hiding", True, 0.028, 12)


class TestReIDMetricHelpers:
    """Test re-identification metric helper functions."""

    def test_record_reid_embedding_generated(self) -> None:
        """record_reid_embedding_generated should record metrics."""
        record_reid_embedding_generated(0.015)
        record_reid_embedding_generated(0.020)

    def test_record_reid_match(self) -> None:
        """record_reid_match should record metrics."""
        record_reid_match("new_track", 0.85)
        record_reid_match("reidentified", 0.92)
        record_reid_match("cross_camera", 0.78)


class TestThreatDetectionMetricHelpers:
    """Test threat detection metric helper functions."""

    def test_record_threat_detection_no_threat(self) -> None:
        """record_threat_detection_inference should handle no threat case."""
        record_threat_detection_inference(False, None, "none", 0.05)

    def test_record_threat_detection_with_threat(self) -> None:
        """record_threat_detection_inference should handle threat case."""
        record_threat_detection_inference(True, "knife", "high", 0.08)
        record_threat_detection_inference(True, "gun", "critical", 0.06)


class TestDemographicsMetricHelpers:
    """Test demographics metric helper functions."""

    def test_record_demographics_inference(self) -> None:
        """record_demographics_inference should record metrics."""
        record_demographics_inference("21-35", "male", 0.1)
        record_demographics_inference("36-50", "female", 0.12)
        record_demographics_inference("11-20", "unknown", 0.09)


class TestFaceQualityMetricHelpers:
    """Test face quality metric helper functions."""

    def test_record_face_quality_high(self) -> None:
        """High quality faces should be categorized correctly."""
        record_face_quality_assessment(0.85)

    def test_record_face_quality_medium(self) -> None:
        """Medium quality faces should be categorized correctly."""
        record_face_quality_assessment(0.65)

    def test_record_face_quality_low(self) -> None:
        """Low quality faces should be categorized correctly."""
        record_face_quality_assessment(0.45)

    def test_record_face_quality_rejected(self) -> None:
        """Rejected quality faces should be categorized correctly."""
        record_face_quality_assessment(0.25)


class TestMetricsExposure:
    """Test that metrics are exposed correctly."""

    def test_get_metrics_returns_bytes(self) -> None:
        """get_metrics should return bytes in Prometheus format."""
        metrics = get_metrics()
        assert isinstance(metrics, bytes)

    def test_get_metrics_contains_action_recognition(self) -> None:
        """Metrics should contain action recognition metrics."""
        metrics = get_metrics().decode("utf-8")
        assert "enrichment_action_recognition" in metrics

    def test_get_metrics_contains_pose_estimation(self) -> None:
        """Metrics should contain pose estimation metrics."""
        metrics = get_metrics().decode("utf-8")
        assert "enrichment_pose_estimation" in metrics

    def test_get_metrics_contains_reid(self) -> None:
        """Metrics should contain re-ID metrics."""
        metrics = get_metrics().decode("utf-8")
        assert "enrichment_reid" in metrics

    def test_get_metrics_contains_threat_detection(self) -> None:
        """Metrics should contain threat detection metrics."""
        metrics = get_metrics().decode("utf-8")
        assert "enrichment_threat" in metrics

    def test_get_metrics_contains_demographics(self) -> None:
        """Metrics should contain demographics metrics."""
        metrics = get_metrics().decode("utf-8")
        assert "enrichment_demographics" in metrics

    def test_get_metrics_contains_face_quality(self) -> None:
        """Metrics should contain face quality metrics."""
        metrics = get_metrics().decode("utf-8")
        assert "enrichment_face_quality" in metrics

    def test_get_metrics_contains_ocr(self) -> None:
        """Metrics should contain OCR metrics."""
        metrics = get_metrics().decode("utf-8")
        assert "enrichment_ocr" in metrics


# =============================================================================
# OCR Metrics Tests
# =============================================================================


class TestOCRMetricsDefinitions:
    """Test OCR metric definitions."""

    def test_ocr_inference_seconds_histogram_exists(self) -> None:
        """OCR_INFERENCE_SECONDS histogram should be defined."""
        assert OCR_INFERENCE_SECONDS is not None

    def test_ocr_texts_per_image_histogram_exists(self) -> None:
        """OCR_TEXTS_PER_IMAGE histogram should be defined."""
        assert OCR_TEXTS_PER_IMAGE is not None

    def test_ocr_requests_counter_exists(self) -> None:
        """OCR_REQUESTS_TOTAL counter should be defined."""
        assert OCR_REQUESTS_TOTAL is not None
        assert "status" in OCR_REQUESTS_TOTAL._labelnames

    def test_ocr_errors_counter_exists(self) -> None:
        """OCR_ERRORS_TOTAL counter should be defined."""
        assert OCR_ERRORS_TOTAL is not None
        assert "error_type" in OCR_ERRORS_TOTAL._labelnames

    def test_ocr_confidence_histogram_exists(self) -> None:
        """OCR_CONFIDENCE histogram should be defined."""
        assert OCR_CONFIDENCE is not None

    def test_ocr_image_quality_histogram_exists(self) -> None:
        """OCR_IMAGE_QUALITY histogram should be defined."""
        assert OCR_IMAGE_QUALITY is not None

    def test_ocr_enhanced_images_counter_exists(self) -> None:
        """OCR_ENHANCED_IMAGES_TOTAL counter should be defined."""
        assert OCR_ENHANCED_IMAGES_TOTAL is not None

    def test_ocr_blurry_images_counter_exists(self) -> None:
        """OCR_BLURRY_IMAGES_TOTAL counter should be defined."""
        assert OCR_BLURRY_IMAGES_TOTAL is not None


class TestOCRMetricHelpers:
    """Test OCR metric helper functions."""

    def test_record_ocr_inference_success(self) -> None:
        """record_ocr_inference should record successful inference."""
        record_ocr_inference(
            duration_seconds=0.15,
            texts_detected=2,
            success=True,
            confidence=0.95,
            image_quality=0.8,
        )
        # No exception means success

    def test_record_ocr_inference_failure(self) -> None:
        """record_ocr_inference should record failed inference."""
        record_ocr_inference(
            duration_seconds=0.05,
            texts_detected=0,
            success=False,
            image_quality=0.3,
        )

    def test_record_ocr_inference_with_enhancement(self) -> None:
        """record_ocr_inference should record enhanced image flag."""
        record_ocr_inference(
            duration_seconds=0.2,
            texts_detected=1,
            success=True,
            confidence=0.88,
            is_enhanced=True,
        )

    def test_record_ocr_inference_with_blur(self) -> None:
        """record_ocr_inference should record blurry image flag."""
        record_ocr_inference(
            duration_seconds=0.12,
            texts_detected=0,
            success=True,
            confidence=0.4,
            is_blurry=True,
        )

    def test_record_ocr_inference_with_all_flags(self) -> None:
        """record_ocr_inference should handle all optional parameters."""
        record_ocr_inference(
            duration_seconds=0.25,
            texts_detected=3,
            success=True,
            confidence=0.92,
            image_quality=0.75,
            is_enhanced=True,
            is_blurry=True,
        )

    def test_record_ocr_inference_zero_confidence(self) -> None:
        """record_ocr_inference should handle zero confidence correctly."""
        record_ocr_inference(
            duration_seconds=0.1,
            texts_detected=0,
            success=True,
            confidence=0.0,
        )

    def test_record_ocr_error_model_not_loaded(self) -> None:
        """record_ocr_error should record model_not_loaded errors."""
        record_ocr_error("model_not_loaded")

    def test_record_ocr_error_inference_error(self) -> None:
        """record_ocr_error should record inference_error."""
        record_ocr_error("inference_error")

    def test_record_ocr_error_invalid_image(self) -> None:
        """record_ocr_error should record invalid_image errors."""
        record_ocr_error("invalid_image")

    def test_record_ocr_error_timeout(self) -> None:
        """record_ocr_error should record timeout errors."""
        record_ocr_error("timeout")
