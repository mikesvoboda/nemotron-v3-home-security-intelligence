/**
 * EntityTrackingPanel - Shows cross-camera entity matches within EventDetailModal
 *
 * Displays:
 * - Timeline of cross-camera appearances
 * - Current location highlighting
 * - Similarity scores as color-coded badges
 * - Movement pattern summary (camera1 -> camera2 -> camera3)
 *
 * Only renders when entity has multiple appearances.
 */

import { useQuery } from '@tanstack/react-query';
import { clsx } from 'clsx';
import { format } from 'date-fns';
import { ArrowRight, Camera, MapPin, Route, User } from 'lucide-react';

import { fetchEntityHistory } from '../../services/api';

import type { EntityAppearance, EntityHistoryResponse } from '../../services/api';

export interface EntityTrackingPanelProps {
  /** Entity ID to display tracking history for */
  entityId: string;
  /** Current camera ID to highlight in the timeline */
  currentCameraId: string;
  /** Current timestamp for reference */
  currentTimestamp: string;
  /** Optional CSS class name */
  className?: string;
}

/**
 * Get similarity score badge color based on score value
 * - Green: >= 95%
 * - Blue: >= 90% and < 95%
 * - Yellow: >= 85% and < 90%
 * - Gray: < 85%
 */
function getSimilarityBadgeClasses(score: number | null): string {
  if (score === null) return 'bg-gray-500/20 text-gray-400 border-gray-500/40';
  const percent = score * 100;
  if (percent >= 95) return 'bg-green-500/20 text-green-400 border-green-500/40';
  if (percent >= 90) return 'bg-blue-500/20 text-blue-400 border-blue-500/40';
  if (percent >= 85) return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40';
  return 'bg-gray-500/20 text-gray-400 border-gray-500/40';
}

/**
 * Format similarity score as percentage
 */
function formatSimilarity(score: number | null): string {
  if (score === null) return 'N/A';
  return `${Math.round(score * 100)}%`;
}

/**
 * Format timestamp for display
 */
function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    return format(date, 'MMM d, h:mm a');
  } catch {
    return isoString;
  }
}

/**
 * Skeleton loading component
 */
