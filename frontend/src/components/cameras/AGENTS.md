# Cameras Components Directory

## Purpose

Components for camera-related functionality including scene change detection, anomaly timeline display, and camera selection. These components help users monitor camera health, detect tampering, and filter views by camera.

## Key Components

| File                            | Purpose                                        |
| ------------------------------- | ---------------------------------------------- |
| `CameraSelector.tsx`            | Camera dropdown with React 19 useTransition    |
| `CameraSelector.test.tsx`       | Test suite for CameraSelector                  |
| `CameraAnomalyTimeline.tsx`     | Timeline of baseline anomaly events            |
| `CameraAnomalyTimeline.test.tsx`| Test suite for CameraAnomalyTimeline           |
| `SceneChangeIndicator.tsx`      | Visual badge for scene change alerts           |
| `SceneChangeIndicator.test.tsx` | Test suite for SceneChangeIndicator            |
| `SceneChangeHistory.tsx`        | List of recent scene change events             |
| `SceneChangeHistory.test.tsx`   | Test suite for SceneChangeHistory              |
| `index.ts`                      | Barrel exports for all components              |

## Component Details

### CameraSelector

Camera selection dropdown with React 19 useTransition for non-blocking UI updates.

**Features:**
- Dropdown with "All Cameras" option
- Camera status indicators (online/offline/error)
- useTransition prevents UI blocking during selection
- Loading spinner during transition
- Memoized for performance

**Props:**
| Prop         | Type                         | Description                        |
| ------------ | ---------------------------- | ---------------------------------- |
| `value`      | `string`                     | Selected camera ID (empty = all)   |
| `onChange`   | `(cameraId: string) => void` | Selection change callback          |
| `cameras`    | `CameraOption[]`             | Available cameras                  |
| `allLabel`   | `string`                     | Label for "All" option             |
| `showStatus` | `boolean`                    | Show status indicators             |
| `className`  | `string`                     | Optional CSS class                 |
| `disabled`   | `boolean`                    | Disable selector                   |

**CameraOption Type:**
```typescript
interface CameraOption {
  id: string;
  name: string;
  status?: 'online' | 'offline' | 'error';
}
```

### CameraAnomalyTimeline

Timeline display of anomaly events detected against camera baseline patterns.

**Features:**
- Fetches anomalies using useCameraAnomaliesQuery
- Severity-based color coding (critical/high/medium/low)
- Shows detection class, anomaly score, expected vs observed frequency
- Sorted by timestamp (most recent first)
- Legend explaining severity thresholds
- Loading, error, and empty states

**Severity Thresholds:**
| Severity | Score Range | Color  |
| -------- | ----------- | ------ |
| Critical | >= 90%      | Red    |
| High     | 75-89%      | Orange |
| Medium   | 50-74%      | Yellow |
| Low      | < 50%       | Blue   |

**Props:**
| Prop         | Type      | Description                   |
| ------------ | --------- | ----------------------------- |
| `cameraId`   | `string`  | Camera ID to fetch anomalies  |
| `cameraName` | `string`  | Camera name for display       |
| `days`       | `number`  | Days to look back (default: 7)|
| `showHeader` | `boolean` | Show card header              |
| `className`  | `string`  | Optional CSS class            |

### SceneChangeIndicator

Visual badge/indicator for active scene change detection.

**Features:**
- Pulsing animation for high/medium severity
- Compact mode for small spaces (icon only)
- Severity-based colors (red/amber/yellow)
- Time since activity display
- Memoized for performance

**Change Types:**
| Type            | Label         | Severity |
| --------------- | ------------- | -------- |
| `view_blocked`  | View Blocked  | High     |
| `view_tampered` | Tampered      | High     |
| `angle_changed` | Angle Changed | Medium   |

**Props:**
| Prop            | Type                  | Description                    |
| --------------- | --------------------- | ------------------------------ |
| `activityState` | `CameraActivityState` | Activity state from hook       |
| `compact`       | `boolean`             | Compact badge mode             |
| `className`     | `string`              | Optional CSS class             |
| `showDetails`   | `boolean`             | Show time since activity       |

### SceneChangeHistory

Scrollable list of recent scene change events.

**Features:**
- Shows camera name, change type badge, similarity score
- Relative timestamps ("5m ago", "2h ago")
- Click handler for navigation
- Dismiss button for acknowledging events
- Empty state with success message
- "More events" indicator when exceeding maxItems
- Memoized for performance

