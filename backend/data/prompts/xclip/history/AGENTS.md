# X-CLIP Version History - Agent Guide

## Purpose

This directory contains version history for X-CLIP action recognition configurations. Each file represents a snapshot of the action class list at a specific version.

## Files

| File      | Version | Created At                       | Created By | Description                                       |
| --------- | ------- | -------------------------------- | ---------- | ------------------------------------------------- |
| `v1.json` | 1       | 2026-01-06T13:16:23.588431+00:00 | system     | Initial default configuration (16 action classes) |

## File Format

```json
{
  "model_name": "xclip",
  "config": {
    "action_classes": [
      "walking",
      "running",
      "crouching",
      ...
    ]
  },
  "version": 1,
  "created_at": "2026-01-06T13:16:23.588431+00:00",
  "created_by": "system",
  "description": "Initial default configuration",
  "updated_at": "2026-01-06T13:16:23.588431+00:00"
}
```

## Version Management

See `/backend/data/prompts/nemotron/history/AGENTS.md` for version management details (API usage, restore, comparison).

## Related Documentation

- `/backend/data/prompts/xclip/AGENTS.md` - X-CLIP configuration overview
- `/backend/services/prompt_storage.py` - Version management service
