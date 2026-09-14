/**
 * LineZoneCrossingCard - Card displaying line zone crossing counts (NEM-4714)
 *
 * Displays a summary of line zone crossing statistics including:
 * - Entry count (in)
 * - Exit count (out)
 * - Net flow (in - out)
 * - Reset functionality with confirmation
 *
 * Part of Phase 1C: Frontend Line Zone Crossing Display.
 *
 * @module components/zones/LineZoneCrossingCard
 */

import { clsx } from 'clsx';
import { ArrowDownRight, ArrowUpRight, RotateCcw } from 'lucide-react';
import { memo, useCallback, useState } from 'react';

import Button from '../common/Button';

import type { LineZoneWithCounts } from '../../types/zoneAnalytics';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the LineZoneCrossingCard component.
 */
export interface LineZoneCrossingCardProps {
  /** Line zone data with crossing counts */
  zone: LineZoneWithCounts;
  /** Callback when reset button is clicked */
  onReset?: (zoneId: number) => void;
  /** Whether a reset operation is in progress */
  isResetting?: boolean;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * LineZoneCrossingCard component.
 *
 * Displays crossing statistics for a line zone with reset functionality.
 *
 * @param props - Component props
 * @returns Rendered component
 */
function LineZoneCrossingCardComponent({
  zone,
  onReset,
  isResetting = false,
  className,
}: LineZoneCrossingCardProps) {
  const [showConfirm, setShowConfirm] = useState(false);
  const netFlow = zone.in_count - zone.out_count;

  const handleReset = useCallback(() => {
    if (showConfirm) {
      onReset?.(zone.id);
      setShowConfirm(false);
    } else {
      setShowConfirm(true);
    }
  }, [zone.id, onReset, showConfirm]);

  const handleCancelReset = useCallback(() => {
    setShowConfirm(false);
  }, []);

  return (
    <div
      className={clsx('rounded-lg border border-gray-700 bg-gray-800/50 p-4', className)}
      data-testid={`line-zone-card-${zone.id}`}
    >
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-medium text-white">{zone.name}</h3>
        <span
          className={clsx(
            'rounded-full px-2 py-0.5 text-xs font-medium',
            zone.enabled ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'
          )}
          data-testid="zone-status-badge"
        >
          {zone.enabled ? 'Active' : 'Inactive'}
        </span>
      </div>

      {/* Counts */}
      <div className="mb-4 grid grid-cols-3 gap-3">
        {/* In Count */}
        <div className="text-center">
          <div className="flex items-center justify-center gap-1 text-green-400">
            <ArrowDownRight className="h-4 w-4" aria-hidden="true" />
            <span className="text-2xl font-bold" data-testid="in-count">
              {zone.in_count}
            </span>
          </div>
          <span className="text-xs text-gray-400">In</span>
        </div>

        {/* Out Count */}
        <div className="text-center">
          <div className="flex items-center justify-center gap-1 text-red-400">
            <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
            <span className="text-2xl font-bold" data-testid="out-count">
              {zone.out_count}
            </span>
          </div>
          <span className="text-xs text-gray-400">Out</span>
        </div>

        {/* Net Flow */}
        <div className="text-center">
          <div
            className={clsx(
              'text-2xl font-bold',
              netFlow > 0 ? 'text-green-400' : netFlow < 0 ? 'text-red-400' : 'text-gray-400'
            )}
            data-testid="net-flow"
          >
            {netFlow > 0 ? '+' : ''}
            {netFlow}
          </div>
          <span className="text-xs text-gray-400">Net</span>
        </div>
      </div>

      {/* Reset button */}
      <Button
        variant={showConfirm ? 'danger' : 'outline-primary'}
        size="sm"
        onClick={handleReset}
        disabled={isResetting}
        leftIcon={<RotateCcw className={clsx('h-4 w-4', isResetting && 'animate-spin')} />}
        fullWidth
        data-testid="reset-button"
      >
        {isResetting ? 'Resetting...' : showConfirm ? 'Confirm Reset' : 'Reset Counts'}
      </Button>

      {/* Cancel confirmation */}
      {showConfirm && (
        <button
          type="button"
          onClick={handleCancelReset}
          className="mt-2 w-full text-center text-xs text-gray-400 hover:text-gray-200"
          data-testid="cancel-reset-button"
        >
          Cancel
        </button>
      )}
    </div>
  );
}

/**
 * Memoized LineZoneCrossingCard for performance.
 */
export const LineZoneCrossingCard = memo(LineZoneCrossingCardComponent);

export default LineZoneCrossingCard;
