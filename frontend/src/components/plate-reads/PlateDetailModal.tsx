/**
 * PlateDetailModal Component
 *
 * Modal displaying complete history for a selected license plate.
 * Shows summary statistics, camera breakdown, and paginated timeline
 * of all detections for this plate.
 *
 * @see frontend/src/services/plateReadsApi.ts - API client
 * @see frontend/src/types/plateRead.ts - Type definitions
 */

import { Dialog, Transition } from '@headlessui/react';
import { useQuery } from '@tanstack/react-query';
import { clsx } from 'clsx';
import {
  AlertCircle,
  Camera,
  ChevronLeft,
  ChevronRight,
  Clock,
  ImageOff,
  Sparkles,
  X,
} from 'lucide-react';
import { Fragment, useCallback, useMemo, useState } from 'react';

import { VehicleMatchBadge } from './VehicleMatchBadge';
import { useVehicleMatchQuery } from '../../hooks/useVehicleMatchQuery';
import { searchPlateReads } from '../../services/plateReadsApi';
import {
  formatConfidence,
  getConfidenceLevel,
  getQualityLabel,
} from '../../types/plateRead';
import ConfidenceBadge from '../common/ConfidenceBadge';
import EmptyState from '../common/EmptyState';
import IconButton from '../common/IconButton';
import Skeleton from '../common/Skeleton';

import type { PlateRead, PlateReadListResponse } from '../../types/plateRead';

// ============================================================================
// Types
// ============================================================================

export interface PlateDetailModalProps {
  /** Plate text to display details for. Pass null to close the modal. */
  plateText: string | null;
  /** Callback when the modal should close */
  onClose: () => void;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format timestamp to a readable date/time string.
 */
function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return isoString;
  }
}

/**
 * Format relative time from timestamp.
 */
function formatRelativeTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;

    return formatTimestamp(isoString);
  } catch {
    return isoString;
  }
}

/**
 * Get badge color classes based on confidence level.
 */
function getConfidenceBadgeClasses(confidence: number): string {
  const level = getConfidenceLevel(confidence);
  switch (level) {
    case 'high':
      return 'bg-green-500/20 text-green-400 border-green-500/30';
    case 'medium':
      return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    case 'low':
      return 'bg-red-500/20 text-red-400 border-red-500/30';
    default:
      return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  }
}

/**
 * Get quality badge color classes.
 */
function getQualityBadgeClasses(score: number): string {
  if (score >= 0.9) return 'bg-green-500/20 text-green-400';
  if (score >= 0.7) return 'bg-blue-500/20 text-blue-400';
  if (score >= 0.5) return 'bg-yellow-500/20 text-yellow-400';
  return 'bg-red-500/20 text-red-400';
}

// ============================================================================
// Sub-Components
// ============================================================================

interface PlateReadItemProps {
  read: PlateRead;
}

/**
 * Individual plate read item in the timeline.
 */
function PlateReadItem({ read }: PlateReadItemProps) {
  return (
    <div
      className="flex items-start gap-4 rounded-lg border border-gray-800 bg-black/30 p-4"
      data-testid={`plate-read-item-${read.id}`}
    >
      {/* Timestamp Column */}
      <div className="flex flex-col">
        <span className="text-sm font-medium text-white">
          {formatTimestamp(read.timestamp)}
        </span>
        <span className="text-xs text-gray-500">
          {formatRelativeTime(read.timestamp)}
        </span>
      </div>

      {/* Camera */}
      <div className="flex items-center gap-1.5 text-sm text-gray-400">
        <Camera className="h-4 w-4" />
        <span>{read.camera_id}</span>
      </div>

      {/* Confidence Badge */}
      <div className="ml-auto flex items-center gap-2">
        <ConfidenceBadge confidence={read.ocr_confidence} size="sm" />

        {/* Quality Indicator */}
        <span
          className={clsx(
            'rounded px-2 py-0.5 text-xs font-medium',
            getQualityBadgeClasses(read.image_quality_score)
          )}
          title={`Quality: ${formatConfidence(read.image_quality_score)}`}
        >
          {getQualityLabel(read.image_quality_score)}
        </span>

        {/* Enhanced indicator */}
        {read.is_enhanced && (
          <span
            className="flex items-center gap-1 rounded bg-purple-500/20 px-2 py-0.5 text-xs font-medium text-purple-400"
            title="Low-light enhancement applied"
          >
            <Sparkles className="h-3 w-3" />
            Enhanced
          </span>
        )}

        {/* Blurry indicator */}
        {read.is_blurry && (
          <span
            className="flex items-center gap-1 rounded bg-orange-500/20 px-2 py-0.5 text-xs font-medium text-orange-400"
            title="Motion blur detected"
          >
            <ImageOff className="h-3 w-3" />
            Blurry
          </span>
        )}
      </div>
    </div>
  );
}

