# Settings Panel Components

> Components for system configuration and settings management.

---

## Overview

Settings components provide configuration interfaces for cameras, AI models, notifications, storage, and system behavior. They are organized into tabbed sections within the main settings page.

**Location:** `frontend/src/components/settings/`

---

## Page Components

### SettingsPage

Main settings page with tab navigation.

**Location:** `frontend/src/components/settings/SettingsPage.tsx`

**Tab Structure:**

- General (household, property)
- Cameras
- AI Models
- Notifications
- Storage
- Advanced

**Features:**

- Persistent tab state in URL
- Unsaved changes warning
- Settings validation
- Reset to defaults

---

## Camera Settings

### CamerasSettings

Camera configuration management.

**Location:** `frontend/src/components/settings/CamerasSettings.tsx`

**Features:**

- Camera list with status
- Add/edit/remove cameras
- Stream URL configuration
- Snapshot intervals
- Zone assignment

---

### CalibrationPanel

Camera calibration interface.

**Location:** `frontend/src/components/settings/CalibrationPanel.tsx`

**Props:**

| Prop       | Type         | Default | Description          |
| ---------- | ------------ | ------- | -------------------- |
| cameraId   | `string`     | -       | Camera to calibrate  |
| onComplete | `() => void` | -       | Calibration complete |

---

### AreaCameraLinking

Link cameras to property areas.

**Location:** `frontend/src/components/settings/AreaCameraLinking.tsx`

**Props:**

| Prop    | Type                         | Default | Description       |
| ------- | ---------------------------- | ------- | ----------------- |
| areas   | `Area[]`                     | -       | Property areas    |
| cameras | `Camera[]`                   | -       | Available cameras |
| onLink  | `(areaId, cameraId) => void` | -       | Link handler      |

---

## AI Model Settings

### AIModelsSettings

AI model configuration dashboard.

**Location:** `frontend/src/components/settings/AIModelsSettings.tsx`

**Features:**

- Model status overview
- Enable/disable models
- Model-specific configuration
- VRAM usage monitoring

---

### AIModelsTab

AI models tab content.

**Location:** `frontend/src/components/settings/AIModelsTab.tsx`

---

### ModelManagementPanel

Model download and update management.

**Location:** `frontend/src/components/settings/ModelManagementPanel.tsx`

**Features:**

- Available models list
- Download progress
- Version management
- Model deletion

---

### DetectionThresholdsPanel

Detection confidence thresholds.

**Location:** `frontend/src/components/settings/DetectionThresholdsPanel.tsx`

**Props:**

| Prop       | Type               | Default | Description        |
| ---------- | ------------------ | ------- | ------------------ |
| thresholds | `ThresholdConfig`  | -       | Current thresholds |
| onSave     | `(config) => void` | -       | Save handler       |

---

## GPU Configuration

### GpuAssignmentTable

GPU assignment configuration table.

**Location:** `frontend/src/components/settings/GpuAssignmentTable.tsx`

**Props:**

| Prop        | Type                       | Default | Description         |
| ----------- | -------------------------- | ------- | ------------------- |
| gpus        | `GpuDevice[]`              | -       | Available GPUs      |
| assignments | `Assignment[]`             | -       | Current assignments |
| onAssign    | `(modelId, gpuId) => void` | -       | Assignment handler  |

---

### GpuDeviceCard

Individual GPU device card.

**Location:** `frontend/src/components/settings/GpuDeviceCard.tsx`

**Props:**

| Prop        | Type        | Default | Description         |
| ----------- | ----------- | ------- | ------------------- |
| gpu         | `GpuDevice` | -       | GPU device info     |
| utilization | `number`    | -       | Current utilization |

---

### GpuStrategySelector

GPU assignment strategy selector.

**Location:** `frontend/src/components/settings/GpuStrategySelector.tsx`

**Props:**

| Prop     | Type                 | Default | Description      |
| -------- | -------------------- | ------- | ---------------- |
| strategy | `Strategy`           | -       | Current strategy |
| onChange | `(strategy) => void` | -       | Change handler   |

**Strategies:**

- `manual` - Manual assignment
- `auto-balanced` - Distribute by VRAM
- `dedicated` - One model per GPU
- `shared` - All models on one GPU

---

### VRAMUsageCard

VRAM usage visualization.

**Location:** `frontend/src/components/settings/VRAMUsageCard.tsx`

**Props:**

| Prop   | Type           | Default | Description           |
| ------ | -------------- | ------- | --------------------- |
| gpuId  | `string`       | -       | GPU device ID         |
| used   | `number`       | -       | Used VRAM (MB)        |
| total  | `number`       | -       | Total VRAM (MB)       |
| models | `ModelUsage[]` | -       | Models using this GPU |

---

### GpuApplyButton

Apply GPU configuration button.

**Location:** `frontend/src/components/settings/GpuApplyButton.tsx`

**Props:**

| Prop       | Type         | Default | Description             |
| ---------- | ------------ | ------- | ----------------------- |
| hasChanges | `boolean`    | -       | Unsaved changes exist   |
| onApply    | `() => void` | -       | Apply handler           |
| isApplying | `boolean`    | -       | Application in progress |

---

## Notification Settings

### NotificationSettings

Notification configuration panel.

**Location:** `frontend/src/components/settings/NotificationSettings.tsx`

**Features:**

- Email configuration
- Webhook endpoints
- Push notifications
- Alert severity filters
- Quiet hours

---

## Alert Rules

### AlertRulesSettings

Alert rule management.

**Location:** `frontend/src/components/settings/AlertRulesSettings.tsx`

**Features:**

- Rule list with enable/disable
- Create/edit rules
- Trigger conditions
- Action configuration

