# Florence-2 Version History - Agent Guide

## Purpose

This directory contains version history for Florence-2 VQA (Visual Question Answering) prompt configurations. Each file represents a snapshot of the VQA query list at a specific version.

## Files

| File      | Version | Created At                       | Created By | Description                                   |
| --------- | ------- | -------------------------------- | ---------- | --------------------------------------------- |
| `v1.json` | 1       | 2026-01-06T13:16:23.587691+00:00 | system     | Initial default configuration (8 VQA queries) |

## File Format

```json
{
  "model_name": "florence2",
  "config": {
    "vqa_queries": [
      "What is this person wearing?",
      "What is this person carrying?",
      ...
    ]
  },
  "version": 1,
  "created_at": "2026-01-06T13:16:23.587691+00:00",
  "created_by": "system",
  "description": "Initial default configuration",
  "updated_at": "2026-01-06T13:16:23.587691+00:00"
}
```

## Version Management

See `/backend/data/prompts/nemotron/history/AGENTS.md` for version management details (API usage, restore, comparison).

## Related Documentation

- `/backend/data/prompts/florence2/AGENTS.md` - Florence-2 configuration overview
- `/backend/services/prompt_storage.py` - Version management service
