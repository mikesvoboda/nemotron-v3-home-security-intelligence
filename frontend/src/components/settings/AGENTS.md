# Settings Components Directory

## Purpose

Contains components for application configuration and system settings. Includes camera management, AI model status, and processing parameters. These components provide administrative controls for the security system, organized in a tabbed interface.

## Key Components

### SettingsPage.tsx

**Purpose:** Main settings page with tabbed interface for different settings categories

**Key Features:**

- Headless UI Tab component for accessible tab navigation
- Three settings tabs: CAMERAS, PROCESSING, AI MODELS
- Tab icons: Camera, Settings, Cpu
- NVIDIA dark theme with green accent for selected tab
- Keyboard navigation support
- Focus ring styling for accessibility

**Tab Configuration:**

```typescript
const tabs = [
  { id: 'cameras', name: 'CAMERAS', icon: Camera, component: CamerasSettings },
  { id: 'processing', name: 'PROCESSING', icon: SettingsIcon, component: ProcessingSettings },
  { id: 'ai-models', name: 'AI MODELS', icon: Cpu, component: AIModelsSettings },
];
```

**No props** - Top-level page component

### CamerasSettings.tsx

**Purpose:** Full CRUD interface for managing security cameras

**Key Features:**

- Table view of all cameras with status indicators
- Add new camera via modal form
- Edit existing camera (inline edit via modal)
- Delete camera with confirmation dialog
- Form validation: name (min 2 chars), folder_path (valid path format)
- Status dropdown: active/inactive
- Last seen timestamp display
- Empty state with "Add Camera" call-to-action
- Loading and error states with retry button

**Props:**

- No props (top-level settings component)

**State Management:**

```typescript
const [cameras, setCameras] = useState<Camera[]>([]);
const [loading, setLoading] = useState(boolean);
const [error, setError] = useState<string | null>(null);
const [isModalOpen, setIsModalOpen] = useState(boolean);
const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(boolean);
const [editingCamera, setEditingCamera] = useState<Camera | null>(null);
const [deletingCamera, setDeletingCamera] = useState<Camera | null>(null);
const [formData, setFormData] = useState<CameraFormData>({});
const [formErrors, setFormErrors] = useState<CameraFormErrors>({});
const [submitting, setSubmitting] = useState(boolean);
```

**Camera Interface:**

```typescript
interface Camera {
  id: string;
  name: string;
  folder_path: string;
  status: string; // "online", "offline", or "error"
  last_seen_at?: string; // ISO timestamp
}
```

**Validation:**

- Name: Minimum 2 characters, trimmed
- Folder path: Must match regex `/^[/.][a-zA-Z0-9_\-/.]+$/`
- Shows inline error messages on validation failure

**Modal Features (Headless UI):**

- Animated entry/exit (fade + scale)
- Backdrop blur
- Click outside to close
- Escape key to close
- Form submission on Enter key

### AIModelsSettings.tsx

**Purpose:** Display AI model status and performance metrics

**Key Features:**

- Two model cards: RT-DETRv2 (detection) and Nemotron (risk analysis)
- Status badges: loaded (green), unloaded (gray), error (red)
- Memory usage per model with progress bar
- Inference speed (FPS) when model is loaded
- Total GPU memory display at bottom
- Read-only display (no configuration controls)
- Handles null values gracefully (shows N/A)

**Props:**

```typescript
interface AIModelsSettingsProps {
  rtdetrModel?: ModelInfo;
  nemotronModel?: ModelInfo;
  totalMemory?: number | null;
  className?: string;
}

interface ModelInfo {
  name: string; // "RT-DETRv2", "Nemotron"
  status: 'loaded' | 'unloaded' | 'error';
  memoryUsed: number | null; // MB
  inferenceFps: number | null; // Frames per second
  description: string; // Model description
}
```

**Default Values:**

- RT-DETRv2: "Real-time object detection model"
- Nemotron: "Risk analysis and reasoning model"
- Both default to 'unloaded' status with null metrics

### ProcessingSettings.tsx

**Purpose:** Editable event processing configuration with range sliders

**Key Features:**

- Batch window duration (30-300 seconds, step 10)
- Idle timeout (10-120 seconds, step 5)
- Retention period (1-90 days, step 1)
- Confidence threshold (0.00-1.00, step 0.01)
- Range sliders for intuitive value adjustment
- Current value display next to each slider
- Save Changes / Reset buttons
- Success/error feedback messages
- Storage usage indicator (placeholder)
- Clear Old Data button (placeholder)
- Application name and version display

**Props:**

```typescript
interface ProcessingSettingsProps {
  className?: string;
}
```

**State:**

```typescript
const [config, setConfig] = useState<SystemConfig | null>(null);
const [editedConfig, setEditedConfig] = useState<SystemConfig | null>(null);
const [loading, setLoading] = useState(boolean);
const [saving, setSaving] = useState(boolean);
const [error, setError] = useState<string | null>(null);
const [success, setSuccess] = useState(boolean);
```

**SystemConfig Interface:**

