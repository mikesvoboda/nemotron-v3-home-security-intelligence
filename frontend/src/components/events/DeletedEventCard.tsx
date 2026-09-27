/**
 * DeletedEventCard - Card component for displaying soft-deleted events in trash view
 *
 * Features:
 * - Reduced opacity styling to indicate deleted state
 * - Shows time since deletion
 * - Restore button to recover the event
 * - Permanent delete button with confirmation dialog
 *
 * @module components/events/DeletedEventCard
 */

import { Clock, Eye, RotateCcw, Trash2, AlertTriangle } from 'lucide-react';
import { memo, useState, useCallback } from 'react';

import { cardPropsComparator } from '../../utils/memoization';
import { getRiskColor, getRiskLevel } from '../../utils/risk';
import Button from '../common/Button';
import RiskBadge from '../common/RiskBadge';
import VerdictBadge from '../common/VerdictBadge';

import type { DeletedEvent } from '../../services/api';

export interface DeletedEventCardProps {
  /** The deleted event data */
  event: DeletedEvent;
  /** Callback when restore button is clicked */
  onRestore: (eventId: number) => void;
  /** Callback when permanent delete is confirmed */
  onPermanentDelete: (eventId: number) => void;
  /** Whether a restore operation is in progress */
  isRestoring?: boolean;
  /** Whether a delete operation is in progress */
  isDeleting?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Whether the event is selected (for bulk actions) */
  isSelected?: boolean;
  /** Callback when selection changes (for bulk actions) */
  onSelectionChange?: (eventId: number, selected: boolean) => void;
  /** Whether to show selection checkbox */
  showSelection?: boolean;
}

/**
 * Formats the time since deletion in a human-readable format
 */
