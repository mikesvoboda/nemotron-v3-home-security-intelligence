/**
 * MemberDetectionHistory - Display paginated list of detections linked to a member
 *
 * Features:
 * - Paginated detection list
 * - Filter by camera, date range
 * - Sort by date or confidence
 * - Unlink detection with confirmation
 * - Empty state when no detections
 * - Loading and error states
 *
 * @module components/household/MemberDetectionHistory
 * @see NEM-4855 Phase 2 - Person-Entity Linking
 */

import { Dialog, Transition } from '@headlessui/react';
import {
  AlertTriangle,
  Camera,
  Filter,
  Loader2,
  RefreshCw,
  X,
} from 'lucide-react';
import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';

import {
  useMemberDetectionsQuery,
  useUnlinkDetection,
} from '../../hooks/useHouseholdApi';

import type { MemberDetection, MemberDetectionsParams } from '../../hooks/useHouseholdApi';

// ============================================================================
// Types
// ============================================================================

interface MemberDetectionHistoryProps {
  memberId: number;
  memberName?: string;
  onNavigate?: (params: { eventId: number; detectionId: number }) => void;
}

type SortOption = 'date_desc' | 'date_asc' | 'confidence_desc' | 'confidence_asc';

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format date for display in YYYY-MM-DD format.
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Format time for display in HH:MM format.
 */
