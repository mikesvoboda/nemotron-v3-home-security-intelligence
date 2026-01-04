---
title: Prompt Management API
description: REST API endpoints for managing AI model prompt configurations
source_refs:
  - backend/api/routes/prompt_management.py
  - backend/api/schemas/prompt_management.py
  - backend/models/prompt_version.py
  - backend/services/prompt_service.py
---

# Prompt Management API

The Prompt Management API provides endpoints for managing AI model prompt configurations. This includes CRUD operations for prompts, version history tracking, testing configurations, and import/export capabilities.

## Endpoints Overview

| Method | Endpoint                                     | Description                                   |
| ------ | -------------------------------------------- | --------------------------------------------- |
| GET    | `/api/ai-audit/prompts`                      | Get all model prompt configurations           |
| GET    | `/api/ai-audit/prompts/{model}`              | Get prompt configuration for a specific model |
| PUT    | `/api/ai-audit/prompts/{model}`              | Update prompt configuration for a model       |
| GET    | `/api/ai-audit/prompts/export`               | Export all prompt configurations              |
| GET    | `/api/ai-audit/prompts/history`              | Get version history for prompts               |
| POST   | `/api/ai-audit/prompts/history/{version_id}` | Restore a specific prompt version             |
| POST   | `/api/ai-audit/prompts/test`                 | Test a prompt configuration                   |
| POST   | `/api/ai-audit/prompts/import`               | Import prompt configurations                  |
| POST   | `/api/ai-audit/prompts/import/preview`       | Preview import changes before applying        |

---

## Supported AI Models

The API supports configuration management for the following AI models:

| Model        | Enum Value     | Description                       |
| ------------ | -------------- | --------------------------------- |
| Nemotron     | `nemotron`     | Risk analysis LLM (system prompt) |
| Florence-2   | `florence2`    | Scene analysis queries            |
| YOLO-World   | `yolo_world`   | Custom object detection classes   |
| X-CLIP       | `xclip`        | Action recognition classes        |
| Fashion-CLIP | `fashion_clip` | Clothing category classification  |

---

## GET /api/ai-audit/prompts

Fetch current prompt configurations for all AI models.

Returns the active prompt/configuration for each supported model including version numbers.

**Source:** [`get_all_prompts`](../../backend/api/routes/prompt_management.py:37)

**Response:** `200 OK`

```json
{
  "version": "1.0",
  "exported_at": "2025-12-23T12:00:00Z",
  "prompts": {
    "nemotron": {
      "system_prompt": "You are a security analysis AI...",
      "version": 3
    },
    "florence2": {
      "queries": [
        "What is the person doing?",
        "What objects are they carrying?",
        "Describe the environment",
        "Is there anything unusual in this scene?"
      ],
      "version": 1
    },
    "yolo_world": {
      "classes": ["knife", "gun", "package", "crowbar", "spray paint"],
      "confidence_threshold": 0.35,
      "version": 2
    },
    "xclip": {
      "action_classes": ["loitering", "running away", "fighting", "breaking in"],
      "version": 1
    },
    "fashion_clip": {
      "clothing_categories": ["dark hoodie", "face mask", "gloves", "all black"],
      "version": 1
    }
  }
}
```

**Example Request:**

```bash
curl http://localhost:8000/api/ai-audit/prompts
```

---

## GET /api/ai-audit/prompts/{model}

Fetch prompt configuration for a specific AI model.

**Source:** [`get_prompt_for_model`](../../backend/api/routes/prompt_management.py:305)

**Parameters:**

| Name    | Type   | In   | Required | Description                                                                |
| ------- | ------ | ---- | -------- | -------------------------------------------------------------------------- |
| `model` | string | path | Yes      | Model name: `nemotron`, `florence2`, `yolo_world`, `xclip`, `fashion_clip` |

**Response:** `200 OK`

```json
{
  "model": "nemotron",
  "config": {
    "system_prompt": "You are a security analysis AI. Analyze the following detection context and provide a risk assessment..."
  },
  "version": 3,
  "created_at": "2025-12-20T15:30:00Z",
  "created_by": "admin",
  "change_description": "Improved risk scoring criteria"
}
```

