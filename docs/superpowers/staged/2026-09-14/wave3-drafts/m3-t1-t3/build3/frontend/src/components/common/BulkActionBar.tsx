/**
 * BulkActionBar - Reusable action bar for bulk operations
 *
 * Displays when items are selected, providing action buttons and selection info.
 * Can be customized with different actions for different contexts.
 *
 * @module components/common/BulkActionBar
 * NEM-3615: Add bulk actions to EventTimeline and EntitiesPage
 */

import { Check, X } from 'lucide-react';

import type { ReactNode } from 'react';

/**
 * Action button configuration
 */
export interface BulkAction {
  /** Unique identifier for the action */
  id: string;
  /** Display label for the action */
  label: string;
  /** Icon to display (Lucide icon component) */
  icon?: ReactNode;
  /** Callback when action is clicked */
  onClick: () => void;
  /** Whether the action is destructive (shows in red) */
  destructive?: boolean;
  /** Whether the action is disabled */
  disabled?: boolean;
  /** Loading state for async actions */
  loading?: boolean;
  /** Tooltip text */
  tooltip?: string;
}

export interface BulkActionBarProps {
  /** Number of items currently selected */
  selectedCount: number;
  /** Total number of items available */
  totalCount?: number;
  /** Array of action buttons to display */
  actions: BulkAction[];
  /** Callback to clear selection */
  onClearSelection: () => void;
  /** Optional label for the item type (e.g., "events", "entities") */
  itemLabel?: string;
  /** Whether the bar is visible */
  visible?: boolean;
  /** Optional class name */
  className?: string;
}

/**
 * BulkActionBar displays selection info and action buttons for bulk operations.
 *
 * Features:
 * - Shows selection count
 * - Clear selection button
 * - Customizable action buttons
 * - Support for loading/disabled states
 * - Sticky positioning option
 *
 * @example
 * ```tsx
 * <BulkActionBar
 *   selectedCount={selectedIds.size}
 *   totalCount={events.length}
 *   itemLabel="events"
 *   onClearSelection={() => deselectAll()}
 *   actions={[
 *     {
 *       id: 'mark-reviewed',
 *       label: 'Mark Reviewed',
 *       icon: <Check className="h-4 w-4" />,
 *       onClick: () => handleMarkReviewed(),
 *       loading: isMarking,
 *     },
 *     {
 *       id: 'export',
 *       label: 'Export',
 *       icon: <Download className="h-4 w-4" />,
 *       onClick: () => handleExport(),
 *     },
 *     {
 *       id: 'delete',
 *       label: 'Delete',
 *       icon: <Trash2 className="h-4 w-4" />,
 *       onClick: () => handleDelete(),
 *       destructive: true,
 *     },
 *   ]}
 * />
 * ```
 */
export default function BulkActionBar({
  selectedCount,
  totalCount,
  actions,
  onClearSelection,
  itemLabel = 'items',
  visible = true,
  className = '',
}: BulkActionBarProps) {
  if (!visible || selectedCount === 0) {
    return null;
  }

  return (
    <div
      className={`flex items-center justify-between rounded-lg border border-[#76B900]/30 bg-[#76B900]/10 px-4 py-3 ${className}`}
      role="toolbar"
      aria-label="Bulk actions"
    >
      {/* Selection Info */}
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#76B900]/20">
          <Check className="h-4 w-4 text-[#76B900]" />
        </div>
        <div className="text-sm">
          <span className="font-semibold text-white">{selectedCount}</span>
          <span className="text-gray-400">
            {totalCount !== undefined ? ` of ${totalCount}` : ''} {itemLabel} selected
          </span>
        </div>
        <button
          onClick={onClearSelection}
          className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
          aria-label="Clear selection"
        >
          <X className="h-3 w-3" />
          Clear
        </button>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-2">
        {actions.map((action) => (
          <button
            key={action.id}
            onClick={action.onClick}
            disabled={action.disabled || action.loading}
            title={action.tooltip}
            className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-all disabled:cursor-not-allowed disabled:opacity-50 ${
              action.destructive
                ? 'border border-red-500/30 bg-red-500/10 text-red-400 hover:border-red-500/50 hover:bg-red-500/20'
                : 'border border-gray-700 bg-[#1A1A1A] text-gray-300 hover:border-gray-600 hover:bg-[#252525]'
            }`}
            aria-label={action.label}
          >
            {action.loading ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            ) : (
              action.icon
            )}
            <span className="hidden sm:inline">{action.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
