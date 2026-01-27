"""Prometheus metrics for AI enrichment service video analytics features (NEM-3722).

This module defines Prometheus metrics specific to the enrichment service's
video analytics capabilities including action recognition, pose estimation,
threat detection, demographics, and re-identification.

These metrics complement the existing metrics in model_manager.py (VRAM metrics)
and model.py (inference latency metrics) by providing video analytics-specific
tracking metrics.

Note: VRAM metrics (usage, budget, evictions) are already defined in model_manager.py
and should be imported from there, not redefined here.

Usage:
    from metrics import (
        record_action_recognition_inference,
        record_pose_estimation_inference,
        record_reid_embedding_generated,
    )

    # Record action recognition inference
    record_action_recognition_inference("loitering", 0.85, 0.5)

    # Record pose estimation
    record_pose_estimation_inference("standing", True, 0.025)

    # Record re-ID embedding generation
    record_reid_embedding_generated(0.015)
"""

from prometheus_client import Counter, Histogram, generate_latest

# =============================================================================
# Action Recognition Metrics
# =============================================================================

ACTION_RECOGNITION_INFERENCES_TOTAL = Counter(
    "enrichment_action_recognition_inferences_total",
    "Total number of action recognition inferences",
    ["action_type", "is_suspicious"],
)

ACTION_RECOGNITION_INFERENCE_LATENCY = Histogram(
    "enrichment_action_recognition_inference_latency_seconds",
    "Action recognition inference latency in seconds",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)

ACTION_RECOGNITION_CONFIDENCE = Histogram(
    "enrichment_action_recognition_confidence",
    "Confidence scores for action recognition",
    ["action_type"],
    buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99],
)

ACTION_RECOGNITION_FRAMES_PROCESSED = Counter(
    "enrichment_action_recognition_frames_processed_total",
    "Total number of frames processed for action recognition",
)

# =============================================================================
# Pose Estimation Metrics
# =============================================================================

POSE_ESTIMATION_INFERENCES_TOTAL = Counter(
    "enrichment_pose_estimation_inferences_total",
    "Total number of pose estimation inferences",
    ["posture", "is_suspicious"],
)

POSE_ESTIMATION_INFERENCE_LATENCY = Histogram(
    "enrichment_pose_estimation_inference_latency_seconds",
    "Pose estimation inference latency in seconds",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
)

POSE_KEYPOINTS_DETECTED = Histogram(
    "enrichment_pose_keypoints_detected",
    "Number of keypoints detected per pose",
    buckets=[5, 10, 12, 14, 16, 17],  # 17 is max for COCO keypoints
)

POSE_SUSPICIOUS_ALERTS_TOTAL = Counter(
    "enrichment_pose_suspicious_alerts_total",
    "Total number of suspicious pose alerts",
    ["posture_type"],
)

# =============================================================================
# Re-Identification (ReID) Metrics
# =============================================================================

REID_EMBEDDINGS_GENERATED_TOTAL = Counter(
    "enrichment_reid_embeddings_generated_total",
    "Total number of re-ID embeddings generated",
)

REID_EMBEDDING_LATENCY = Histogram(
    "enrichment_reid_embedding_latency_seconds",
    "Re-ID embedding generation latency in seconds",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25],
)

REID_MATCHES_TOTAL = Counter(
    "enrichment_reid_matches_total",
    "Total number of successful re-ID matches",
    ["match_type"],  # new_track, reidentified, cross_camera
)

REID_MATCH_SIMILARITY = Histogram(
    "enrichment_reid_match_similarity",
    "Cosine similarity scores for re-ID matches",
    buckets=[0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95],
)

# =============================================================================
# Threat Detection Metrics
# =============================================================================

THREAT_DETECTION_INFERENCES_TOTAL = Counter(
    "enrichment_threat_detection_inferences_total",
    "Total number of threat detection inferences",
    ["threat_type", "severity"],
)

THREAT_DETECTION_INFERENCE_LATENCY = Histogram(
    "enrichment_threat_detection_inference_latency_seconds",
    "Threat detection inference latency in seconds",
    buckets=[0.025, 0.05, 0.1, 0.25, 0.5],
)

THREAT_ALERTS_TOTAL = Counter(
    "enrichment_threat_alerts_total",
    "Total number of threat alerts generated",
    ["threat_type"],  # gun, knife, bat, etc.
)

# =============================================================================
# Demographics Metrics
# =============================================================================

DEMOGRAPHICS_INFERENCES_TOTAL = Counter(
    "enrichment_demographics_inferences_total",
    "Total number of demographics inferences",
    ["age_range", "gender"],
)

DEMOGRAPHICS_INFERENCE_LATENCY = Histogram(
    "enrichment_demographics_inference_latency_seconds",
    "Demographics inference latency in seconds",
    buckets=[0.025, 0.05, 0.1, 0.25, 0.5],
)

# =============================================================================
# Face Quality Metrics (for Face Recognition pipeline)
# =============================================================================

