# Settings Components

This directory contains components for the Settings page of the home security dashboard.

## AIModelsSettings

Display AI model information and status for the YOLO26 object detection model and Nemotron risk analysis model.

### Features

- **Model Status Badges**: Shows loaded/unloaded/error status with color coding
- **Memory Usage**: Displays GPU memory usage per model with progress bars
- **Inference Speed**: Shows FPS performance when models are loaded
- **Total GPU Memory**: Summary card showing total GPU memory
- **NVIDIA Dark Theme**: Consistent with dashboard design

### Props

```typescript
interface AIModelsSettingsProps {
  yolo26Model?: ModelInfo;
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

### Default Behavior

When no props are provided, the component displays placeholder data:

- Both models shown as "unloaded"
- Memory and FPS shown as "N/A"
- Default names: "YOLO26" and "Nemotron"

### Usage

```typescript
import { AIModelsSettings } from '@/components/settings';

// Basic usage with default placeholder data
<AIModelsSettings />

// With real data
<AIModelsSettings
  yolo26Model={{
    name: 'YOLO26',
    status: 'loaded',
    memoryUsed: 4096,
    inferenceFps: 30,
    description: 'Real-time object detection model'
  }}
  nemotronModel={{
    name: 'Nemotron-3',
    status: 'loaded',
    memoryUsed: 8192,
    inferenceFps: 15,
    description: 'Risk analysis and reasoning model'
  }}
  totalMemory={24576}
/>
```

### Layout

- Two-column grid on large screens (`lg:grid-cols-2`)
- Single column on mobile
- Each model gets its own card
- Optional total memory summary card at bottom

### Styling

- **Cards**: Dark background (#1E1E1E, #1A1A1A) with gray borders
- **NVIDIA Green**: #76B900 for active elements (icons, loaded status)
- **Status Colors**:
  - Green: loaded
  - Gray: unloaded
  - Red: error
- **Progress Bars**: Tremor ProgressBar component with color coding

### Data Sources

The component can be populated from:

- **GPU Stats API**: `/api/system/gpu` - provides memory and FPS data
- **Health API**: `/api/system/health` - could provide model status
- **WebSocket**: `/ws/system` - real-time system status updates

Currently, model management endpoints don't exist in the backend, so this component primarily shows static/mock data or data derived from GPU stats.

### Examples

See `AIModelsSettings.example.tsx` for complete examples:

- Default placeholder display
- With real GPU stats
- Mixed states (one loaded, one unloaded)
- Error state handling
- Integration with hooks

### Testing

Comprehensive test coverage in `AIModelsSettings.test.tsx`:

- ✓ Status badge rendering (all states)
- ✓ Memory usage display and formatting
- ✓ Inference speed display
- ✓ Total GPU memory
- ✓ Null value handling
- ✓ Edge cases (zero, decimals, large numbers)
- ✓ Layout and grid
- ✓ Custom className support

Run tests:

```bash
cd frontend && npm test -- --run AIModelsSettings
```

### Future Enhancements

Potential improvements:

- Real-time model loading/unloading controls
- Model configuration options
- Performance history charts
- Model version information
- Temperature per model (if available)
- Power consumption metrics

### Related Components

- `/dashboard/GpuStats.tsx` - GPU metrics display (uses same GPU data)
- Other settings components (coming soon):
  - `GeneralSettings.tsx`
  - `CameraSettings.tsx`
  - `AlertSettings.tsx`
  - `StorageSettings.tsx`