**Example Requests:**

```bash
# Get Nemotron prompt
curl http://localhost:8000/api/ai-audit/prompts/nemotron

# Get Florence-2 queries
curl http://localhost:8000/api/ai-audit/prompts/florence2

# Get YOLO-World classes
curl http://localhost:8000/api/ai-audit/prompts/yolo_world
```

**Errors:**

| Code | Description                           |
| ---- | ------------------------------------- |
| 404  | No configuration found for model      |
| 422  | Invalid model name (validation error) |

---

## PUT /api/ai-audit/prompts/{model}

Update prompt configuration for a specific AI model.

Creates a new version of the configuration while preserving history. The new version automatically becomes the active configuration.

**Source:** [`update_prompt_for_model`](../../backend/api/routes/prompt_management.py:332)

**Parameters:**

| Name    | Type   | In   | Required | Description          |
| ------- | ------ | ---- | -------- | -------------------- |
| `model` | string | path | Yes      | Model name to update |

**Request Body:**

```json
{
  "config": {
    "system_prompt": "Updated system prompt text..."
  },
  "change_description": "Added more detailed risk criteria"
}
```

**Request Fields:**

| Field                | Type   | Required | Description                                       |
| -------------------- | ------ | -------- | ------------------------------------------------- |
| `config`             | object | Yes      | New configuration for the model (cannot be empty) |
| `change_description` | string | No       | Optional description of what changed              |

**Response:** `200 OK`

```json
{
  "model": "nemotron",
  "config": {
    "system_prompt": "Updated system prompt text..."
  },
  "version": 4,
  "created_at": "2025-12-23T14:00:00Z",
  "created_by": null,
  "change_description": "Added more detailed risk criteria"
}
```

**Example Requests:**

```bash
# Update Nemotron system prompt
curl -X PUT http://localhost:8000/api/ai-audit/prompts/nemotron \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "system_prompt": "You are an advanced security AI..."
    },
    "change_description": "Improved threat analysis instructions"
  }'

# Update YOLO-World detection classes
curl -X PUT http://localhost:8000/api/ai-audit/prompts/yolo_world \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "classes": ["knife", "gun", "package", "crowbar", "spray paint", "baseball bat"],
      "confidence_threshold": 0.40
    },
    "change_description": "Added baseball bat to detection classes"
  }'

# Update Florence-2 scene analysis queries
curl -X PUT http://localhost:8000/api/ai-audit/prompts/florence2 \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "queries": [
        "What is the person doing?",
        "What objects are they carrying?",
        "Describe the environment",
        "Is there anything unusual in this scene?",
        "What time of day does this appear to be?"
      ]
    }
  }'
```

**Errors:**

| Code | Description                        |
| ---- | ---------------------------------- |
| 422  | Invalid model name or empty config |

---

## GET /api/ai-audit/prompts/export

Export all prompt configurations as JSON.

Returns a complete export of all model configurations suitable for backup, sharing, or importing into another instance.

**Source:** [`export_prompts`](../../backend/api/routes/prompt_management.py:60)

**Response:** `200 OK`

```json
{
  "version": "1.0",
  "exported_at": "2025-12-23T12:00:00Z",
  "prompts": {
    "nemotron": {
      "system_prompt": "You are a security analysis AI...",
      "version": 3
    },
    "florence2": {
      "queries": ["What is the person doing?", "..."],
      "version": 1
    },
    "yolo_world": {
      "classes": ["knife", "gun", "package"],
      "confidence_threshold": 0.35,
      "version": 2
    },
    "xclip": {
      "action_classes": ["loitering", "running away"],
      "version": 1
    },
    "fashion_clip": {
      "clothing_categories": ["dark hoodie", "face mask"],
      "version": 1
    }
  }
}
```

**Example Request:**

```bash
# Export and save to file
curl http://localhost:8000/api/ai-audit/prompts/export > prompts-backup.json
```

---

## GET /api/ai-audit/prompts/history

Get version history for prompt configurations.

Returns a list of all prompt versions, optionally filtered by model.

**Source:** [`get_prompt_history`](../../backend/api/routes/prompt_management.py:83)

**Parameters:**

