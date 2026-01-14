import { AlertTriangle, Bell, Loader2, RefreshCw } from 'lucide-react';
import { useMemo, useState } from 'react';

import { useAlertsInfiniteQuery, useInfiniteScroll, useCamerasQuery, useSnoozeEvent } from '../../hooks';
import { updateEvent } from '../../services/api';
import { getRiskLevel } from '../../utils/risk';
import RiskBadge from '../common/RiskBadge';
import SafeErrorMessage from '../common/SafeErrorMessage';
import EventCard from '../events/EventCard';
import EventDetailModal from '../events/EventDetailModal';

import type { AlertRiskFilter } from '../../hooks';
import type { Event } from '../../services/api';
import type { RiskLevel } from '../../utils/risk';
import type { Detection } from '../events/EventCard';
import type { Event as ModalEvent } from '../events/EventDetailModal';

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
 */
export default function AlertsPage({ onViewEventDetails, className = '' }: AlertsPageProps) {
  // State for selected risk level filter (high or critical)
  const [riskFilter, setRiskFilter] = useState<AlertRiskFilter>('all');

  // State for event detail modal
  const [selectedEventForModal, setSelectedEventForModal] = useState<number | null>(null);

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
      onViewDetails: onViewEventDetails ? () => onViewEventDetails(event.id) : undefined,
      onClick: (eventId: string) => setSelectedEventForModal(parseInt(eventId, 10)),
      onSnooze: handleSnooze,
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

  return (
    <div data-testid="alerts-page" className={`flex flex-col ${className}`}>
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <AlertTriangle className="h-8 w-8 text-orange-500" />
          <h1 className="text-3xl font-bold text-white">Alerts</h1>
        </div>
        <p className="mt-2 text-gray-400">High and critical risk events requiring attention</p>
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

      {/* Results Summary */}
      <div className="mb-4 flex flex-col gap-2">
        <p className="text-sm text-gray-400">
          {isLoading
            ? 'Loading...'
            : `${totalCount} alert${totalCount !== 1 ? 's' : ''} found`}
          {alerts.length < totalCount && ` (showing ${alerts.length})`}
        </p>
        {/* Risk Summary Badges */}
        {!isLoading && !isError && alerts.length > 0 && (
          <div className="flex items-center gap-2 text-sm">
            {riskCounts.critical > 0 && (
              <div className="flex items-center gap-1.5">
                <RiskBadge level="critical" size="sm" animated={false} />
                <span className="font-semibold text-red-400">{riskCounts.critical}</span>
              </div>
            )}
            {riskCounts.high > 0 && (
              <div className="flex items-center gap-1.5">
                <RiskBadge level="high" size="sm" animated={false} />
                <span className="font-semibold text-orange-400">{riskCounts.high}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Alert List */}
      {isLoading ? (
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]">
          <div className="text-center">
            <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-700 border-t-[#76B900]" />
            <p className="text-gray-400">Loading alerts...</p>
          </div>
        </div>
      ) : isError ? (
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-red-900/50 bg-red-950/20">
          <div className="text-center">
            <p className="mb-2 text-lg font-semibold text-red-400">Error Loading Alerts</p>
            <SafeErrorMessage message={error?.message || 'An error occurred'} size="sm" color="gray" />
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
      ) : (
        <>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
            {alerts.map((event: Event) => (
              <EventCard key={event.id} {...getEventCardProps(event)} />
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
