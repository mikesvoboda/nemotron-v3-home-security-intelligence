/**
 * FaceEventsTab Component
 *
 * Displays a feed of face detection events with filtering capabilities,
 * infinite scroll support, and action buttons for identifying unknown faces.
 *
 * Features:
 * - Filter by status (all/known/unknown)
 * - Filter by camera
 * - Filter by date
 * - Infinite scroll / Load More pagination
 * - Action buttons for unknown faces (Identify, Add New)
 * - View Detection button for known faces
 *
 * @module components/face-recognition/FaceEventsTab
 * @see NEM-4688 Phase 2 - Face Events & Enrollment
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 */

import { AlertCircle, Calendar, Eye, Loader2, Search, User, UserPlus, UserX } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';

import { useCamerasQuery } from '../../hooks/useCamerasQuery';
import { useFaceEventsQuery, type FaceEventsQueryFilters } from '../../hooks/useFaceEventsQuery';
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll';
import { InfiniteScrollStatus } from '../common';

import type { FaceDetectionEvent } from '../../types/faceRecognition';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the FaceEventsTab component.
 */
export interface FaceEventsTabProps {
  /** Callback when user clicks Identify on an unknown face event */
  onIdentify: (eventId: number) => void;
  /** Callback when user clicks Add New Person on an unknown face event */
  onAddNewPerson: (eventId: number) => void;
  /** Callback when user clicks View Detection on a face event */
  onViewDetection: (detectionId: string) => void;
  /** Optional additional class names */
  className?: string;
}

/**
 * Filter state for face events.
 */
