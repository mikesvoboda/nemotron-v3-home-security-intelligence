# Vulture whitelist - false positives for pytest fixtures
# Fixtures are used by pytest via dependency injection, not direct calls
#
# Usage: uv run vulture backend/ vulture_whitelist.py --min-confidence 80

# Protocol method parameters (required by abstract signature)
_.input_data

# Test fixtures that are injected by pytest
_.isolated_db
_.reset_fallback_service
_.integration_db
_.benchmark_db
_.memory_test_db
_.clean_pipeline
_.clean_seed_data
_.clean_tables
_.clean_cameras
_.clean_detections
_.clean_events
_.clean_full_stack
_.clean_logs
_.clean_test_data
_.cleanup_keys
_.temp_foscam_dir
_.temp_thumbnail_dir
_.reset_redis_global_state
_.reset_semaphore

# Test mock fixtures
_.mock_pil_image
_.mock_pynvml_not_available
_.mock_pynvml_no_gpu
_.override_media_rate_limiter

# Config fixtures
_.cfg

# Exception handler variables (required by signature)
_.exc_tb

# Notification service placeholders (not yet implemented)
_.device_tokens

# Mock function parameters (required by interface signature but unused in mock body)
# e.g., async def mock_seek(pos): pass - pos is required by UploadFile.seek signature
_.pos
