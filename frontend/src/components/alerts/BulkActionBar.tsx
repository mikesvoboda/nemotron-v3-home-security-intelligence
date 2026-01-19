import { CheckSquare, Loader2, X } from 'lucide-react';

export interface BulkActionBarProps {
  /** Number of currently selected alerts */
  selectedCount: number;
  /** Total number of alerts available */
  totalCount: number;
  /** Callback to select all alerts */
  onSelectAll: () => void;
  /** Callback to clear selection */
  onClearSelection: () => void;
  /** Callback to dismiss all selected alerts */
  onDismissSelected: () => void;
  /** Whether bulk operation is in progress */
  isProcessing?: boolean;
}

/**
 * BulkActionBar displays when alerts are selected, providing
 * bulk actions like select all, clear, and dismiss selected.
 * Styled with NVIDIA green (#76B900) accent color.
 */
export default function BulkActionBar({
  selectedCount,
  totalCount,
  onSelectAll,
  onClearSelection,
  onDismissSelected,
  isProcessing = false,
}: BulkActionBarProps) {
  // Don't render if nothing is selected
  if (selectedCount === 0) {
    return null;
  }

  return (
    <div
      className="sticky top-0 z-20 mb-4 flex items-center justify-between rounded-lg bg-[#76B900] px-4 py-3 text-white"
      role="toolbar"
      aria-label="Bulk actions for selected alerts"
      data-testid="bulk-action-bar"
    >
      <div className="flex items-center gap-3">
        <CheckSquare className="h-5 w-5" aria-hidden="true" />
        <span className="font-medium" data-testid="selected-count">
          {selectedCount} selected
        </span>
        {selectedCount < totalCount && (
          <button
            onClick={onSelectAll}
            className="text-sm underline hover:no-underline"
            disabled={isProcessing}
            aria-label={`Select all ${totalCount} alerts`}
          >
            Select all {totalCount}
          </button>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onClearSelection}
          className="flex items-center gap-1 rounded bg-white/20 px-3 py-1.5 text-sm hover:bg-white/30 disabled:opacity-50"
          disabled={isProcessing}
          aria-label="Clear selection"
        >
          <X className="h-4 w-4" aria-hidden="true" />
          Clear
        </button>
        <button
          onClick={onDismissSelected}
          className="flex items-center gap-1 rounded bg-white px-3 py-1.5 text-sm font-medium text-[#76B900] hover:bg-white/90 disabled:opacity-50"
          disabled={isProcessing}
          aria-label={`Dismiss ${selectedCount} selected alerts`}
        >
          {isProcessing ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              Dismissing...
            </>
          ) : (
            'Dismiss Selected'
          )}
        </button>
      </div>
    </div>
  );
}
