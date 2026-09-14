# Backup Components Directory

## Purpose

Components for database backup and restore operations in the NVIDIA Security Intelligence home security monitoring dashboard. Provides a complete backup management interface with create, download, delete, and restore functionality.

## Key Components

| File                 | Purpose                                            |
| -------------------- | -------------------------------------------------- |
| `BackupSection.tsx`  | Main backup management container with all features |
| `BackupList.tsx`     | Table display of available backups with actions    |
| `BackupProgress.tsx` | Progress indicator for running backup/restore jobs |
| `RestoreModal.tsx`   | Modal dialog for file upload and restore flow      |
| `index.ts`           | Barrel exports for all components and types        |

## Component Details

### BackupSection

Main orchestrator component integrating all backup functionality.

**Features:**
- Create new backups with progress tracking
- View list of existing backups
- Download completed backups
- Delete backups with confirmation
- Restore from backup file via modal

**Props:**
| Prop        | Type     | Description      |
| ----------- | -------- | ---------------- |
| `className` | `string` | Optional CSS class |

**Usage:**
```tsx
<BackupSection />
```

### BackupList

Displays a list of available backups with status indicators and actions.

**Features:**
- Shows backup ID, status badge, creation date, and file size
- Download button for completed backups
- Delete button with confirmation dialog
- Loading skeleton, empty state, and error state

**Props:**
| Prop           | Type                               | Description                        |
| -------------- | ---------------------------------- | ---------------------------------- |
| `backups`      | `BackupListItem[]`                 | List of backup items               |
| `isLoading`    | `boolean`                          | Whether list is loading            |
| `isError`      | `boolean`                          | Whether there's an error           |
| `errorMessage` | `string`                           | Error message if any               |
| `onDelete`     | `(backupId: string) => Promise<void>` | Delete callback              |
| `isDeleting`   | `boolean`                          | Whether delete is in progress      |
| `deletingId`   | `string`                           | ID of backup being deleted         |
| `onRetry`      | `() => void`                       | Retry callback for errors          |
| `className`    | `string`                           | Optional CSS class                 |

**Status Types:**
- `pending` - Yellow badge, clock icon
- `running` - Blue badge, spinning loader
- `completed` - Green badge, checkmark icon
- `failed` - Red badge, X icon

### BackupProgress

Visual progress indicator for running backup or restore jobs.

**Features:**
- Progress bar with percentage display
- Status badge showing current state
- Current step description
- Tables progress (X of Y tables)
- Error message display for failures
- Success message on completion

**Props:**
| Prop           | Type                                    | Description                |
| -------------- | --------------------------------------- | -------------------------- |
| `progress`     | `BackupJobProgress \| RestoreJobProgress` | Progress information     |
| `status`       | `string`                                | Current status label       |
| `errorMessage` | `string \| null`                        | Error message if failed    |
| `isComplete`   | `boolean`                               | Whether job is complete    |
| `isFailed`     | `boolean`                               | Whether job failed         |
| `className`    | `string`                                | Optional CSS class         |
| `size`         | `'sm' \| 'md'`                          | Size variant               |

### RestoreModal

Multi-step modal dialog for restore operations.

**Features:**
- Drag and drop file upload
- Warning banner about data overwrite
- Upload progress indicator
- Restore progress with polling
- Success state with items restored summary
- Error state with retry option

**Modal States:**
- `upload` - File dropzone with warning
- `uploading` - Upload progress spinner
- `restoring` - Restore progress with BackupProgress
- `complete` - Success message with items restored count
- `error` - Error message with retry button

**Props:**
| Prop                | Type         | Description                     |
| ------------------- | ------------ | ------------------------------- |
| `isOpen`            | `boolean`    | Whether modal is open           |
| `onClose`           | `() => void` | Close callback                  |
| `onRestoreComplete` | `() => void` | Callback when restore completes |

## Data Flow

```
BackupSection
├── useBackupList()         → fetches backup list
├── useCreateBackup()       → mutation for creating backups
├── useDeleteBackup()       → mutation for deleting backups
├── useBackupJob()          → polls active backup job status
├── BackupList              → displays backup list
│   └── BackupRow           → individual backup with actions
├── BackupProgress          → shows active backup progress
└── RestoreModal
    ├── useStartRestore()   → mutation for starting restore
    └── useRestoreJob()     → polls restore job status
```

## Hooks Used

| Hook              | Source                               | Purpose                     |
| ----------------- | ------------------------------------ | --------------------------- |
| `useBackupList`   | `frontend/src/hooks/useBackup.ts`    | Fetch list of backups       |
| `useBackupJob`    | `frontend/src/hooks/useBackup.ts`    | Poll backup job status      |
| `useCreateBackup` | `frontend/src/hooks/useBackup.ts`    | Start new backup mutation   |
| `useDeleteBackup` | `frontend/src/hooks/useBackup.ts`    | Delete backup mutation      |
| `useRestoreJob`   | `frontend/src/hooks/useBackup.ts`    | Poll restore job status     |
| `useStartRestore` | `frontend/src/hooks/useBackup.ts`    | Start restore from file     |

## Test Coverage

No test files currently exist in this directory. Tests should cover:
- BackupList loading, empty, and error states
- BackupList delete confirmation flow
- BackupProgress visual states (pending, running, complete, failed)
- RestoreModal multi-step flow
- RestoreModal file validation
- BackupSection integration with hooks

## Related Files

| File                                  | Purpose                    |
| ------------------------------------- | -------------------------- |
| `frontend/src/hooks/useBackup.ts`     | Backup/restore hooks       |
| `frontend/src/types/backup.ts`        | Backup type definitions    |
| `frontend/src/services/backupApi.ts`  | API functions for backups  |

## Entry Points

- **Start here:** `BackupSection.tsx` - Main component used in settings page
- **For customization:** `BackupList.tsx` - Standalone backup list display
