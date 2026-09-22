# Settings Panel Components

> Components for system configuration and settings management.

---

## Overview

Settings components provide configuration interfaces for cameras, AI models, notifications, storage, and system behavior. They are organized into tabbed sections within the main settings page.

**Location:** `frontend/src/components/settings/`

---

## Page Components

### SettingsPage

Main settings page with tab navigation. Each tab is a route (`/settings/<tab>`); the active tab is derived from `location.pathname`, so tab state lives in the URL.

**Location:** `frontend/src/components/settings/SettingsPage.tsx`

**Tab Structure** (`settingsTabsConfig.ts`):

| Tab id          | Route                     |
| --------------- | ------------------------- |
| `cameras`       | `/settings/cameras`       |
| `rules`         | `/settings/rules`         |
| `processing`    | `/settings/processing`    |
| `notifications` | `/settings/notifications` |
| `ambient`       | `/settings/ambient`       |
| `calibration`   | `/settings/calibration`   |
| `access`        | `/settings/access`        |
| `prompts`       | `/settings/prompts`       |
| `storage`       | `/settings/storage`       |
| `ai-models`     | `/settings/ai-models`     |
| `admin`         | `/settings/admin`         |

**Features:**

- Horizontally scrolling tab nav with keyboard-accessible chevron buttons when tabs overflow (`ScrollableNavList`)
- Tab panels are lazy-loaded route components (see `App.tsx` lazy imports)

---

## Camera Settings

### CamerasSettings

Camera configuration management.

**Location:** `frontend/src/components/settings/CamerasSettings.tsx`

**Features:**

- Camera list with add/edit forms
- ONVIF device discovery (`ONVIFDiscoveryPanel`)
- Zone assignment via `ZoneEditor` (from `components/zones`)

---

### CalibrationPanel

Camera calibration interface (calibration tab content). Fetches its own data; takes no camera prop.

**Location:** `frontend/src/components/settings/CalibrationPanel.tsx`

**Props:**

| Prop      | Type     | Default | Description            |
| --------- | -------- | ------- | ---------------------- |
| className | `string` | -       | Additional CSS classes |

---

### AreaCameraLinking

Link cameras to property areas. Fetches properties/cameras itself.

**Location:** `frontend/src/components/settings/AreaCameraLinking.tsx`

**Props:**

| Prop        | Type     | Default | Description                                                 |
| ----------- | -------- | ------- | ----------------------------------------------------------- |
| householdId | `number` | -       | Optional household filter (defaults to 1, single household) |
| className   | `string` | -       | Additional CSS classes                                      |

---

## AI Model Settings

### AIModelsSettings

AI model configuration dashboard.

**Location:** `frontend/src/components/settings/AIModelsSettings.tsx`

---

### AIModelsTab

AI models tab content.

**Location:** `frontend/src/components/settings/AIModelsTab.tsx`

**Props:**

| Prop      | Type     | Default | Description                   |
| --------- | -------- | ------- | ----------------------------- |
| className | `string` | -       | Optional custom styling class |

---

### ModelManagementPanel

AI model management panel; model data comes from `useModelZooStatusQuery`.

**Location:** `frontend/src/components/settings/ModelManagementPanel.tsx`

**Features:**

- VRAM usage overview with progress bar (`VRAMUsageCard`)
- Model status summary (loaded / unloaded / disabled counts)
- Model cards grouped by category
- Per-model VRAM usage and load statistics

---

### DetectionThresholdsPanel

Detection confidence thresholds. Self-contained; takes no data props.

**Location:** `frontend/src/components/settings/DetectionThresholdsPanel.tsx`

**Props:**

| Prop      | Type     | Default | Description            |
| --------- | -------- | ------- | ---------------------- |
| className | `string` | -       | Additional CSS classes |

---

## GPU Configuration

### GpuAssignmentTable

GPU assignment configuration table.

**Location:** `frontend/src/components/settings/GpuAssignmentTable.tsx`

**Props:**

