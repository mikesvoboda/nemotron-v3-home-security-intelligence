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

import { useState } from 'react';
import { Clock, Eye, RotateCcw, Trash2, AlertTriangle } from 'lucide-react';

import type { DeletedEvent } from '../../services/api';
import { getRiskColor, getRiskLevel } from '../../utils/risk';
import RiskBadge from '../common/RiskBadge';
import Button from '../common/Button';

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
export default function DeletedEventCard({
  event,
  onRestore,
  onPermanentDelete,
  isRestoring = false,
  isDeleting = false,
  className = '',
}: DeletedEventCardProps) {
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);

  // Default to 0 if risk_score is null/undefined
  const riskScore = event.risk_score ?? 0;
  const riskLevel = getRiskLevel(riskScore);
  const timeSinceDeletion = formatTimeSinceDeletion(event.deleted_at);

  const handleRestore = () => {
    onRestore(event.id);
  };

  const handlePermanentDeleteClick = () => {
    setShowConfirmDialog(true);
  };

  const handleConfirmDelete = () => {
    setShowConfirmDialog(false);
    onPermanentDelete(event.id);
  };

  const handleCancelDelete = () => {
    setShowConfirmDialog(false);
  };

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
              <Button
                variant="secondary"
                size="sm"
                onClick={handleCancelDelete}
                className="flex-1"
              >
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
            <RiskBadge level={riskLevel} score={riskScore} showScore={true} size="sm" />
          </div>

          {/* Risk Progress Bar */}
          <div className="mb-2">
            <div
              className="h-1.5 w-full overflow-hidden rounded-full bg-gray-800"
              role="progressbar"
              aria-valuenow={riskScore}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className="h-full rounded-full"
                style={{
                  width: `${riskScore}%`,
                  backgroundColor: getRiskColor(riskLevel),
                }}
              />
            </div>
          </div>

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
}
