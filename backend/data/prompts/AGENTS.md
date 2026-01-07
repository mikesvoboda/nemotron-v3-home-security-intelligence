# Prompts Directory - Agent Guide

## Purpose

The `backend/data/prompts/` directory stores versioned JSON configuration files for all AI models in the security intelligence pipeline. Each model has its own subdirectory with a `current.json` file and a `history/` folder for version tracking.

This file-based storage system provides:

- Persistent configuration for AI models across restarts
- Version history tracking for all configuration changes
- Import/export capability for backup and transfer
- Atomic updates with rollback support

## Directory Structure

```
prompts/
├── AGENTS.md           # This file
├── nemotron/           # Nemotron LLM risk analysis prompts
│   ├── current.json    # Current active configuration
│   └── history/        # Version history
│       └── v1.json     # Version 1 (initial default)
├── florence2/          # Florence-2 VQA (Visual Question Answering) prompts
│   ├── current.json
│   └── history/
│       └── v1.json
├── fashion_clip/       # Fashion-CLIP clothing analysis prompts
│   ├── current.json
│   └── history/
│       └── v1.json
├── xclip/              # X-CLIP action recognition prompts
│   ├── current.json
│   └── history/
│       └── v1.json
└── yolo_world/         # YOLO-World object detection prompts
    ├── current.json
    └── history/
        └── v1.json
```

## File Format

All prompt configurations are stored as JSON with a consistent structure:

```json
{
  "model_name": "model_identifier",
  "config": {
    // Model-specific configuration fields
  },
  "version": 1,
  "created_at": "2026-01-06T13:16:23.587270+00:00",
  "created_by": "system|user|import",
  "description": "Description of changes",
  "updated_at": "2026-01-06T13:16:23.587270+00:00"
}
```

## Model-Specific Configurations

### Nemotron (LLM Risk Analysis)

**Config fields:**

- `system_prompt` (string): Full system prompt with risk interpretation guide
- `temperature` (float): LLM temperature setting (0-2), default 0.7
- `max_tokens` (int): Maximum tokens in response (100-8192), default 2048

### Florence-2 (Visual Question Answering)

**Config fields:**

- `vqa_queries` (array of strings): List of questions to ask about detected objects

### Fashion-CLIP (Clothing Analysis)

**Config fields:**

- `clothing_categories` (array): List of clothing categories to detect
- `suspicious_indicators` (array): List of suspicious attire patterns

### X-CLIP (Action Recognition)

**Config fields:**

- `action_classes` (array): List of human actions to recognize in video/images

### YOLO-World (Object Detection)

**Config fields:**

- `object_classes` (array): List of object categories to detect
- `confidence_threshold` (float): Minimum confidence score (0-1), default 0.5

## Version History

Each time a configuration is updated, the system:

1. Creates a new version file in `history/vN.json` (where N is the version number)
2. Updates `current.json` with the new configuration
3. Increments the version number
4. Records timestamp and creator metadata

This allows rollback to any previous configuration version.

## Service Integration

The `PromptStorageService` (in `/backend/services/prompt_storage.py`) manages all interactions with these files:

| Operation           | Purpose                                     |
| ------------------- | ------------------------------------------- |
| `get_config()`      | Get current active configuration            |
| `update_config()`   | Update configuration and create new version |
| `get_history()`     | Retrieve version history with pagination    |
| `get_version()`     | Get a specific historical version           |
| `restore_version()` | Rollback to a previous version              |
| `export_all()`      | Export all configurations for backup        |
| `import_configs()`  | Import configurations from backup           |
| `validate_config()` | Validate configuration before saving        |

## Default Configurations

Default configurations are defined in `prompt_storage.py` as `DEFAULT_CONFIGS`. When a model is first accessed and no configuration file exists, the system automatically initializes it with the default values and creates version 1.

## Usage by API

The prompt configurations are managed via REST API endpoints:

| Endpoint                                           | Purpose                         |
| -------------------------------------------------- | ------------------------------- |
| `GET /api/prompts/{model}/config`                  | Get current config              |
| `PUT /api/prompts/{model}/config`                  | Update config (creates version) |
| `GET /api/prompts/{model}/history`                 | Get version history             |
| `GET /api/prompts/{model}/versions/{version}`      | Get specific version            |
| `POST /api/prompts/{model}/versions/{version}/...` | Restore version                 |
| `POST /api/prompts/{model}/test`                   | Test config with mock inference |
| `GET /api/prompts/export`                          | Export all configs              |
| `POST /api/prompts/import`                         | Import configs from backup      |

See `/backend/api/routes/prompt_management.py` for implementation details.

## Runtime vs Version Control

**Checked into git:**

- `history/v1.json` - Initial default configurations

**Runtime-generated (not in git):**

- `current.json` - May differ from v1 if configurations have been updated
- `history/v2.json`, `v3.json`, etc. - User-created configuration versions

**Why version 1 is checked in:**
The initial default configurations (v1) are checked into version control to ensure:

- New deployments start with known-good configurations
- Default prompts are code-reviewed and tested
- Configuration schema is documented in the repository

## Security Considerations

- File paths are internally generated and validated to prevent path traversal
- Model names are validated against `SUPPORTED_MODELS` whitelist
- Configuration validation prevents malformed configs from being saved
- No user-supplied paths are used for file operations

## Related Documentation

- `/backend/services/prompt_storage.py` - Prompt storage service implementation
- `/backend/api/routes/prompt_management.py` - API endpoints for prompt management
- `/backend/api/schemas/prompt_management.py` - API request/response schemas
- `/backend/models/prompt_config.py` - Database model (unused in file-based storage)
- `/backend/services/prompts.py` - System prompt templates