| Name     | Type    | In    | Required | Description                                    |
| -------- | ------- | ----- | -------- | ---------------------------------------------- |
| `model`  | string  | query | No       | Filter by specific model                       |
| `limit`  | integer | query | No       | Maximum results to return (1-100, default: 50) |
| `offset` | integer | query | No       | Offset for pagination (default: 0)             |

**Response:** `200 OK`

```json
{
  "versions": [
    {
      "id": 5,
      "model": "nemotron",
      "version": 3,
      "created_at": "2025-12-23T12:00:00Z",
      "created_by": "admin",
      "change_description": "Improved risk scoring criteria",
      "is_active": true
    },
    {
      "id": 4,
      "model": "yolo_world",
      "version": 2,
      "created_at": "2025-12-22T10:00:00Z",
      "created_by": null,
      "change_description": "Added package detection",
      "is_active": true
    },
    {
      "id": 3,
      "model": "nemotron",
      "version": 2,
      "created_at": "2025-12-21T08:00:00Z",
      "created_by": "admin",
      "change_description": null,
      "is_active": false
    }
  ],
  "total_count": 15
}
```

**Example Requests:**

```bash
# Get all version history
curl http://localhost:8000/api/ai-audit/prompts/history

# Get history for Nemotron only
curl "http://localhost:8000/api/ai-audit/prompts/history?model=nemotron"

# Paginate results
curl "http://localhost:8000/api/ai-audit/prompts/history?limit=10&offset=20"
```

---

## POST /api/ai-audit/prompts/history/{version_id}

Restore a specific prompt version.

Creates a new version with the configuration from the specified version, making it the active configuration. The original version remains unchanged.

**Source:** [`restore_prompt_version`](../../backend/api/routes/prompt_management.py:267)

**Parameters:**

| Name         | Type    | In   | Required | Description                  |
| ------------ | ------- | ---- | -------- | ---------------------------- |
| `version_id` | integer | path | Yes      | ID of the version to restore |

**Response:** `200 OK`

```json
{
  "restored_version": 2,
  "model": "nemotron",
  "new_version": 4,
  "message": "Successfully restored version 2 as new version 4"
}
```

**Example Request:**

```bash
curl -X POST http://localhost:8000/api/ai-audit/prompts/history/3
```

**Errors:**

| Code | Description       |
| ---- | ----------------- |
| 404  | Version not found |

---

## POST /api/ai-audit/prompts/test

Test a modified prompt configuration against an event or image.

Runs inference with the modified configuration and compares results with the original configuration. Currently only supports Nemotron testing.

**Source:** [`test_prompt`](../../backend/api/routes/prompt_management.py:121)

**Request Body:**

```json
{
  "model": "nemotron",
  "config": {
    "system_prompt": "Modified system prompt to test..."
  },
  "event_id": 42,
  "image_path": null
}
```

**Request Fields:**

| Field        | Type    | Required | Description                                        |
| ------------ | ------- | -------- | -------------------------------------------------- |
| `model`      | string  | Yes      | Model to test (currently only `nemotron`)          |
| `config`     | object  | Yes      | Configuration to test                              |
| `event_id`   | integer | No       | Event ID to test against (requires existing event) |
| `image_path` | string  | No       | Image path to test with                            |

**Note:** Either `event_id` or `image_path` must be provided.

**Response:** `200 OK`

```json
{
  "model": "nemotron",
  "before_score": 65,
  "after_score": 72,
  "before_response": null,
  "after_response": {
    "risk_score": 72,
    "risk_level": "ELEVATED",
    "reasoning": "..."
  },
  "improved": true,
  "test_duration_ms": 2450,
  "error": null
}
```

**Response Fields:**

| Field              | Type    | Description                                     |
| ------------------ | ------- | ----------------------------------------------- |
| `model`            | string  | Model that was tested                           |
| `before_score`     | integer | Risk score before changes (from original event) |
| `after_score`      | integer | Risk score with new configuration (nullable)    |
| `before_response`  | object  | Full response before changes (nullable)         |
| `after_response`   | object  | Full response with new configuration (nullable) |
| `improved`         | boolean | Whether the change is considered an improvement |
| `test_duration_ms` | integer | Test duration in milliseconds                   |
| `error`            | string  | Error message if test failed (nullable)         |