function EntityTrackingSkeleton() {
  return (
    <div
      data-testid="entity-tracking-skeleton"
      className="animate-pulse rounded-lg border border-gray-800 bg-[#1F1F1F] p-4"
    >
      <div className="mb-4 flex items-center justify-between">
        <div className="h-5 w-40 rounded bg-gray-700" />
        <div className="h-4 w-24 rounded bg-gray-700" />
      </div>
      <div className="mb-4 h-8 w-full rounded bg-gray-700" />
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-full bg-gray-700" />
            <div className="flex-1">
              <div className="mb-1 h-4 w-32 rounded bg-gray-700" />
              <div className="h-3 w-20 rounded bg-gray-700" />
            </div>
            <div className="h-5 w-12 rounded bg-gray-700" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Movement pattern summary showing camera flow
 */
function MovementPatternSummary({ appearances }: { appearances: EntityAppearance[] }) {
  // Sort by timestamp ascending
  const sorted = [...appearances].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  // Get unique cameras in order of appearance
  const cameraFlow: string[] = [];
  for (const appearance of sorted) {
    const name = appearance.camera_name || appearance.camera_id;
    if (cameraFlow.length === 0 || cameraFlow[cameraFlow.length - 1] !== name) {
      cameraFlow.push(name);
    }
  }

  return (
    <div
      data-testid="movement-pattern-summary"
      className="mb-4 flex items-center gap-2 rounded-lg bg-black/30 px-3 py-2"
    >
      <Route className="h-4 w-4 flex-shrink-0 text-[#76B900]" aria-hidden="true" />
      <div className="flex flex-wrap items-center gap-1 text-sm">
        {cameraFlow.map((camera, index) => (
          <span key={`${camera}-${index}`} className="flex items-center gap-1">
            <span className="text-gray-300">{camera}</span>
            {index < cameraFlow.length - 1 && (
              <ArrowRight className="h-3 w-3 text-gray-500" aria-hidden="true" />
            )}
          </span>
        ))}
      </div>
    </div>
  );
}

/**
 * Single timeline item for an appearance
 */
function TimelineItem({
  appearance,
  isCurrentLocation,
  isLast,
}: {
  appearance: EntityAppearance;
  isCurrentLocation: boolean;
  isLast: boolean;
}) {
  const cameraName = appearance.camera_name || appearance.camera_id;

  return (
    <div className="relative flex gap-3 pb-3">
      {/* Timeline connector line */}
      {!isLast && (
        <div className="absolute left-4 top-8 h-full w-px border-l-2 border-dashed border-gray-700" />
      )}

      {/* Timeline dot/icon */}
      <div
        className={clsx(
          'relative z-10 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full',
          isCurrentLocation
            ? 'bg-[#76B900] ring-2 ring-[#76B900]/30'
            : 'bg-gray-800'
        )}
      >
        {isCurrentLocation ? (
          <MapPin className="h-4 w-4 text-black" aria-hidden="true" />
        ) : (
          <Camera className="h-4 w-4 text-gray-400" aria-hidden="true" />
        )}
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span
              className={clsx(
                'font-medium',
                isCurrentLocation ? 'text-[#76B900]' : 'text-white'
              )}
            >
              {cameraName}
            </span>
            {isCurrentLocation && (
              <span
                data-testid="current-location-badge"
                className="rounded-full bg-[#76B900]/20 px-2 py-0.5 text-xs font-medium text-[#76B900]"
              >
                Current
              </span>
            )}
          </div>

          {/* Similarity badge */}
          {appearance.similarity_score !== null && appearance.similarity_score !== undefined && (
            <span
              className={clsx(
                'rounded border px-1.5 py-0.5 text-xs font-medium',
                getSimilarityBadgeClasses(appearance.similarity_score)
              )}
            >
              {formatSimilarity(appearance.similarity_score)}
            </span>
          )}
        </div>

        {/* Timestamp */}
        <div className="mt-0.5 text-xs text-gray-400">
          {formatTimestamp(appearance.timestamp)}
        </div>
      </div>
    </div>
  );
}

/**
 * EntityTrackingPanel - Main component
 */
export default function EntityTrackingPanel({
  entityId,
  currentCameraId,
  currentTimestamp: _currentTimestamp,
  className,
}: EntityTrackingPanelProps) {
  // Use TanStack Query to fetch entity history
  // Hook must be called unconditionally, but enabled flag controls whether it runs
  const {
    data: history,
    isLoading,
    isError,
  } = useQuery<EntityHistoryResponse>({
    queryKey: ['entityHistory', entityId],
    queryFn: () => fetchEntityHistory(entityId),
    enabled: !!entityId,
    staleTime: 30000, // 30 seconds
    retry: 1,
  });

  // Don't render if no entity ID
  if (!entityId) {
    return null;
  }

  // Show skeleton while loading
  if (isLoading) {
    return <EntityTrackingSkeleton />;
  }

  // Don't render on error or if no data
  if (isError || !history) {
    return null;
  }

  // Only render when entity has multiple appearances
  if (!history.appearances || history.appearances.length <= 1) {
    return null;
  }

  // Sort appearances by timestamp (most recent last for timeline)
  const sortedAppearances = [...history.appearances].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  const EntityIcon = history.entity_type === 'vehicle' ? Camera : User;

  return (
    <div
      data-testid="entity-tracking-panel"
      className={clsx('rounded-lg border border-gray-800 bg-[#1F1F1F] p-4', className)}
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <EntityIcon className="h-5 w-5 text-[#76B900]" aria-hidden="true" />
          <h3 className="text-lg font-semibold text-white">Cross-Camera Tracking</h3>
        </div>
        <span className="text-sm text-gray-400">
          {history.count} {history.count === 1 ? 'appearance' : 'appearances'}
        </span>
      </div>

      {/* Movement Pattern Summary */}
      <MovementPatternSummary appearances={sortedAppearances} />

      {/* Timeline */}
      <div className="space-y-0">
        {sortedAppearances.map((appearance, index) => {
          const isCurrentLocation = appearance.camera_id === currentCameraId;
          const isLast = index === sortedAppearances.length - 1;

          return (
            <TimelineItem
              key={appearance.detection_id}
              appearance={appearance}
              isCurrentLocation={isCurrentLocation}
              isLast={isLast}
            />
          );
        })}
      </div>
    </div>
  );
}
