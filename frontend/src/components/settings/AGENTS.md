# Settings Components Directory

## Purpose

Components for the Settings page (`/settings`) - camera management, alert
rules, processing parameters, notifications, calibration, access control,
prompts, storage, AI model management, and admin tools. The page is a tabbed
shell (`SettingsPage.tsx`) whose tabs are nested routes under `/settings/*`.

There is no settings barrel and no shared settings store: each panel owns its
own data fetching (typed client in `../../services/api`, or a TanStack Query
hook in `../../hooks/`). See `README.md` in this directory for the AI-models
tab specifics.

## Files

Components are imported by path (mostly lazy `import()` in `App.tsx`); this
directory has **no `index.ts` barrel**. Most components have a co-located
`*.test.tsx`; the exceptions are called out below. `__tests__/` holds extra
suites (`CamerasSettings.motionSensitivity.test.tsx`,
`FeatureTogglesPanel.test.tsx`).

| File (plus co-located test unless noted) | Purpose                                                            |
| ---------------------------------------- | ------------------------------------------------------------------ |
| `AGENTS.md`, `README.md`                 | Docs for this directory                                            |
| `SettingsPage.tsx`                       | Tabbed shell with nested `/settings/*` routes                      |
| `settingsTabsConfig.ts`                  | Tab id/name/path/icon/description list                             |
| `CamerasSettings.tsx`                    | Camera CRUD (FTP + RTSP), ONVIF discovery, RTSP test               |
| `ONVIFDiscoveryPanel.tsx`                | Modal for network camera discovery via ONVIF                       |
| `ConnectionStatusCard.tsx`               | RTSP connection-test result card                                   |
| `AreaCameraLinking.tsx`                  | Link cameras to areas/zones                                        |
| `AlertRulesSettings.tsx`                 | Alert-rule CRUD with channels, schedule, test                      |
| `ProcessingSettings.tsx`                 | Batch/retention/confidence config; composes many panels            |
| `BatchPresetSelector.tsx`                | Preset selector for batch settings                                 |
| `BatchSettingsTooltips.tsx`              | Validation feedback/tooltips for batch settings                    |
| `BatchStatusMonitor.tsx`                 | Live batch aggregator status                                       |
| `CleanupPreviewPanel.tsx`                | Dry-run preview of retention cleanup                               |
| `OrphanCleanupPanel.tsx`                 | Orphan-file cleanup with configurable parameters                   |
| `DetectionThresholdsPanel.tsx`           | Per-detector confidence thresholds                                 |
| `DetectorSettings.tsx`                   | Detector configuration                                             |
| `DlqMonitor.tsx`                         | Dead-letter queue monitor (+ `.msw.test.tsx`)                      |
| `QueueSettings.tsx`                      | Queue config panel (no co-located test)                            |
| `RateLimitingSettings.tsx`               | Rate-limit config panel (no co-located test)                       |
| `NotificationSettings.tsx`               | Email/webhook notification status + tests                          |
| `MqttSettings.tsx`                       | MQTT configuration (no co-located test)                            |
| `AmbientStatusSettings.tsx`              | Ambient status display settings                                    |
| `CalibrationPanel.tsx`                   | AI calibration and feedback statistics                             |
| `AccessControlSettings.tsx`              | Access control config UI (no co-located test)                      |
| `AccessScheduleEditor.tsx`               | Zone access schedule editor                                        |
| `ZoneAccessSettings.tsx`                 | Zone-based access control                                          |
| `PropertyManagement.tsx`                 | Properties and areas management                                    |
| `HouseholdSettings.tsx`                  | Household organization management                                  |
| `PromptManagementPanel.tsx`              | AI prompt management (also `prompts/` subdir)                      |
| `prompts/`                               | Prompt editor, diff view, import/export components                 |
| `StorageDashboard.tsx`                   | Disk usage + DB record counts (+ `.msw.test.tsx`)                  |
| `AIModelsTab.tsx`                        | AI MODELS tab: AIModelsSettings + Model Zoo (+ no co-located test) |
| `AIModelsSettings.tsx`                   | Detection + Nemotron status cards                                  |
| `ModelManagementPanel.tsx`               | Model management panel (VRAM usage, statuses)                      |
| `ModelZooPanel.tsx`                      | Model Zoo admin table with load/unload/reload                      |
| `ModelCard.tsx`                          | One Model Zoo model card                                           |
| `VRAMUsageCard.tsx`                      | GPU VRAM usage visualization                                       |
| `FeatureTogglesPanel.tsx`                | AI processing feature toggles (test lives in `__tests__/`)         |
| `GpuAssignmentTable.tsx`                 | GPU assignment table per AI service                                |
| `GpuDeviceCard.tsx`                      | Single GPU device card                                             |
| `GpuStrategySelector.tsx`                | GPU assignment strategy radio group                                |
| `GpuBatchActions.tsx`                    | Batch GPU assignment actions                                       |
| `GpuApplyButton.tsx`                     | Save/apply GPU configuration                                       |
| `GpuVersionHistory.tsx`                  | Config version history + diff view (no co-located test)            |
| `RawSettingsPanel.tsx`                   | Admin raw-settings editor (NEM-4951)                               |
| `LoggingSettings.tsx`                    | Logging configuration UI                                           |
| `RiskSensitivitySettings.tsx`            | Risk sensitivity configuration                                     |
| `SeverityThresholds.tsx`                 | Risk-score threshold editor                                        |
| `AdminSettings.tsx`                      | ADMIN tab (developer tools entry)                                  |

