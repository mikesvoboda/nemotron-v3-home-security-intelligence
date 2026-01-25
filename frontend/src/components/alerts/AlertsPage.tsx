import { AlertTriangle, Bell, Grid, Loader2, Rows3, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

import AlertCameraGroup from './AlertCameraGroup';
import BulkActionBar from './BulkActionBar';
import {
  useAlertsInfiniteQuery,
  useInfiniteScroll,
  useCamerasQuery,
  useSnoozeEvent,
} from '../../hooks';
import { updateEvent } from '../../services/api';
import { getRiskLevel } from '../../utils/risk';
import { FeatureErrorBoundary } from '../common/FeatureErrorBoundary';
import SafeErrorMessage from '../common/SafeErrorMessage';
import { AlertCardSkeleton } from '../common/skeletons';
import EventCard from '../events/EventCard';
import EventDetailModal from '../events/EventDetailModal';

import type { AlertRiskFilter } from '../../hooks';
import type { Event } from '../../services/api';
import type { RiskLevel } from '../../utils/risk';
import type { Detection } from '../events/EventCard';
import type { Event as ModalEvent } from '../events/EventDetailModal';

/** Represents a group of alerts for a single camera */
interface CameraAlertGroup {
  cameraId: string;
  cameraName: string;
  alerts: Event[];
  highestSeverity: RiskLevel;
}

// Severity ranking for sorting (lower number = higher severity)
// Defined outside component to avoid unnecessary recreations
const SEVERITY_RANK: Record<RiskLevel, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

export interface AlertsPageProps {
  onViewEventDetails?: (eventId: number) => void;
  className?: string;
}

/**
 * AlertsPage component displays high and critical risk security events
 * These are events that require immediate attention.
 *
 * Uses cursor-based pagination with infinite scroll for efficient loading
 * of large datasets.
 *
 * Features:
 * - Bulk selection and dismiss functionality
 * - Keyboard shortcuts (Ctrl/Cmd+A to select all, Escape to clear)
 */
export default function AlertsPage({ onViewEventDetails, className = '' }: AlertsPageProps) {
  // State for selected risk level filter (high or critical)
  const [riskFilter, setRiskFilter] = useState<AlertRiskFilter>('all');

  // State for event detail modal
  const [selectedEventForModal, setSelectedEventForModal] = useState<number | null>(null);

  // State for bulk selection
  const [selectedAlerts, setSelectedAlerts] = useState<Set<number>>(new Set());
  const [isBulkProcessing, setIsBulkProcessing] = useState(false);

  // State for view mode (grouped by camera or flat grid)
  const [viewMode, setViewMode] = useState<'grouped' | 'grid'>('grouped');

  // Fetch cameras for camera name lookup
  const { cameras } = useCamerasQuery();

  // Snooze mutation
  const { snooze } = useSnoozeEvent();

  // Fetch alerts with infinite scroll support
  const {
    alerts,
    totalCount,
    isLoading,
    isFetching,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    error,
    isError,
    refetch,
  } = useAlertsInfiniteQuery({
    riskFilter,
    limit: 25,
  });

  // Set up infinite scroll
  const { sentinelRef, isLoadingMore } = useInfiniteScroll({
    onLoadMore: fetchNextPage,
    hasMore: hasNextPage,
    isLoading: isFetchingNextPage,
  });

  // Create a memoized camera name lookup map
  const cameraNameMap = useMemo(() => {
    const map = new Map<string, string>();
    cameras.forEach((camera) => {
      map.set(camera.id, camera.name);
    });
    return map;
  }, [cameras]);

  // Calculate risk level counts from loaded alerts
  const riskCounts = useMemo(() => {
    return alerts.reduce(
      (acc: Record<RiskLevel, number>, event: Event) => {
        const level = event.risk_level || getRiskLevel(event.risk_score || 0);
        acc[level as RiskLevel] = (acc[level as RiskLevel] || 0) + 1;
        return acc;
      },
      { critical: 0, high: 0, medium: 0, low: 0 } as Record<RiskLevel, number>
    );
  }, [alerts]);

  // Sort alerts by severity (critical first) for grid view
  const sortedAlerts = useMemo(() => {
    return [...alerts].sort((a, b) => {
      const levelA = (a.risk_level as RiskLevel) || getRiskLevel(a.risk_score || 0);
      const levelB = (b.risk_level as RiskLevel) || getRiskLevel(b.risk_score || 0);
      const rankDiff = SEVERITY_RANK[levelA] - SEVERITY_RANK[levelB];
      if (rankDiff !== 0) return rankDiff;
      // Same severity - sort by timestamp (newest first)
      return new Date(b.started_at).getTime() - new Date(a.started_at).getTime();
    });
  }, [alerts]);

  // Group alerts by camera and sort by highest severity
  const cameraGroups = useMemo((): CameraAlertGroup[] => {
    // Group alerts by camera_id
    const groupMap = new Map<string, Event[]>();

    alerts.forEach((event: Event) => {
      const existing = groupMap.get(event.camera_id) || [];
      existing.push(event);
      groupMap.set(event.camera_id, existing);
    });

    // Convert to array with metadata
    const groups: CameraAlertGroup[] = Array.from(groupMap.entries()).map(
      ([cameraId, cameraAlerts]) => {
        // Find highest severity in this group
        let highestSeverity: RiskLevel = 'low';
        cameraAlerts.forEach((alert) => {
          const level = (alert.risk_level as RiskLevel) || getRiskLevel(alert.risk_score || 0);
          if (SEVERITY_RANK[level] < SEVERITY_RANK[highestSeverity]) {
            highestSeverity = level;
          }
        });

        return {
          cameraId,
          cameraName: cameraNameMap.get(cameraId) || 'Unknown Camera',
          alerts: cameraAlerts,
          highestSeverity,
        };
      }
    );

    // Sort groups by highest severity (critical first, then high, etc.)
    groups.sort((a, b) => SEVERITY_RANK[a.highestSeverity] - SEVERITY_RANK[b.highestSeverity]);

    return groups;
  }, [alerts, cameraNameMap]);

  // Bulk selection handlers
  const toggleSelection = useCallback((alertId: number) => {
    setSelectedAlerts((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(alertId)) {
        newSet.delete(alertId);
      } else {
        newSet.add(alertId);
      }
      return newSet;
    });
  }, []);

  const selectAll = useCallback(() => {
    const allIds = new Set(alerts.map((event: Event) => event.id));
    setSelectedAlerts(allIds);
  }, [alerts]);

  const clearSelection = useCallback(() => {
    setSelectedAlerts(new Set());
  }, []);

  const handleBulkDismiss = useCallback(async () => {
    if (selectedAlerts.size === 0) return;

    setIsBulkProcessing(true);
    try {
      // Dismiss all selected alerts by marking them as reviewed
      const promises = Array.from(selectedAlerts).map((id) => updateEvent(id, { reviewed: true }));
      await Promise.all(promises);

      // Clear selection and refetch
      setSelectedAlerts(new Set());
      void refetch();
    } catch (err) {
      console.error('Failed to dismiss selected alerts:', err);
    } finally {
      setIsBulkProcessing(false);
    }
  }, [selectedAlerts, refetch]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLInputElement;

      // Escape to clear selection - always works (even when focused on checkbox)
      if (e.key === 'Escape') {
        clearSelection();
        return;
      }

      // Don't trigger other shortcuts if user is typing in an input (except checkboxes)
      const isTextInput =
        (target.tagName === 'INPUT' && target.type !== 'checkbox') ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable;
      if (isTextInput) {
        return;
      }

      // Ctrl/Cmd+A to select all
      if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
        e.preventDefault();
        selectAll();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [selectAll, clearSelection]);

  // Clear selection when alerts change (e.g., filter change)
  useEffect(() => {
    setSelectedAlerts(new Set());
  }, [riskFilter]);

  // Convert Event to EventCard props
  const getEventCardProps = (event: Event) => {
    const camera_name = cameraNameMap.get(event.camera_id) || 'Unknown Camera';
    const detections: Detection[] = [];

    return {
      id: String(event.id),
      timestamp: event.started_at,
      camera_name,
      risk_score: event.risk_score || 0,
      risk_label: event.risk_level || getRiskLevel(event.risk_score || 0),
      summary: event.summary || 'No summary available',
      detections,
      started_at: event.started_at,
      ended_at: event.ended_at,
      thumbnail_url: event.thumbnail_url ?? undefined,
      onViewDetails: onViewEventDetails ? () => onViewEventDetails(event.id) : undefined,
      onClick: (eventId: string) => setSelectedEventForModal(parseInt(eventId, 10)),
      onSnooze: handleSnooze,
      hasCheckboxOverlay: true,
    };
  };

  // Handle modal close
  const handleModalClose = () => {
    setSelectedEventForModal(null);
  };

  // Handle mark as reviewed from modal
  const handleMarkReviewed = async (eventId: string) => {
    try {
      await updateEvent(parseInt(eventId, 10), { reviewed: true });
      // Refetch to reflect changes
      void refetch();
    } catch (err) {
      console.error('Failed to mark event as reviewed:', err);
    }
  };

  // Handle navigation between events in modal
  const handleNavigate = (direction: 'prev' | 'next') => {
    if (selectedEventForModal === null) return;

    const currentIndex = alerts.findIndex((e: Event) => e.id === selectedEventForModal);
    if (currentIndex === -1) return;

    const newIndex = direction === 'prev' ? currentIndex - 1 : currentIndex + 1;
    if (newIndex >= 0 && newIndex < alerts.length) {
      setSelectedEventForModal(alerts[newIndex].id);
    }
  };

  // Convert API Event to ModalEvent format
  const getModalEvent = (): ModalEvent | null => {
    if (selectedEventForModal === null) return null;

    const event = alerts.find((e: Event) => e.id === selectedEventForModal);
    if (!event) return null;

    const camera_name = cameraNameMap.get(event.camera_id) || 'Unknown Camera';

    return {
      id: String(event.id),
      timestamp: event.started_at,
      camera_name,
      risk_score: event.risk_score || 0,
      risk_label: event.risk_level || getRiskLevel(event.risk_score || 0),
      summary: event.summary || 'No summary available',
      detections: [], // Detections will be loaded by the modal
      started_at: event.started_at,
      ended_at: event.ended_at,
      reviewed: event.reviewed,
      notes: event.notes,
    };
  };

  // Handle snooze action
  const handleSnooze = (eventId: string, seconds: number) => {
    void snooze(parseInt(eventId, 10), seconds);
  };

  // Handle filter change - resets to first page
  const handleFilterChange = (newFilter: AlertRiskFilter) => {
    setRiskFilter(newFilter);
  };

  // Handle refresh
  const handleRefresh = () => {
    void refetch();
  };

  // Handle checkbox change
  const handleCheckboxChange = (eventId: number) => {
    toggleSelection(eventId);
  };

  // Handle dismiss all for a camera group
  const handleDismissAllForCamera = useCallback(
    async (cameraId: string) => {
      const group = cameraGroups.find((g) => g.cameraId === cameraId);
      if (!group) return;

      setIsBulkProcessing(true);
      try {
        const promises = group.alerts.map((alert) => updateEvent(alert.id, { reviewed: true }));
        await Promise.all(promises);
        void refetch();
      } catch (err) {
        console.error('Failed to dismiss alerts for camera:', err);
      } finally {
        setIsBulkProcessing(false);
      }
    },
    [cameraGroups, refetch]
  );

  return (
    <div data-testid="alerts-page" className={`flex flex-col ${className}`}>
      {/* Header with Alert Summary */}
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <AlertTriangle className="h-8 w-8 text-orange-500" />
          <h1 className="text-3xl font-bold text-white">Alerts</h1>
        </div>
        <p className="mt-2 text-gray-400">High and critical risk events requiring attention</p>

        {/* Prominent Alert Count Summary */}
        {!isLoading && !isError && alerts.length > 0 && (
          <div
            className="mt-4 flex flex-wrap items-center gap-3"
            data-testid="alert-severity-summary"
          >
            {riskCounts.critical > 0 && (
              <div className="flex items-center gap-2 rounded-lg border border-red-500/50 bg-red-500/10 px-4 py-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-red-500/20">
                  <span className="text-lg font-bold text-red-400">{riskCounts.critical}</span>
                </div>
                <span className="text-sm font-medium text-red-300">Critical</span>
              </div>
            )}
            {riskCounts.high > 0 && (
              <div className="flex items-center gap-2 rounded-lg border border-orange-500/50 bg-orange-500/10 px-4 py-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-orange-500/20">
                  <span className="text-lg font-bold text-orange-400">{riskCounts.high}</span>
                </div>
                <span className="text-sm font-medium text-orange-300">High</span>
              </div>
            )}
            {riskCounts.medium > 0 && (
              <div className="flex items-center gap-2 rounded-lg border border-yellow-500/50 bg-yellow-500/10 px-4 py-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-yellow-500/20">
                  <span className="text-lg font-bold text-yellow-400">{riskCounts.medium}</span>
                </div>
                <span className="text-sm font-medium text-yellow-300">Medium</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Filter and Refresh Bar */}
      <div className="mb-6 flex flex-col gap-4 rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <label htmlFor="risk-filter" className="text-sm font-medium text-gray-300">
            Filter by severity:
          </label>
          <select
            id="risk-filter"
            value={riskFilter}
            onChange={(e) => handleFilterChange(e.target.value as AlertRiskFilter)}
            className="rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
          >
            <option value="all">All Alerts</option>
            <option value="critical">Critical Only</option>
            <option value="high">High Only</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          {/* View Mode Toggle */}
          <div className="flex rounded-md border border-gray-700 bg-[#1A1A1A]">
            <button
              onClick={() => setViewMode('grouped')}
              aria-pressed={viewMode === 'grouped'}
              aria-label="Group by camera"
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium transition-colors ${
                viewMode === 'grouped'
                  ? 'bg-[#76B900]/20 text-[#76B900]'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              <Rows3 className="h-4 w-4" />
              <span className="hidden sm:inline">Grouped</span>
            </button>
            <button
              onClick={() => setViewMode('grid')}
              aria-pressed={viewMode === 'grid'}
              aria-label="Grid view"
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium transition-colors ${
                viewMode === 'grid'
                  ? 'bg-[#76B900]/20 text-[#76B900]'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              <Grid className="h-4 w-4" />
              <span className="hidden sm:inline">Grid</span>
            </button>
          </div>

          <button
            onClick={handleRefresh}
            disabled={isFetching}
            aria-label="Refresh alerts"
            className="flex items-center gap-2 rounded-md bg-[#76B900]/10 px-4 py-2 text-sm font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Results Summary */}
      <div className="mb-4">
        <p className="text-sm text-gray-400">
          {isLoading ? 'Loading...' : `${totalCount} alert${totalCount !== 1 ? 's' : ''} found`}
          {alerts.length < totalCount && ` (showing ${alerts.length})`}
        </p>
      </div>

      {/* Bulk Action Bar */}
      <BulkActionBar
        selectedCount={selectedAlerts.size}
        totalCount={alerts.length}
        onSelectAll={selectAll}
        onClearSelection={clearSelection}
        onDismissSelected={() => void handleBulkDismiss()}
        isProcessing={isBulkProcessing}
      />

      {/* Alert List */}
      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 6 }, (_, i) => (
            <AlertCardSkeleton key={i} />
          ))}
        </div>
      ) : isError ? (
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-red-900/50 bg-red-950/20">
          <div className="text-center">
            <p className="mb-2 text-lg font-semibold text-red-400">Error Loading Alerts</p>
            <SafeErrorMessage
              message={error?.message || 'An error occurred'}
              size="sm"
              color="gray"
            />
          </div>
        </div>
      ) : alerts.length === 0 ? (
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]">
          <div className="text-center">
            <Bell className="mx-auto mb-4 h-16 w-16 text-gray-600" />
            <p className="mb-2 text-lg font-semibold text-gray-300">No Alerts at This Time</p>
            <p className="text-sm text-gray-500">
              {riskFilter === 'all'
                ? 'There are no high or critical risk events to review. Keep up the good work!'
                : `There are no ${riskFilter} risk events to review.`}
            </p>
          </div>
        </div>
      ) : viewMode === 'grouped' ? (
        <>
          {/* Grouped View - Alerts grouped by camera */}
          <div className="flex flex-col gap-4" data-testid="alerts-grouped-view">
            {cameraGroups.map((group) => (
              <AlertCameraGroup
                key={group.cameraId}
                cameraId={group.cameraId}
                cameraName={group.cameraName}
                alerts={group.alerts}
                onSnooze={handleSnooze}
                onDismissAll={(cameraId) => void handleDismissAllForCamera(cameraId)}
                onAlertClick={(eventId) => setSelectedEventForModal(eventId)}
              />
            ))}
          </div>

          {/* Infinite Scroll Sentinel */}
          <div ref={sentinelRef} className="mt-4 flex justify-center py-4">
            {(isLoadingMore || isFetchingNextPage) && (
              <div className="flex items-center gap-2 text-gray-400">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span>Loading more alerts...</span>
              </div>
            )}
            {!hasNextPage && alerts.length > 0 && (
              <p className="text-sm text-gray-500">All alerts loaded</p>
            )}
          </div>
        </>
      ) : (
        <>
          {/* Grid View - Flat list of alerts sorted by severity */}
          <div
            className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3"
            data-testid="alerts-grid-view"
          >
            {sortedAlerts.map((event: Event) => {
              const isSelected = selectedAlerts.has(event.id);
              return (
                <div
                  key={event.id}
                  className={`relative ${isSelected ? 'rounded-lg ring-2 ring-[#76B900] ring-offset-2 ring-offset-[#121212]' : ''}`}
                >
                  {/* Checkbox overlay */}
                  <div className="absolute left-3 top-3 z-10">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => handleCheckboxChange(event.id)}
                      className="h-5 w-5 cursor-pointer rounded border-gray-600 bg-[#1A1A1A] text-[#76B900] focus:ring-2 focus:ring-[#76B900] focus:ring-offset-0"
                      aria-label={`Select alert ${event.id}`}
                    />
                  </div>
                  <EventCard {...getEventCardProps(event)} />
                </div>
              );
            })}
          </div>

          {/* Infinite Scroll Sentinel */}
          <div ref={sentinelRef} className="mt-4 flex justify-center py-4">
            {(isLoadingMore || isFetchingNextPage) && (
              <div className="flex items-center gap-2 text-gray-400">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span>Loading more alerts...</span>
              </div>
            )}
            {!hasNextPage && alerts.length > 0 && (
              <p className="text-sm text-gray-500">All alerts loaded</p>
            )}
          </div>
        </>
      )}

      {/* Event Detail Modal */}
      <EventDetailModal
        event={getModalEvent()}
        isOpen={selectedEventForModal !== null}
        onClose={handleModalClose}
        onMarkReviewed={(eventId) => void handleMarkReviewed(eventId)}
        onNavigate={handleNavigate}
      />
    </div>
  );
}

/**
 * AlertsPage with FeatureErrorBoundary wrapper.
 *
 * Wraps the AlertsContent component in a FeatureErrorBoundary to prevent
 * errors in the Alerts page from crashing the entire application.
 * Other parts of the dashboard will continue to work if this page errors.
 */
function AlertsPageWithErrorBoundary(props: AlertsPageProps) {
  return (
    <FeatureErrorBoundary
      feature="Alerts"
      fallback={
        <div className="flex min-h-[400px] flex-col items-center justify-center rounded-lg border border-red-500/30 bg-red-900/20 p-8 text-center">
          <AlertTriangle className="mb-4 h-12 w-12 text-red-400" />
          <h3 className="mb-2 text-lg font-semibold text-red-400">Alerts Unavailable</h3>
          <p className="max-w-md text-sm text-gray-400">
            Unable to load alerts. Please refresh the page or try again later. Other parts of the
            application should still work.
          </p>
        </div>
      }
    >
      <AlertsPage {...props} />
    </FeatureErrorBoundary>
  );
}

export { AlertsPageWithErrorBoundary };
