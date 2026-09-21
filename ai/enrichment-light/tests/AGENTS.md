# Enrichment-Light Tests Directory

## Purpose

Unit tests for the enrichment-light service's model-loading configuration logic (`ai/enrichment-light/model.py`): which models load at startup vs on demand, driven by environment variables. Regression coverage for NEM-5376. No GPU required.

## Directory Structure

```
ai/enrichment-light/tests/
├── AGENTS.md                 # This file
├── __init__.py               # Package marker
└── test_model_loading.py     # should_load_model / should_preload_model env logic
```

## Running Tests

```bash
uv run pytest ai/enrichment-light/tests/ -v
```

## Testing Patterns

- `clean_env` fixture monkeypatches away enrichment-related env vars so tests never inherit ambient config.
- Covers: default-to-light loading, heavy-assignment overrides, empty vs partial vs full preload lists, invalid model names in preload lists, and docker-compose default-value simulation.

## Related

- `/ai/enrichment-light/AGENTS.md` — service documentation
- `/ai/gateway/adapters/enrichment_light.py` — the gateway route (`/enrich-lt`) that fronts this service in production