**Props:**
| Prop             | Type                                | Description                  |
| ---------------- | ----------------------------------- | ---------------------------- |
| `events`         | `SceneChangeEventData[]`            | Recent scene change events   |
| `maxItems`       | `number`                            | Max events to display (20)   |
| `onEventClick`   | `(event) => void`                   | Event click handler          |
| `onDismiss`      | `(eventId: number) => void`         | Dismiss event handler        |
| `className`      | `string`                            | Optional CSS class           |
| `showEmptyState` | `boolean`                           | Show empty state message     |
| `emptyMessage`   | `string`                            | Custom empty message         |

## Data Flow

```
CameraSelector
└── useTransition()        → non-blocking selection updates

CameraAnomalyTimeline
└── useCameraAnomaliesQuery()
    └── fetchCameraAnomalies() → GET /api/cameras/{id}/anomalies

SceneChangeIndicator / SceneChangeHistory
└── useSceneChangeEvents()
    └── WebSocket scene_change events → real-time updates
```

## Hooks Used

| Hook                      | Source                                             | Purpose                      |
| ------------------------- | -------------------------------------------------- | ---------------------------- |
| `useCameraAnomaliesQuery` | `frontend/src/hooks/useCameraAnomaliesQuery.ts`    | Fetch camera anomalies       |
| `useSceneChangeEvents`    | `frontend/src/hooks/useSceneChangeEvents.ts`       | Real-time scene change data  |

## Test Coverage

**CameraSelector.test.tsx** covers:
- Accessible select rendering
- "All Cameras" option display
- Camera options with status text
- Custom className application
- Selection change with useTransition
- Rapid selection handling
- Disabled state
- Status indicators by type
- Keyboard navigation
- Edge cases (empty cameras, special characters)

**CameraAnomalyTimeline.test.tsx** covers:
- Loading state display
- Error state display
- Empty state with camera name
- Anomaly item rendering
- Anomaly count and period display
- Detection class display
- Timestamp sorting (most recent first)
- Severity indicators (critical/high/low)
- Severity badge with percentage
- Days parameter passing
- Header visibility toggle
- Severity legend display

**SceneChangeIndicator.test.tsx** covers:
- Null rendering when inactive
- Compact mode rendering
- Change type labels
- Severity styling
- Time display formatting
- Accessibility (role="alert", aria-label)

**SceneChangeHistory.test.tsx** covers:
- Empty state rendering
- Custom empty message
- Event list rendering
- maxItems limiting
- "More events" indicator
- Camera name display
- Change type badges
- Similarity score percentage
- Relative time formatting
- Click handler
- Keyboard (Enter) handler
- Dismiss button
- Event propagation (dismiss vs click)
- Accessibility (role="list", aria-label)

## Related Types

**From `frontend/src/hooks/useSceneChangeEvents.ts`:**
```typescript
interface SceneChangeEventData {
  id: number;
  cameraId: string;
  cameraName: string;
  detectedAt: string;
  changeType: 'view_blocked' | 'view_tampered' | 'angle_changed';
  similarityScore: number;
  receivedAt: Date;
}

interface CameraActivityState {
  cameraId: string;
  cameraName: string;
  lastActivityAt: Date;
  lastChangeType: string;
  isActive: boolean;
}
```

**From `frontend/src/services/api.ts`:**
```typescript
interface CameraAnomalyEvent {
  timestamp: string;
  detection_class: string;
  anomaly_score: number;
  expected_frequency: number;
  observed_frequency: number;
  reason: string;
}
```

## Styling

- NVIDIA dark theme with gray-800/900 backgrounds
- NVIDIA green (`#76B900`) for online status and accents
- Severity colors: red-500, amber-500, yellow-500, blue-500
- Tremor components (Card, Title, Badge)
- Tailwind transitions and animations

## Related Linear Issues

- NEM-3575 - Scene change detection components
- NEM-3577 - Camera anomaly timeline
- NEM-3749 - React 19 useTransition for non-blocking filter

## Entry Points

- **Start here:** `CameraSelector.tsx` - Used in event timeline and filters
- **For monitoring:** `SceneChangeHistory.tsx` - Used in analytics page
- **For alerts:** `SceneChangeIndicator.tsx` - Used in camera grid cards
