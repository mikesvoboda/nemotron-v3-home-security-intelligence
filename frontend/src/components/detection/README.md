# Detection Components

React components for visualizing object detections with bounding boxes.

## Components

### BoundingBoxOverlay

Renders SVG bounding boxes over images/video for detected objects.

**Features:**
- Color-coded boxes by object type or custom colors
- Labels with object type and confidence percentage
- Responsive scaling with container
- Click handler for individual boxes
- Confidence threshold filtering
- Hover effects for interactive boxes

**Props:**
```typescript
interface BoundingBoxOverlayProps {
  boxes: BoundingBox[];
  imageWidth: number;
  imageHeight: number;
  showLabels?: boolean;        // default: true
  showConfidence?: boolean;    // default: true
  minConfidence?: number;      // default: 0 (0-1 range)
  onClick?: (box: BoundingBox) => void;
}

interface BoundingBox {
  x: number;                   // top-left x (pixels)
  y: number;                   // top-left y (pixels)
  width: number;               // box width (pixels)
  height: number;              // box height (pixels)
  label: string;               // e.g., "person", "car"
  confidence: number;          // 0-1
  color?: string;              // optional custom color
}
```

**Default Colors:**
- `person`: Red (#ef4444)
- `car`: Blue (#3b82f6)
- `dog`: Amber (#f59e0b)
- `cat`: Purple (#8b5cf6)
- `package`: Green (#10b981)
- `default`: Gray (#6b7280)

**Example:**
```tsx
import { BoundingBoxOverlay, BoundingBox } from '@/components/detection';

const boxes: BoundingBox[] = [
  {
    x: 100,
    y: 100,
    width: 200,
    height: 300,
    label: 'person',
    confidence: 0.95,
  },
  {
    x: 400,
    y: 200,
    width: 150,
    height: 100,
    label: 'car',
    confidence: 0.87,
  },
];

function MyComponent() {
  return (
    <div className="relative">
      <img src="/camera-feed.jpg" alt="Camera" />
      <BoundingBoxOverlay
        boxes={boxes}
        imageWidth={1920}
        imageHeight={1080}
        minConfidence={0.7}
        onClick={(box) => console.log('Clicked:', box)}
      />
    </div>
  );
}
```

### DetectionImage

Convenience component that combines an image with bounding box overlay.

**Features:**
- Automatic dimension detection on image load
- All BoundingBoxOverlay features
- Proper stacking and positioning
- Responsive image handling

**Props:**
```typescript
interface DetectionImageProps {
  src: string;
  alt: string;
  boxes: BoundingBox[];
  showLabels?: boolean;
  showConfidence?: boolean;
  minConfidence?: number;
  className?: string;
  onClick?: (box: BoundingBox) => void;
}
```

**Example:**
```tsx
import { DetectionImage, BoundingBox } from '@/components/detection';

const boxes: BoundingBox[] = [
  {
    x: 100,
    y: 100,
    width: 200,
    height: 300,
    label: 'person',
    confidence: 0.95,
  },
];

function CameraView() {
  return (
    <DetectionImage
      src="/camera-feed.jpg"
      alt="Front door camera"
      boxes={boxes}
      showLabels={true}
      showConfidence={true}
      minConfidence={0.8}
      className="rounded-lg shadow-lg"
      onClick={(box) => console.log('Detection clicked:', box)}
    />
  );
}
```

## Use Cases

### Camera Grid with Detections
```tsx
function CameraGrid({ cameras }) {
  return (
    <div className="grid grid-cols-2 gap-4">
      {cameras.map((camera) => (
        <DetectionImage
          key={camera.id}
          src={camera.imageUrl}
          alt={camera.name}
          boxes={camera.detections}
          minConfidence={0.7}
          className="rounded-lg"
        />
      ))}
    </div>
  );
}
```

### Event Detail Modal
```tsx
function EventDetailModal({ event }) {
  const handleBoxClick = (box: BoundingBox) => {
    alert(`Detected ${box.label} with ${(box.confidence * 100).toFixed(0)}% confidence`);
  };

  return (
    <div className="modal">
      <DetectionImage
        src={event.imageUrl}
        alt="Event snapshot"
        boxes={event.detections}
        onClick={handleBoxClick}
        className="w-full max-h-96"
      />
    </div>
  );
}
```

### Custom Filtering
```tsx
function FilteredDetections() {
  const [minConf, setMinConf] = useState(0.5);
  const [showPeople, setShowPeople] = useState(true);

  const filteredBoxes = boxes.filter(box =>
    showPeople || box.label !== 'person'
  );

  return (
    <div>
      <input
        type="range"
        min="0"
        max="1"
        step="0.1"
        value={minConf}
        onChange={(e) => setMinConf(parseFloat(e.target.value))}
      />
      <DetectionImage
        src="/camera.jpg"
        alt="Camera"
        boxes={filteredBoxes}
        minConfidence={minConf}
      />
    </div>
  );
}
```

## Styling

Components use Tailwind CSS classes and are compatible with the NVIDIA dark theme:
- Overlay uses absolute positioning with `z-index: 10`
- SVG scales responsively with `preserveAspectRatio="none"`
- Labels have semi-transparent backgrounds
- Hover effects increase stroke width on clickable boxes

## Testing

Comprehensive tests cover:
- Rendering with multiple boxes
- Label and confidence display
- Confidence filtering
- Click handlers
- Edge cases (empty boxes, invalid dimensions)
- Responsive scaling
- Color schemes

Run tests:
```bash
cd frontend
npm test -- --run src/components/detection/
```