**Example Request:**

```bash
curl -X POST http://localhost:8000/api/ai-audit/prompts/test \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nemotron",
    "config": {
      "system_prompt": "You are an advanced security AI. Be more conservative with risk scores..."
    },
    "event_id": 42
  }'
```

---

## POST /api/ai-audit/prompts/import

Import prompt configurations from JSON.

Validates and imports configurations for each model, creating new versions for each imported configuration.

**Source:** [`import_prompts`](../../backend/api/routes/prompt_management.py:153)

**Request Body:**

```json
{
  "version": "1.0",
  "prompts": {
    "nemotron": {
      "system_prompt": "Imported system prompt..."
    },
    "yolo_world": {
      "classes": ["knife", "gun", "package"],
      "confidence_threshold": 0.35
    }
  }
}
```

**Request Fields:**

| Field     | Type   | Required | Description                            |
| --------- | ------ | -------- | -------------------------------------- |
| `version` | string | No       | Import format version (default: "1.0") |
| `prompts` | object | Yes      | Model configurations to import         |

**Response:** `200 OK`

```json
{
  "imported_models": ["nemotron", "yolo_world"],
  "skipped_models": ["unknown_model"],
  "new_versions": {
    "nemotron": 4,
    "yolo_world": 3
  },
  "message": "Imported 2 model configurations"
}
```

**Response Fields:**

| Field             | Type          | Description                                 |
| ----------------- | ------------- | ------------------------------------------- |
| `imported_models` | array[string] | Models successfully imported                |
| `skipped_models`  | array[string] | Models skipped (unknown or failed)          |
| `new_versions`    | object        | New version numbers for each imported model |
| `message`         | string        | Summary message                             |

**Example Request:**

```bash
# Import from previously exported file
curl -X POST http://localhost:8000/api/ai-audit/prompts/import \
  -H "Content-Type: application/json" \
  -d @prompts-backup.json
```

---

## POST /api/ai-audit/prompts/import/preview

Preview import changes without applying them.

Validates the import data and computes diffs against current configurations. Use this before actual import to review changes.

**Source:** [`preview_import_prompts`](../../backend/api/routes/prompt_management.py:214)

**Request Body:**

```json
{
  "version": "1.0",
  "prompts": {
    "nemotron": {
      "system_prompt": "New system prompt..."
    },
    "yolo_world": {
      "classes": ["knife", "gun", "package", "crowbar"],
      "confidence_threshold": 0.4
    }
  }
}
```

**Response:** `200 OK`

```json
{
  "version": "1.0",
  "valid": true,
  "validation_errors": [],
  "diffs": [
    {
      "model": "nemotron",
      "has_changes": true,
      "current_version": 3,
      "current_config": {
        "system_prompt": "Current system prompt...",
        "version": 3
      },
      "imported_config": {
        "system_prompt": "New system prompt..."
      },
      "changes": ["Changed: system_prompt"]
    },
    {
      "model": "yolo_world",
      "has_changes": true,
      "current_version": 2,
      "current_config": {
        "classes": ["knife", "gun", "package"],
        "confidence_threshold": 0.35
      },
      "imported_config": {
        "classes": ["knife", "gun", "package", "crowbar"],
        "confidence_threshold": 0.4
      },
      "changes": ["classes: Added ['crowbar']", "Changed: confidence_threshold"]
    }
  ],
  "total_changes": 2,
  "unknown_models": []
}
```

**Response Fields:**

| Field               | Type             | Description                              |
| ------------------- | ---------------- | ---------------------------------------- |
| `version`           | string           | Import format version                    |
| `valid`             | boolean          | Whether the import data is valid         |
| `validation_errors` | array[string]    | List of validation errors                |
| `diffs`             | array[DiffEntry] | Diff entries for each model              |
| `total_changes`     | integer          | Total number of models with changes      |
| `unknown_models`    | array[string]    | Models in import that are not recognized |

**Diff Entry Fields:**

