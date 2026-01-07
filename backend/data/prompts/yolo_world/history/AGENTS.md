# YOLO-World Version History - Agent Guide

## Purpose

This directory contains version history for YOLO-World object detection configurations. Each file represents a snapshot of the object class list and confidence threshold at a specific version.

## Files

| File      | Version | Created At                       | Created By | Description                                                       |
| --------- | ------- | -------------------------------- | ---------- | ----------------------------------------------------------------- |
| `v1.json` | 1       | 2026-01-06T13:16:23.588185+00:00 | system     | Initial default configuration (14 object classes + 0.5 threshold) |

## File Format

```json
{
  "model_name": "yolo_world",
  "config": {
    "object_classes": [
      "person",
      "car",
      "knife",
      ...
    ],
    "confidence_threshold": 0.5
  },
  "version": 1,
  "created_at": "2026-01-06T13:16:23.588185+00:00",
  "created_by": "system",
  "description": "Initial default configuration",
  "updated_at": "2026-01-06T13:16:23.588185+00:00"
}
```

## Version Management

See `/backend/data/prompts/nemotron/history/AGENTS.md` for version management details (API usage, restore, comparison).

## Related Documentation

- `/backend/data/prompts/yolo_world/AGENTS.md` - YOLO-World configuration overview
- `/backend/services/prompt_storage.py` - Version management service
