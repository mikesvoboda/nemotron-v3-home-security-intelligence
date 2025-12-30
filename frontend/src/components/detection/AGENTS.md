# Detection Components Directory

## Purpose

Contains components for visualizing AI object detection results on images. Provides bounding box overlays with labels, confidence scores, and interactive features.

## Key Components

### DetectionImage.tsx

**Purpose:** Wrapper component that displays an image with bounding box overlays and optional lightbox

**Key Features:**

- Loads image and captures natural dimensions
- Renders BoundingBoxOverlay as absolute positioned SVG
- Handles image load event to provide dimensions to overlay
- Container uses relative positioning for overlay alignment
- Supports all BoundingBoxOverlay features via prop forwarding
- Optional lightbox integration for full-size image viewing
- Hover overlay with "Click to enlarge" hint when lightbox enabled

**Props:**

- `src: string` - Image URL (required)
- `alt: string` - Image alt text for accessibility (required)
- `boxes: BoundingBox[]` - Array of bounding boxes to display (required)
- `showLabels?: boolean` - Show object labels (default: true)
- `showConfidence?: boolean` - Show confidence scores (default: true)
- `minConfidence?: number` - Filter boxes below threshold (default: 0)
- `className?: string` - Additional CSS classes
- `onClick?: (box: BoundingBox) => void` - Click handler for boxes
- `enableLightbox?: boolean` - Enable lightbox on image click (default: false)
- `lightboxCaption?: string` - Caption to display in lightbox

**State:**

- `imageDimensions: { width: number; height: number } | null` - Natural image size
- `isLightboxOpen: boolean` - Controls lightbox visibility

**Pattern:**

```tsx
// Basic usage
<DetectionImage
  src="/images/front_door.jpg"
  alt="Front door camera"
  boxes={detections}
  showLabels={true}
  showConfidence={true}
/>

// With lightbox
<DetectionImage
  src="/images/front_door.jpg"
  alt="Front door camera"
  boxes={detections}
  enableLightbox={true}
  lightboxCaption="Person detected at 2:45 PM"
/>
```

**Dependencies:**

- `./BoundingBoxOverlay` - SVG bounding box rendering
- `../common/Lightbox` - Full-size image modal

### BoundingBoxOverlay.tsx

**Purpose:** SVG overlay that renders colored bounding boxes with labels over an image

**Key Features:**

- Pure SVG rendering for crisp, scalable boxes
- Color-coded by object type: person (red), car (blue), dog (amber), cat (purple), package (green)
- Custom colors supported via `box.color` property
- Label badges positioned above boxes with object name + confidence
- Minimum confidence filtering (hide boxes below threshold)
- Optional click handlers for interactive boxes
- Hover effects: stroke width increases on mouseover
- Handles edge cases: zero dimensions, no boxes, missing data

**Props:**

- `boxes: BoundingBox[]` - Array of bounding boxes (required)
- `imageWidth: number` - Natural image width in pixels (required)
- `imageHeight: number` - Natural image height in pixels (required)
- `showLabels?: boolean` - Display label badges (default: true)
- `showConfidence?: boolean` - Show confidence in labels (default: true)
- `minConfidence?: number` - Filter boxes below this value (default: 0)
- `onClick?: (box: BoundingBox) => void` - Click handler for boxes

**BoundingBox Interface:**

```typescript
{
  x: number;          // Top-left x coordinate (pixels)
  y: number;          // Top-left y coordinate (pixels)
  width: number;      // Box width (pixels)
  height: number;     // Box height (pixels)
  label: string;      // Object type: "person", "car", "dog", etc.
  confidence: number; // Confidence score 0-1
  color?: string;     // Optional custom color (e.g., "#ff0000")
}
```

**Default Colors:**

- person: #ef4444 (red) - Important for security
- car: #3b82f6 (blue) - Vehicle detection
- dog: #f59e0b (amber) - Pets
- cat: #8b5cf6 (purple) - Pets
- package: #10b981 (green) - Deliveries
- default: #6b7280 (gray) - Unknown objects

**SVG Structure:**

- Root SVG with `preserveAspectRatio="none"` for responsive scaling
- viewBox matches image natural dimensions
- Each box is a `<g>` group containing:
  - `<rect>` for bounding box (stroke only, no fill)
  - `<rect>` for label background (filled with object color)
  - `<text>` for label text (white)

**Interaction:**

- Boxes with onClick handler: pointer-events-auto, cursor-pointer
- Hover: stroke-width increases from 3 to 5
- Transition: 0.2s ease

### DetectionThumbnail.tsx

**Purpose:** Displays detection images with server-rendered bounding boxes from the API

**Key Features:**

- Fetches detection images from `/api/detections/{id}/image` endpoint
- Backend renders bounding boxes and confidence labels on the image
- Shows loading skeleton while image loads
- Handles error states with retry functionality
- Size variants: sm (120x90), md (240x180), lg (320x240)
- Supports click handlers with proper keyboard accessibility

**Props:**

- `detectionId: number` - Detection ID to fetch image for (required)
- `alt: string` - Image alt text for accessibility (required)
- `size?: DetectionThumbnailSize` - Size variant: 'sm' | 'md' | 'lg' (default: 'md')
- `className?: string` - Additional CSS classes
- `onClick?: () => void` - Click handler
- `showLoading?: boolean` - Show loading placeholder (default: true)
- `loadingPlaceholder?: ReactNode` - Custom loading component
- `errorComponent?: ReactNode` - Custom error component

**States:**

- `loading` - Shows skeleton while image loads
- `loaded` - Shows the image from API
- `error` - Shows error display with retry button

**Pattern:**

```tsx
<DetectionThumbnail
  detectionId={123}
  alt="Person detected at front door"
  size="md"
  onClick={() => openDetailModal(123)}
/>
```

