# Zones Components Directory

## Purpose

Contains components for managing camera detection zones. Zones define regions of interest on camera feeds where detection should be focused, providing spatial context for AI analysis and risk assessment.

## Files

| File                       | Purpose                                            |
| -------------------------- | -------------------------------------------------- |
| `ZoneEditor.tsx`           | Main modal for zone management with drawing UI     |
| `ZoneEditor.test.tsx`      | Test suite for ZoneEditor                          |
| `ZoneCanvas.tsx`           | SVG canvas for drawing and displaying zones        |
| `ZoneCanvas.test.tsx`      | Test suite for ZoneCanvas                          |
| `ZoneForm.tsx`             | Form for zone properties (name, type, color)       |
| `ZoneForm.test.tsx`        | Test suite for ZoneForm                            |
| `ZoneList.tsx`             | List view of zones with CRUD actions               |
| `ZoneList.test.tsx`        | Test suite for ZoneList                            |
| `LineZoneEditor.tsx`       | Tripwire/line zone drawing component               |
| `LineZoneEditor.test.tsx`  | Test suite for LineZoneEditor                      |
| `PolygonZoneEditor.tsx`    | Polygon zone drawing with zone type support        |
| `PolygonZoneEditor.test.tsx` | Test suite for PolygonZoneEditor                 |
| `CameraZoneOverlay.tsx`    | SVG overlay for camera feeds with zone display     |
| `index.ts`                 | Barrel exports                                     |

## Key Components

### ZoneEditor.tsx

**Purpose:** Main modal component for managing camera zones with drawing and editing capabilities

**Key Features:**

- Headless UI Dialog with backdrop blur and animations
- View existing zones overlaid on camera snapshot
- Draw new rectangle or polygon zones on canvas
- Edit zone properties via ZoneForm
- Delete zones with confirmation dialog
- Enable/disable zone toggle
- Different editor modes: view, draw, edit, create
- Color picker for zone visualization
- Shape selection (rectangle or polygon)

**Props:**

```typescript
interface ZoneEditorProps {
  /** Camera to configure zones for */
  camera: Camera;
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal is closed */
  onClose: () => void;
}

type EditorMode = 'view' | 'draw' | 'edit' | 'create';
```

**State Management:**

```typescript
const [zones, setZones] = useState<Zone[]>([]);
const [loading, setLoading] = useState(true);
const [mode, setMode] = useState<EditorMode>('view');
const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
const [editingZone, setEditingZone] = useState<Zone | null>(null);
const [deletingZone, setDeletingZone] = useState<Zone | null>(null);
const [drawShape, setDrawShape] = useState<ZoneShape>('rectangle');
const [drawColor, setDrawColor] = useState('#3B82F6');
const [pendingCoordinates, setPendingCoordinates] = useState<Point[] | null>(null);
```

**Data Flow:**

```
ZoneEditor (modal container)
├── ZoneCanvas (drawing/display)
├── ZoneList (existing zones)
├── ZoneForm (create/edit form)
└── Delete confirmation dialog
```

### ZoneCanvas.tsx

**Purpose:** SVG canvas for drawing and displaying zone polygons over a camera snapshot

**Key Features:**

- Displays camera snapshot as background image
- Renders existing zones as colored polygons
- Interactive drawing mode for new zones
- Point-by-point polygon drawing
- Rectangle drawing with two points
- Selection highlighting
- Hover effects on zones
- Coordinate normalization (0-1 range)

**Props:**

```typescript
interface ZoneCanvasProps {
  /** Camera snapshot URL */
  snapshotUrl: string;
  /** Existing zones to display */
  zones: Zone[];
  /** Currently selected zone ID */
  selectedZoneId?: string | null;
  /** Whether drawing mode is active */
  isDrawing?: boolean;
  /** Shape being drawn */
  drawShape?: ZoneShape;
  /** Color for new zone */
  drawColor?: string;
  /** Current drawing coordinates */
  drawingCoordinates?: Point[];
  /** Callback when zone is clicked */
  onZoneClick?: (zoneId: string) => void;
  /** Callback when drawing completes */
  onDrawComplete?: (coordinates: Point[]) => void;
  /** Additional CSS classes */
  className?: string;
}

interface Point {
  x: number;
  y: number;
}
```

### ZoneForm.tsx

**Purpose:** Form component for zone properties with validation

**Key Features:**

- Zone name input with validation
- Zone type dropdown (entry, perimeter, interior, restricted)
- Color picker for zone visualization
- Enable/disable toggle
- Form validation (name required, min length)
- Save and Cancel buttons
- Loading state during submission

