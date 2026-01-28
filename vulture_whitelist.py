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
_.clean_data
_.test_events
_.cleanup_cache
_.reader_id
_.clean_soft_delete_tables
_.cleanup_test_keys
_.performance_db
_.pool_test_db
_.slow_query_test_db
_.reset_redis_global
_.sample_nemotron_config
_.reset_signal_handler_state
_.clean_job_data
_.clean_exports
_.sample_export_events
_.ensure_export_dir

# Variables from tuple unpacking (required by signature but unused in tests)
_.shard_hint
_.transaction

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
_.auto_enhance
_.plate_crop

# ASGI middleware parameters (required by ASGI signature in test mock apps)
# async def minimal_app(scope, receive, send): pass
_.receive
_.scope
_.send

# DI container service aliases - REMOVED: these are no longer imported
# They were only used in string literals for cast() calls
# See: backend/api/dependencies.py uses cast("ServiceName", ...) without import

# Test fixtures used for side effects (data setup)
_.sample_anomalies
_.clean_summaries
_.multiple_summaries
_.enable_api_key_auth
_.service_reset
_.cleanup_redis_keys
_.cleanup_stale_databases
_.inputs2
_.trace_state

# SQLAlchemy event handler parameters (required by signature but unused in handler body)
_.flush_context
_.instances

# asyncpg callback parameters (required by signature but unused in callback body)
_.pid

# Type annotations used only in TYPE_CHECKING blocks (mypy only, not runtime)
_.Sentinel
_.CursorResult
