<<<<<<< HEAD
import { AlertTriangle, Bell, Loader2, RefreshCw } from 'lucide-react';
import { useMemo, useState } from 'react';

import { useAlertsInfiniteQuery, useInfiniteScroll, useCamerasQuery } from '../../hooks';
import { updateEvent } from '../../services/api';
=======
import { AlertTriangle, CheckCheck, Settings } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import AlertActions from './AlertActions';
import AlertCard from './AlertCard';
import AlertFilters from './AlertFilters';
import { fetchCameras, fetchEvents, isAbortError, updateEvent } from '../../services/api';
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)
import { getRiskLevel } from '../../utils/risk';

<<<<<<< HEAD
import type { AlertRiskFilter } from '../../hooks';
import type { Event } from '../../services/api';
import type { RiskLevel } from '../../utils/risk';
import type { Detection } from '../events/EventCard';
import type { Event as ModalEvent } from '../events/EventDetailModal';
=======
import type { AlertFilterType } from './AlertFilters';
import type { Camera, Event, EventsQueryParams } from '../../services/api';
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)

export interface AlertsPageProps {
  onConfigureRules?: () => void;
  className?: string;
}

interface AlertState {
  id: string;
  eventId: number;
  acknowledged: boolean;
  dismissed: boolean;
}

/**
<<<<<<< HEAD
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
=======
 * AlertsPage component - Redesigned with actionable alert management
 * Differentiates from Timeline with alert-specific actions and severity filtering
 */
