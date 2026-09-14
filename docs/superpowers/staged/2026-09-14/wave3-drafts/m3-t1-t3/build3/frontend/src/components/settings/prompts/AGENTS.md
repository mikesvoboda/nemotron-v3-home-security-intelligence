# Prompt Management Components Directory

## Purpose

Contains components for managing AI model prompt configurations. These components provide the UI for viewing, editing, testing, and importing/exporting prompt configurations across all AI models used in the security monitoring system.

## Files

| File                            | Purpose                                                        | Status |
| ------------------------------- | -------------------------------------------------------------- | ------ |
| `ConfigDiffView.tsx`            | Display configuration diff for a single model with highlighting | Active |
| `ConfigDiffView.test.tsx`       | Test suite for ConfigDiffView                                  | Active |
| `EventSelector.tsx`             | Searchable event selector for A/B testing                      | Active |
| `EventSelector.test.tsx`        | Test suite for EventSelector                                   | Active |
| `ImportExportButtons.tsx`       | Export/Import buttons with file handling and preview modal     | Active |
| `ImportExportButtons.test.tsx`  | Test suite for ImportExportButtons                             | Active |
| `ImportPreviewModal.tsx`        | Modal for previewing import changes before applying            | Active |
| `ImportPreviewModal.test.tsx`   | Test suite for ImportPreviewModal                              | Active |
| `PromptConfigEditor.tsx`        | Modal for editing AI model prompt configurations               | Active |
| `PromptConfigEditor.test.tsx`   | Test suite for PromptConfigEditor                              | Active |
| `PromptManagementPage.tsx`      | Main page for managing AI model prompt configurations          | Active |
| `PromptManagementPage.test.tsx` | Test suite for PromptManagementPage                            | Active |
| `PromptTestModal.tsx`           | A/B testing modal for prompt configuration comparison          | Active |
| `PromptTestModal.test.tsx`      | Test suite for PromptTestModal                                 | Active |
| `TestResultsComparison.tsx`     | Side-by-side comparison of A/B test results                    | Active |
| `TestResultsComparison.test.tsx`| Test suite for TestResultsComparison                           | Active |
| `index.ts`                      | Barrel exports for prompt management components                | Active |

## Subdirectories

### model-forms/

Model-specific configuration forms for each AI model. See `model-forms/AGENTS.md` for details.

## Key Components

### PromptManagementPage.tsx

**Purpose:** Main page component for managing AI model prompt configurations

**Features:**
- Model selector for switching between AI models (Nemotron, Florence-2, YOLO-World, X-CLIP, Fashion-CLIP)
- Current configuration display with Edit button
- Version history with Restore functionality
- Export/Import buttons with diff preview
- URL-based state management for selected model

**Related Issues:** NEM-2697, NEM-2699

**Usage:**

```tsx
// Route: /settings/prompts
<PromptManagementPage />
```

---

### PromptConfigEditor.tsx

**Purpose:** Modal for editing AI model prompt configurations

**Props Interface:**

```typescript
interface PromptConfigEditorProps {
  isOpen: boolean;
  onClose: () => void;
  model: AIModelEnum;
  initialConfig: Record<string, unknown>;
  onSave: (config: Record<string, unknown>, changeDescription: string) => void;
  isSaving?: boolean;
}
```

**Key Features:**
- Renders model-specific form based on selected model
- Change description input for version tracking
- "Test Changes" button to open A/B testing modal
- Save/Cancel actions

---

### PromptTestModal.tsx

**Purpose:** A/B testing modal for comparing prompt configurations

**Props Interface:**

```typescript
interface PromptTestModalProps {
  isOpen: boolean;
  onClose: () => void;
  model: AIModelEnum;
  modifiedConfig: Record<string, unknown>;
}
```

**Key Features:**
- Event selector for choosing test events
- Runs inference with both current and modified configs in parallel
- Side-by-side results comparison
- Rate limit warning notice

**Related Issues:** NEM-2698

---

### ImportExportButtons.tsx

**Purpose:** Export and Import buttons with integrated file handling

**Props Interface:**

```typescript
interface ImportExportButtonsProps {
  onImportSuccess?: () => void;
  onExportError?: (error: Error) => void;
  onImportError?: (error: Error) => void;
}
```

**Key Features:**
- Export button triggers JSON download
- Import button with hidden file input
- Opens ImportPreviewModal for diff preview before applying

---

### ImportPreviewModal.tsx

**Purpose:** Modal for previewing import changes before applying

**Props Interface:**

```typescript
interface ImportPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  previewData: PromptsImportPreviewResponse | null;
  fileName: string;
  onApplyImport: () => void;
  isImporting?: boolean;
}
```

**Key Features:**
- Shows file name and affected models count
- Validation errors display
- Unknown models warning
- Per-model configuration diffs via ConfigDiffView
- Apply Import / Cancel actions

---

### ConfigDiffView.tsx

**Purpose:** Display configuration diff for a single model with visual highlighting

**Props Interface:**

```typescript
interface ConfigDiffViewProps {
  diff: PromptDiffEntry;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}
```

**Key Features:**
- Model name with change status badge (WILL CHANGE / NO CHANGE)
- Red highlighting for removed values
- Green highlighting for added values
- Expandable/collapsible diff details

---

### TestResultsComparison.tsx

**Purpose:** Side-by-side comparison of A/B test results

**Props Interface:**

```typescript
interface TestResultsComparisonProps {
  currentResult: TestResult | null;
  modifiedResult: TestResult | null;
  currentVersion?: number;
  isLoading?: boolean;
  error?: string | null;
}

interface TestResult {
  riskScore: number;
  riskLevel: string;
  reasoning?: string;
  summary?: string;
  processingTimeMs: number;
  tokensUsed?: number;
}
```

**Key Features:**
- Two-column grid with current vs modified results
- Risk score with colored progress bar
- Processing time and token usage metrics
- Delta summary showing score and time differences

---

### EventSelector.tsx

**Purpose:** Searchable event selector for A/B testing

**Props Interface:**

```typescript
interface EventSelectorProps {
  events: Event[];
  selectedEventId: number | null;
  onSelect: (eventId: number) => void;
  disabled?: boolean;
  isLoading?: boolean;
}
```

**Key Features:**
- Search by camera, event ID, or risk level
- Event cards with risk badge and detection count
- Relative time display
- Selected state highlighting

## Patterns

### URL-Based State Management

PromptManagementPage uses `useSearchParams` to persist the selected model in the URL, enabling deep linking and browser history navigation.

### Model-Specific Forms

PromptConfigEditor renders the appropriate form component from `model-forms/` based on the selected model using a switch statement.

### Parallel API Calls

PromptTestModal runs inference for both configurations simultaneously using `Promise.all()` for faster results.

### Hook-Based Data Fetching

Components use custom hooks from `usePromptQueries.ts` and `usePromptImportExport.ts` for data fetching and mutations with TanStack Query.

## Dependencies

- `@tremor/react` - UI components (Dialog, Card, Badge, Select, Tabs, etc.)
- `@tanstack/react-query` - Data fetching and caching
- `lucide-react` - Icons
- `react-router-dom` - URL state management
- `../../hooks/usePromptQueries` - Prompt config queries and mutations
- `../../hooks/usePromptImportExport` - Import/export hooks
- `../../types/promptManagement` - Type definitions

## Entry Points

**Start here:** `PromptManagementPage.tsx` - Main page component
**Also see:** `PromptConfigEditor.tsx` - Configuration editing
**Also see:** `PromptTestModal.tsx` - A/B testing functionality
**Also see:** `ImportExportButtons.tsx` - Import/export operations
