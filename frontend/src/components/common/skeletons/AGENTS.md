# Skeleton Components Directory

## Purpose

Contains loading skeleton components for various UI elements. These components provide visual placeholders with shimmer animations while content is being loaded, improving perceived performance and preventing layout shift.

## Files

| File                          | Purpose                                    | Status |
| ----------------------------- | ------------------------------------------ | ------ |
| `AlertCardSkeleton.tsx`       | Loading skeleton for alert cards           | Active |
| `AlertCardSkeleton.test.tsx`  | Test suite for AlertCardSkeleton           | Active |
| `CameraCardSkeleton.tsx`      | Loading skeleton for camera cards          | Active |
| `CameraCardSkeleton.test.tsx` | Test suite for CameraCardSkeleton          | Active |
| `ChartSkeleton.tsx`           | Loading skeleton for charts                | Active |
| `ChartSkeleton.test.tsx`      | Test suite for ChartSkeleton               | Active |
| `EntityCardSkeleton.tsx`      | Loading skeleton for entity cards          | Active |
| `EntityCardSkeleton.test.tsx` | Test suite for EntityCardSkeleton          | Active |
| `EventCardSkeleton.tsx`       | Loading skeleton for event cards           | Active |
| `EventCardSkeleton.test.tsx`  | Test suite for EventCardSkeleton           | Active |
| `StatsCardSkeleton.tsx`       | Loading skeleton for stats cards           | Active |
| `StatsCardSkeleton.test.tsx`  | Test suite for StatsCardSkeleton           | Active |
| `TableRowSkeleton.tsx`        | Loading skeleton for table rows            | Active |
| `TableRowSkeleton.test.tsx`   | Test suite for TableRowSkeleton            | Active |
| `index.ts`                    | Barrel exports for skeleton components     | Active |

## Key Components

### AlertCardSkeleton.tsx

**Purpose:** Loading placeholder matching AlertCard layout

**Props Interface:**

```typescript
interface AlertCardSkeletonProps {
  className?: string;
}
```

**Key Features:**
- Severity accent bar on left edge
- Header with camera name and status badge placeholders
- Timestamp with icon placeholder
- Risk badge placeholder
- Alert summary (2-line text)
- Action buttons row

---

### CameraCardSkeleton.tsx

**Purpose:** Loading placeholder matching CameraCard layout

**Props Interface:**

```typescript
interface CameraCardSkeletonProps {
  className?: string;
}
```

**Key Features:**
- Aspect-ratio video thumbnail area
- Status indicator badge (top-right)
- Camera name footer with timestamp

---

### ChartSkeleton.tsx

**Purpose:** Loading placeholder for chart components

**Props Interface:**

```typescript
interface ChartSkeletonProps {
  height?: number;  // Default: 300
  className?: string;
}
```

**Key Features:**
- Y-axis labels (5 items)
- Bar/line chart area with 10 animated bars
- X-axis labels (10 items)
- Configurable height

---

### EntityCardSkeleton.tsx

**Purpose:** Loading placeholder matching EntityCard layout

**Props Interface:**

```typescript
interface EntityCardSkeletonProps {
  className?: string;
}
```

**Key Features:**
- Header with entity type badge and ID
- Thumbnail area (128px height)
- Two-column stats (Appearances / Cameras)
- Timestamp rows with icons

---

### EventCardSkeleton.tsx

**Purpose:** Loading placeholder matching EventCard layout

**Props Interface:**

```typescript
interface EventCardSkeletonProps {
  className?: string;
}
```

**Key Features:**
- Thumbnail column (64x64)
- Header with title, timestamp, and risk badge
- Object type badges row
- Risk score progress bar
- Summary text (2 lines)
- Detections section with badge placeholders

---

### StatsCardSkeleton.tsx

**Purpose:** Loading placeholder matching stat card layout

**Props Interface:**

```typescript
interface StatsCardSkeletonProps {
  className?: string;
}
```

**Key Features:**
- Icon placeholder (48x48)
- Value placeholder (large text)
- Label placeholder (smaller text)
- Horizontal layout with gap

---

### TableRowSkeleton.tsx

**Purpose:** Loading placeholder for table rows

**Props Interface:**

```typescript
interface TableRowSkeletonProps {
  columns?: number;  // Default: 4
  rows?: number;     // Default: 1
  className?: string;
}
```

**Key Features:**
- Configurable column count
- Configurable row count
- Variable widths for visual variety (96, 128, 80, 112, 64, 160px cycle)
- Divider between rows

## Patterns

### Common Props

All skeleton components accept an optional `className` prop for additional styling.

### Accessibility

All skeletons include:
- `aria-hidden="true"` - Hidden from screen readers
- `role="presentation"` - Indicates decorative content
- `data-testid` - For test targeting

### Animation

All skeletons use the `animate-shimmer` animation class via the base `Skeleton` component. The shimmer effect creates a subtle loading indication.

### Variant Usage

The base `Skeleton` component supports variants:
- `text` - For text lines (single or multi-line with `lines` prop)
- `circular` - For circular elements (icons, avatars)
- `rectangular` - For boxes, cards, images

### Layout Matching

Each skeleton closely matches its corresponding component's layout to prevent layout shift when content loads. Dimensions are matched to the actual component sizes.

## Usage Example

```tsx
import { EventCardSkeleton, CameraCardSkeleton, ChartSkeleton } from '../common/skeletons';

// Single skeleton
{isLoading && <EventCardSkeleton />}

// Multiple skeletons
{isLoading && (
  <div className="space-y-4">
    {Array.from({ length: 3 }).map((_, i) => (
      <EventCardSkeleton key={i} />
    ))}
  </div>
)}

// Table loading
{isLoading && <TableRowSkeleton columns={5} rows={10} />}
```

## Dependencies

- `clsx` - Conditional class composition
- `../Skeleton` - Base skeleton component with shimmer animation

## Entry Points

**Start here:** `index.ts` - Barrel exports for all skeletons
**Base component:** `../Skeleton.tsx` - Provides shimmer animation and variants

## Related Components

Each skeleton corresponds to a content component:

| Skeleton              | Content Component                |
| --------------------- | -------------------------------- |
| AlertCardSkeleton     | AlertCard (alerts page)          |
| CameraCardSkeleton    | CameraCard (cameras grid)        |
| ChartSkeleton         | Various Recharts components      |
| EntityCardSkeleton    | EntityCard (re-id entities)      |
| EventCardSkeleton     | EventCard (timeline/alerts)      |
| StatsCardSkeleton     | StatsCard (dashboard)            |
| TableRowSkeleton      | Table rows (various tables)      |