| Field             | Type    | Description                              |
| ----------------- | ------- | ---------------------------------------- |
| `model`           | string  | Model name                               |
| `has_changes`     | boolean | Whether there are changes for this model |
| `current_version` | integer | Current version number (nullable if new) |
| `current_config`  | object  | Current configuration (nullable if new)  |
| `imported_config` | object  | Configuration from import                |
| `changes`         | array   | Human-readable list of changes           |

**Example Request:**

```bash
curl -X POST http://localhost:8000/api/ai-audit/prompts/import/preview \
  -H "Content-Type: application/json" \
  -d @prompts-to-import.json
```

---

## Model Configuration Schemas

### Nemotron Configuration

The Nemotron model uses a system prompt for risk analysis.

```json
{
  "system_prompt": "You are a security analysis AI. Analyze the detection context and provide:\n1. Risk score (0-100)\n2. Risk level (LOW, MODERATE, ELEVATED, HIGH, CRITICAL)\n3. Detailed reasoning\n4. Recommended actions"
}
```

| Field           | Type   | Description                             |
| --------------- | ------ | --------------------------------------- |
| `system_prompt` | string | Full system prompt template for the LLM |

### Florence-2 Configuration

Florence-2 uses natural language queries for scene analysis.

```json
{
  "queries": [
    "What is the person doing?",
    "What objects are they carrying?",
    "Describe the environment",
    "Is there anything unusual in this scene?"
  ]
}
```

| Field     | Type          | Description                        |
| --------- | ------------- | ---------------------------------- |
| `queries` | array[string] | List of queries for scene analysis |

### YOLO-World Configuration

YOLO-World uses custom object classes for detection.

```json
{
  "classes": [
    "knife",
    "gun",
    "package",
    "crowbar",
    "spray paint",
    "Amazon box",
    "FedEx package",
    "suspicious bag"
  ],
  "confidence_threshold": 0.35
}
```

| Field                  | Type          | Description                            |
| ---------------------- | ------------- | -------------------------------------- |
| `classes`              | array[string] | Custom object classes to detect        |
| `confidence_threshold` | float         | Minimum confidence threshold (0.0-1.0) |

### X-CLIP Configuration

X-CLIP uses action classes for activity recognition.

```json
{
  "action_classes": [
    "loitering",
    "running away",
    "fighting",
    "breaking in",
    "climbing fence",
    "hiding",
    "normal walking"
  ]
}
```

| Field            | Type          | Description                 |
| ---------------- | ------------- | --------------------------- |
| `action_classes` | array[string] | Action classes to recognize |

### Fashion-CLIP Configuration

Fashion-CLIP classifies clothing categories.

```json
{
  "clothing_categories": [
    "dark hoodie",
    "face mask",
    "gloves",
    "all black",
    "delivery uniform",
    "high-vis vest",
    "business attire"
  ]
}
```

| Field                 | Type          | Description                     |
| --------------------- | ------------- | ------------------------------- |
| `clothing_categories` | array[string] | Clothing categories to classify |

---

## Default Configurations

If no custom version exists in the database, the API returns these defaults:

### Nemotron Default

```json
{
  "system_prompt": "[Full MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT]",
  "version": 1
}
```

### Florence-2 Default

```json
{
  "queries": [
    "What is the person doing?",
    "What objects are they carrying?",
    "Describe the environment",
    "Is there anything unusual in this scene?"
  ]
}
```

### YOLO-World Default

```json
{
  "classes": [
    "knife",
    "gun",
    "package",
    "crowbar",
    "spray paint",
    "Amazon box",
    "FedEx package",
    "suspicious bag"
  ],
  "confidence_threshold": 0.35
}
```

### X-CLIP Default

```json
{
  "action_classes": [
    "loitering",
    "running away",
    "fighting",
    "breaking in",
    "climbing fence",
    "hiding",
    "normal walking"
  ]
}
```

### Fashion-CLIP Default

```json
{
  "clothing_categories": [
    "dark hoodie",
    "face mask",
    "gloves",
    "all black",
    "delivery uniform",
    "high-vis vest",
    "business attire"
  ]
}
```

---

## Data Models

### ModelPromptConfig

Configuration for a specific AI model.

**Source:** [`ModelPromptConfig`](../../backend/api/schemas/prompt_management.py:69)

