# Settings Components Directory

## Purpose

Contains components for application configuration and system settings. Includes camera management, AI model status, and processing parameters. These components provide administrative controls for the security system.

## Key Components

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

- No props (top-level settings page component)

**State Management:**

- `cameras: Camera[]` - All cameras from API
- `loading: boolean` - Initial load state
- `error: string | null` - Error message
- `isModalOpen: boolean` - Add/edit modal visibility
- `isDeleteModalOpen: boolean` - Delete confirmation modal
- `editingCamera: Camera | null` - Camera being edited (null for add)
- `deletingCamera: Camera | null` - Camera being deleted
- `formData: CameraFormData` - Form state
- `formErrors: CameraFormErrors` - Validation errors
- `submitting: boolean` - Form submission state

**Camera Interface:**

```typescript
{
  id: string;
  name: string;
  folder_path: string;
  status: string;           // "active" or "inactive"
  last_seen_at?: string;    // ISO timestamp
}
```

**API Integration:**

- `fetchCameras()` - Load all cameras
- `createCamera(data)` - POST new camera
- `updateCamera(id, data)` - PUT camera updates
- `deleteCamera(id)` - DELETE camera

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

- `rtdetrModel?: ModelInfo` - RT-DETRv2 model status
- `nemotronModel?: ModelInfo` - Nemotron model status
- `totalMemory?: number | null` - Total GPU memory in MB
- `className?: string`

**ModelInfo Interface:**

```typescript
{
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

**Display Features:**

- Tremor Card, ProgressBar, Title, Text, Badge components
- Icons: Cpu (RT-DETRv2), Brain (Nemotron), Activity, Zap
- Color-coded status badges
- Memory usage as GB with percentage progress bar
- Inference FPS only shown when model is loaded

### ProcessingSettings.tsx

**Purpose:** Display event processing configuration (read-only)

**Key Features:**

- Batch window duration (seconds)
- Idle timeout (seconds)
- Retention period (days)
- Application name and version
- Read-only inputs (disabled, cursor-not-allowed)
- Info banner: "Settings are currently read-only"
- Fetches config from `/api/system/config` endpoint
- Loading skeletons and error handling

**Props:**

- `className?: string`

**State:**

- `config: SystemConfig | null` - Configuration from API
- `loading: boolean` - Loading state
- `error: string | null` - Error message

**SystemConfig Interface:**

```typescript
{
  batch_window_seconds: number; // 90
  batch_idle_timeout_seconds: number; // 30
  retention_days: number; // 30
  app_name: string; // "NVIDIA Security Intelligence"
  version: string; // "0.1.0"
}
```

**API Integration:**

- `fetchConfig()` - GET /api/system/config

**UI Notes:**

- Blue info banner explains read-only state
- Disabled inputs have opacity-60 and cursor-not-allowed
- Uses Tremor Card, Title, Text components
- Settings icon from lucide-react

### AIModelsSettings.example.tsx

**Purpose:** Example usage of AIModelsSettings component

Shows:

- Loaded models with metrics
- Unloaded models
- Error state
- Null values handling

### ProcessingSettings.example.tsx

**Purpose:** Example usage of ProcessingSettings component

Demonstrates read-only configuration display

### index.ts

**Purpose:** Barrel export for settings components

**Exports:**

```typescript
export { default as CamerasSettings } from './CamerasSettings';
export { default as AIModelsSettings } from './AIModelsSettings';
export { default as ProcessingSettings } from './ProcessingSettings';
```

### README.md

**Purpose:** Documentation for settings components

Contains usage examples, prop descriptions, and integration notes

## Important Patterns

### CRUD Operations (CamerasSettings)

Standard create-read-update-delete pattern:

1. **Read:** Fetch on mount, display in table
2. **Create:** Modal form → validate → POST → reload list
3. **Update:** Modal form (pre-filled) → validate → PUT → reload list
4. **Delete:** Confirmation modal → DELETE → reload list

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

Display inline errors:

```tsx
{
  formErrors.name && <p className="mt-1 text-sm text-red-500">{formErrors.name}</p>;
}
```

### Read-Only Displays

AIModelsSettings and ProcessingSettings are read-only:

- No form submission
- Disabled inputs with visual indicators
- Info banners explaining why read-only
- Future: Add edit functionality when backend supports it

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
- Grid layout: 1 col → 2 cols (lg breakpoint)

### ProcessingSettings

- Card: bg-[#1A1A1A], border-gray-800
- Info banner: bg-blue-500/10, border-blue-500/30, text-blue-400
- Disabled inputs: opacity-60, cursor-not-allowed
- Labels: text-gray-300, descriptions: text-gray-500
- Application info: border-t border-gray-800, gray text

## Testing

Comprehensive test coverage:

- `CamerasSettings.test.tsx` - CRUD operations, modals, validation, loading/error states
- `AIModelsSettings.test.tsx` - Model status display, memory usage, FPS display
- `ProcessingSettings.test.tsx` - Config fetching, read-only inputs, error handling

## Entry Points

**Start here:** `CamerasSettings.tsx` - Understand full CRUD pattern with modals
**Then explore:** `AIModelsSettings.tsx` - See read-only status display
**Finally:** `ProcessingSettings.tsx` - Learn config fetching pattern

## Dependencies

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

- `@tremor/react` - Card, Title, Text
- `lucide-react` - Icons (AlertCircle, Settings)
- `../../services/api` - fetchConfig

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

- Enable editing (PUT /api/system/config endpoint)
- Validation: min/max values, dependencies
- Apply/Revert buttons
- Restart required warnings
- Advanced settings (debug mode, logging level)
- Import/export configuration

### General

- Settings page tabs or sidebar navigation
- Search/filter across all settings
- Change history/audit log
- Settings profiles (dev/staging/prod)
- Help text and tooltips
- Reset to defaults button
