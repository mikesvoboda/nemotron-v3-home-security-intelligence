# Exports Components Directory

## Purpose

Contains React components for data export functionality, providing modal-based export job creation and progress tracking. These components enable users to export events, alerts, or full backups in various formats (CSV, JSON, Excel, ZIP) with filtering options.

## Files

| File                                    | Purpose                                      |
| --------------------------------------- | -------------------------------------------- |
| `ExportModal.tsx`                       | Modal for configuring and starting exports   |
| `ExportProgress.tsx`                    | Progress tracking for running export jobs    |
| `__tests__/ExportProgress.test.tsx`     | Test suite for ExportProgress                |

## Key Components

### ExportModal.tsx

**Purpose:** Modal dialog for initiating and tracking export jobs

**Key Features:**

- Export type selection (events, alerts, full backup)
- Format selection (CSV, JSON, Excel, ZIP)
- Filter options:
  - Camera selection
  - Risk level filter
  - Date range picker
  - Review status filter
- Progress tracking integration via ExportProgress
- Success/error feedback

**Layout:**

```
+------------------------------------------+
|  Export Data                          [X] |
+------------------------------------------+
|  Export Type:  [Events v]                 |
|  Format:       [CSV v]                    |
|  Camera:       [All cameras v]            |
|  Risk Level:   [All levels v]             |
|  Start Date:   [____/____/____]           |
|  End Date:     [____/____/____]           |
|  Review Status:[All events v]             |
+------------------------------------------+
|  [Cancel]              [Start Export]     |
+------------------------------------------+
```

**Props Interface:**

```typescript
interface ExportModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** Pre-populate filters */
  initialFilters?: Partial<ExportJobCreateParams>;
  /** Callback when export completes */
  onExportComplete?: (success: boolean) => void;
}
```

**Related:** NEM-2386

---

### ExportProgress.tsx

**Purpose:** Real-time progress tracking for running export jobs

**Key Features:**

- Progress bar with percentage
- Status indicators (pending, running, completed, failed)
- Estimated time remaining
- Cancel export option
- Download link on completion
- Error message display

**Props Interface:**

```typescript
interface ExportProgressProps {
  /** Job ID to track */
  jobId: string;
  /** Callback when export completes successfully */
  onComplete?: () => void;
  /** Callback when export fails */
  onError?: (error: string) => void;
  /** Callback when export is cancelled */
  onCancel?: () => void;
}
```

## Types

### ExportType

Export content type:

```typescript
type ExportType = 'events' | 'alerts' | 'full_backup';
```

### ExportFormat

Export file format:

```typescript
type ExportFormat = 'csv' | 'json' | 'excel' | 'zip';
```

### ExportJobCreateParams

Parameters for creating an export job:

```typescript
interface ExportJobCreateParams {
  export_type: ExportType;
  export_format: ExportFormat;
  camera_id: string | null;
  risk_level: string | null;
  start_date: string | null;
  end_date: string | null;
  reviewed: boolean | null;
}
```

## Related Hooks

- `useDateRangeState` - Date range selection state management (without URL persistence for modals)

## Styling

- Dark theme with NVIDIA branding
- Background colors: `#1A1A1A`, `#121212`
- Primary accent: `#76B900` (NVIDIA Green)
- Tremor Card component for modal styling
- Progress bar colors based on status

## API Endpoints Used

- `GET /api/cameras` - Fetch cameras for filter dropdown
- `POST /api/exports` - Create export job
- `GET /api/jobs/{job_id}` - Poll job status
- `DELETE /api/jobs/{job_id}` - Cancel export job

## Entry Points

**Start here:** `ExportModal.tsx` - Main modal component for export configuration
**Then explore:** `ExportProgress.tsx` - Progress tracking component

## Dependencies

- `@tremor/react` - Button, Select, SelectItem, Card, Title, Text
- `lucide-react` - AlertCircle, Download, FileSpreadsheet, FileText, Loader2, X icons
- `clsx` - Conditional class composition
- `../../hooks/useDateRangeState` - Date range state hook
- `../../services/api` - startExportJob, fetchCameras
- `../../types/export` - Export type definitions