## Key Components

### SettingsPage.tsx

**Purpose:** Shell for the Settings page with route-based tab navigation
(NEM-4938 converted the old in-page tabs to nested sub-routes).

**Key Features:**

- Tabs come from `settingsTabsConfig.ts` and render as `NavLink`s; each tab's
  panel renders in an `<Outlet/>` from the router, not from local state
- Eleven tabs: CAMERAS, RULES, PROCESSING, NOTIFICATIONS, AMBIENT,
  CALIBRATION, ACCESS, PROMPTS, STORAGE, AI MODELS, ADMIN
- Horizontal scroll with chevron buttons and fade shadows when tabs overflow
  (NEM-3520); keyboard-accessible scroll buttons
- Wraps content in `DebugModeProvider` (`../../contexts/DebugModeContext`)
- Exported as `SettingsPageWithErrorBoundary` (also named export), which wraps
  the page in `FeatureErrorBoundary` and shows `SecureContextWarning`

**Props:** none (top-level page component). Panels are lazy-imported in
`App.tsx` (`import('./components/settings/CamerasSettings')` etc.).

### CamerasSettings.tsx

**Purpose:** CRUD interface for cameras, supporting FTP-folder and RTSP-stream
ingestion.

**Key Features:**

- Table of cameras with status indicators and relative last-seen timestamps
  (`formatRelativeTime` from `../../utils/time`)
- Add/edit via Headless UI `Dialog` modal; delete with confirmation dialog
- Validation via Zod `cameraFormSchema` (`../../schemas/camera.ts`), which
  mirrors the backend Pydantic constraints (`_validate_folder_path`,
  `CAMERA_STATUS_VALUES = online | offline | error | unknown`, RTSP URL
  formats, motion sensitivity bounds)
- Form fields: name, folder_path, status, motion_sensitivity, ingestion_mode
  (`ftp` | `rtsp`), rtsp_url, rtsp_username, rtsp_password
- RTSP connection testing through `useRtspTest` + `ConnectionStatusCard`
- ONVIF network discovery through `ONVIFDiscoveryPanel`
- Soft-delete/restore: deleted-camera list and restore via
  `useDeletedCamerasQuery` / `useRestoreCameraMutation`

**State:** data comes from hooks - `useCamerasQuery`, `useCameraMutation`
(POST create / PATCH update / DELETE), `useSettingsQuery` +
`useUpdateSettings`. No direct `fetch` calls.

### AIModelsSettings.tsx

**Purpose:** Read-only status cards for the detection model and Nemotron.

**Props:**