function formatTimeSinceDeletion(deletedAt: string): string {
  const deletedDate = new Date(deletedAt);
  const now = new Date();
  const diffMs = now.getTime() - deletedDate.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 60) {
    return diffMins <= 1 ? 'Just now' : `${diffMins} minutes ago`;
  }

  if (diffHours < 24) {
    return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
  }

  if (diffDays < 30) {
    return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`;
  }

  return deletedDate.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/**
 * DeletedEventCard displays a soft-deleted event with restore and permanent delete actions.
 */
const DeletedEventCard = memo(function DeletedEventCard({
  event,
  onRestore,
  onPermanentDelete,
  isRestoring = false,
  isDeleting = false,
  className = '',
  isSelected = false,
  onSelectionChange,
  showSelection = false,
}: DeletedEventCardProps) {
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);

  // Risk level + score as ONE nullable object, the shape ActivityFeed
  // ships: the JSX branch then narrows both without a non-null assertion
  // or a dead `?? 'low'` fallback. null means there is no level to show —
  // a NULL score under D11 is verification_failed/unverified, NOT a score
  // of 0, and the `?? 0` this replaces rendered a never-verified
  // soft-deleted event as a confident green "Low 0" (M1 review F-E
  // follow-through).
  const risk =
    event.risk_score === null || event.risk_score === undefined
      ? null
      : { score: event.risk_score, level: getRiskLevel(event.risk_score) };
  const timeSinceDeletion = formatTimeSinceDeletion(event.deleted_at);

  const handleRestore = useCallback(() => {
    onRestore(event.id);
  }, [onRestore, event.id]);

  const handlePermanentDeleteClick = useCallback(() => {
    setShowConfirmDialog(true);
  }, []);

  const handleConfirmDelete = useCallback(() => {
    setShowConfirmDialog(false);
    onPermanentDelete(event.id);
  }, [onPermanentDelete, event.id]);

  const handleCancelDelete = useCallback(() => {
    setShowConfirmDialog(false);
  }, []);

  const handleSelectionChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onSelectionChange?.(event.id, e.target.checked);
    },
    [onSelectionChange, event.id]
  );

  return (
    <div
      className={`relative rounded-lg border border-gray-800 bg-[#1F1F1F] opacity-70 shadow-lg transition-all hover:opacity-90 ${className}`}
      data-testid={`deleted-event-card-${event.id}`}
    >
      {/* Confirmation Dialog */}
      {showConfirmDialog && (
        <div
          className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-black/80 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby={`confirm-delete-title-${event.id}`}
        >
          <div className="w-full max-w-sm rounded-lg bg-[#2A2A2A] p-4 shadow-xl">
            <div className="mb-3 flex items-center gap-2 text-yellow-500">
              <AlertTriangle className="h-5 w-5" />
              <h3 id={`confirm-delete-title-${event.id}`} className="font-semibold">
                Permanent Delete
              </h3>
            </div>
            <p className="mb-4 text-sm text-gray-300">
              This action cannot be undone. The event and all associated data will be permanently
              removed.
            </p>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={handleCancelDelete} className="flex-1">
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={handleConfirmDelete}
                isLoading={isDeleting}
                className="flex-1"
              >
                Delete Forever
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="flex gap-4 p-4">
        {/* Selection Checkbox */}
        {showSelection && (
          <div className="flex flex-shrink-0 items-center">
            <input
              type="checkbox"
              checked={isSelected}
              onChange={handleSelectionChange}
              className="h-5 w-5 cursor-pointer rounded border-gray-600 bg-gray-800 text-primary focus:ring-2 focus:ring-primary/50 focus:ring-offset-0"
              aria-label={`Select event ${event.id}`}
              data-testid={`select-event-${event.id}`}
            />
          </div>
        )}

        {/* Thumbnail */}
        <div className="flex-shrink-0">
          {event.thumbnail_url ? (
            <img
              src={event.thumbnail_url}
              alt={`${event.camera_id} event thumbnail`}
              className="h-16 w-16 rounded-md object-cover grayscale"
            />
          ) : (
            <div className="flex h-16 w-16 items-center justify-center rounded-md bg-gray-800">
              <Eye className="h-6 w-6 text-gray-600" />
            </div>
          )}
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          {/* Header */}
          <div className="mb-2 flex items-start justify-between">
            <div className="min-w-0 flex-1">
              <h3 className="truncate text-base font-semibold text-white">{event.camera_id}</h3>
              <div className="mt-1 flex items-center gap-1.5 text-sm text-text-secondary">
                <Clock className="h-3.5 w-3.5" />
                <span>{new Date(event.started_at).toLocaleString()}</span>
              </div>
            </div>
            {risk !== null ? (
              <RiskBadge level={risk.level} score={risk.score} showScore={true} size="sm" />
            ) : (
              // Same swap EventCard/MobileEventCard ship: with no level to
              // show, the verdict badge states the real state ('none' →
              // Unverified). A colored Low badge may never stand in for
              // "not checked" — soft-deleted is not soft-verified.
              <VerdictBadge verdict={event.verification?.verdict} size="sm" />
            )}
          </div>

          {/* Risk Progress Bar — only when a score exists. A 0%-filled bar
              under an "Unverified" badge would re-lie in a second medium:
              the trough itself reads as "measured, and low". */}
          {risk !== null && (
            <div className="mb-2">
              <div
                className="h-1.5 w-full overflow-hidden rounded-full bg-gray-800"
                role="progressbar"
                aria-valuenow={risk.score}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${risk.score}%`,
                    backgroundColor: getRiskColor(risk.level),
                  }}
                />
              </div>
            </div>
          )}

          {/* Summary */}
          <p className="mb-3 line-clamp-2 text-sm text-gray-400">{event.summary}</p>

          {/* Deleted At Info */}
          <div className="mb-3 flex items-center gap-1.5 rounded bg-red-500/10 px-2 py-1 text-xs text-red-400">
            <Trash2 className="h-3.5 w-3.5" />
            <span>Deleted {timeSinceDeletion}</span>
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <Button
              variant="outline-primary"
              size="sm"
              leftIcon={<RotateCcw className="h-4 w-4" />}
              onClick={handleRestore}
              isLoading={isRestoring}
              disabled={isDeleting}
            >
              Restore
            </Button>
            <Button
              variant="danger"
              size="sm"
              leftIcon={<Trash2 className="h-4 w-4" />}
              onClick={handlePermanentDeleteClick}
              disabled={isRestoring || isDeleting}
            >
              Delete Forever
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}, cardPropsComparator);

export default DeletedEventCard;
