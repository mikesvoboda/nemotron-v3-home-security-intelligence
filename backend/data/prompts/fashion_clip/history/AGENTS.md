# Fashion-CLIP Version History - Agent Guide

## Purpose

This directory contains version history for Fashion-CLIP clothing analysis configurations. Each file represents a snapshot of the clothing categories and suspicious indicators at a specific version.

## Files

| File      | Version | Created At                       | Created By | Description                                                  |
| --------- | ------- | -------------------------------- | ---------- | ------------------------------------------------------------ |
| `v1.json` | 1       | 2026-01-06T13:16:23.587943+00:00 | system     | Initial default configuration (17 categories + 6 indicators) |

## File Format

```json
{
  "model_name": "fashion_clip",
  "config": {
    "clothing_categories": [
      "casual wear",
      "formal wear",
      ...
    ],
    "suspicious_indicators": [
      "all black",
      "face mask",
      ...
    ]
  },
  "version": 1,
  "created_at": "2026-01-06T13:16:23.587943+00:00",
  "created_by": "system",
  "description": "Initial default configuration",
  "updated_at": "2026-01-06T13:16:23.587943+00:00"
}
```

## Version Management

See `/backend/data/prompts/nemotron/history/AGENTS.md` for version management details (API usage, restore, comparison).

## Related Documentation

- `/backend/data/prompts/fashion_clip/AGENTS.md` - Fashion-CLIP configuration overview
- `/backend/services/prompt_storage.py` - Version management service
