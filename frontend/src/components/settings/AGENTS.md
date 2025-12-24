# Settings Components - AI Agent Guide

## Purpose

This directory contains settings page components for the home security dashboard. Each component represents a tab or section in the settings interface.

## Components

### CamerasSettings.tsx

Manages camera configurations for the security system.

**Features:**

- Display list of all cameras in a table format
- Show camera status (active/inactive) with color indicators
- Display last seen timestamp for each camera
- Add new camera with form validation
- Edit existing camera details
- Delete camera with confirmation modal
- Empty state when no cameras are configured
- Error handling with retry capability

**API Integration:**

- `fetchCameras()` - Load all cameras on mount
- `createCamera(data)` - Create new camera
- `updateCamera(id, data)` - Update existing camera
- `deleteCamera(id)` - Delete camera

**Form Validation:**

- Name: Required, minimum 2 characters
- Folder Path: Required, must be valid path format (starts with `/` or `.`)
- Status: Active or Inactive (dropdown)

**UI Components:**

- Camera table with sortable columns (Name, Folder Path, Status, Last Seen, Actions)
- Add/Edit modal using Headless UI Dialog with transitions
- Delete confirmation modal with warning icon
- NVIDIA dark theme styling with green accents
- Lucide React icons (Camera, Edit2, Trash2, Plus, AlertCircle, X)

**Testing:**
24 comprehensive tests covering:

- Initial loading states (loading, success, error, empty)
- Add camera flow (validation, success, error handling)
- Edit camera flow (pre-fill form, update, error handling)
- Delete camera flow (confirmation, success, error, cancellation)
- Accessibility features (aria-labels, modal interactions)
- Status handling and display

Run tests:

```bash
cd frontend && npm test -- --run CamerasSettings
```

### AIModelsSettings.tsx

Displays AI model information and status for the RT-DETRv2 object detection model and Nemotron risk analysis model.

**Features:**

- Model status badges (loaded/unloaded/error)
- GPU memory usage per model with progress bars
- Inference speed (FPS) display
- Total GPU memory summary
- NVIDIA dark theme styling

**Props:**

```typescript
interface AIModelsSettingsProps {
  rtdetrModel?: ModelInfo;
  nemotronModel?: ModelInfo;
  totalMemory?: number | null; // Total GPU memory in MB
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

**Default Behavior:**

- If no props provided, displays placeholder data with "unloaded" status
- Memory displayed in GB (converted from MB)
- FPS rounded to integer
- Null values shown as "N/A"

**Usage:**

```typescript
import { AIModelsSettings } from '@/components/settings';

// With real data from GPU stats
<AIModelsSettings
  rtdetrModel={{
    name: 'RT-DETRv2',
    status: 'loaded',
    memoryUsed: 4096,
    inferenceFps: 30,
    description: 'Real-time object detection model'
  }}
  nemotronModel={{
    name: 'Nemotron',
    status: 'loaded',
    memoryUsed: 8192,
    inferenceFps: 15,
    description: 'Risk analysis and reasoning model'
  }}
  totalMemory={24576}
/>

// With placeholder data
<AIModelsSettings />
```

**Layout:**

- Two-column grid on large screens
- Stacked on mobile
- Each model gets its own card
- Optional total memory card at bottom

**Styling:**

- NVIDIA green (#76B900) for active elements
- Dark cards (#1E1E1E, #1A1A1A)
- Status badges with color coding:
  - Green: loaded
  - Gray: unloaded
  - Red: error

## Testing

All components have comprehensive test coverage including:

- Status badge rendering for all states
- Memory usage display and formatting
- Inference speed display
- Total GPU memory
- Null value handling
- Edge cases (zero values, decimals, large numbers)
- Layout and grid rendering
- Custom className support

Run tests:

```bash
cd frontend && npm test -- --run AIModelsSettings
```

### ProcessingSettings.tsx

Manages AI processing pipeline configuration.

**Features:**

- Display and edit batch window seconds
- Display and edit batch idle timeout seconds
- Display and edit retention days
- Show current system configuration
- Form validation for numeric inputs

**Testing:**
Comprehensive tests covering configuration display and updates.

Run tests:

```bash
cd frontend && npm test -- --run ProcessingSettings
```

## Future Components

Additional settings tabs may include:

- GeneralSettings.tsx - App configuration
- AlertSettings.tsx - Notification preferences
- StorageSettings.tsx - Retention and cleanup
- SystemSettings.tsx - System resources and performance

## Design Patterns

### Card-based Layout

Each model uses a Tremor Card with:

- Title with icon
- Status badge
- Description text
- Metric rows with icons and values
- Progress bars for memory usage

### Null Handling

All numeric values handle null gracefully:

- Display "N/A" for null values
- Don't show progress bars if percentage can't be calculated
- Hide inference speed section for unloaded models

### Color Coding

Follow consistent color scheme:

- NVIDIA green (#76B900) for healthy/active states
- Yellow for warnings
- Red for errors
- Gray for inactive/unknown states

## Integration Notes

This component can be integrated with:

- GPU stats API (`/api/system/gpu`)
- Health check API (`/api/system/health`)
- Real-time system status WebSocket (`/ws/system`)

Currently displays static/mock data since AI model management endpoints are not yet implemented in the backend.

## Related Files

- `/frontend/src/components/dashboard/GpuStats.tsx` - GPU metrics display
- `/frontend/src/services/api.ts` - API client (includes fetchGPUStats)
- `/frontend/src/hooks/useSystemStatus.ts` - System status polling