**Props:**

```typescript
interface ZoneFormProps {
  /** Initial form data (for editing) */
  initialData?: ZoneFormData;
  /** Whether the form is for editing */
  isEditing?: boolean;
  /** Whether form is submitting */
  isSubmitting?: boolean;
  /** Callback on form submission */
  onSubmit: (data: ZoneFormData) => void;
  /** Callback on cancel */
  onCancel: () => void;
}

interface ZoneFormData {
  name: string;
  zone_type: ZoneType;
  color: string;
  enabled: boolean;
}

type ZoneType = 'entry' | 'perimeter' | 'interior' | 'restricted';
```

### ZoneList.tsx

**Purpose:** List view of zones with CRUD action buttons

**Key Features:**

- Table of existing zones for a camera
- Zone name with color indicator
- Zone type badge
- Enable/disable status indicator
- Edit button (opens ZoneForm)
- Delete button (with confirmation)
- Empty state message
- Loading skeleton

**Props:**

```typescript
interface ZoneListProps {
  /** Zones to display */
  zones: Zone[];
  /** Currently selected zone ID */
  selectedZoneId?: string | null;
  /** Callback when zone is selected */
  onSelect?: (zoneId: string) => void;
  /** Callback to edit zone */
  onEdit?: (zone: Zone) => void;
  /** Callback to delete zone */
  onDelete?: (zone: Zone) => void;
  /** Whether list is loading */
  loading?: boolean;
}
```

### LineZoneEditor.tsx (NEM-3720)

**Purpose:** Component for drawing tripwire/line zones on camera feeds

**Key Features:**

- Two-point line drawing (start and end)
- Line preview while drawing
- Direction indicator arrow (optional)
- Minimum line length enforcement
- Display of existing line zones
- Selection and interaction with existing lines
- Keyboard navigation (Escape to cancel)

**Props:**

```typescript
interface LineZoneEditorProps {
  /** URL for the camera snapshot background image */
  snapshotUrl: string;
  /** Whether the component is in drawing mode */
  isDrawing?: boolean;
  /** Color for the line being drawn */
  lineColor?: string;
  /** Whether to show direction indicator arrow */
  showDirection?: boolean;
  /** Existing line zones to display */
  existingLines?: [Point, Point][];
  /** Currently selected line index */
  selectedLineIndex?: number;
  /** Callback when line drawing is complete */
  onLineComplete?: (points: [Point, Point]) => void;
  /** Callback when drawing is cancelled */
  onCancel?: () => void;
  /** Callback when an existing line is selected */
  onLineSelect?: (index: number) => void;
}
```

### PolygonZoneEditor.tsx (NEM-3720)

**Purpose:** Component for drawing polygon zones (restricted areas) on camera feeds

**Key Features:**

- Multi-point polygon drawing
- Polygon preview while drawing
- Vertex markers with visual feedback
- Minimum 3 points requirement
- Undo last point (Ctrl+Z)
- Zone type styling and indicators
- Display of existing polygon zones
- Selection and interaction with existing zones
- Keyboard navigation (Escape to cancel, Enter to complete)

**Props:**

```typescript
interface PolygonZoneEditorProps {
  /** URL for the camera snapshot background image */
  snapshotUrl: string;
  /** Whether the component is in drawing mode */
  isDrawing?: boolean;
  /** Type of zone being created (for styling) */
  zoneType?: ZoneType;
  /** Color for the zone being drawn */
  zoneColor?: string;
  /** Existing zones to display */
  existingZones?: ExistingZone[];
  /** Currently selected zone ID */
  selectedZoneId?: string;
  /** Callback when polygon drawing is complete */
  onPolygonComplete?: (points: Point[]) => void;
  /** Callback when drawing is cancelled */
  onCancel?: () => void;
  /** Callback when an existing zone is selected */
  onZoneSelect?: (zoneId: string) => void;
}
```

### index.ts

**Barrel exports:**

```typescript
export { default as ZoneEditor } from './ZoneEditor';
export { default as ZoneCanvas } from './ZoneCanvas';
export { default as ZoneForm } from './ZoneForm';
export { default as ZoneList } from './ZoneList';
export { default as LineZoneEditor } from './LineZoneEditor';
export { default as PolygonZoneEditor } from './PolygonZoneEditor';
export { default as CameraZoneOverlay } from './CameraZoneOverlay';

export type { ZoneEditorProps } from './ZoneEditor';
export type { ZoneCanvasProps, Point } from './ZoneCanvas';
export type { ZoneFormProps, ZoneFormData } from './ZoneForm';
export type { ZoneListProps } from './ZoneList';
export type { LineZoneEditorProps } from './LineZoneEditor';
export type { PolygonZoneEditorProps, ExistingZone } from './PolygonZoneEditor';
export type { CameraZoneOverlayProps, OverlayMode } from './CameraZoneOverlay';
```