```typescript
interface SystemConfig {
  batch_window_seconds: number; // Default: 90
  batch_idle_timeout_seconds: number; // Default: 30
  retention_days: number; // Default: 30
  detection_confidence_threshold: number; // Default: 0.5
  app_name: string; // "NVIDIA Security Intelligence"
  version: string; // e.g., "0.1.0"
}
```

**API Integration:**

- `fetchConfig()` - GET /api/system/config
- `updateConfig(updates)` - PATCH /api/system/config

### DlqMonitor.tsx

**Purpose:** Dead Letter Queue monitoring and management component

**Props Interface:**

```typescript
interface DlqMonitorProps {
  className?: string;
  refreshInterval?: number; // Polling interval in ms. Default: 30000 (30s)
}
```

**Key Features:**

- Badge showing total failed job count
- Expandable panels for each queue (detection, analysis)
- Job details with error messages and timestamps
- "Requeue All" button with confirmation dialog
- "Clear All" button with confirmation dialog
- Auto-refresh capability (configurable interval)
- Original job payload viewer (collapsible)

**Queue Types:**

- `dlq:detection_queue` - Failed RT-DETRv2 detection jobs
- `dlq:analysis_queue` - Failed Nemotron analysis jobs

**Job Information:**

- Error message
- Attempt count
- First failed timestamp
- Last failed timestamp
- Original job payload (JSON)

**Actions:**

- **Requeue All:** Moves all failed jobs back to their original queues for retry
- **Clear All:** Permanently deletes all failed jobs (destructive)

**Usage:**

```tsx
import DlqMonitor from './DlqMonitor';

<DlqMonitor
  refreshInterval={30000} // Auto-refresh every 30 seconds
  className="mt-4"
/>;
```

---

### NotificationSettings.tsx

**Purpose:** Display notification configuration status for email and webhook channels

**Key Features:**

- Shows overall notification system enabled/disabled status
- Email (SMTP) configuration panel:
  - Configuration status badge (Configured/Not Configured)
  - SMTP host, port, from address, TLS status
  - Default recipients display with badges
  - "Send Test Email" button with loading state
- Webhook configuration panel:
  - Configuration status badge
  - Webhook URL display
  - Timeout setting
  - "Send Test Webhook" button with loading state
- Available channels summary
- Test result feedback (success/error with 5-second auto-dismiss)
- Configuration note explaining environment variable setup

**Props:**

```typescript
interface NotificationSettingsProps {
  className?: string;
}
```

**API Integration:**

- `fetchNotificationConfig()` - GET /api/notifications/config
- `testNotification(channel)` - POST /api/notifications/test/{channel}

### StorageDashboard.tsx

**Purpose:** Real-time disk usage metrics and storage breakdown dashboard

**Key Features:**

- Overall disk usage with progress bar (color-coded by percentage):
  - Green (<50%), Yellow (50-75%), Orange (75-90%), Red (>90%)
- Storage breakdown by category (3-column grid):
  - Thumbnails (cyan accent)
  - Camera images (violet accent)
  - Video clips (amber accent)
- Database record counts (4-column grid):
  - Events, Detections, GPU Stats, Logs
- Cleanup preview with dry-run button showing:
  - Records that would be deleted by category
  - Space to be reclaimed
  - Retention period
- Auto-refresh with configurable poll interval (default: 60s)
- Loading skeleton and error states with retry button

**Props:**

```typescript
interface StorageDashboardProps {
  className?: string;
}
```

**Hooks Used:**

- `useStorageStats({ pollInterval, enablePolling })` - Custom hook for storage data

**Helper Functions:**

- `formatBytes(bytes)` - Converts bytes to human-readable string (KB, MB, GB, TB)
- `formatNumber(num)` - Adds thousands separator

### index.ts

**Purpose:** Barrel export for settings components

```typescript
export { default as CamerasSettings } from './CamerasSettings';
export { default as AIModelsSettings } from './AIModelsSettings';
export { default as ProcessingSettings } from './ProcessingSettings';
export { default as DlqMonitor } from './DlqMonitor';
export { default as NotificationSettings } from './NotificationSettings';
export { default as StorageDashboard } from './StorageDashboard';
```

### README.md

Documentation for settings components with usage examples and integration notes.

### Example Files

- `AIModelsSettings.example.tsx` - Example usage of AIModelsSettings
- `ProcessingSettings.example.tsx` - Example usage of ProcessingSettings

## Important Patterns

### CRUD Operations (CamerasSettings)

Standard create-read-update-delete pattern:

1. **Read:** Fetch on mount, display in table
2. **Create:** Modal form -> validate -> POST -> reload list
3. **Update:** Modal form (pre-filled) -> validate -> PUT -> reload list
4. **Delete:** Confirmation modal -> DELETE -> reload list

### Modal State Management

Two modals with separate state:

- `isModalOpen` + `editingCamera` - Add/edit modal
- `isDeleteModalOpen` + `deletingCamera` - Delete confirmation

Clear state on close:

```typescript
const handleCloseModal = () => {
  setIsModalOpen(false);
  setEditingCamera(null);
  setFormData({ name: '', folder_path: '', status: 'active' });
  setFormErrors({});
};
```

### Form Validation

Client-side validation before API call:

