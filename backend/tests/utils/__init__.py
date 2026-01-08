"""Centralized test utilities package for the backend test suite.

This package consolidates test utilities that were previously scattered across
multiple files, improving discoverability and reuse.

Package Structure:
- async_helpers: Async testing utilities (context managers, timeouts, concurrent testing)
- strategies: Hypothesis strategies for property-based testing
- assertions: Common assertion helpers for response validation

Migration Guide:
- Old: `from backend.tests.async_utils import ...`
- New: `from backend.tests.utils import ...` (preferred)
- Note: Old imports still work via backwards-compatible re-exports

Usage Examples:
    # Import specific utilities
    from backend.tests.utils import (
        # Async helpers
        AsyncClientMock,
        async_timeout,
        run_concurrent_tasks,
        create_mock_redis_client,

        # Assertions
        assert_json_contains,
        assert_status_ok,
        assert_validation_error,

        # Hypothesis strategies
        camera_ids,
        risk_scores,
        detection_dict_strategy,
    )

    # Or import submodules directly
    from backend.tests.utils.async_helpers import AsyncClientMock
    from backend.tests.utils.strategies import risk_scores
    from backend.tests.utils.assertions import assert_json_contains
"""

# =============================================================================
# Async Helpers (from async_helpers.py)
# =============================================================================
# =============================================================================
# Assertion Helpers (from assertions.py)
# =============================================================================
from backend.tests.utils.assertions import (
    assert_datetime_field,
    assert_error_response,
    assert_in_range,
    assert_json_contains,
    assert_json_equals,
    assert_json_list,
    assert_json_not_contains,
    assert_json_schema,
    assert_pagination_response,
    assert_status_code,
    assert_status_ok,
    assert_uuid_field,
    assert_validation_error,
)
from backend.tests.utils.async_helpers import (
    AsyncClientMock,
    AsyncTimeoutError,
    ConcurrentResult,
    async_timeout,
    create_async_mock_client,
    create_async_session_mock,
    create_mock_db_context,
    create_mock_redis_client,
    create_mock_response,
    mock_async_context_manager,
    run_concurrent_tasks,
    simulate_concurrent_requests,
    with_timeout,
)

# =============================================================================
# Hypothesis Strategies (from strategies.py)
# =============================================================================
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
    # Async helpers
    "AsyncClientMock",
    "AsyncTimeoutError",
    "ConcurrentResult",
    # Alert strategies
    "alert_rule_dict_strategy",
    # Batch/Analysis strategies
    "analysis_queue_item_strategy",
    # Assertion helpers
    "assert_datetime_field",
    "assert_error_response",
    "assert_in_range",
    "assert_json_contains",
    "assert_json_equals",
    "assert_json_list",
    "assert_json_not_contains",
    "assert_json_schema",
    "assert_pagination_response",
    "assert_status_code",
    "assert_status_ok",
    "assert_uuid_field",
    "assert_validation_error",
    "async_timeout",
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
    # Hypothesis strategies - basic types
    "confidence_scores",
    "cooldown_seconds",
    "create_async_mock_client",
    "create_async_session_mock",
    "create_mock_db_context",
    "create_mock_redis_client",
    "create_mock_response",
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
    "mock_async_context_manager",
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
    "run_concurrent_tasks",
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
    "simulate_concurrent_requests",
    "time_string_strategy",
    "utc_timestamps",
    "valid_bbox_xyxy_strategy",
    "variable_formats",
    "variable_names",
    "with_timeout",
]