| Prop                   | Type                                                      | Default | Description                       |
| ---------------------- | --------------------------------------------------------- | ------- | --------------------------------- |
| assignments            | `GpuAssignment[]`                                         | -       | Current GPU assignments           |
| gpus                   | `GpuDevice[]`                                             | -       | Available GPU devices             |
| serviceStatuses        | `ServiceHealthStatus[]`                                   | -       | Service health status             |
| strategy               | `string`                                                  | -       | Current assignment strategy       |
| onAssignmentChange     | `(service: string, gpuIndex: number \| null) => void`     | -       | Change a service's GPU assignment |
| onVramOverrideChange   | `(service: string, vramOverride: number \| null) => void` | -       | Change VRAM budget override       |
| onExclusiveGpuChange   | `(service: string, exclusive: boolean) => void`           | -       | Exclusive GPU flag (NEM-4944)     |
| onPriorityWeightChange | `(service: string, priority: number) => void`             | -       | Priority weight (NEM-4944)        |
| isLoading              | `boolean`                                                 | -       | Loading state                     |
| hasPendingChanges      | `boolean`                                                 | -       | Unsaved changes exist             |
| className              | `string`                                                  | -       | Additional CSS classes            |

---

### GpuDeviceCard

Individual GPU device card.

**Location:** `frontend/src/components/settings/GpuDeviceCard.tsx`

**Props:**

| Prop             | Type              | Default | Description                   |
| ---------------- | ----------------- | ------- | ----------------------------- |
| gpu              | `GpuDevice`       | -       | GPU device information        |
| assignedServices | `GpuAssignment[]` | -       | Services assigned to this GPU |
| isLoading        | `boolean`         | -       | Loading state                 |
| className        | `string`          | -       | Additional CSS classes        |

---

### GpuStrategySelector

GPU assignment strategy selector with server-side preview.

**Location:** `frontend/src/components/settings/GpuStrategySelector.tsx`

**Props:**

| Prop                | Type                                                     | Default | Description                  |
| ------------------- | -------------------------------------------------------- | ------- | ---------------------------- |
| selectedStrategy    | `string`                                                 | -       | Currently selected strategy  |
| availableStrategies | `string[]`                                               | -       | Strategies from the backend  |
| onStrategyChange    | `(strategy: string) => void`                             | -       | Selection handler            |
| onPreview           | `(strategy: string) => Promise<StrategyPreviewResponse>` | -       | Preview strategy assignments |
| isPreviewLoading    | `boolean`                                                | -       | Preview in progress          |
| previewError        | `string \| null`                                         | -       | Preview error message        |
| previewData         | `StrategyPreviewResponse \| null`                        | -       | Last preview result          |
| disabled            | `boolean`                                                | -       | Disable the selector         |
| className           | `string`                                                 | -       | Additional CSS classes       |

**Strategies** (ids in `GpuStrategySelector.tsx`; the list is served by the backend via `availableStrategies`):

- `manual` - User assigns GPUs to services
- `vram_based` - Distribute by VRAM availability
- `latency_optimized` - Minimize pipeline latency
- `isolation_first` - Isolate services across GPUs
- `balanced` - Balanced distribution

---

### VRAMUsageCard

VRAM usage visualization.

**Location:** `frontend/src/components/settings/VRAMUsageCard.tsx`

**Props:**

| Prop         | Type      | Default | Description              |
| ------------ | --------- | ------- | ------------------------ |
| budgetMb     | `number`  | -       | Total VRAM budget in MB  |
| usedMb       | `number`  | -       | Used VRAM in MB          |
| availableMb  | `number`  | -       | Available VRAM in MB     |
| usagePercent | `number`  | -       | Usage percentage (0-100) |
| isLoading    | `boolean` | -       | Loading state            |
| compact      | `boolean` | -       | Compact display mode     |
| className    | `string`  | -       | Additional CSS classes   |

---

### GpuApplyButton

Save/apply GPU configuration.

**Location:** `frontend/src/components/settings/GpuApplyButton.tsx`

**Props:**

