"""Hypothesis strategies - backwards compatibility re-exports.

This module has been moved to backend.tests.utils.strategies.

For new code, prefer importing from:
    from backend.tests.utils import camera_ids, risk_scores, ...

Or directly from:
    from backend.tests.utils.strategies import camera_ids, risk_scores, ...

This file provides backwards-compatible re-exports so existing imports continue to work.

Usage:
    from backend.tests.strategies import detection_dict_strategy, event_dict_strategy
    from hypothesis import given

    @given(detection=detection_dict_strategy())
    def test_detection_property(detection):
        assert 0 <= detection["confidence"] <= 1
"""

# Re-export everything from the new location for backwards compatibility
from backend.tests.utils.strategies import (
    # Alert strategies
    alert_rule_dict_strategy,
    # Batch/Analysis strategies
    analysis_queue_item_strategy,
    # Event strategies
    batch_ids,
    batch_summary_strategy,
    # Bounding box strategies
    bbox_and_image_strategy,
    bbox_strategy,
    bbox_tuple_strategy,
    # Camera strategies
    camera_folder_paths,
    camera_ids,
    camera_names,
    channel_lists,
    # Basic types
    confidence_scores,
    cooldown_seconds,
    dedup_key_strategy,
    # Detection strategies
    detection_dict_strategy,
    detection_ids_csv_strategy,
    detection_ids_json_strategy,
    detection_list_strategy,
    event_dict_strategy,
    # File hash strategies
    file_paths,
    image_dimensions_strategy,
    invalid_bbox_xyxy_strategy,
    invalid_confidence_scores,
    invalid_dedup_key_strategy,
    invalid_risk_scores,
    # Severity threshold strategies
    invalid_severity_thresholds_strategy,
    non_negative_integers,
    normalized_bbox_strategy,
    normalized_coords,
    notification_channels,
    # Object types
    object_type_lists,
    object_types,
    # Timestamp strategies
    ordered_timestamp_pair,
    # Search strategies
    phrase_search_strategy,
    positive_integers,
    # Prompt parser strategies
    prompt_section_strategy,
    prompt_variable_strategy,
    risk_levels,
    risk_score_floats,
    risk_scores,
    # Schedule strategies
    schedule_strategy,
    search_operators,
    search_query_strategy,
    search_terms,
    severity_enums,
    severity_levels,
    severity_thresholds_strategy,
    sha256_hashes,
    simple_prompt_strategy,
    time_string_strategy,
    utc_timestamps,
    valid_bbox_xyxy_strategy,
    variable_formats,
    variable_names,
)

__all__ = [
    # Alert strategies
    "alert_rule_dict_strategy",
    # Batch/Analysis strategies
    "analysis_queue_item_strategy",
    # Event strategies
    "batch_ids",
    "batch_summary_strategy",
    # Bounding box strategies
    "bbox_and_image_strategy",
    "bbox_strategy",
    "bbox_tuple_strategy",
    # Camera strategies
    "camera_folder_paths",
    "camera_ids",
    "camera_names",
    "channel_lists",
    # Basic types
    "confidence_scores",
    "cooldown_seconds",
    "dedup_key_strategy",
    # Detection strategies
    "detection_dict_strategy",
    "detection_ids_csv_strategy",
    "detection_ids_json_strategy",
    "detection_list_strategy",
    "event_dict_strategy",
    # File hash strategies
    "file_paths",
    "image_dimensions_strategy",
    "invalid_bbox_xyxy_strategy",
    "invalid_confidence_scores",
    "invalid_dedup_key_strategy",
    "invalid_risk_scores",
    # Severity threshold strategies
    "invalid_severity_thresholds_strategy",
    "non_negative_integers",
    "normalized_bbox_strategy",
    "normalized_coords",
    "notification_channels",
    # Object types
    "object_type_lists",
    "object_types",
    # Timestamp strategies
    "ordered_timestamp_pair",
    # Search strategies
    "phrase_search_strategy",
    "positive_integers",
    # Prompt parser strategies
    "prompt_section_strategy",
    "prompt_variable_strategy",
    "risk_levels",
    "risk_score_floats",
    "risk_scores",
    # Schedule strategies
    "schedule_strategy",
    "search_operators",
    "search_query_strategy",
    "search_terms",
    "severity_enums",
    "severity_levels",
    "severity_thresholds_strategy",
    "sha256_hashes",
    "simple_prompt_strategy",
    "time_string_strategy",
    "utc_timestamps",
    "valid_bbox_xyxy_strategy",
    "variable_formats",
    "variable_names",
]