```typescript
interface AIModelsSettingsProps {
  rtdetrModel?: ModelInfo; // NOT named yolo26Model
  nemotronModel?: ModelInfo;
  totalMemory?: number | null; // MB
  className?: string;
}

interface ModelInfo {
  name: string;
  status: 'loaded' | 'unloaded' | 'error';
  memoryUsed: number | null; // MB
  inferenceFps: number | null;
  description: string;
}
```

**Default Behavior:** With no props, derives both models from `useAIMetrics()`
(`../../hooks/useAIMetrics`); the detection model defaults to name
`RT-DETRv2`, description "Real-time object detection model", and Nemotron
gets "Risk analysis and reasoning model". Unloaded state shows N/A metrics.

**Layout:** `grid grid-cols-1 gap-6 lg:grid-cols-2`; Tremor `Card`
(`bg-[#1E1E1E] border-gray-800`) per model with `ProgressBar` for memory and
status `Badge` (loaded green, unloaded gray, error red).

Model **control** (load/unload/reload buttons) is not here - it lives in
`ModelZooPanel.tsx` via `useLoadModel` / `useUnloadModel` / `useReloadModel` /
`useUnloadAllModels` (`../../hooks/useModelZoo.ts`).

### ProcessingSettings.tsx

**Purpose:** Event-processing configuration plus a composition surface for
related admin panels.

**Sliders (measured from the component):**

| Setting                        | Range     | Step |
| ------------------------------ | --------- | ---- |
| Batch Window Duration          | 30-300 s  | 10   |
| Idle Timeout                   | 10-120 s  | 5    |
| Event Retention Period         | 1-90 days | 1    |
| Log Retention Period           | 1-90 days | 1    |
| Detection Confidence Threshold | 0.00-1.00 | 0.01 |
| Fast-Path Confidence Threshold | 0.00-1.00 | 0.01 |

Detection confidence is marked DEPRECATED in the backend
(`ConfigResponse.detection_confidence_threshold`); the settings API
(`/api/v1/settings`, through `useSettingsQuery` / `useUpdateSettings`) is the
forward path.

**Composition:** renders `BatchPresetSelector`, `BatchSettingsTooltips`,
`BatchStatusMonitor`, `CleanupPreviewPanel`, `DetectionThresholdsPanel`,
`DlqMonitor`, `QueueSettings`, `RateLimitingSettings`, `SeverityThresholds`,
`StorageDashboard`, and `AnomalyConfigPanel` (from `../analytics`). The
"Clear Old Data" button runs a real cleanup via `triggerCleanup()` (not a
placeholder); the storage section is the live `StorageDashboard`.

**API Integration:** `fetchConfig()` GET /api/system/config, `updateConfig()`
PATCH /api/system/config, plus `fetchAnomalyConfig()`. `SystemConfig` is the
generated type re-exported from `../../services/api` (fields include
`app_name`, `version`, `retention_days`, `log_retention_days`,
`batch_window_seconds`, `batch_idle_timeout_seconds`,
`detection_confidence_threshold`, `fast_path_confidence_threshold`,
`grafana_url`, `debug`).

### DlqMonitor.tsx

**Purpose:** Dead-letter queue monitoring; embedded in ProcessingSettings.

**Props:** `{ className?: string; refreshInterval?: number }` - default
refresh 30000 ms; `refreshInterval <= 0` disables polling.

**Queues tracked:** `dlq:detection_queue`, `dlq:analysis_queue`. Red `Badge`
shows the total failed count; per-queue panels expand to show job error
messages, timestamps, and original payloads.

**Actions:** Requeue All -> `requeueAllDlqJobs()` ->
POST `/api/dlq/requeue-all/{queue_name}`; Clear All -> DELETE
`/api/dlq/{queue_name}` (destructive). Tests: `DlqMonitor.test.tsx` and
`DlqMonitor.msw.test.tsx`.

### NotificationSettings.tsx

**Purpose:** Notification channel status (email/SMTP and webhook) with
send-test buttons.

**API Integration:** `fetchNotificationConfig()` GET
`/api/notification/config` (singular `notification`), updates via PATCH the
same path, `testNotification()` POST `/api/notification/test`. Also uses
`useIntegratedNotifications` and `useCamerasQuery` hooks.