---

## Household Settings

### HouseholdSettings

Household member management.

**Location:** `frontend/src/components/settings/HouseholdSettings.tsx`

**Features:**

- Member list
- Face enrollment
- Trust levels
- Access schedules

---

### AccessControlSettings

Access control configuration.

**Location:** `frontend/src/components/settings/AccessControlSettings.tsx`

---

### AccessScheduleEditor

Time-based access schedule editor.

**Location:** `frontend/src/components/settings/AccessScheduleEditor.tsx`

**Props:**

| Prop     | Type                 | Default | Description      |
| -------- | -------------------- | ------- | ---------------- |
| schedule | `Schedule`           | -       | Current schedule |
| onChange | `(schedule) => void` | -       | Change handler   |

---

### ZoneAccessSettings

Zone-based access settings.

**Location:** `frontend/src/components/settings/ZoneAccessSettings.tsx`

---

## Storage Settings

### StorageDashboard

Storage usage and cleanup dashboard.

**Location:** `frontend/src/components/settings/StorageDashboard.tsx`

**Features:**

- Storage usage by category
- Retention policies
- Manual cleanup
- Disk space warnings

---

### CleanupPreviewPanel

Preview cleanup operations.

**Location:** `frontend/src/components/settings/CleanupPreviewPanel.tsx`

**Props:**

| Prop       | Type         | Default | Description         |
| ---------- | ------------ | ------- | ------------------- |
| olderThan  | `number`     | -       | Days threshold      |
| categories | `string[]`   | -       | Categories to clean |
| onConfirm  | `() => void` | -       | Confirm cleanup     |

---

### OrphanCleanupPanel

Orphaned file cleanup.

**Location:** `frontend/src/components/settings/OrphanCleanupPanel.tsx`

---

## Prompt Management

### PromptManagementPanel

AI prompt configuration panel.

**Location:** `frontend/src/components/settings/PromptManagementPanel.tsx`

---

### PromptManagementPage

Full prompt management page.

**Location:** `frontend/src/components/settings/prompts/PromptManagementPage.tsx`

---

### PromptConfigEditor

Prompt template editor.

**Location:** `frontend/src/components/settings/prompts/PromptConfigEditor.tsx`

**Props:**

| Prop   | Type               | Default | Description          |
| ------ | ------------------ | ------- | -------------------- |
| prompt | `PromptConfig`     | -       | Prompt configuration |
| onSave | `(config) => void` | -       | Save handler         |
| onTest | `() => void`       | -       | Test handler         |

---

### PromptTestModal

Prompt testing modal.

**Location:** `frontend/src/components/settings/prompts/PromptTestModal.tsx`

**Props:**

| Prop     | Type         | Default | Description      |
| -------- | ------------ | ------- | ---------------- |
| promptId | `string`     | -       | Prompt to test   |
| isOpen   | `boolean`    | -       | Modal visibility |
| onClose  | `() => void` | -       | Close handler    |

---

### Model Configuration Forms

Specialized configuration forms for each model type:

- `NemotronConfigForm.tsx` - Nemotron model settings
- `Florence2ConfigForm.tsx` - Florence-2 model settings
- `YoloWorldConfigForm.tsx` - YOLO-World settings
- `XClipConfigForm.tsx` - X-CLIP settings
- `FashionClipConfigForm.tsx` - FashionCLIP settings

---

### ConfigDiffView

Configuration diff viewer.

**Location:** `frontend/src/components/settings/prompts/ConfigDiffView.tsx`

**Props:**

| Prop   | Type     | Default | Description            |
| ------ | -------- | ------- | ---------------------- |
| before | `object` | -       | Previous configuration |
| after  | `object` | -       | New configuration      |

---

### ImportExportButtons

Configuration import/export.

**Location:** `frontend/src/components/settings/prompts/ImportExportButtons.tsx`

---

## Advanced Settings

### ProcessingSettings

Pipeline processing configuration.

**Location:** `frontend/src/components/settings/ProcessingSettings.tsx`

**Features:**

- Batch window timing
- Frame sampling rates
- Queue limits
- Worker counts

---

### QueueSettings

Queue configuration panel.

**Location:** `frontend/src/components/settings/QueueSettings.tsx`

---

### RateLimitingSettings

API rate limiting configuration.

**Location:** `frontend/src/components/settings/RateLimitingSettings.tsx`

---

### DlqMonitor

Dead letter queue monitoring.

**Location:** `frontend/src/components/settings/DlqMonitor.tsx`

**Features:**

- Failed message count
- Error inspection
- Retry/discard actions
- Error patterns

---

### FeatureTogglesPanel

Feature flag management.

**Location:** `frontend/src/components/settings/FeatureTogglesPanel.tsx`

---

### RiskSensitivitySettings

Risk scoring sensitivity.

**Location:** `frontend/src/components/settings/RiskSensitivitySettings.tsx`

---

### SeverityThresholds

Alert severity threshold configuration.

**Location:** `frontend/src/components/settings/SeverityThresholds.tsx`

---

### AmbientStatusSettings

Ambient background status settings.

**Location:** `frontend/src/components/settings/AmbientStatusSettings.tsx`

---

### PropertyManagement

Property configuration.

**Location:** `frontend/src/components/settings/PropertyManagement.tsx`

---

### AdminSettings

Administrative settings.

**Location:** `frontend/src/components/settings/AdminSettings.tsx`

---

## Testing

```bash
cd frontend && npm test -- --testPathPattern=settings
```

Test coverage includes:

- Form validation
- Settings persistence
- Error handling
- Reset functionality
- GPU configuration logic
- Prompt template validation