interface FaceEventFilters {
  status: 'all' | 'known' | 'unknown';
  cameraId?: string;
  startDate?: string;
  endDate?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format timestamp for display.
 */
function formatEventTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

/**
 * Format confidence as percentage.
 */
function formatConfidence(confidence: number | null | undefined): string {
  if (confidence === null || confidence === undefined) {
    return '';
  }
  return `${Math.round(confidence * 100)}%`;
}

// ============================================================================
// Sub-Components
// ============================================================================

/**
 * Loading skeleton for face events.
 */
function FaceEventsLoading(): React.ReactElement {
  return (
    <div className="space-y-4" data-testid="face-events-loading">
      {Array.from({ length: 5 }, (_, i) => (
        <div
          key={i}
          className="flex animate-pulse items-start gap-4 rounded-lg border border-gray-700 bg-[#1A1A1A] p-4"
        >
          <div className="h-16 w-16 flex-shrink-0 rounded-lg bg-gray-700" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-32 rounded bg-gray-700" />
            <div className="h-3 w-48 rounded bg-gray-700" />
            <div className="h-3 w-24 rounded bg-gray-700" />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Empty state for face events.
 */
function FaceEventsEmpty(): React.ReactElement {
  return (
    <div
      className="flex min-h-[300px] flex-col items-center justify-center rounded-lg border border-gray-800 bg-[#1A1A1A] p-8 text-center"
      data-testid="face-events-empty"
    >
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#76B900]/10">
        <User className="h-8 w-8 text-[#76B900]" />
      </div>
      <h3 className="mb-2 text-lg font-semibold text-white">No Face Events</h3>
      <p className="max-w-sm text-gray-400">
        No face detection events match your current filters. Try adjusting your filters or check
        back later.
      </p>
    </div>
  );
}

/**
 * Error state for face events.
 */
function FaceEventsError({
  error,
  onRetry,
}: {
  error: Error;
  onRetry: () => void;
}): React.ReactElement {
  return (
    <div
      className="flex min-h-[300px] flex-col items-center justify-center rounded-lg border border-red-900/50 bg-red-900/10 p-8 text-center"
      data-testid="face-events-error"
    >
      <AlertCircle className="mb-4 h-12 w-12 text-red-400" />
      <h3 className="mb-2 text-lg font-semibold text-red-400">Failed to Load Face Events</h3>
      <p className="mb-4 max-w-sm text-gray-400">{error.message}</p>
      <button
        onClick={onRetry}
        className="rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
      >
        Try Again
      </button>
    </div>
  );
}

/**
 * Face thumbnail display.
 */
function FaceThumbnail({
  event,
}: {
  event: FaceDetectionEvent;
}): React.ReactElement {
  if (event.thumbnail_url) {
    return (
      <div className="h-16 w-16 flex-shrink-0 overflow-hidden rounded-lg bg-gray-700">
        <img
          src={event.thumbnail_url}
          alt={event.matched_person_name ?? 'Unknown person'}
          className="h-full w-full object-cover"
        />
      </div>
    );
  }

  return (
    <div
      className="flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-lg bg-gray-700"
      data-testid={`face-thumbnail-placeholder-${event.id}`}
    >
      {event.is_unknown ? (
        <UserX className="h-8 w-8 text-gray-500" />
      ) : (
        <User className="h-8 w-8 text-gray-500" />
      )}
    </div>
  );
}

/**
 * Individual face event card.
 */
function FaceEventCard({
  event,
  onIdentify,
  onAddNewPerson,
  onViewDetection,
}: {
  event: FaceDetectionEvent;
  onIdentify: (eventId: number) => void;
  onAddNewPerson: (eventId: number) => void;
  onViewDetection: (detectionId: string) => void;
}): React.ReactElement {
  const handleIdentify = useCallback(() => {
    onIdentify(event.id);
  }, [event.id, onIdentify]);

  const handleAddNewPerson = useCallback(() => {
    onAddNewPerson(event.id);
  }, [event.id, onAddNewPerson]);

  const handleViewDetection = useCallback(() => {
    if (event.detection_id) {
      onViewDetection(event.detection_id);
    }
  }, [event.detection_id, onViewDetection]);

  return (
    <div
      className="flex items-start gap-4 rounded-lg border border-gray-700 bg-[#1A1A1A] p-4 transition-colors hover:border-gray-600"
      data-testid={`face-event-card-${event.id}`}
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      tabIndex={0}
      role="article"
      aria-label={
        event.is_unknown
          ? `Unknown person detected at ${event.camera_name}`
          : `${event.matched_person_name} detected at ${event.camera_name}`
      }
    >
      {/* Thumbnail */}
      <FaceThumbnail event={event} />

      {/* Content */}
      <div className="flex-1">
        {/* Time and Camera */}
        <div className="mb-1 flex items-center gap-2 text-sm text-gray-400">
          <span>{formatEventTime(event.timestamp)}</span>
          <span className="text-gray-600">-</span>
          <span>{event.camera_name}</span>
        </div>

        {/* Person Info */}
        {event.is_unknown ? (
          <div className="mb-2">
            <span className="font-medium text-yellow-400">Unknown person</span>
          </div>
        ) : (
          <div className="mb-2">
            <span className="font-medium text-white">{event.matched_person_name}</span>
            {event.match_confidence !== null && event.match_confidence !== undefined && (
              <span className="ml-2 text-sm text-green-400">
                ({formatConfidence(event.match_confidence)} confidence)
              </span>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-wrap gap-2">
          {event.is_unknown ? (
            <>
              <button
                onClick={handleIdentify}
                className="flex items-center gap-1 rounded-md bg-[#76B900] px-3 py-1.5 text-xs font-medium text-black transition-colors hover:bg-[#88d200]"
                aria-label="Identify this person"
              >
                <Search className="h-3 w-3" />
                Identify
              </button>
              <button
                onClick={handleAddNewPerson}
                className="flex items-center gap-1 rounded-md border border-gray-600 bg-[#252525] px-3 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:bg-[#303030]"
                aria-label="Add as new person"
              >
                <UserPlus className="h-3 w-3" />
                Add New
              </button>
            </>
          ) : (
            <button
              onClick={handleViewDetection}
              disabled={!event.detection_id}
              className="flex items-center gap-1 rounded-md border border-gray-600 bg-[#252525] px-3 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:bg-[#303030] disabled:cursor-not-allowed disabled:opacity-50"
              aria-label="View detection details"
            >
              <Eye className="h-3 w-3" />
              View Detection
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * FaceEventsTab displays a filterable, paginated list of face detection events.
 *
 * @param props - Component props
 * @returns The FaceEventsTab component
 */
export default function FaceEventsTab({
  onIdentify,
  onAddNewPerson,
  onViewDetection,
  className = '',
}: FaceEventsTabProps): React.ReactElement {
  // Local filter state
  const [filters, setFilters] = useState<FaceEventFilters>({
    status: 'all',
    cameraId: undefined,
    startDate: undefined,
    endDate: undefined,
  });

  // Fetch cameras for the filter dropdown
  const { cameras, isLoading: camerasLoading } = useCamerasQuery();

  // Convert local filters to API filters
  const apiFilters: FaceEventsQueryFilters = useMemo(() => {
    const result: FaceEventsQueryFilters = {};

    if (filters.status === 'unknown') {
      result.unknown_only = true;
    } else if (filters.status === 'known') {
      result.unknown_only = false;
    }

    if (filters.cameraId) {
      result.camera_id = parseInt(filters.cameraId, 10);
    }

    if (filters.startDate) {
      // Convert date to start of day ISO string
      result.start_date = new Date(filters.startDate).toISOString();
    }

    if (filters.endDate) {
      // Convert date to end of day ISO string
      const endDate = new Date(filters.endDate);
      endDate.setHours(23, 59, 59, 999);
      result.end_date = endDate.toISOString();
    }

    return result;
  }, [filters]);

  // Fetch face events with infinite scroll
  const {
    events,
    totalCount,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    error,
    isError,
    refetch,
  } = useFaceEventsQuery({
    filters: apiFilters,
    limit: 20,
    refetchInterval: 30000,
  });

  // Infinite scroll hook
  const {
    sentinelRef,
    isLoadingMore,
    error: scrollError,
    retry,
  } = useInfiniteScroll({
    onLoadMore: fetchNextPage,
    hasMore: hasNextPage,
    isLoading: isFetchingNextPage,
    enabled: !isLoading && events.length > 0,
  });

  // Handle filter changes
  const handleStatusChange = useCallback((event: React.ChangeEvent<HTMLSelectElement>) => {
    setFilters((prev) => ({ ...prev, status: event.target.value as 'all' | 'known' | 'unknown' }));
  }, []);

  const handleCameraChange = useCallback((event: React.ChangeEvent<HTMLSelectElement>) => {
    setFilters((prev) => ({ ...prev, cameraId: event.target.value || undefined }));
  }, []);

  const handleDateChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    setFilters((prev) => ({ ...prev, startDate: event.target.value || undefined }));
  }, []);

  // Handle retry
  const handleRetry = useCallback(() => {
    void refetch();
  }, [refetch]);

  // Handle Load More click
  const handleLoadMore = useCallback(() => {
    void fetchNextPage();
  }, [fetchNextPage]);

  // Count text
  const countText = totalCount === 1 ? '1 event' : `${totalCount} events`;

  return (
    <div className={`rounded-lg bg-[#121212] p-6 ${className}`} data-testid="face-events-tab">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-xl font-semibold text-white">Face Events</h2>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Status Filter */}
          <select
            value={filters.status}
            onChange={handleStatusChange}
            className="rounded-lg border border-gray-700 bg-[#1F1F1F] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            aria-label="Filter by status"
          >
            <option value="all">All</option>
            <option value="known">Known</option>
            <option value="unknown">Unknown</option>
          </select>

          {/* Camera Filter */}
          <select
            value={filters.cameraId ?? ''}
            onChange={handleCameraChange}
            disabled={camerasLoading}
            className="rounded-lg border border-gray-700 bg-[#1F1F1F] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900] disabled:opacity-50"
            aria-label="Filter by camera"
          >
            <option value="">All Cameras</option>
            {cameras.map((camera) => (
              <option key={camera.id} value={camera.id}>
                {camera.name}
              </option>
            ))}
          </select>

          {/* Date Filter */}
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-gray-400" />
            <input
              type="date"
              value={filters.startDate ?? ''}
              onChange={handleDateChange}
              className="rounded-lg border border-gray-700 bg-[#1F1F1F] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
              aria-label="Filter by date"
            />
          </div>
        </div>
      </div>

      {/* Event count */}
      {!isLoading && !isError && events.length > 0 && (
        <div className="mb-4 text-sm text-gray-400">{countText}</div>
      )}

      {/* Content */}
      {isLoading ? (
        <FaceEventsLoading />
      ) : isError && error ? (
        <FaceEventsError error={error} onRetry={handleRetry} />
      ) : events.length === 0 ? (
        <FaceEventsEmpty />
      ) : (
        <>
          {/* Event List */}
          <div className="space-y-4" data-testid="face-events-list">
            {events.map((event) => (
              <FaceEventCard
                key={event.id}
                event={event}
                onIdentify={onIdentify}
                onAddNewPerson={onAddNewPerson}
                onViewDetection={onViewDetection}
              />
            ))}
          </div>

          {/* Load More / Infinite Scroll Status */}
          {hasNextPage && !isFetchingNextPage && !isLoadingMore && (
            <div className="mt-6 flex justify-center">
              <button
                onClick={handleLoadMore}
                className="rounded-lg border border-gray-700 bg-[#1F1F1F] px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-[#252525]"
                aria-label="Load more events"
              >
                Load More
              </button>
            </div>
          )}

          {/* Loading indicator for next page */}
          {(isFetchingNextPage || isLoadingMore) && (
            <div
              className="mt-6 flex flex-col items-center justify-center py-4"
              data-testid="infinite-scroll-loading"
            >
              <Loader2 className="h-6 w-6 animate-spin text-[#76B900]" />
              <p className="mt-2 text-sm text-gray-400">Loading more events...</p>
            </div>
          )}

          {/* End of list */}
          {!hasNextPage && events.length > 0 && (
            <div className="mt-6 text-center text-sm text-gray-500">All events loaded</div>
          )}

          {/* Scroll sentinel for infinite scroll */}
          <InfiniteScrollStatus
            sentinelRef={sentinelRef}
            isLoading={isFetchingNextPage || isLoadingMore}
            hasMore={hasNextPage}
            error={scrollError}
            onRetry={retry}
            showEndMessage={false}
            className="mt-4"
          />
        </>
      )}
    </div>
  );
}

export { FaceEventsTab };
export type { FaceEventFilters };