```typescript
const validateForm = (data: CameraFormData): CameraFormErrors => {
  const errors = {};
  if (!data.name || data.name.trim().length < 2) {
    errors.name = 'Name must be at least 2 characters';
  }
  // ... more validations
  return errors;
};
```

### Edit Detection (ProcessingSettings)

Track changes between original and edited config:

```typescript
const hasChanges = editedConfig && config && (
  editedConfig.batch_window_seconds !== config.batch_window_seconds ||
  // ... compare other fields
);
```

### Loading States

Three-state pattern:

1. **Loading:** Show skeletons or spinner
2. **Error:** Show error message with retry button
3. **Loaded:** Show data

```tsx
if (loading) return <LoadingSkeleton />;
if (error) return <ErrorDisplay error={error} onRetry={loadData} />;
return <DataDisplay data={data} />;
```

## Styling Conventions

### SettingsPage

- Page background: bg-[#121212]
- Tab list: bg-[#1A1A1A], border-gray-800
- Selected tab: bg-[#76B900], text-black
- Tab panel: bg-[#1A1A1A], border-gray-800

### CamerasSettings

- Table: border-gray-800, divide-y divide-gray-800
- Thead: bg-gray-900
- Tbody: bg-card, hover:bg-gray-900/50
- Action buttons: rounded p-1.5, hover:bg-gray-800
- Modal: bg-panel, border-gray-800, backdrop-blur
- Primary button: bg-primary (#76B900), text-gray-900
- Danger button: bg-red-500, text-white

### AIModelsSettings

- Model cards: bg-[#1E1E1E], border-gray-800
- Status badges: Tremor Badge with color coding
- Progress bars: Tremor ProgressBar
- GPU memory card: bg-[#1A1A1A]
- Grid layout: 1 col -> 2 cols (lg breakpoint)

### ProcessingSettings

- Card: bg-[#1A1A1A], border-gray-800
- Range sliders: accent-[#76B900]
- Error banner: bg-red-500/10, border-red-500/30, text-red-500
- Success banner: bg-green-500/10, border-green-500/30, text-green-500
- Labels: text-gray-300, descriptions: text-gray-500
- Application info: border-t border-gray-800, gray text

## Testing

Comprehensive test coverage:

- `SettingsPage.test.tsx` - Tab navigation, keyboard support, tab panel rendering
- `CamerasSettings.test.tsx` - CRUD operations, modals, validation, loading/error states
- `AIModelsSettings.test.tsx` - Model status display, memory usage, FPS display
- `ProcessingSettings.test.tsx` - Config fetching, slider interaction, save/reset, error handling

## Entry Points

**Start here:** `SettingsPage.tsx` - Understand tabbed layout structure
**Then explore:** `CamerasSettings.tsx` - Learn full CRUD pattern with modals
**Next:** `ProcessingSettings.tsx` - See editable config with range sliders
**Finally:** `AIModelsSettings.tsx` - Understand status display pattern

## Dependencies

### SettingsPage

- `@headlessui/react` - Tab component
- `lucide-react` - Icons (Camera, Settings, Cpu)
- `clsx` - Class composition

### CamerasSettings

- `@headlessui/react` - Dialog, Transition for modals
- `lucide-react` - Icons (AlertCircle, Camera, Edit2, Plus, Trash2, X)
- `clsx` - Conditional class composition
- `../../services/api` - Camera CRUD functions

### AIModelsSettings

- `@tremor/react` - Card, ProgressBar, Title, Text, Badge
- `lucide-react` - Icons (Brain, Cpu, Activity, Zap)
- `clsx` - Class composition

### ProcessingSettings

- `@tremor/react` - Card, Title, Text, Button
- `lucide-react` - Icons (AlertCircle, Settings, Save, RotateCcw, Trash2)
- `../../services/api` - fetchConfig, updateConfig

## API Endpoints Used

- `GET /api/cameras` - List all cameras
- `POST /api/cameras` - Create new camera
- `PUT /api/cameras/:id` - Update camera
- `DELETE /api/cameras/:id` - Delete camera
- `GET /api/system/config` - Fetch system configuration
- `PATCH /api/system/config` - Update system configuration
- `GET /api/dlq/stats` - Fetch DLQ statistics
- `GET /api/dlq/:queueName/jobs` - Fetch failed jobs for a queue
- `POST /api/dlq/:queueName/requeue` - Requeue all failed jobs
- `DELETE /api/dlq/:queueName` - Clear all failed jobs

## Future Enhancements

### CamerasSettings

- Test camera connection before saving
- Bulk import/export cameras (JSON/CSV)
- Camera groups/locations
- Thumbnail preview in table
- Sort and filter table columns
- Camera health monitoring

### AIModelsSettings

- Reload/restart model buttons
- Model switching (different versions)
- Performance graphs (historical FPS)
- Memory allocation controls
- Model configuration parameters

### ProcessingSettings

- Validation with min/max dependencies
- Restart required warnings
- Advanced settings (debug mode, logging level)
- Import/export configuration

### General

- Settings search/filter
- Change history/audit log
- Settings profiles (dev/staging/prod)
- Help text and tooltips
- Reset to defaults button
