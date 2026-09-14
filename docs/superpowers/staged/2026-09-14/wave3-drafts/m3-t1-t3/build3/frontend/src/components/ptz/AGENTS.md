# PTZ Controls Components Directory (NEM-4885)

## Purpose

Contains components for PTZ (Pan-Tilt-Zoom) camera control. Provides a D-pad style interface for controlling PTZ-capable cameras with directional movement, zoom, and preset navigation.

## Files

| File               | Purpose                                       |
| ------------------ | --------------------------------------------- |
| `PTZControls.tsx`  | D-pad style PTZ control interface             |
| `index.ts`         | Barrel export                                 |

## Key Components

### PTZControls.tsx

**Purpose:** D-pad style interface for PTZ camera control with directional buttons, zoom controls, and preset selection.

**Props Interface:**

```typescript
interface PTZControlsProps {
  /** Camera ID to control */
  cameraId: string;
  /** Compact mode for overlay usage */
  compact?: boolean;
  /** Whether to show preset selector */
  showPresets?: boolean;
  /** Optional className for styling */
  className?: string;
  /** Whether the camera supports PTZ (disables controls when false) */
  ptzSupported?: boolean;
}
```

**Key Features:**

- Directional D-pad for pan and tilt control (up, down, left, right)
- Center stop button to halt all movement
- Zoom in/out buttons
- Optional preset selector dropdown
- Compact mode for overlay usage (smaller buttons, tighter spacing)
- Loading states during command execution
- Keyboard accessible with proper ARIA labels
- Dark mode styling with NVIDIA green accent

**Usage:**

```tsx
import { PTZControls } from '../ptz';

// Basic usage
<PTZControls cameraId="camera-1" />

// Compact mode for overlay
<PTZControls cameraId="camera-1" compact />

// With presets
<PTZControls cameraId="camera-1" showPresets />

// Full featured
<PTZControls
  cameraId="camera-1"
  showPresets
  compact={false}
  className="p-4 bg-gray-900 rounded-lg"
/>
```

## Related Files

| Location                            | Purpose                          |
| ----------------------------------- | -------------------------------- |
| `src/hooks/usePtzControl.ts`        | Hook for PTZ command execution   |
| `src/hooks/usePresets.ts`           | Hook for preset management       |
| `src/services/ptzApi.ts`            | PTZ API service functions        |
| `src/types/ptz.ts`                  | PTZ TypeScript types             |

## Integration Points

- **RTSPPreviewPlayer**: Uses PTZControls in compact mode as an overlay on live video
- **usePtzControl hook**: Provides mutations for pan, tilt, zoom, and stop commands
- **usePresets hook**: Provides query and mutation for preset management

## Styling Conventions

### D-Pad Buttons

- Size: h-11 w-11 (normal) or h-9 w-9 (compact)
- Background: bg-gray-800
- Hover: bg-gray-700
- Active: bg-[#76B900] (NVIDIA green)
- Focus ring: focus-visible:ring-[#76B900]

### Stop Button

- Different styling to indicate danger action
- Hover: bg-red-600
- Active: bg-red-700

### Preset Selector

- Select dropdown with custom styling
- Focus border: #76B900
- Loading indicator when navigating to preset

## Accessibility

- All buttons have `aria-label` attributes
- Loading state indicated with `aria-busy`
- Preset selector has accessible label
- Keyboard navigable
- Visual feedback for disabled state
