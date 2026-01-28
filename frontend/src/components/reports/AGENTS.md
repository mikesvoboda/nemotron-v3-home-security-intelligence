# Reports Components

## Purpose

Components for creating and managing scheduled security reports in the NVIDIA Security Intelligence dashboard. Allows users to configure automated report generation with customizable schedules, formats, and delivery options.

**Related Issue:** NEM-3667 - Scheduled Reports Frontend UI

## Key Components

| File                           | Purpose                                           |
| ------------------------------ | ------------------------------------------------- |
| `ScheduledReportForm.tsx`      | Form for creating and editing scheduled reports   |
| `ScheduledReportForm.test.tsx` | Test suite for ScheduledReportForm                |
| `index.ts`                     | Barrel exports for report components              |

## Component Details

### ScheduledReportForm

A comprehensive form component for creating and editing scheduled report configurations.

**Props:**

| Prop              | Type                                                        | Default | Description                          |
| ----------------- | ----------------------------------------------------------- | ------- | ------------------------------------ |
| `report`          | `ScheduledReport?`                                          | -       | Existing report for editing          |
| `onSubmit`        | `(data: ScheduledReportCreate \| ScheduledReportUpdate) => Promise<void>` | - | Submit handler                      |
| `onCancel`        | `() => void`                                                | -       | Cancel handler                       |
| `isSubmitting`    | `boolean?`                                                  | `false` | Whether form is submitting           |
| `apiError`        | `string \| null?`                                           | -       | API error message                    |
| `onClearApiError` | `() => void?`                                               | -       | Clear API error callback             |

**Form Sections:**

1. **Basic Information**
   - Report name (required, max 255 chars)
   - Enabled toggle

2. **Schedule Configuration**
   - Frequency selector (daily, weekly, monthly)
   - Day of week selector (for weekly reports)
   - Day of month selector (for monthly reports)
   - Hour and minute selectors
   - Timezone selector

3. **Output Configuration**
   - Format buttons (PDF, CSV, JSON)
   - Include charts checkbox
   - Include event details checkbox

4. **Email Recipients**
   - Email input with Add button
   - Tag-style display of added emails
   - Remove button per email
   - Max 10 recipients

**Validation:**

| Field              | Rules                                           |
| ------------------ | ----------------------------------------------- |
| `name`             | Required, max 255 characters                    |
| `day_of_week`      | 0-6 (Monday-Sunday) for weekly reports          |
| `day_of_month`     | 1-31 for monthly reports                        |
| `email_recipients` | Valid email format, max 254 chars, max 10 total |

**Usage:**

```tsx
import { ScheduledReportForm } from '@/components/reports';

// Create mode
<ScheduledReportForm
  onSubmit={handleCreate}
  onCancel={handleCancel}
/>

// Edit mode
<ScheduledReportForm
  report={existingReport}
  onSubmit={handleUpdate}
  onCancel={handleCancel}
/>

// With error handling
<ScheduledReportForm
  onSubmit={handleSubmit}
  onCancel={handleCancel}
  isSubmitting={isPending}
  apiError={error?.message}
  onClearApiError={() => setError(null)}
/>
```

## Test Coverage

The test suite covers:

**Create Mode:**
- Empty form rendering
- Validation error for empty name
- Form submission with valid data
- Cancel button functionality

**Edit Mode:**
- Form population with existing report data
- Day of week selector for weekly frequency

**Frequency Selection:**
- Day of month selector for monthly
- Hidden day selectors for daily

**Email Recipients:**
- Adding email recipients
- Removing email recipients
- Adding email on Enter key

**Format Selection:**
- Selecting different output formats (PDF, CSV, JSON)

**Toggles:**
- Enabled state toggle
- Include charts checkbox
- Include event details checkbox

**Error Handling:**
- API error display
- Error dismissal via clear button

**Submitting State:**
- Disabled inputs when submitting
- Loading state on submit button

## Dependencies

- `clsx` - Conditional class composition
- `lucide-react` - Icons (AlertCircle, Plus, Trash2, X)
- `../../types/scheduledReport` - Type definitions and constants
- `../common/Button` - Shared button component

## Form State

```typescript
interface FormState {
  name: string;
  frequency: ReportFrequency;      // 'daily' | 'weekly' | 'monthly'
  day_of_week: number;             // 0-6 (Monday-Sunday)
  day_of_month: number;            // 1-31
  hour: number;                    // 0-23
  minute: number;                  // 0, 15, 30, 45
  timezone: string;                // e.g., 'UTC', 'America/New_York'
  format: ReportFormat;            // 'pdf' | 'csv' | 'json'
  enabled: boolean;
  email_recipients: string[];
  include_charts: boolean;
  include_event_details: boolean;
}
```

## Styling

Uses Tailwind CSS with NVIDIA dark theme:

- Form sections separated by `border-t border-gray-800`
- Input backgrounds: `bg-[#1A1A1A]`
- Input borders: `border-gray-700` (normal), `border-[#76B900]` (focus), `border-red-500` (error)
- Toggle switch: `bg-[#76B900]` (enabled), `bg-gray-600` (disabled)
- Format buttons: Selected with `border-[#76B900] bg-[#76B900]/10`
- Email tags: `bg-gray-700` rounded pills