function formatTime(dateString: string): string {
  const date = new Date(dateString);
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${hours}:${minutes}`;
}

/**
 * Format confidence as percentage.
 */
function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

// ============================================================================
// Constants
// ============================================================================

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: 'date_desc', label: 'Newest First' },
  { value: 'date_asc', label: 'Oldest First' },
  { value: 'confidence_desc', label: 'Highest Confidence' },
  { value: 'confidence_asc', label: 'Lowest Confidence' },
];

const DEFAULT_LIMIT = 20;

// ============================================================================
// Components
// ============================================================================

/**
 * Unlink confirmation dialog.
 */
function UnlinkConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  isUnlinking,
}: {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isUnlinking: boolean;
}) {
  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/50" />
        </Transition.Child>

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
              <Dialog.Panel className="w-full max-w-md transform rounded-lg bg-[#1A1A1A] border border-gray-700 p-6 shadow-xl transition-all">
                <div className="flex items-center gap-3 mb-4">
                  <AlertTriangle className="h-6 w-6 text-yellow-500" />
                  <Dialog.Title className="text-lg font-semibold text-white">
                    Unlink Detection
                  </Dialog.Title>
                </div>

                <p className="text-gray-300 mb-6">
                  Are you sure you want to unlink this detection? This will remove the association
                  between this person detection and the household member.
                </p>

                <div className="flex justify-end gap-3">
                  <button
                    type="button"
                    onClick={onClose}
                    disabled={isUnlinking}
                    className="px-4 py-2 text-sm font-medium text-gray-300 hover:text-white transition-colors disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={onConfirm}
                    disabled={isUnlinking}
                    className="px-4 py-2 text-sm font-medium bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
                  >
                    {isUnlinking && <Loader2 className="h-4 w-4 animate-spin" />}
                    Confirm
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

/**
 * Detection row component.
 */
function DetectionRow({
  detection,
  onUnlink,
  onView,
}: {
  detection: MemberDetection;
  onUnlink: () => void;
  onView: () => void;
}) {
  const thumbnailUrl = detection.thumbnail_url || '/placeholder-person.png';

  return (
    <div
      data-testid="detection-card"
      className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-4 hover:border-gray-600 transition-colors"
    >
      <div className="flex items-center gap-4">
        {/* Thumbnail */}
        <img
          src={thumbnailUrl}
          alt="Detection thumbnail"
          className="w-16 h-16 object-cover rounded-lg border border-gray-700 flex-shrink-0"
        />

        {/* Content */}
        <div className="flex-1 min-w-0">
          <p className="text-white font-medium truncate">{detection.event_summary}</p>
          <div className="mt-1 text-sm text-gray-400">
            <span>{detection.camera_name}</span>
            <span className="mx-2">-</span>
            <span>{formatDate(detection.detected_at)} at {formatTime(detection.detected_at)}</span>
          </div>
          <div className="mt-1 text-sm text-gray-400">
            <span>Confidence: {formatConfidence(detection.confidence)}</span>
            <span className="mx-2">-</span>
            <span>Risk: {detection.event_risk_score}</span>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            <span>Linked at </span>
            <span>{formatTime(detection.linked_at)}</span>
          </div>
          {detection.notes && (
            <div className="text-xs text-gray-500 mt-1">
              Notes: {detection.notes}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            type="button"
            onClick={onView}
            className="px-3 py-1.5 text-xs font-medium text-[#76B900] hover:bg-[#76B900]/10 rounded transition-colors"
            aria-label="View event"
          >
            View Event
          </button>
          <button
            type="button"
            onClick={onUnlink}
            className="px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-500/10 rounded transition-colors"
            aria-label="Unlink"
          >
            Unlink
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function MemberDetectionHistory({
  memberId,
  memberName = 'Member',
  onNavigate,
}: MemberDetectionHistoryProps) {

  // State
  const [localDetections, setLocalDetections] = useState<MemberDetection[]>([]);
  const [offset, setOffset] = useState(0);
  const [cameraFilter, setCameraFilter] = useState<string>('');
  const [fromDate, setFromDate] = useState<string>('');
  const [toDate, setToDate] = useState<string>('');
  const [sort, setSort] = useState<SortOption>('date_desc');
  const [unlinkTarget, setUnlinkTarget] = useState<number | null>(null);
  const [unlinkError, setUnlinkError] = useState<string | null>(null);

  // Build query params
  const queryParams: MemberDetectionsParams = useMemo(
    () => ({
      limit: DEFAULT_LIMIT,
      offset,
      camera: cameraFilter || undefined,
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
      sort,
    }),
    [offset, cameraFilter, fromDate, toDate, sort]
  );

  // Data fetching
  const detectionsQuery = useMemberDetectionsQuery(memberId, queryParams);
  const unlinkMutation = useUnlinkDetection();

  // Sync local detections with query data
  useEffect(() => {
    if (detectionsQuery.data?.items) {
      if (offset === 0) {
        setLocalDetections(detectionsQuery.data.items);
      } else {
        // Append new items for "Load More"
        setLocalDetections((prev) => {
          const existingIds = new Set(prev.map((d) => d.detection_id));
          const newItems = detectionsQuery.data.items.filter(
            (d) => !existingIds.has(d.detection_id)
          );
          return [...prev, ...newItems];
        });
      }
    }
  }, [detectionsQuery.data, offset]);

  // Reset offset when filters change
  useEffect(() => {
    setOffset(0);
  }, [cameraFilter, fromDate, toDate, sort]);

  // Extract unique camera names
  const cameraOptions = useMemo(() => {
    const cameras = new Set<string>();
    localDetections.forEach((d) => cameras.add(d.camera_name));
    return Array.from(cameras).sort();
  }, [localDetections]);

  // Computed values
  const total = detectionsQuery.data?.total ?? 0;
  const hasMore = localDetections.length < total;
  const isLoadingMore = detectionsQuery.isLoading && offset > 0;
  const isInitialLoading = detectionsQuery.isLoading && offset === 0 && localDetections.length === 0;

  // Handlers
  const handleLoadMore = useCallback(() => {
    setOffset((prev) => prev + localDetections.length);
  }, [localDetections.length]);

  const handleClearFilters = useCallback(() => {
    setCameraFilter('');
    setFromDate('');
    setToDate('');
    setOffset(0);
  }, []);

  const handleUnlink = useCallback((detectionId: number) => {
    setUnlinkTarget(detectionId);
    setUnlinkError(null);
  }, []);

  const handleConfirmUnlink = useCallback(() => {
    if (unlinkTarget === null) return;

    unlinkMutation.mutate(
      { memberId, detectionId: unlinkTarget },
      {
        onSuccess: () => {
          setLocalDetections((prev) =>
            prev.filter((d) => d.detection_id !== unlinkTarget)
          );
          setUnlinkTarget(null);
          setUnlinkError(null);
        },
        onError: (error) => {
          setUnlinkError((error)?.message || 'Failed to unlink detection');
        },
      }
    );
  }, [unlinkTarget, memberId, unlinkMutation]);

  const handleCancelUnlink = useCallback(() => {
    setUnlinkTarget(null);
    setUnlinkError(null);
  }, []);

  const handleViewEvent = useCallback(
    (detection: MemberDetection) => {
      if (onNavigate) {
        onNavigate({ eventId: detection.event_id, detectionId: detection.detection_id });
      }
      // If no onNavigate prop, use window.location for navigation
      // (component may be used without router context)
      else if (typeof window !== 'undefined') {
        window.location.href = `/events/${detection.event_id}`;
      }
    },
    [onNavigate]
  );

  const handleRetry = useCallback(() => {
    void detectionsQuery.refetch();
  }, [detectionsQuery]);

  // Loading state
  if (isInitialLoading) {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-white">
          Detection History for {memberName}
        </h2>
        <div
          role="status"
          aria-label="Loading"
          className="flex items-center justify-center py-12"
        >
          <Loader2
            className="h-8 w-8 animate-spin text-[#76B900]"
            data-testid="loading-spinner"
          />
          <span className="ml-2 text-gray-400">Loading detections...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (detectionsQuery.isError) {
    const errorMessage =
      (detectionsQuery.error)?.message || 'An error occurred';

    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-white">
          Detection History for {memberName}
        </h2>
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-6 text-center">
          <p className="text-red-400 mb-4">{errorMessage}</p>
          <button
            type="button"
            onClick={handleRetry}
            className="px-4 py-2 text-sm font-medium bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors inline-flex items-center gap-2"
            aria-label="Retry"
          >
            <RefreshCw className="h-4 w-4" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Empty state
  if (localDetections.length === 0 && !detectionsQuery.isLoading) {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-white">
          Detection History for {memberName}
        </h2>
        <div className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-8 text-center">
          <Camera className="h-12 w-12 mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400 mb-2">No detections found</p>
          <p className="text-sm text-gray-500">
            {memberName} has not been linked to any detections yet.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <h2 className="text-lg font-semibold text-white">
        Detection History for {memberName}
      </h2>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4 p-4 rounded-lg bg-[#1A1A1A] border border-gray-700">
        {/* Camera Filter */}
        <div className="flex items-center gap-2">
          <label htmlFor="camera-filter" className="text-sm text-gray-400">
            <Filter className="h-4 w-4 inline mr-1" />
            Filter by Camera
          </label>
          <select
            id="camera-filter"
            aria-label="Filter by Camera"
            value={cameraFilter}
            onChange={(e) => setCameraFilter(e.target.value)}
            className="px-3 py-1.5 bg-[#121212] border border-gray-700 rounded text-sm text-white focus:outline-none focus:ring-2 focus:ring-[#76B900]"
          >
            <option value="">All Cameras</option>
            {cameraOptions.map((camera) => (
              <option key={camera} value={camera}>
                {camera}
              </option>
            ))}
          </select>
        </div>

        {/* Date Range */}
        <div className="flex items-center gap-2">
          <label htmlFor="from-date" className="text-sm text-gray-400">
            From Date
          </label>
          <input
            type="date"
            id="from-date"
            aria-label="From Date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="px-3 py-1.5 bg-[#121212] border border-gray-700 rounded text-sm text-white focus:outline-none focus:ring-2 focus:ring-[#76B900]"
          />
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="to-date" className="text-sm text-gray-400">
            To Date
          </label>
          <input
            type="date"
            id="to-date"
            aria-label="To Date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className="px-3 py-1.5 bg-[#121212] border border-gray-700 rounded text-sm text-white focus:outline-none focus:ring-2 focus:ring-[#76B900]"
          />
        </div>

        {/* Sort */}
        <div className="flex items-center gap-2">
          <label htmlFor="sort-select" className="text-sm text-gray-400">
            Sort by
          </label>
          <select
            id="sort-select"
            aria-label="Sort by"
            value={sort}
            onChange={(e) => setSort(e.target.value as SortOption)}
            className="px-3 py-1.5 bg-[#121212] border border-gray-700 rounded text-sm text-white focus:outline-none focus:ring-2 focus:ring-[#76B900]"
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {/* Clear Filters */}
        <button
          type="button"
          onClick={handleClearFilters}
          className="px-3 py-1.5 text-sm font-medium text-gray-400 hover:text-white transition-colors"
          aria-label="Clear filters"
        >
          <X className="h-4 w-4 inline mr-1" />
          Clear Filters
        </button>
      </div>

      {/* Unlink Error Display (global) */}
      {unlinkError && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30">
          <p className="text-sm text-red-400">{unlinkError}</p>
        </div>
      )}

      {/* Detection List */}
      <div className="space-y-3">
        {localDetections.map((detection) => (
          <DetectionRow
            key={detection.detection_id}
            detection={detection}
            onUnlink={() => handleUnlink(detection.detection_id)}
            onView={() => handleViewEvent(detection)}
          />
        ))}
      </div>

      {/* Pagination */}
      {total > 0 && (
        <div className="flex items-center justify-between py-4">
          <p className="text-sm text-gray-400">
            Showing 1-{localDetections.length} of {total}
          </p>

          {hasMore && (
            <button
              type="button"
              onClick={handleLoadMore}
              disabled={isLoadingMore}
              className="px-4 py-2 text-sm font-medium bg-[#76B900] hover:bg-[#5a8f00] text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
              aria-label={isLoadingMore ? 'Loading' : 'Load More'}
            >
              {isLoadingMore && (
                <span role="status">
                  <Loader2 className="h-4 w-4 animate-spin" />
                </span>
              )}
              {isLoadingMore ? 'Loading...' : 'Load More'}
            </button>
          )}
        </div>
      )}

      {/* Unlink Confirmation Dialog */}
      <UnlinkConfirmDialog
        isOpen={unlinkTarget !== null}
        onClose={handleCancelUnlink}
        onConfirm={handleConfirmUnlink}
        isUnlinking={unlinkMutation.isPending}
      />
    </div>
  );
}