| Prop            | Type                            | Default | Description                                 |
| --------------- | ------------------------------- | ------- | ------------------------------------------- |
| hasChanges      | `boolean`                       | -       | Unsaved changes exist                       |
| onSave          | `() => Promise<void>`           | -       | Save without restarting services            |
| onApply         | `() => Promise<GpuApplyResult>` | -       | Save and restart services                   |
| isSaving        | `boolean`                       | -       | Save in progress                            |
| isApplying      | `boolean`                       | -       | Apply in progress                           |
| serviceStatuses | `ServiceStatus[]`               | -       | Service statuses for restart progress       |
| lastApplyResult | `GpuApplyResult \| null`        | -       | Last apply result (success/failure display) |
| error           | `string \| null`                | -       | Error message                               |
| disabled        | `boolean`                       | -       | Disable buttons                             |
| className       | `string`                        | -       | Additional CSS classes                      |

---

## Notification Settings

### NotificationSettings

Notification configuration panel.

**Location:** `frontend/src/components/settings/NotificationSettings.tsx`

**Features:**

- Email (SMTP) configuration status with test action
- Webhook configuration status with test action
- Desktop / push / audio notification controls (permission-aware)
- Quiet hours scheduler (`useQuietHoursPeriods` and its mutations)
- Risk-level filters with camera-threshold conflict detection

---

## Alert Rules

### AlertRulesSettings

Alert rule management.

**Location:** `frontend/src/components/settings/AlertRulesSettings.tsx`

**Features:**

- Create/edit alert rules (validation, including schedule start/end times)
- Toggle rules enabled/disabled

---

## Household Settings

### HouseholdSettings

Household member and vehicle management.

**Location:** `frontend/src/components/settings/HouseholdSettings.tsx`

**Features:**

- Household members CRUD (`HouseholdMemberCreate` / `HouseholdMemberUpdate`)
- Member roles and trust levels (`full` = never trigger alerts, `partial` = reduced alert severity)
- Vehicle management

---

### AccessControlSettings

Combined access control section: `HouseholdSettings` + `ZoneAccessSettings` in tabs (NEM-3608).

**Location:** `frontend/src/components/settings/AccessControlSettings.tsx`

---

### ZoneAccessSettings

Zone-based access control configuration.

**Location:** `frontend/src/components/settings/ZoneAccessSettings.tsx`

**Features:**

- Zone selector, owner assignment
- Allowed members / vehicles multi-select
- Access schedule editor (embeds `AccessScheduleEditor`)

---

### AccessScheduleEditor

Time-based access schedule editor.

**Location:** `frontend/src/components/settings/AccessScheduleEditor.tsx`

**Props:**

| Prop      | Type                                    | Default | Description                     |
| --------- | --------------------------------------- | ------- | ------------------------------- |
| schedules | `AccessSchedule[]`                      | -       | Current access schedules        |
| onChange  | `(schedules: AccessSchedule[]) => void` | -       | Change handler                  |
| members   | `HouseholdMember[]`                     | -       | Household members for selection |
| disabled  | `boolean`                               | -       | Disable the editor              |
| className | `string`                                | -       | Additional CSS classes          |

---

## Storage Settings

### StorageDashboard

Storage usage and cleanup dashboard (real-time disk usage metrics, storage breakdown, cleanup dry-run preview via `useStorageStatsQuery` / `useCleanupPreviewMutation`).

**Location:** `frontend/src/components/settings/StorageDashboard.tsx`

---

### CleanupPreviewPanel

Preview cleanup operations. Self-contained; takes no configuration props.

**Location:** `frontend/src/components/settings/CleanupPreviewPanel.tsx`

**Props:**

| Prop      | Type     | Default | Description            |
| --------- | -------- | ------- | ---------------------- |
| className | `string` | -       | Additional CSS classes |

---

### OrphanCleanupPanel

Orphaned file cleanup with configurable parameters (NEM-3568; backend: `backend/api/routes/admin.py`).

**Location:** `frontend/src/components/settings/OrphanCleanupPanel.tsx`

**Features:**