| Field                | Type     | Description                              |
| -------------------- | -------- | ---------------------------------------- |
| `model`              | string   | Model identifier (enum value)            |
| `config`             | object   | Model-specific configuration             |
| `version`            | integer  | Version number of this configuration     |
| `created_at`         | datetime | When this version was created (nullable) |
| `created_by`         | string   | Who created this version (nullable)      |
| `change_description` | string   | Description of changes (nullable)        |

### PromptVersionInfo

Information about a single prompt version.

**Source:** [`PromptVersionInfo`](../../backend/api/schemas/prompt_management.py:127)

| Field                | Type     | Description                         |
| -------------------- | -------- | ----------------------------------- |
| `id`                 | integer  | Version record ID                   |
| `model`              | string   | Model identifier                    |
| `version`            | integer  | Version number                      |
| `created_at`         | datetime | When this version was created       |
| `created_by`         | string   | Who created this version (nullable) |
| `change_description` | string   | Description of changes (nullable)   |
| `is_active`          | boolean  | Whether this is the active version  |

### PromptTestResult

Result of a prompt test.

**Source:** [`PromptTestResult`](../../backend/api/schemas/prompt_management.py:114)

| Field              | Type    | Description                                    |
| ------------------ | ------- | ---------------------------------------------- |
| `model`            | string  | Model that was tested                          |
| `before_score`     | integer | Risk score before changes (nullable)           |
| `after_score`      | integer | Risk score after changes (nullable)            |
| `before_response`  | object  | Full response before changes (nullable)        |
| `after_response`   | object  | Full response after changes (nullable)         |
| `improved`         | boolean | Whether the change improved results (nullable) |
| `test_duration_ms` | integer | Test duration in milliseconds                  |
| `error`            | string  | Error message if test failed (nullable)        |

---

## Prompt Template Variables

When configuring the Nemotron system prompt, the following context is available at runtime:

| Variable          | Description                                             |
| ----------------- | ------------------------------------------------------- |
| Detection data    | RT-DETR object detections with labels, confidence, bbox |
| Scene description | Florence-2 scene analysis results                       |
| Object details    | YOLO-World custom object detections                     |
| Action analysis   | X-CLIP action recognition results                       |
| Clothing analysis | Fashion-CLIP clothing classification                    |
| Zone information  | Which zones were triggered                              |
| Baseline data     | Comparison with normal scene baseline                   |
| Weather           | Current weather conditions                              |
| Time context      | Time of day, day of week                                |
| Camera metadata   | Camera name, location, last activity                    |
| Cross-camera      | Related detections from other cameras                   |

The system prompt should instruct the LLM how to interpret and synthesize this context into a coherent risk assessment.

---

## Best Practices

### Prompt Engineering

1. **Be specific** - Clearly define what constitutes different risk levels
2. **Use examples** - Include sample scenarios in the prompt
3. **Define output format** - Specify exact JSON structure expected
4. **Handle edge cases** - Include instructions for ambiguous situations

### Version Management

1. **Always use change descriptions** - Document why changes were made
2. **Test before deploying** - Use the `/test` endpoint to validate changes
3. **Preview imports** - Always preview before importing configurations
4. **Keep backups** - Regularly export configurations

### Testing Workflow

```bash
# 1. Export current configuration as backup
curl http://localhost:8000/api/ai-audit/prompts/export > backup.json

# 2. Test new configuration against an event
curl -X POST http://localhost:8000/api/ai-audit/prompts/test \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nemotron",
    "config": {"system_prompt": "..."},
    "event_id": 123
  }'

# 3. If satisfied, update the configuration
curl -X PUT http://localhost:8000/api/ai-audit/prompts/nemotron \
  -H "Content-Type: application/json" \
  -d '{
    "config": {"system_prompt": "..."},
    "change_description": "Tested and verified improvement"
  }'
```

---

## Related Documentation

- [AI Audit API](ai-audit.md) - Event auditing and quality metrics
- [Model Zoo API](model-zoo.md) - AI model status and health
- [Enrichment API](enrichment.md) - Vision model results
- [Events API](events.md) - Event data that prompts analyze
