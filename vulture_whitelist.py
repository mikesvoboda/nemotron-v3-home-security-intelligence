# Vulture whitelist - false positives for pytest fixtures
# Fixtures are used by pytest via dependency injection, not direct calls
#
# Usage: uv run vulture backend/ vulture_whitelist.py --min-confidence 80

# Test fixtures that are injected by pytest
_.isolated_db
_.integration_db
_.benchmark_db
_.memory_test_db
_.clean_pipeline
_.clean_seed_data

# Exception handler variables (required by signature)
_.exc_tb

# Notification service placeholders (not yet implemented)
_.device_tokens