### StorageDashboard.tsx

**Purpose:** Disk usage, per-category storage breakdown, and DB record counts.

- Polls `useStorageStatsQuery({ refetchInterval: 60000 })`
- Usage bar colors: emerald <50%, yellow <75%, orange <90%, red above
- Breakdown cards (3-col): Thumbnails (cyan), Camera images (violet), Video
  clips (amber)
- Record counts (4-col): Events, Detections, GPU Stats, Logs
- Cleanup preview via `useCleanupPreviewMutation` (dry-run)
- Helpers `formatBytes()` / `formatNumber()` are local to the file

### AlertRulesSettings.tsx

**Purpose:** CRUD for alert rules that drive notifications.

- Table + add/edit/delete modals, enable/disable toggle, and a "test rule
  against recent events" action (`RuleTestResponse`)
- Form conditions: `object_types`, `camera_ids`, risk levels, optional
  schedule (`AlertRuleSchedule`; start/end times required when enabled)
- Actions are a `channels: string[]` list (component-local form state) - the
  canonical `AlertRule` / `AlertRuleCreate` / `AlertRuleUpdate` types come
  from `../../services/api`
- There is no numeric "priority" field on rules

### SeverityThresholds.tsx

**Purpose:** Visual editor for risk-score severity thresholds.

**Threshold values:** `low_max` (slider 1-98), `medium_max` (slider
`low_max + 1` to 99), `high_max` (slider `medium_max + 1` to 99). Critical is
implied above `high_max`. Validation enforces low < medium < high.

**API:** `fetchSeverityConfig()` GET /api/system/severity;
`updateSeverityThresholds()` PUT /api/system/severity (both defined in
`backend/api/routes/system.py`; the PUT requires `verify_api_key`).

### README.md

Companion doc covering how settings panels fetch data and what
`AIModelsSettings` renders. There is no barrel file and no `*.example.tsx`
files in this directory (older revisions of this doc claimed both - they do
not exist).

## Important Patterns

### Data fetching (all panels)

- Reads: `../../services/api` typed functions or TanStack Query hooks in
  `../../hooks/` (`useSettingsApi` for the settings API, feature hooks like
  `useCamerasQuery`)
- Writes: POST/PATCH/DELETE through the same client, then rely on query
  invalidation or refetch
- `SettingsPage` passes no data down; it is routing only

### CRUD (CamerasSettings)

1. Read: `useCamerasQuery` -> table
2. Create: modal -> Zod validate -> `useCameraMutation` POST -> refetch
3. Update: pre-filled modal -> validate -> PATCH -> refetch
4. Delete: confirm modal -> DELETE (soft delete; restore available)

### Modal state (CamerasSettings)

`isModalOpen` + `editingCamera` for add/edit; `isDeleteModalOpen` +
`deletingCamera` for delete; state cleared on close. Modals are Headless UI
`Dialog`/`Transition` with fade+scale animation, backdrop blur, Escape to
close.

### Loading/saving states

`loading` / `saving` / `error` / `success` booleans with Tremor banners
(`bg-red-500/10` error, `bg-green-500/10` success); ProcessingSettings shows
a `BatchSettingsTooltips` validation summary rather than raw slider min/max.

## Styling Conventions

- Page background: `bg-[#121212]`; tab strip `bg-[#1A1A1A] border-gray-800`;
  active tab `bg-[#76B900] text-gray-950` (NVIDIA green)
- Tables: `divide-y divide-gray-800 bg-card`, inputs `bg-card` with
  `focus:ring-primary`
- AI model cards: `bg-[#1E1E1E] border-gray-800`; storage panels
  `bg-[#1A1A1A]/50`
- Range sliders: `accent-[#76B900]` on `bg-gray-700` tracks
- Error banner `bg-red-500/10 border-red-500/30 text-red-500`; success
  `bg-green-500/10 border-green-500/30 text-green-500`

## Testing