- `min_age_hours` slider (1-720 h) - minimum file age before deletion
- `max_delete_gb` slider (0.1-100 GB) - maximum bytes deleted per run
- Dry-run preview and confirmed cleanup with results display (files scanned, orphans found, deleted, bytes freed)

---

## Prompt Management

### PromptManagementPanel

AI prompt configuration panel.

**Location:** `frontend/src/components/settings/PromptManagementPanel.tsx`

---

### PromptManagementPage

Full prompt management page.

**Location:** `frontend/src/components/settings/prompts/PromptManagementPage.tsx`

The `prompts/` directory also contains `EventSelector`, `ImportPreviewModal`, and `TestResultsComparison` used by the page.

---

### PromptConfigEditor

Model configuration editor (modal).

**Location:** `frontend/src/components/settings/prompts/PromptConfigEditor.tsx`

**Props:**

| Prop          | Type                                                                   | Default | Description                  |
| ------------- | ---------------------------------------------------------------------- | ------- | ---------------------------- |
| isOpen        | `boolean`                                                              | -       | Modal visibility             |
| onClose       | `() => void`                                                           | -       | Close handler                |
| model         | `AIModelEnum`                                                          | -       | The AI model being edited    |
| initialConfig | `Record<string, unknown>`                                              | -       | Initial configuration values |
| onSave        | `(config: Record<string, unknown>, changeDescription: string) => void` | -       | Save handler                 |
| isSaving      | `boolean`                                                              | -       | Save in progress             |

---

### PromptTestModal

Configuration testing modal.

**Location:** `frontend/src/components/settings/prompts/PromptTestModal.tsx`

**Props:**

| Prop           | Type                      | Default | Description                    |
| -------------- | ------------------------- | ------- | ------------------------------ |
| isOpen         | `boolean`                 | -       | Modal visibility               |
| onClose        | `() => void`              | -       | Close handler                  |
| model          | `AIModelEnum`             | -       | The AI model being tested      |
| modifiedConfig | `Record<string, unknown>` | -       | Modified configuration to test |

---

### Model Configuration Forms

Specialized configuration forms for each model type, in `frontend/src/components/settings/prompts/model-forms/`:

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

| Prop             | Type              | Default | Description                                 |
| ---------------- | ----------------- | ------- | ------------------------------------------- |
| diff             | `PromptDiffEntry` | -       | The diff entry to display                   |
| collapsed        | `boolean`         | -       | Collapsed view (model name and status only) |
| onToggleCollapse | `() => void`      | -       | Expand/collapse handler                     |

---

### ImportExportButtons

Configuration import/export.

**Location:** `frontend/src/components/settings/prompts/ImportExportButtons.tsx`

---

## Advanced Settings

### ProcessingSettings

Pipeline processing configuration: batch window, idle timeout, retention period, and confidence threshold, with batch presets (`BatchPresetSelector`, `BatchSettingsTooltips`, `BatchStatusMonitor`) and embedded queue/rate-limit settings (`QueueSettings`, NEM-3670).

**Location:** `frontend/src/components/settings/ProcessingSettings.tsx`

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

- Badge with total failed-job count; per-queue counts (detection, analysis)
- Failed-job inspection
- Retry and permanent-delete actions (delete requires confirmation)

---

### FeatureTogglesPanel

Feature flag management.

**Location:** `frontend/src/components/settings/FeatureTogglesPanel.tsx`

---

### RiskSensitivitySettings

Risk scoring sensitivity: view/adjust calibration thresholds (Low, Medium, High), adjust learning-rate decay factor, view feedback statistics, reset to defaults (NEM-2320).

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

Property and area configuration: nested area management per property, camera count per area, navigation to `AreaCameraLinking` for camera assignment.

**Location:** `frontend/src/components/settings/PropertyManagement.tsx`

---

### AdminSettings

Administrative settings.

**Location:** `frontend/src/components/settings/AdminSettings.tsx`

---

## Testing

```bash
cd frontend && npm test -- src/components/settings
```

Test coverage includes:

- Form validation
- Settings persistence
- Error handling
- Reset functionality
- GPU configuration logic
- Prompt template validation