export default function AlertsPage({ onConfigureRules, className = '' }: AlertsPageProps) {
  // Events data
  const [events, setEvents] = useState<Event[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Cameras for name lookup
  const [cameras, setCameras] = useState<Camera[]>([]);

  // Alert state management (acknowledged/dismissed)
  const [alertStates, setAlertStates] = useState<Map<string, AlertState>>(new Map());

  // Filter and selection state
  const [activeFilter, setActiveFilter] = useState<AlertFilterType>('all');
  const [selectedAlerts, setSelectedAlerts] = useState<Set<string>>(new Set());

  // Pagination
  const [pagination] = useState({
    limit: 50,
    offset: 0,
  });

  // Create camera name lookup map
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)
  const cameraNameMap = useMemo(() => {
    const map = new Map<string, string>();
    cameras.forEach((camera) => {
      map.set(camera.id, camera.name);
    });
    return map;
  }, [cameras]);

<<<<<<< HEAD
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
=======
  // Load cameras
  useEffect(() => {
    const loadCameras = async () => {
      try {
        const data = await fetchCameras();
        setCameras(data);
      } catch (err) {
        console.error('Failed to load cameras:', err);
      }
    };
    void loadCameras();
  }, []);

  // Load high/critical risk events
  useEffect(() => {
    const controller = new AbortController();

    const loadAlerts = async () => {
      setLoading(true);
      setError(null);
      try {
        // Fetch high risk events
        const highParams: EventsQueryParams = {
          risk_level: 'high',
          limit: pagination.limit,
          offset: pagination.offset,
        };
        const highResponse = await fetchEvents(highParams, { signal: controller.signal });

        // Fetch critical risk events
        const criticalParams: EventsQueryParams = {
          risk_level: 'critical',
          limit: pagination.limit,
          offset: pagination.offset,
        };
        const criticalResponse = await fetchEvents(criticalParams, { signal: controller.signal });

        // Combine and sort by timestamp
        const allAlerts = [...highResponse.items, ...criticalResponse.items];
        allAlerts.sort(
          (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
        );

        setEvents(allAlerts);
        setTotalCount(highResponse.pagination.total + criticalResponse.pagination.total);

        // Initialize alert states for new alerts
        const newStates = new Map(alertStates);
        allAlerts.forEach((event) => {
          const alertId = String(event.id);
          if (!newStates.has(alertId)) {
            newStates.set(alertId, {
              id: alertId,
              eventId: event.id,
              acknowledged: event.reviewed || false,
              dismissed: false,
            });
          }
        });
        setAlertStates(newStates);
      } catch (err) {
        if (isAbortError(err)) return;
        setError(err instanceof Error ? err.message : 'Failed to load alerts');
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };
    void loadAlerts();

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- alertStates not needed as dependency (would cause infinite loop)
  }, [pagination]);

  // Filter alerts based on active filter
  const filteredAlerts = useMemo(() => {
    return events.filter((event) => {
      const alertId = String(event.id);
      const alertState = alertStates.get(alertId);

      // Don't show dismissed alerts
      if (alertState?.dismissed) return false;

      const severity = event.risk_level || getRiskLevel(event.risk_score || 0);

      switch (activeFilter) {
        case 'all':
          return true;
        case 'critical':
          return severity === 'critical';
        case 'high':
          return severity === 'high';
        case 'medium':
          return severity === 'medium';
        case 'unread':
          return !alertState?.acknowledged;
        default:
          return true;
      }
    });
  }, [events, alertStates, activeFilter]);

  // Calculate filter counts
  const filterCounts = useMemo(() => {
    const counts = {
      all: 0,
      critical: 0,
      high: 0,
      medium: 0,
      unread: 0,
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)
    };

    events.forEach((event) => {
      const alertId = String(event.id);
      const alertState = alertStates.get(alertId);

      // Don't count dismissed alerts
      if (alertState?.dismissed) return;

      const severity = event.risk_level || getRiskLevel(event.risk_score || 0);

      counts.all++;
      if (severity === 'critical') counts.critical++;
      if (severity === 'high') counts.high++;
      if (severity === 'medium') counts.medium++;
      if (!alertState?.acknowledged) counts.unread++;
    });

    return counts;
  }, [events, alertStates]);

  // Handle individual alert acknowledge
  const handleAcknowledge = async (alertId: string) => {
    const state = alertStates.get(alertId);
    if (!state) return;

    try {
<<<<<<< HEAD
      await updateEvent(parseInt(eventId, 10), { reviewed: true });
      // Refetch to reflect changes
      void refetch();
=======
      await updateEvent(state.eventId, { reviewed: true });
      setAlertStates((prev) => {
        const next = new Map(prev);
        next.set(alertId, { ...state, acknowledged: true });
        return next;
      });
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)
    } catch (err) {
      console.error('Failed to acknowledge alert:', err);
    }
  };

  // Handle individual alert dismiss
  const handleDismiss = (alertId: string) => {
    setAlertStates((prev) => {
      const next = new Map(prev);
      const state = prev.get(alertId);
      if (state) {
        next.set(alertId, { ...state, dismissed: true });
      }
      return next;
    });
    // Remove from selection if selected
    setSelectedAlerts((prev) => {
      const next = new Set(prev);
      next.delete(alertId);
      return next;
    });
  };

<<<<<<< HEAD
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

  // Handle filter change - resets to first page
  const handleFilterChange = (newFilter: AlertRiskFilter) => {
    setRiskFilter(newFilter);
  };

  // Handle refresh
  const handleRefresh = () => {
    void refetch();
  };

=======
  // Handle snooze (placeholder - would need backend support)
  const handleSnooze = (alertId: string, _seconds: number) => {
    // In a real implementation, this would set a timer or backend state
    handleDismiss(alertId);
  };

  // Handle view event
  const handleViewEvent = (_eventId: number) => {
    // Navigate to event detail or open modal - placeholder
  };

  // Handle alert selection
  const handleSelectChange = (alertId: string, selected: boolean) => {
    setSelectedAlerts((prev) => {
      const next = new Set(prev);
      if (selected) {
        next.add(alertId);
      } else {
        next.delete(alertId);
      }
      return next;
    });
  };

  // Handle select all
  const handleSelectAll = (selectAll: boolean) => {
    if (selectAll) {
      setSelectedAlerts(new Set(filteredAlerts.map((e) => String(e.id))));
    } else {
      setSelectedAlerts(new Set());
    }
  };

  // Handle batch acknowledge
  const handleAcknowledgeSelected = async () => {
    const promises = Array.from(selectedAlerts).map((alertId) => handleAcknowledge(alertId));
    await Promise.all(promises);
    setSelectedAlerts(new Set());
  };

  // Handle batch dismiss
  const handleDismissSelected = () => {
    selectedAlerts.forEach((alertId) => handleDismiss(alertId));
    setSelectedAlerts(new Set());
  };

  // Handle mark all read
  const handleMarkAllRead = async () => {
    const unacknowledgedAlerts = filteredAlerts.filter((event) => {
      const alertState = alertStates.get(String(event.id));
      return !alertState?.acknowledged;
    });

    const promises = unacknowledgedAlerts.map((event) => handleAcknowledge(String(event.id)));
    await Promise.all(promises);
  };

  const hasUnacknowledged = filterCounts.unread > 0;

>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)
  return (
    <div data-testid="alerts-page" className={`flex flex-col ${className}`}>
      {/* Header with Statistics */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-8 w-8 text-orange-500" />
              <h1 className="text-3xl font-bold text-white">Alerts</h1>
            </div>
            <p className="mt-2 text-gray-400">
              <span className="font-semibold text-orange-400">{filterCounts.unread}</span>{' '}
              unacknowledged | {totalCount} total
            </p>
          </div>

<<<<<<< HEAD
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
=======
          {/* Header Actions */}
          <div className="flex items-center gap-3">
            {hasUnacknowledged && (
              <button
                onClick={() => void handleMarkAllRead()}
                className="flex items-center gap-2 rounded-lg bg-green-600/20 px-4 py-2 text-sm font-medium text-green-400 transition-colors hover:bg-green-600/30"
              >
                <CheckCheck className="h-4 w-4" />
                Mark All Read
              </button>
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)
            )}
            {onConfigureRules && (
              <button
                onClick={onConfigureRules}
                className="flex items-center gap-2 rounded-lg bg-[#76B900]/20 px-4 py-2 text-sm font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/30"
              >
                <Settings className="h-4 w-4" />
                Configure Rules
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="mb-6">
        <AlertFilters
          activeFilter={activeFilter}
          onFilterChange={setActiveFilter}
          counts={filterCounts}
        />
      </div>

      {/* Batch Actions */}
      {filteredAlerts.length > 0 && (
        <div className="mb-6">
          <AlertActions
            selectedCount={selectedAlerts.size}
            totalCount={filteredAlerts.length}
            hasUnacknowledged={hasUnacknowledged}
            onSelectAll={handleSelectAll}
            onAcknowledgeSelected={() => void handleAcknowledgeSelected()}
            onDismissSelected={handleDismissSelected}
            onClearSelection={() => setSelectedAlerts(new Set())}
          />
        </div>
      )}

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
            <p className="text-sm text-gray-400">{error?.message || 'An error occurred'}</p>
          </div>
        </div>
<<<<<<< HEAD
      ) : alerts.length === 0 ? (
=======
      ) : filteredAlerts.length === 0 ? (
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]">
          <div className="text-center">
            <AlertTriangle className="mx-auto mb-4 h-16 w-16 text-gray-600" />
            <p className="mb-2 text-lg font-semibold text-gray-300">No Alerts at This Time</p>
            <p className="text-sm text-gray-500">
              {activeFilter === 'all'
                ? 'There are no high or critical risk events to review.'
                : `No ${activeFilter} severity alerts to display.`}
            </p>
          </div>
        </div>
      ) : (
<<<<<<< HEAD
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
=======
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {filteredAlerts.map((event) => {
            const alertId = String(event.id);
            const alertState = alertStates.get(alertId);
            const severity = (event.risk_level || getRiskLevel(event.risk_score || 0)) as
              | 'low'
              | 'medium'
              | 'high'
              | 'critical';
            const status = alertState?.acknowledged ? 'acknowledged' : 'pending';

            return (
              <AlertCard
                key={alertId}
                id={alertId}
                eventId={event.id}
                severity={severity}
                status={status}
                timestamp={event.started_at}
                camera_name={cameraNameMap.get(event.camera_id) || 'Unknown Camera'}
                risk_score={event.risk_score || 0}
                summary={event.summary || 'No summary available'}
                dedup_key={`${event.camera_id}:${event.id}`}
                selected={selectedAlerts.has(alertId)}
                onAcknowledge={
                  status === 'pending' ? (id: string) => void handleAcknowledge(id) : undefined
                }
                onDismiss={handleDismiss}
                onSnooze={handleSnooze}
                onViewEvent={handleViewEvent}
                onSelectChange={handleSelectChange}
              />
            );
          })}
        </div>
      )}
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)
    </div>
  );
}