- Run this directory: `cd frontend && npm test -- src/components/settings/`
- MSW integration variants exist for `DlqMonitor` and `StorageDashboard`
- Extra suites in `__tests__/`: camera motion-sensitivity, FeatureTogglesPanel
- Components with no co-located test today: `AIModelsTab`,
  `AccessControlSettings`, `MqttSettings`, `QueueSettings`,
  `RateLimitingSettings`, `GpuVersionHistory`

## Entry Points

**Start here:** `SettingsPage.tsx` + `settingsTabsConfig.ts` - routing shell
**Then explore:** `CamerasSettings.tsx` - full CRUD + modal + Zod pattern
**Next:** `ProcessingSettings.tsx` - composition surface + settings API
**Model work:** `ModelZooPanel.tsx` + `../../hooks/useModelZoo.ts`

## Dependencies

- `@tremor/react` - Card, Title, Text, Badge, Button, ProgressBar
- `@headlessui/react` - Dialog/Transition (CamerasSettings modals)
- `react-router-dom` - NavLink/Outlet (SettingsPage)
- `lucide-react` - icons
- `clsx` - class composition
- `zod` - camera form schema in `../../schemas/camera.ts`
- `../../services/api` - typed REST client
- `../../hooks/` - `useCamerasQuery`, `useRtspTest`, `useSettingsApi`,
  `useStorageStatsQuery`, `useModelZoo`, `useAIMetrics`,
  `useIntegratedNotifications`

## API Endpoints Used

Verified in `backend/api/routes/` (and the client in
`frontend/src/services/api.ts`):

- `GET /api/cameras`, `POST /api/cameras`, `PATCH /api/cameras/{id}`,
  `DELETE /api/cameras/{id}` (`backend/api/routes/cameras.py`; camera updates
  are PATCH, not PUT)
- `GET /api/system/config`, `PATCH /api/system/config`
  (`backend/api/routes/system.py` `patch_config`)
- `GET /api/system/severity`, `PUT /api/system/severity`
  (`backend/api/routes/system.py`; PUT guarded by `verify_api_key`)
- `GET /api/dlq/stats`, `GET /api/dlq/jobs/{queue_name}`,
  `POST /api/dlq/requeue/{queue_name}`,
  `POST /api/dlq/requeue-all/{queue_name}`, `DELETE /api/dlq/{queue_name}`
  (`backend/api/routes/dlq.py`; the jobs path is `/jobs/{queue_name}`, not
  `/{queueName}/jobs`)
- `GET /api/notification/config`, `PATCH /api/notification/config`,
  `POST /api/notification/test`, `GET /api/notification/history`
  (`backend/api/routes/notification.py`; singular `notification`)
- `GET /api/system/models`, `POST /api/system/models/{model_name}/load` /
  `unload` / `reload`, `POST /api/system/models/unload-all`,
  `GET /api/system/models/vram-summary`
  (`backend/api/routes/model_management.py`) - Model Zoo panel

### ONVIFDiscoveryPanel.tsx

Modal for discovering ONVIF cameras on the network; device list with
manufacturer/model/IP, RTSP URL extraction, one-click add, progress and
timeout/error handling.

```typescript
interface ONVIFDiscoveryPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onDeviceSelect: (device: OnvifDevice) => void; // not onSelectDevice
}
```

### ConnectionStatusCard.tsx

Renders an RTSP test result: status, stream capabilities (resolution, codec,
framerate), audio/PTZ detection, latency/bitrate, troubleshooting hints.

```typescript
interface ConnectionStatusCardProps {
  result: RTSPTestResult | null; // single prop
}
```

## Already Implemented (older drafts listed these as "future")

- Model reload/restart buttons - `ModelZooPanel` + `useModelZoo` hooks
- Batch settings tooltips and presets - `BatchSettingsTooltips`,
  `BatchPresetSelector` (NEM-3873)
- Severity range validation - live in `SeverityThresholds`
- Camera connection testing before save - `useRtspTest` + ConnectionStatusCard
- Raw settings editing and version history - `RawSettingsPanel` (NEM-4951),
  `GpuVersionHistory`

Anything not on that list (settings search, audit log, profiles, bulk camera
import) remains unbuilt; treat those as ideas, not behavior.
