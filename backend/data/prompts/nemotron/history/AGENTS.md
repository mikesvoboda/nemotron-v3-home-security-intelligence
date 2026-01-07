# Nemotron Version History - Agent Guide

## Purpose

This directory contains version history for Nemotron LLM prompt configurations. Each file represents a snapshot of the configuration at a specific version, allowing rollback and comparison.

## Files

| File      | Version | Created At                       | Created By | Description                   |
| --------- | ------- | -------------------------------- | ---------- | ----------------------------- |
| `v1.json` | 1       | 2026-01-06T13:16:23.587270+00:00 | system     | Initial default configuration |

Additional version files (`v2.json`, `v3.json`, etc.) will be created automatically when users update the Nemotron configuration via the API.

## File Format

Each version file contains a complete snapshot of the configuration:

```json
{
  "model_name": "nemotron",
  "config": {
    "system_prompt": "<|im_start|>system\n...full prompt text...<|im_end|>",
    "temperature": 0.7,
    "max_tokens": 2048
  },
  "version": 1,
  "created_at": "2026-01-06T13:16:23.587270+00:00",
  "created_by": "system",
  "description": "Initial default configuration",
  "updated_at": "2026-01-06T13:16:23.587270+00:00"
}
```

## Version Numbering

- Versions are auto-incremented starting from 1
- Each update creates a new version file
- Version numbers are never reused
- Gaps in version numbers indicate deleted versions

## Usage

### View Version History

```bash
# List all versions (newest first)
curl http://localhost:8000/api/prompts/nemotron/history

# Get specific version
curl http://localhost:8000/api/prompts/nemotron/versions/1
```

### Restore Previous Version

```bash
# Restore version 1 (creates new version with old config)
curl -X POST http://localhost:8000/api/prompts/nemotron/versions/1/restore \
  -H "Content-Type: application/json" \
  -d '{"description": "Restored original defaults"}'
```

### Compare Versions

```bash
# Diff two versions
diff v1.json v2.json
```

## Version Control

**Checked into git:**

- `v1.json` - Initial default configuration (baseline for all deployments)

**Runtime-generated (not in git):**

- `v2.json`, `v3.json`, etc. - User-created configuration versions

## Backup and Recovery

To backup all prompt configurations:

```bash
# Export all configs
curl http://localhost:8000/api/prompts/export > prompts_backup.json

# Restore from backup
curl -X POST http://localhost:8000/api/prompts/import \
  -H "Content-Type: application/json" \
  -d @prompts_backup.json
```

## Related Documentation

- `/backend/data/prompts/nemotron/AGENTS.md` - Nemotron configuration overview
- `/backend/services/prompt_storage.py` - Version management service
- `/backend/api/routes/prompt_management.py` - API endpoints
