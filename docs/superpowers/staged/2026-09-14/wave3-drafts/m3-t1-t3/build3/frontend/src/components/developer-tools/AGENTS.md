# Developer Tools Components Directory

## Purpose

Contains React components for the Developer Tools page, providing debugging, profiling, and development utilities for the home security system. These components enable developers to inspect system configuration, capture performance profiles, record/replay requests, manage log levels, generate test data, and monitor memory usage.

## Files

| File                            | Purpose                                                |
| ------------------------------- | ------------------------------------------------------ |
| `DeveloperToolsPage.tsx`        | Main page with collapsible sections for all dev tools  |
| `DeveloperToolsPage.test.tsx`   | Test suite for DeveloperToolsPage                      |
| `CircuitBreakerDebugPanel.tsx`  | Circuit breaker state inspection and management        |
| `CircuitBreakerDebugPanel.test.tsx` | Test suite for CircuitBreakerDebugPanel            |
| `CleanupRow.tsx`                | Individual row for cleanup operations in TestDataPanel |
| `CleanupRow.test.tsx`           | Test suite for CleanupRow                              |
| `ConfigInspectorPanel.tsx`      | System configuration inspection with JSON viewer       |
| `ConfigInspectorPanel.test.tsx` | Test suite for ConfigInspectorPanel                    |
| `ConfirmWithTextDialog.tsx`     | Confirmation dialog requiring text input               |
| `ConfirmWithTextDialog.test.tsx`| Test suite for ConfirmWithTextDialog                   |
| `LogLevelPanel.tsx`             | Runtime log level configuration                        |
| `LogLevelPanel.test.tsx`        | Test suite for LogLevelPanel                           |
| `MemorySnapshotPanel.tsx`       | Memory profiling and snapshot capture                  |
| `MemorySnapshotPanel.test.tsx`  | Test suite for MemorySnapshotPanel                     |
| `ProfilingPanel.tsx`            | Performance profiling with CPU/memory monitoring       |
| `ProfilingPanel.test.tsx`       | Test suite for ProfilingPanel                          |
| `RecordingDetailModal.tsx`      | Modal for viewing recording details                    |
| `RecordingDetailModal.test.tsx` | Test suite for RecordingDetailModal                    |
| `RecordingReplayPanel.tsx`      | Request recording and replay functionality             |
| `RecordingReplayPanel.test.tsx` | Test suite for RecordingReplayPanel                    |
| `RecordingsList.tsx`            | List of captured request recordings                    |
| `RecordingsList.test.tsx`       | Test suite for RecordingsList                          |
| `ReplayResultsModal.tsx`        | Modal showing replay comparison results                |
| `ReplayResultsModal.test.tsx`   | Test suite for ReplayResultsModal                      |
| `SeedRow.tsx`                   | Individual row for seed data operations                |
| `SeedRow.test.tsx`              | Test suite for SeedRow                                 |
| `TestDataPanel.tsx`             | Test data generation and cleanup utilities             |
| `TestDataPanel.test.tsx`        | Test suite for TestDataPanel                           |

## Key Components

### DeveloperToolsPage.tsx

**Purpose:** Main developer tools dashboard with collapsible sections for all debugging utilities

**Key Features:**

- Collapsible sections for each tool category
- Performance profiling panel
- Request recording and replay panel
- Configuration inspector panel
- Log level control panel
- Test data generation panel
- Memory snapshot panel
- Circuit breaker debug panel

**Layout:**

```
+------------------------------------------------+
|   Developer Tools                     [Header] |
+------------------------------------------------+
| [>] Performance Profiling                      |
|     ProfilingPanel                             |
+------------------------------------------------+
| [>] Request Recording                          |
|     RecordingReplayPanel                       |
+------------------------------------------------+
| [>] Configuration Inspector                    |
|     ConfigInspectorPanel                       |
+------------------------------------------------+
| [>] Log Level                                  |
|     LogLevelPanel                              |
+------------------------------------------------+
| [>] Test Data                                  |
|     TestDataPanel                              |
+------------------------------------------------+
| [>] Memory Snapshot                            |
|     MemorySnapshotPanel                        |
+------------------------------------------------+
| [>] Circuit Breakers                           |
|     CircuitBreakerDebugPanel                   |
+------------------------------------------------+
```

**No props** - Top-level page component

**Related:** NEM-2719

---

### ProfilingPanel.tsx

**Purpose:** Performance profiling with CPU/memory snapshot capture

**Key Features:**

- Start/stop profiling controls
- CPU and memory usage display
- Profile duration tracking
- Download profile data
- Auto-refresh during profiling

---

### RecordingReplayPanel.tsx

