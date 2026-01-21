# Custom Directory - Agent Guide

## Purpose

This directory contains custom configurations and resources for the Home Security Intelligence system. It serves as a place for user-specific customizations that are not part of the core application.

## Directory Contents

```
custom/
  AGENTS.md     # This file
  cache/        # Runtime cache directory (created as needed)
  clips/        # Custom video clips directory
    AGENTS.md   # Clips directory guide
```

## Key Subdirectories

### clips/

**Purpose:** Storage for custom video clips used in testing, demos, or specific processing scenarios.

**Usage:**

- Place video files here for manual testing of the detection pipeline
- Can be used for benchmark clips with known objects
- Useful for debugging specific detection scenarios

## Customization Guidelines

### Adding Custom Resources

1. Create subdirectories as needed for organization
2. Keep test data separate from production data
3. Document any custom configurations in this file

### Example Use Cases

- **Custom Detection Models:** Place alternative model weights or configurations
- **Test Clips:** Video clips for validating detection accuracy
- **Custom Prompts:** Alternative LLM prompts for risk analysis
- **Camera Overlays:** Custom overlays or watermarks for specific cameras

## Git Ignore Rules

Custom files may be excluded from version control. Check `.gitignore` for patterns like:

- `custom/**/*.mp4`
- `custom/**/*.avi`
- Large binary files

## Related Directories

- `/data/` - Runtime data (database, logs, thumbnails)
- `/ai/` - AI model configurations
- `/export/foscam/` - Camera upload directory
