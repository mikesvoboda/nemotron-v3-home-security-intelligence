import { Check, CheckSquare, Square, X } from 'lucide-react';
import { memo } from 'react';

export interface AlertActionsProps {
  selectedCount: number;
  totalCount: number;
  hasUnacknowledged: boolean;
  onSelectAll: (selectAll: boolean) => void;
  onAcknowledgeSelected: () => void;
  onDismissSelected: () => void;
  onClearSelection: () => void;
}

/**
 * AlertActions component provides batch operations for selected alerts
 * Includes select all, acknowledge, and dismiss functionality
 */
const AlertActions = memo(function AlertActions({
  selectedCount,
  totalCount,
  hasUnacknowledged,
  onSelectAll,
  onAcknowledgeSelected,
  onDismissSelected,
  onClearSelection,
}: AlertActionsProps) {
  // Don't render if there are no alerts
  if (totalCount === 0) {
    return null;
  }

  const allSelected = selectedCount === totalCount && totalCount > 0;
  const someSelected = selectedCount > 0;

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
      {/* Selection info and controls */}
      <div className="flex items-center gap-3">
        {/* Select/Deselect All */}
        <button
          onClick={() => onSelectAll(!allSelected)}
          className="flex items-center gap-2 text-sm font-medium text-gray-300 hover:text-white"
          aria-label={allSelected ? 'Deselect all alerts' : 'Select all alerts'}
        >
          {allSelected ? (
            <CheckSquare className="h-5 w-5 text-[#76B900]" />
          ) : (
            <Square className="h-5 w-5" />
          )}
          <span>{allSelected ? 'Deselect All' : 'Select All'}</span>
        </button>

        {/* Selection count */}
        {someSelected && (
          <>
            <div className="h-5 w-px bg-gray-700" />
            <span className="text-sm font-medium text-gray-300">{selectedCount} selected</span>
          </>
        )}
      </div>

      {/* Batch action buttons */}
      {someSelected && (
        <>
          <div className="h-5 w-px bg-gray-700" />

          <div className="flex items-center gap-2">
            {/* Acknowledge Selected */}
            {hasUnacknowledged && (
              <button
                onClick={onAcknowledgeSelected}
                disabled={selectedCount === 0}
                className="flex items-center gap-1.5 rounded-md bg-green-600/20 px-3 py-1.5 text-sm font-medium text-green-400 transition-colors hover:bg-green-600/30 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Acknowledge selected alerts"
              >
                <Check className="h-4 w-4" />
                Acknowledge Selected
              </button>
            )}

            {/* Dismiss Selected */}
            <button
              onClick={onDismissSelected}
              disabled={selectedCount === 0}
              className="flex items-center gap-1.5 rounded-md bg-gray-700/50 px-3 py-1.5 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
              aria-label="Dismiss selected alerts"
            >
              <X className="h-4 w-4" />
              Dismiss Selected
            </button>

            {/* Clear Selection */}
            <button
              onClick={onClearSelection}
              className="text-sm font-medium text-gray-400 transition-colors hover:text-white"
              aria-label="Clear selection"
            >
              Clear Selection
            </button>
          </div>
        </>
      )}
    </div>
  );
});

export default AlertActions;
