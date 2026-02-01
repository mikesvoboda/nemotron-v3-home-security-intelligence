/**
 * UnknownStrangersPanel - Displays recent unknown face detections
 *
 * A compact panel showing the most recent unknown face detections with
 * action buttons for quick identification, dismissal, or adding as a
 * new person. Designed for embedding in the Known Persons tab.
 *
 * Features:
 * - Auto-refresh every 30 seconds
 * - Configurable limit (default 3)
 * - Thumbnail display with placeholder fallback
 * - Action buttons: Identify, Dismiss, Add as New Person
 * - View All link to Face Events tab
 * - Loading, error, and empty states
 * - NVIDIA dark theme styling with amber accent
 *
 * @module components/face-recognition/UnknownStrangersPanel
 * @see NEM-4688 Phase 2 - Unknown Strangers Panel
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 */

import { AlertCircle, ArrowRight, Clock, Loader2, User, UserPlus, UserX, X } from 'lucide-react';

import type { FaceDetectionEvent } from '@/types/faceRecognition';

import { useUnknownStrangersQuery } from '@/hooks/useFaceRecognitionApi';

// ============================================================================
// Types
// ============================================================================

export interface UnknownStrangersPanelProps {
  /** Maximum number of unknown faces to display (default: 3) */
  limit?: number;
  /** Callback when Identify button is clicked */
  onIdentify: (eventId: number) => void;
  /** Callback when Add as New Person button is clicked */
  onAddNewPerson: (eventId: number) => void;
  /** Callback when Dismiss button is clicked */
  onDismiss: (eventId: number) => void;
  /** Callback when View All button is clicked */
  onViewAll: () => void;
  /** Optional CSS class name */
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format timestamp to display time (e.g., "10:32 AM")
 */
function formatTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return isoString;
  }
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Loading skeleton for a single event item
 */
function SkeletonItem() {
  return (
    <div className="flex items-start gap-3 p-3" data-testid="skeleton-item">
      {/* Thumbnail skeleton */}
      <div className="h-12 w-12 flex-shrink-0 animate-pulse rounded-lg bg-gray-700" />
      {/* Content skeleton */}
      <div className="flex-1 space-y-2">
        <div className="h-4 w-24 animate-pulse rounded bg-gray-700" />
        <div className="h-3 w-32 animate-pulse rounded bg-gray-700" />
        <div className="flex gap-2">
          <div className="h-6 w-16 animate-pulse rounded bg-gray-700" />
          <div className="h-6 w-14 animate-pulse rounded bg-gray-700" />
          <div className="h-6 w-28 animate-pulse rounded bg-gray-700" />
        </div>
      </div>
    </div>
  );
}

/**
 * Face thumbnail component with fallback placeholder
 */
function FaceThumbnail({
  thumbnailUrl,
  cameraName,
}: {
  thumbnailUrl: string | null | undefined;
  cameraName: string;
}) {
  if (thumbnailUrl) {
    return (
      <img
        src={thumbnailUrl}
        alt={`Unknown face at ${cameraName}`}
        className="h-12 w-12 flex-shrink-0 rounded-lg border border-amber-600/30 object-cover"
      />
    );
  }

  return (
    <div
      className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-lg border border-amber-600/30 bg-gray-800"
      data-testid="face-placeholder"
    >
      <User className="h-6 w-6 text-amber-500/50" />
    </div>
  );
}

/**
 * Single unknown face event item
 */