## Important Patterns

### Zone Data Model

```typescript
interface Zone {
  id: string;
  camera_id: string;
  name: string;
  zone_type: ZoneType;
  shape: ZoneShape;
  coordinates: Point[]; // Normalized 0-1 range
  color: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

type ZoneShape = 'rectangle' | 'polygon';
type ZoneType = 'entry' | 'perimeter' | 'interior' | 'restricted';
```

### Coordinate Normalization

Coordinates are stored as normalized values (0-1 range) to be resolution-independent:

```typescript
// Convert pixel to normalized
const normalizedX = pixelX / imageWidth;
const normalizedY = pixelY / imageHeight;

// Convert normalized to pixel for display
const pixelX = normalizedX * displayWidth;
const pixelY = normalizedY * displayHeight;
```

### Drawing Mode Flow

```
1. User clicks "Draw Zone" button
2. ZoneEditor enters 'draw' mode
3. User selects shape (rectangle or polygon)
4. User clicks on canvas to place points
5. For rectangle: 2 clicks define corners
6. For polygon: multiple clicks, double-click or Enter to finish
7. ZoneCanvas calls onDrawComplete with coordinates
8. ZoneEditor enters 'create' mode
9. ZoneForm shown for zone properties
10. On submit, API creates zone
11. ZoneEditor returns to 'view' mode
```

## Styling Conventions

### ZoneEditor Modal

- Modal: bg-[#1A1A1A], border-gray-800, shadow-2xl
- Max width: 1200px (6xl)
- Max height: calc(100vh - 100px)
- Header: border-b border-gray-800

### ZoneCanvas

- Canvas: bg-black, rounded-lg
- Zone polygon: fill-opacity-30, stroke-width-2
- Selected zone: stroke-width-3, stroke-[#76B900]
- Drawing points: fill-[#76B900], r=6

### ZoneForm

- Form: bg-[#1F1F1F], rounded-lg, p-4
- Inputs: bg-[#1A1A1A], border-gray-700, focus:border-[#76B900]
- Save button: bg-[#76B900], text-black

### ZoneList

- List: bg-[#1F1F1F], border-gray-800
- Row: hover:bg-[#76B900]/5
- Color indicator: w-4 h-4 rounded-full
- Type badge: bg-gray-800, text-gray-300

## Testing

Comprehensive test coverage:

- `ZoneEditor.test.tsx` - Modal lifecycle, mode transitions, zone CRUD, drawing flow
- `ZoneCanvas.test.tsx` - Rendering, drawing interactions, coordinate calculations
- `ZoneForm.test.tsx` - Form validation, submission, field interactions
- `ZoneList.test.tsx` - List rendering, selection, action buttons
- `LineZoneEditor.test.tsx` - Line drawing, start/end points, direction arrows, cancellation
- `PolygonZoneEditor.test.tsx` - Polygon drawing, multi-point, undo, zone type styling

## Entry Points

**Start here:** `ZoneEditor.tsx` - Understand the overall zone management modal
**Then explore:** `ZoneCanvas.tsx` - See drawing and display logic
**Next:** `ZoneList.tsx` - Learn list patterns
**Finally:** `ZoneForm.tsx` - Understand form patterns

## Dependencies

- `@headlessui/react` - Dialog, Transition for modal
- `lucide-react` - Icons (MapPin, PenTool, Plus, Square, X, AlertCircle)
- `clsx` - Conditional class composition
- `react` - useState, useEffect, useCallback, Fragment
- `../../services/api` - fetchZones, createZone, updateZone, deleteZone, getCameraSnapshotUrl

## API Endpoints Used

- `GET /api/cameras/:id/zones` - List zones for camera
- `POST /api/cameras/:id/zones` - Create new zone
- `PUT /api/zones/:id` - Update zone
- `DELETE /api/zones/:id` - Delete zone
- `GET /api/cameras/:id/snapshot` - Get camera snapshot for canvas background

## Future Enhancements

- Zone templates (predefined common zones)
- Copy zone to other cameras
- Zone activity heatmap
- Zone-specific alert rules
- Multi-zone selection
- Zone grouping
- Zone import/export
- AI-suggested zones based on detection patterns