**Purpose:** Request recording and replay for debugging API interactions

**Key Features:**

- Start/stop recording controls
- RecordingsList for viewing captures
- RecordingDetailModal for request details
- ReplayResultsModal for comparison results
- Filter by request type

---

### ConfigInspectorPanel.tsx

**Purpose:** Read-only inspection of system configuration

**Key Features:**

- Hierarchical JSON tree view
- Search/filter configuration values
- Copy configuration to clipboard
- Expandable sections

---

### LogLevelPanel.tsx

**Purpose:** Runtime log level configuration

**Key Features:**

- Log level selector (DEBUG, INFO, WARNING, ERROR)
- Per-logger configuration
- Immediate application of changes
- Persistence indicator

---

### TestDataPanel.tsx

**Purpose:** Test data generation and cleanup utilities

**Key Features:**

- Seed data generation with SeedRow components
- Cleanup operations with CleanupRow components
- ConfirmWithTextDialog for destructive operations
- Progress indicators

---

### MemorySnapshotPanel.tsx

**Purpose:** Memory profiling and heap snapshot capture

**Key Features:**

- Capture memory snapshots
- View memory usage trends
- Download heap dumps
- Garbage collection trigger

---

### CircuitBreakerDebugPanel.tsx

**Purpose:** Circuit breaker state inspection and manual control

**Key Features:**

- View all circuit breaker states
- Manual open/close controls
- Failure count display
- State transition history

---

### ConfirmWithTextDialog.tsx

**Purpose:** Confirmation dialog requiring exact text match for destructive operations

**Key Features:**

- Text input validation
- Customizable confirmation text
- Cancel/confirm actions
- Error state handling

**Props Interface:**

```typescript
interface ConfirmWithTextDialogProps {
  isOpen: boolean;
  title: string;
  description: string;
  confirmText: string; // Text user must type to confirm
  confirmLabel: string;
  variant?: 'default' | 'warning' | 'danger';
  isLoading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}
```

---

### RecordingsList.tsx

**Purpose:** List view of captured request recordings

**Key Features:**

- Timestamp display
- Request method and URL
- Response status
- Click to view details
- Delete recordings

---

### RecordingDetailModal.tsx

**Purpose:** Detailed view of a captured request/response

**Key Features:**

- Request headers and body
- Response headers and body
- Timing information
- Replay button

---

### ReplayResultsModal.tsx

**Purpose:** Comparison of original vs replayed request results

**Key Features:**

- Side-by-side comparison
- Diff highlighting
- Status comparison
- Body diff view

---

### SeedRow.tsx

**Purpose:** Individual row for seed data generation operations

**Key Features:**

- Entity type selection
- Count input
- Generate button
- Progress indicator

---

### CleanupRow.tsx

**Purpose:** Individual row for data cleanup operations

**Key Features:**

- Entity type display
- Count of items to delete
- Delete button
- Confirmation requirement

## Related Hooks

- `useDevToolsSections` - Manages collapsible section open/close state
- `useSystemConfigQuery` - Fetches system configuration data

## Styling

- Dark theme with NVIDIA branding
- Background colors: `#1A1A1A`, `#121212`
- Primary accent: `#76B900` (NVIDIA Green)
- Collapsible sections with chevron indicators

## API Endpoints Used

- `GET /api/system/config` - System configuration
- `POST /api/debug/profile/start` - Start profiling
- `POST /api/debug/profile/stop` - Stop profiling
- `GET /api/debug/recordings` - List recordings
- `POST /api/debug/recordings/replay` - Replay recording
- `PUT /api/system/log-level` - Update log level
- `POST /api/debug/seed` - Generate test data
- `DELETE /api/debug/cleanup` - Cleanup test data
- `POST /api/debug/memory/snapshot` - Capture memory snapshot
- `GET /api/system/circuit-breakers` - Circuit breaker states

## Entry Points

**Start here:** `DeveloperToolsPage.tsx` - Main page integrating all developer tools
**Then explore:** `ProfilingPanel.tsx` - Performance profiling utilities
**Then explore:** `RecordingReplayPanel.tsx` - Request recording and replay
**Also see:** `TestDataPanel.tsx` - Test data generation
**Also see:** `ConfigInspectorPanel.tsx` - Configuration inspection

## Dependencies

- `@tremor/react` - Card, Text components
- `lucide-react` - Activity, Video, Settings, FileText, Database, HardDrive, Zap, Terminal icons
- `clsx` - Conditional class composition
- `../../hooks/useDevToolsSections` - Section state management
- `../../hooks/useSystemConfigQuery` - Configuration data hook
- `../system/CollapsibleSection` - Collapsible section wrapper