function UnknownFaceItem({
  event,
  onIdentify,
  onAddNewPerson,
  onDismiss,
}: {
  event: FaceDetectionEvent;
  onIdentify: (eventId: number) => void;
  onAddNewPerson: (eventId: number) => void;
  onDismiss: (eventId: number) => void;
}) {
  const handleIdentify = (e: React.MouseEvent) => {
    e.stopPropagation();
    onIdentify(event.id);
  };

  const handleAddNewPerson = (e: React.MouseEvent) => {
    e.stopPropagation();
    onAddNewPerson(event.id);
  };

  const handleDismiss = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDismiss(event.id);
  };

  return (
    <div
      className="flex items-start gap-3 border-b border-gray-800 p-3 last:border-b-0 hover:bg-gray-800/30"
      data-testid={`unknown-face-item-${event.id}`}
    >
      {/* Thumbnail */}
      <FaceThumbnail thumbnailUrl={event.thumbnail_url} cameraName={event.camera_name} />

      {/* Content */}
      <div className="min-w-0 flex-1">
        {/* Time and Camera */}
        <div className="mb-1 flex items-center gap-2 text-sm">
          <span
            className="flex items-center gap-1 text-amber-500"
            data-testid={`event-time-${event.id}`}
          >
            <Clock className="h-3.5 w-3.5" />
            {formatTime(event.timestamp)}
          </span>
          <span className="text-gray-500">-</span>
          <span className="truncate font-medium text-white">{event.camera_name}</span>
        </div>

        {/* Description */}
        <p className="mb-2 text-xs text-gray-400">Unknown person detected</p>

        {/* Action Buttons */}
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={handleIdentify}
            className="inline-flex items-center gap-1 rounded border border-[#76B900]/50 bg-[#76B900]/10 px-2 py-1 text-xs font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/20"
          >
            <UserPlus className="h-3 w-3" />
            Identify
          </button>

          <button
            type="button"
            onClick={handleDismiss}
            className="inline-flex items-center gap-1 rounded border border-gray-600 bg-gray-800 px-2 py-1 text-xs font-medium text-gray-300 transition-colors hover:bg-gray-700"
          >
            <X className="h-3 w-3" />
            Dismiss
          </button>

          <button
            type="button"
            onClick={handleAddNewPerson}
            className="inline-flex items-center gap-1 rounded border border-amber-600/50 bg-amber-600/10 px-2 py-1 text-xs font-medium text-amber-500 transition-colors hover:bg-amber-600/20"
          >
            <UserX className="h-3 w-3" />
            Add as New Person
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * UnknownStrangersPanel - Main component
 */
export default function UnknownStrangersPanel({
  limit = 3,
  onIdentify,
  onAddNewPerson,
  onDismiss,
  onViewAll,
  className = '',
}: UnknownStrangersPanelProps) {
  const { data, isLoading, error } = useUnknownStrangersQuery(limit);

  const items = data?.items ?? [];
  const hasMore = data?.has_more ?? false;
  const total = data?.total ?? 0;
  const showViewAll = items.length > 0 && (hasMore || total > items.length);

  // Loading state
  if (isLoading) {
    return (
      <div
        className={`rounded-lg border border-gray-700 bg-[#1A1A1A] p-4 ${className}`}
        data-testid="unknown-strangers-loading"
      >
        {/* Header */}
        <div className="mb-3 flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
            <Loader2 className="h-4 w-4 animate-spin text-amber-500" />
            Recent Unknown Faces
          </h3>
        </div>
        {/* Loading skeletons */}
        <div className="space-y-1">
          <SkeletonItem />
          <SkeletonItem />
          <SkeletonItem />
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        className={`rounded-lg border border-red-900/50 bg-red-900/10 p-4 ${className}`}
        data-testid="unknown-strangers-error"
      >
        <div className="flex items-center gap-2 text-red-400">
          <AlertCircle className="h-5 w-5" />
          <span className="text-sm">
            {error instanceof Error ? error.message : 'Failed to load unknown faces'}
          </span>
        </div>
      </div>
    );
  }

  // Empty state
  if (items.length === 0) {
    return (
      <div
        className={`rounded-lg border border-gray-700 bg-[#1A1A1A] p-4 ${className}`}
        data-testid="unknown-strangers-empty"
      >
        {/* Header */}
        <div className="mb-3">
          <h3 className="text-sm font-semibold text-white">Recent Unknown Faces</h3>
        </div>
        {/* Empty message */}
        <div className="flex flex-col items-center justify-center py-6 text-center">
          <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-gray-800">
            <User className="h-6 w-6 text-gray-600" />
          </div>
          <p className="text-sm text-gray-400">No unknown faces detected</p>
          <p className="text-xs text-gray-500">All clear for now</p>
        </div>
      </div>
    );
  }

  // Normal state with data
  return (
    <div
      className={`rounded-lg border border-gray-700 bg-[#1A1A1A] ${className}`}
      data-testid="unknown-strangers-panel"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 p-4">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
          <span className="flex h-2 w-2 animate-pulse rounded-full bg-amber-500" />
          Recent Unknown Faces
        </h3>
        {showViewAll && (
          <button
            type="button"
            onClick={onViewAll}
            className="inline-flex items-center gap-1 text-xs font-medium text-[#76B900] transition-colors hover:text-[#8AD200]"
          >
            View All
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Event list */}
      <div>
        {items.map((event) => (
          <UnknownFaceItem
            key={event.id}
            event={event}
            onIdentify={onIdentify}
            onAddNewPerson={onAddNewPerson}
            onDismiss={onDismiss}
          />
        ))}
      </div>
    </div>
  );
}