interface CameraBreakdownProps {
  reads: PlateRead[];
}

/**
 * Camera breakdown showing which cameras detected this plate.
 */
function CameraBreakdown({ reads }: CameraBreakdownProps) {
  const cameraStats = useMemo(() => {
    const stats = new Map<string, number>();
    for (const read of reads) {
      stats.set(read.camera_id, (stats.get(read.camera_id) ?? 0) + 1);
    }
    return Array.from(stats.entries()).sort((a, b) => b[1] - a[1]);
  }, [reads]);

  if (cameraStats.length === 0) {
    return null;
  }

  return (
    <div className="mb-6" data-testid="camera-breakdown">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
        Camera Breakdown
      </h3>
      <div className="flex flex-wrap gap-2">
        {cameraStats.map(([cameraId, count]) => (
          <span
            key={cameraId}
            className="flex items-center gap-1.5 rounded-full bg-gray-800 px-3 py-1 text-sm text-gray-300"
          >
            <Camera className="h-3.5 w-3.5" />
            {cameraId}
            <span className="ml-1 rounded bg-gray-700 px-1.5 py-0.5 text-xs font-medium">
              {count}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * PlateDetailModal displays complete history for a selected license plate.
 *
 * Features:
 * - Summary section with first/last seen, total count, average confidence
 * - Camera breakdown showing detection distribution
 * - Paginated timeline of all detections
 * - Loading, error, and empty states
 */
export function PlateDetailModal({ plateText, onClose }: PlateDetailModalProps) {
  const isOpen = plateText !== null;
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Fetch vehicle match for this plate
  const { match: vehicleMatch } = useVehicleMatchQuery(plateText);

  // Fetch plate history
  const {
    data,
    isLoading,
    isError,
    error,
  } = useQuery<PlateReadListResponse, Error>({
    queryKey: ['plate-detail', plateText, page],
    queryFn: () =>
      searchPlateReads({
        text: plateText ?? '',
        exact: true,
        page,
        page_size: pageSize,
      }),
    enabled: isOpen && !!plateText,
  });

  const plateReads = useMemo(() => data?.plate_reads ?? [], [data?.plate_reads]);
  const totalCount = data?.total ?? 0;
  const totalPages = Math.ceil(totalCount / pageSize);

  // Calculate summary statistics
  const summary = useMemo(() => {
    if (plateReads.length === 0) {
      return {
        firstSeen: null,
        lastSeen: null,
        avgConfidence: 0,
        avgQuality: 0,
        enhancedCount: 0,
        blurryCount: 0,
      };
    }

    // Sort by timestamp
    const sortedReads = [...plateReads].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

    const firstSeen = sortedReads[0].timestamp;
    const lastSeen = sortedReads[sortedReads.length - 1].timestamp;

    const avgConfidence =
      plateReads.reduce((sum, r) => sum + r.ocr_confidence, 0) / plateReads.length;
    const avgQuality =
      plateReads.reduce((sum, r) => sum + r.image_quality_score, 0) / plateReads.length;
    const enhancedCount = plateReads.filter((r) => r.is_enhanced).length;
    const blurryCount = plateReads.filter((r) => r.is_blurry).length;

    return {
      firstSeen,
      lastSeen,
      avgConfidence,
      avgQuality,
      enhancedCount,
      blurryCount,
    };
  }, [plateReads]);

  // Pagination handlers
  const handlePrevPage = useCallback(() => {
    setPage((p) => Math.max(1, p - 1));
  }, []);

  const handleNextPage = useCallback(() => {
    setPage((p) => Math.min(totalPages, p + 1));
  }, [totalPages]);

  // Reset page when plate changes
  const handleClose = useCallback(() => {
    setPage(1);
    onClose();
  }, [onClose]);

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={handleClose}>
        {/* Backdrop */}
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/75" aria-hidden="true" />
        </Transition.Child>

        {/* Modal content */}
        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel
                className="w-full max-w-3xl transform overflow-hidden rounded-xl border border-gray-800 bg-[#1A1A1A] shadow-2xl transition-all"
                data-testid="plate-detail-modal"
              >
                {/* Header */}
                <div className="flex items-start justify-between border-b border-gray-800 p-6">
                  <div>
                    <Dialog.Title
                      as="h2"
                      className="flex items-center gap-3 text-2xl font-bold text-white"
                      data-testid="plate-detail-title"
                    >
                      <span
                        className="rounded-lg bg-blue-500/20 px-4 py-2 font-mono text-blue-400"
                        data-testid="plate-text-display"
                      >
                        {plateText}
                      </span>
                      {plateText && (
                        <VehicleMatchBadge
                          plateText={plateText}
                          showDetails
                          data-testid="plate-vehicle-match-badge"
                        />
                      )}
                    </Dialog.Title>
                    <p className="mt-2 text-sm text-gray-400">
                      License plate detection history
                    </p>
                    {/* Vehicle Info Section - shown when plate matches a registered vehicle */}
                    {vehicleMatch && (
                      <div
                        className="mt-3 rounded-lg border border-green-500/30 bg-green-500/10 p-3"
                        data-testid="vehicle-match-info"
                      >
                        <p className="text-sm font-medium text-green-400">
                          Registered Vehicle: {vehicleMatch.vehicle.description}
                        </p>
                        <div className="mt-1 flex flex-wrap gap-3 text-xs text-gray-400">
                          {vehicleMatch.vehicle.color && (
                            <span>Color: {vehicleMatch.vehicle.color}</span>
                          )}
                          {vehicleMatch.owner && (
                            <span>Owner: {vehicleMatch.owner.name} ({vehicleMatch.owner.role})</span>
                          )}
                          <span>
                            Trust: {vehicleMatch.vehicle.trusted ? 'Trusted' : 'Untrusted'}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                  <IconButton
                    icon={<X />}
                    aria-label="Close modal"
                    onClick={handleClose}
                    variant="ghost"
                    size="lg"
                    data-testid="close-modal-button"
                  />
                </div>

                {/* Content */}
                <div className="max-h-[calc(100vh-200px)] overflow-y-auto p-6">
                  {/* Loading State */}
                  {isLoading && (
                    <div data-testid="plate-detail-loading">
                      {/* Summary skeleton */}
                      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
                        {[1, 2, 3, 4].map((i) => (
                          <Skeleton
                            key={i}
                            variant="rectangular"
                            height={80}
                            data-testid={`skeleton-stat-${i}`}
                          />
                        ))}
                      </div>
                      {/* Timeline skeleton */}
                      <div className="space-y-3">
                        {[1, 2, 3].map((i) => (
                          <Skeleton
                            key={i}
                            variant="rectangular"
                            height={72}
                            data-testid={`skeleton-item-${i}`}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Error State */}
                  {isError && (
                    <div
                      className="flex flex-col items-center justify-center py-12"
                      data-testid="plate-detail-error"
                    >
                      <AlertCircle className="h-12 w-12 text-red-500" />
                      <p className="mt-4 text-lg font-medium text-white">
                        Failed to load plate history
                      </p>
                      <p className="mt-2 text-sm text-gray-400">
                        {error?.message ?? 'An unexpected error occurred'}
                      </p>
                    </div>
                  )}

                  {/* Empty State */}
                  {!isLoading && !isError && plateReads.length === 0 && (
                    <EmptyState
                      icon={Camera}
                      title="No detections found"
                      description={`No plate reads found for "${plateText ?? ''}"`}
                      variant="muted"
                      size="sm"
                      testId="plate-detail-empty"
                    />
                  )}

                  {/* Content */}
                  {!isLoading && !isError && plateReads.length > 0 && (
                    <>
                      {/* Summary Section */}
                      <div
                        className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4"
                        data-testid="plate-summary"
                      >
                        {/* First Seen */}
                        <div className="rounded-lg border border-gray-800 bg-black/30 p-3">
                          <div className="flex items-center gap-2 text-sm font-medium text-gray-400">
                            <Clock className="h-4 w-4" />
                            First seen
                          </div>
                          <p
                            className="mt-1 text-sm text-white"
                            data-testid="first-seen"
                          >
                            {summary.firstSeen
                              ? formatTimestamp(summary.firstSeen)
                              : 'N/A'}
                          </p>
                        </div>

                        {/* Last Seen */}
                        <div className="rounded-lg border border-gray-800 bg-black/30 p-3">
                          <div className="flex items-center gap-2 text-sm font-medium text-gray-400">
                            <Clock className="h-4 w-4" />
                            Last seen
                          </div>
                          <p
                            className="mt-1 text-sm text-white"
                            data-testid="last-seen"
                          >
                            {summary.lastSeen
                              ? formatTimestamp(summary.lastSeen)
                              : 'N/A'}
                          </p>
                        </div>

                        {/* Total Count */}
                        <div className="rounded-lg border border-gray-800 bg-black/30 p-3">
                          <div className="text-sm font-medium text-gray-400">
                            Total Detections
                          </div>
                          <p
                            className="mt-1 text-2xl font-bold text-white"
                            data-testid="total-count"
                          >
                            {totalCount}
                          </p>
                        </div>

                        {/* Average Confidence */}
                        <div className="rounded-lg border border-gray-800 bg-black/30 p-3">
                          <div className="text-sm font-medium text-gray-400">
                            Avg Confidence
                          </div>
                          <div className="mt-1" data-testid="avg-confidence">
                            <span
                              className={clsx(
                                'rounded border px-2 py-1 text-sm font-medium',
                                getConfidenceBadgeClasses(summary.avgConfidence)
                              )}
                            >
                              {formatConfidence(summary.avgConfidence)}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Camera Breakdown */}
                      <CameraBreakdown reads={plateReads} />

                      {/* Timeline Header */}
                      <div className="mb-3 flex items-center justify-between">
                        <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
                          Detection Timeline
                        </h3>
                        <span className="text-sm text-gray-500">
                          {(page - 1) * pageSize + 1}-
                          {Math.min(page * pageSize, totalCount)} of {totalCount}
                        </span>
                      </div>

                      {/* Timeline List */}
                      <div
                        className="space-y-3"
                        data-testid="plate-reads-timeline"
                      >
                        {plateReads.map((read) => (
                          <PlateReadItem key={read.id} read={read} />
                        ))}
                      </div>

                      {/* Pagination */}
                      {totalPages > 1 && (
                        <div
                          className="mt-6 flex items-center justify-center gap-4"
                          data-testid="pagination-controls"
                        >
                          <IconButton
                            icon={<ChevronLeft />}
                            aria-label="Previous page"
                            onClick={handlePrevPage}
                            disabled={page === 1}
                            variant="ghost"
                            data-testid="prev-page-button"
                          />
                          <span className="text-sm text-gray-400">
                            Page {page} of {totalPages}
                          </span>
                          <IconButton
                            icon={<ChevronRight />}
                            aria-label="Next page"
                            onClick={handleNextPage}
                            disabled={page >= totalPages}
                            variant="ghost"
                            data-testid="next-page-button"
                          />
                        </div>
                      )}
                    </>
                  )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end border-t border-gray-800 bg-black/20 p-4">
                  <button
                    onClick={handleClose}
                    className="rounded-lg bg-gray-800 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-gray-700"
                    data-testid="footer-close-button"
                  >
                    Close
                  </button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}

export default PlateDetailModal;