**When to Use:**

- Use `DetectionThumbnail` when you want server-rendered bounding boxes (simpler, pre-rendered)
- Use `DetectionImage` when you need client-side control over bounding box rendering

### Example.tsx

**Purpose:** Example component demonstrating detection visualization usage

**Features:**

- Shows DetectionImage with sample detections
- Multiple object types with varying confidence
- Useful for development, testing, and documentation

### index.ts

**Purpose:** Barrel export for easy imports

**Exports:**

```typescript
export { default as BoundingBoxOverlay } from './BoundingBoxOverlay';
export type { BoundingBox, BoundingBoxOverlayProps } from './BoundingBoxOverlay';

export { default as DetectionImage } from './DetectionImage';
export type { DetectionImageProps } from './DetectionImage';

export { default as DetectionThumbnail } from './DetectionThumbnail';
export type { DetectionThumbnailProps, DetectionThumbnailSize } from './DetectionThumbnail';
```

**Usage:**

```tsx
import { DetectionImage, DetectionThumbnail, BoundingBoxOverlay } from '../detection';
import type { BoundingBox, DetectionThumbnailSize } from '../detection';
```

### README.md

**Purpose:** Comprehensive documentation for detection components

Contains:

- Component overview and purpose
- Usage examples with code snippets
- Props documentation
- Integration guide
- Performance notes
- Known limitations

## Important Patterns

### Component Composition

```
DetectionImage (wrapper)
  ├── <img> (base image)
  └── BoundingBoxOverlay (SVG overlay)
```

Separation of concerns:

- `DetectionImage` handles image loading and dimension extraction
- `BoundingBoxOverlay` handles pure SVG rendering

### Coordinate System

- Bounding boxes use pixel coordinates relative to natural image size
- SVG viewBox matches natural dimensions for 1:1 mapping
- preserveAspectRatio="none" allows responsive scaling without distortion

### Confidence Filtering

```typescript
const filteredBoxes = boxes.filter((box) => box.confidence >= minConfidence);
```

Allows showing only high-confidence detections:

- minConfidence=0.5 → Show only 50%+ confidence
- minConfidence=0.8 → Show only 80%+ confidence

### Label Positioning

Labels positioned above boxes at (x, y - 28):

- 24px label height + 4px spacing
- Background rect with rounded corners (rx="4")
- Dynamic width based on label length + confidence

### Color Coding Strategy

- Distinct colors for common object types
- Red for persons (security priority)
- Blue for vehicles
- Warm colors for pets
- Green for packages
- Gray fallback for unknown types

## Styling Conventions

### BoundingBoxOverlay

- Stroke width: 3px (normal), 5px (hover)
- Label font: 14px, 600 weight, Inter/system-ui
- Label background: 90% opacity for slight transparency
- Rounded corners on labels: 4px border-radius

### DetectionImage

- Container: relative positioning, inline-block
- Image: block display, w-full h-full, object-contain
- Overlay: absolute inset-0, z-10

## Testing

Comprehensive test suites:

- `DetectionImage.test.tsx` - Image loading, dimension capture, prop forwarding
- `BoundingBoxOverlay.test.tsx` - SVG rendering, colors, labels, filtering, click handlers
- `DetectionThumbnail.test.tsx` - API image loading, loading/error states, retry, accessibility

## Entry Points

**Start here:** `DetectionThumbnail.tsx` - Simple API-based image loading with server-rendered bboxes
**Then explore:** `DetectionImage.tsx` - Client-side bounding box rendering wrapper
**Deep dive:** `BoundingBoxOverlay.tsx` - Pure SVG rendering for bounding boxes
**Reference:** `README.md` - Usage examples and integration guide

## Dependencies

- `react` - useState hook, React.FC type
- No external UI libraries - pure SVG rendering

## Integration Examples

### With Event Components

```tsx
// EventCard.tsx
<DetectionImage
  src={event.thumbnail_url}
  alt={`${camera_name} detection`}
  boxes={convertToBoundingBoxes(event.detections)}
  showLabels={true}
  showConfidence={true}
/>
```

### With API Data

```typescript
// Convert API Detection[] to BoundingBox[]
const boxes = detections
  .filter((d) => d.bbox)
  .map((d) => ({
    x: d.bbox.x,
    y: d.bbox.y,
    width: d.bbox.width,
    height: d.bbox.height,
    label: d.label,
    confidence: d.confidence,
  }));
```

## Performance Considerations

### Optimization Strategies

1. **Image Loading:** Uses onLoad event to defer overlay until image ready
2. **SVG Efficiency:** Single SVG element with multiple child elements
3. **Filtering:** Client-side confidence filtering reduces rendered boxes
4. **Memoization:** Consider React.memo for BoundingBoxOverlay if many re-renders

### Large Image Handling

- Natural dimensions used (not displayed dimensions)
- SVG scales automatically via viewBox
- No canvas required (pure SVG is efficient for 10-20 boxes)

### Known Limitations

- Very large numbers of boxes (100+) may impact performance
- Label text doesn't wrap (may overflow for very long labels)
- No zoom/pan functionality (consider adding if needed)

## Future Enhancements

- **Zoom/Pan:** Interactive image viewer with detection overlay
- **Label Collision:** Avoid overlapping labels for dense detections
- **Animation:** Animate boxes on appear (fade in, scale up)
- **Tracks:** Show object tracks across frames (video support)
- **Editing:** Allow manual box adjustment (for annotation tools)
- **Export:** Export image with baked-in boxes (canvas rendering)
- **Confidence Slider:** Interactive UI control for minConfidence
- **Color Themes:** Support different color schemes (dark mode, high contrast)
