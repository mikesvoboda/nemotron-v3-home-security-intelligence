# Detection Components

## Purpose

Components for visualizing AI object detection results on camera images. Handles rendering bounding boxes, labels, confidence scores, and interactive detection overlays.

## Components

### BoundingBoxOverlay

SVG-based overlay that renders bounding boxes on top of images with labels and confidence scores.

**File:** `BoundingBoxOverlay.tsx`

**Props Interface:**

```typescript
interface BoundingBox {
  x: number; // Top-left x coordinate (pixels)
  y: number; // Top-left y coordinate (pixels)
  width: number; // Box width (pixels)
  height: number; // Box height (pixels)
  label: string; // Object type (e.g., "person", "car")
  confidence: number; // Detection confidence (0-1)
  color?: string; // Optional custom color (hex)
}

interface BoundingBoxOverlayProps {
  boxes: BoundingBox[];
  imageWidth: number;
  imageHeight: number;
  showLabels?: boolean; // Display labels (default: true)
  showConfidence?: boolean; // Show confidence % (default: true)
  minConfidence?: number; // Filter threshold (default: 0)
  onClick?: (box: BoundingBox) => void; // Click handler
}
```

**Features:**

- SVG-based rendering for crisp, scalable boxes
- Color-coded by object type:
  - Person: Red (`#ef4444`)
  - Car: Blue (`#3b82f6`)
  - Dog: Amber (`#f59e0b`)
  - Cat: Purple (`#8b5cf6`)
  - Package: Green (`#10b981`)
  - Default: Gray (`#6b7280`)
- Interactive hover effects (thicker stroke on hover)
- Confidence threshold filtering
- Label backgrounds with rounded corners
- Clickable boxes with optional callbacks

### DetectionImage

Wrapper component that combines an image with bounding box overlays, handling image loading and dimension tracking.

**File:** `DetectionImage.tsx`

**Props Interface:**

```typescript
interface DetectionImageProps {
  src: string; // Image URL or path
  alt: string; // Accessibility text
  boxes: BoundingBox[]; // Detection results
  showLabels?: boolean; // Pass through to overlay
  showConfidence?: boolean; // Pass through to overlay
  minConfidence?: number; // Pass through to overlay
  className?: string; // Container classes
  onClick?: (box: BoundingBox) => void; // Click handler
}
```

**Features:**

- Automatic image dimension detection via `onLoad` event
- Responsive container with `object-contain` sizing
- Lazy overlay rendering (waits for image load)
- Pass-through props to `BoundingBoxOverlay`
- Relative positioning for overlay stacking

### Example

Comprehensive example component demonstrating all detection features.

**File:** `Example.tsx`

**Exports:**

- `BasicExample` - Simple detection display
- `FilteredExample` - Confidence threshold slider
- `InteractiveExample` - Clickable detections with details
- `CustomizationExample` - Toggle labels and confidence
- `CameraGridExample` - Multi-camera layout
- `DetectionExamples` (default) - Tabbed example viewer

**Features:**

- Sample bounding box data
- Interactive demos
- Grid layout examples
- Color legend
- Confidence filtering UI

## Exports

The directory exports components via `index.ts`:

- `BoundingBoxOverlay` (default export)
- `BoundingBox` (type export)
- `BoundingBoxOverlayProps` (type export)
- `DetectionImage` (default export)
- `DetectionImageProps` (type export)

## Styling Approach

- **Tailwind CSS** for container and layout styling
- **SVG** for bounding box rendering (scalable, crisp at any size)
- **Absolute positioning** for overlay stacking
- **Pointer events** management (overlay transparent except boxes)
- **Transitions** for smooth hover effects
- Dark theme integration:
  - Semi-transparent label backgrounds
  - High contrast stroke colors
  - White text on colored backgrounds

## Usage Examples

```typescript
import { DetectionImage } from '@/components/detection';

// Basic usage
<DetectionImage
  src="/api/images/camera1/latest.jpg"
  alt="Front door camera"
  boxes={detections}
/>

// With confidence filtering
<DetectionImage
  src={imageUrl}
  alt="Camera feed"
  boxes={detections}
  minConfidence={0.7}
  showConfidence={true}
/>

// Interactive with click handler
<DetectionImage
  src={imageUrl}
  alt="Backyard camera"
  boxes={detections}
  onClick={(box) => console.log('Clicked:', box.label)}
/>
```

## Test Files

**Location:** Co-located with components

- `BoundingBoxOverlay.test.tsx` - Tests for SVG overlay rendering, filtering, colors, interactions
- `DetectionImage.test.tsx` - Tests for image loading, dimension tracking, overlay integration

**Coverage Requirements:**

- Rendering with various box configurations
- Color assignment logic
- Confidence filtering
- Label and confidence display toggling
- Click interaction handling
- Edge cases (empty boxes, invalid dimensions, missing data)
- Accessibility (alt text, keyboard navigation)
