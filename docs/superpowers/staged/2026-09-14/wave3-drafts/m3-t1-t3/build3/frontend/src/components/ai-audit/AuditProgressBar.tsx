/**
 * AuditProgressBar Component
 *
 * Displays real-time progress during batch audit processing including:
 * - Progress bar showing completion percentage
 * - Current event counter (e.g., 25 / 100)
 * - Current event ID being processed
 * - Estimated time to completion (ETA)
 * - Cancel button to abort the batch audit
 *
 * This component is designed to display WebSocket progress updates
 * during batch audit operations.
 */

import { X } from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

export interface AuditProgressBarProps {
  /** Current number of events processed */
  current: number;
  /** Total number of events to process */
  total: number;
  /** Estimated time to completion in seconds */
  eta: number;
  /** Current event ID being processed (optional) */
  currentEventId?: number;
  /** Callback when user clicks Cancel button */
  onCancel: () => void;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format ETA in human-readable form (e.g., "2m 30s" or "45s")
 */
function formatEta(seconds: number): string {
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
}

// ============================================================================
// Component
// ============================================================================

/**
 * AuditProgressBar - Real-time progress indicator for batch audit operations
 */
export default function AuditProgressBar({
  current,
  total,
  eta,
  currentEventId,
  onCancel,
}: AuditProgressBarProps) {
  const percentage = total > 0 ? Math.round((current / total) * 100) : 0;
  const isComplete = current === total && total > 0;

  return (
    <div
      className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-6"
      data-testid="audit-progress-bar"
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">
            {isComplete ? 'Audit Complete' : 'Batch Audit in Progress'}
          </h3>
          <p className="mt-1 text-sm text-gray-400">
            {current} / {total} events processed ({percentage}%)
          </p>
        </div>
        {!isComplete && (
          <button
            onClick={onCancel}
            className="rounded-lg bg-red-700 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-red-800"
            aria-label="Cancel batch audit"
          >
            <X className="mr-1 inline h-4 w-4" />
            Cancel
          </button>
        )}
      </div>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="h-3 w-full overflow-hidden rounded-full bg-gray-800">
          <div
            role="progressbar"
            aria-valuenow={current}
            aria-valuemin={0}
            aria-valuemax={total}
            className="h-full bg-gradient-to-r from-[#76B900] to-[#8ACE00] transition-all duration-300"
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>

      {/* Details */}
      <div className="flex items-center justify-between text-sm">
        <div className="text-gray-400">
          {currentEventId && (
            <span className="font-medium">Processing Event #{currentEventId}</span>
          )}
          {!currentEventId && !isComplete && <span>Processing events...</span>}
          {isComplete && <span className="text-[#76B900]">All events processed successfully</span>}
        </div>
        {!isComplete && eta > 0 && (
          <div className="text-gray-400">
            ETA: <span className="font-medium text-white">{formatEta(eta)}</span>
          </div>
        )}
      </div>
    </div>
  );
}