FACE_QUALITY_ASSESSMENTS_TOTAL = Counter(
    "enrichment_face_quality_assessments_total",
    "Total number of face quality assessments",
    ["quality_tier"],  # high, medium, low, rejected
)

FACE_QUALITY_SCORES = Histogram(
    "enrichment_face_quality_scores",
    "Face quality scores from enrichment pipeline",
    buckets=[0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
)


# =============================================================================
# Helper Functions
# =============================================================================


def record_action_recognition_inference(
    action_type: str, confidence: float, duration_seconds: float, is_suspicious: bool = False
) -> None:
    """Record an action recognition inference.

    Args:
        action_type: Type of action detected (walking, loitering, fighting, etc.).
        confidence: Confidence score (0.0 to 1.0).
        duration_seconds: Inference duration in seconds.
        is_suspicious: Whether the action is flagged as suspicious.
    """
    ACTION_RECOGNITION_INFERENCES_TOTAL.labels(
        action_type=action_type, is_suspicious=str(is_suspicious).lower()
    ).inc()
    ACTION_RECOGNITION_INFERENCE_LATENCY.observe(duration_seconds)
    ACTION_RECOGNITION_CONFIDENCE.labels(action_type=action_type).observe(confidence)


def record_action_recognition_frames(frame_count: int) -> None:
    """Record number of frames processed for action recognition.

    Args:
        frame_count: Number of frames processed.
    """
    ACTION_RECOGNITION_FRAMES_PROCESSED.inc(frame_count)


def record_pose_estimation_inference(
    posture: str, is_suspicious: bool, duration_seconds: float, keypoints_detected: int = 17
) -> None:
    """Record a pose estimation inference.

    Args:
        posture: Detected posture (standing, crouching, lying_down, etc.).
        is_suspicious: Whether the pose is flagged as suspicious.
        duration_seconds: Inference duration in seconds.
        keypoints_detected: Number of keypoints detected.
    """
    POSE_ESTIMATION_INFERENCES_TOTAL.labels(
        posture=posture, is_suspicious=str(is_suspicious).lower()
    ).inc()
    POSE_ESTIMATION_INFERENCE_LATENCY.observe(duration_seconds)
    POSE_KEYPOINTS_DETECTED.observe(keypoints_detected)

    if is_suspicious:
        POSE_SUSPICIOUS_ALERTS_TOTAL.labels(posture_type=posture).inc()


def record_reid_embedding_generated(duration_seconds: float) -> None:
    """Record a re-ID embedding generation.

    Args:
        duration_seconds: Time to generate the embedding in seconds.
    """
    REID_EMBEDDINGS_GENERATED_TOTAL.inc()
    REID_EMBEDDING_LATENCY.observe(duration_seconds)


def record_reid_match(match_type: str, similarity: float) -> None:
    """Record a successful re-ID match.

    Args:
        match_type: Type of match (new_track, reidentified, cross_camera).
        similarity: Cosine similarity score of the match.
    """
    REID_MATCHES_TOTAL.labels(match_type=match_type).inc()
    REID_MATCH_SIMILARITY.observe(similarity)


def record_threat_detection_inference(
    has_threat: bool, threat_type: str | None, severity: str, duration_seconds: float
) -> None:
    """Record a threat detection inference.

    Args:
        has_threat: Whether a threat was detected.
        threat_type: Type of threat detected (gun, knife, etc.) or None.
        severity: Severity level (critical, high, medium, low, none).
        duration_seconds: Inference duration in seconds.
    """
    label_threat_type = threat_type if threat_type else "none"
    THREAT_DETECTION_INFERENCES_TOTAL.labels(threat_type=label_threat_type, severity=severity).inc()
    THREAT_DETECTION_INFERENCE_LATENCY.observe(duration_seconds)

    if has_threat and threat_type:
        THREAT_ALERTS_TOTAL.labels(threat_type=threat_type).inc()


def record_demographics_inference(age_range: str, gender: str, duration_seconds: float) -> None:
    """Record a demographics inference.

    Args:
        age_range: Detected age range (0-10, 11-20, 21-35, etc.).
        gender: Detected gender (male, female, unknown).
        duration_seconds: Inference duration in seconds.
    """
    DEMOGRAPHICS_INFERENCES_TOTAL.labels(age_range=age_range, gender=gender).inc()
    DEMOGRAPHICS_INFERENCE_LATENCY.observe(duration_seconds)


def record_face_quality_assessment(quality_score: float) -> None:
    """Record a face quality assessment.

    Args:
        quality_score: Face quality score (0.0 to 1.0).
    """
    # Determine quality tier
    if quality_score >= 0.8:
        tier = "high"
    elif quality_score >= 0.6:
        tier = "medium"
    elif quality_score >= 0.4:
        tier = "low"
    else:
        tier = "rejected"

    FACE_QUALITY_ASSESSMENTS_TOTAL.labels(quality_tier=tier).inc()
    FACE_QUALITY_SCORES.observe(quality_score)


def get_metrics() -> bytes:
    """Generate Prometheus metrics in exposition format.

    Returns:
        Prometheus metrics as bytes in exposition format.
    """
    return generate_latest()
