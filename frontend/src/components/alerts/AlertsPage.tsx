import { AlertTriangle, Bell, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { fetchCameras, fetchEvents, isAbortError, updateEvent } from '../../services/api';
import { getRiskLevel } from '../../utils/risk';
import RiskBadge from '../common/RiskBadge';
import EventCard from '../events/EventCard';
import EventDetailModal from '../events/EventDetailModal';

import type { Camera, Event, EventsQueryParams } from '../../services/api';
import type { RiskLevel } from '../../utils/risk';
import type { Detection } from '../events/EventCard';
import type { Event as ModalEvent } from '../events/EventDetailModal';

export interface AlertsPageProps {
  onViewEventDetails?: (eventId: number) => void;
  className?: string;
}

/**
 * AlertsPage component displays high and critical risk security events
 * These are events that require immediate attention
 */
export default function AlertsPage({ onViewEventDetails, className = '' }: AlertsPageProps) {
  // State for events data
  const [events, setEvents] = useState<Event[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // State for cameras (for displaying camera names)
  const [cameras, setCameras] = useState<Camera[]>([]);

  // State for pagination
  const [pagination, setPagination] = useState({
    limit: 20,
    offset: 0,
  });

  // State for selected risk level filter (high or critical)
  const [riskFilter, setRiskFilter] = useState<'high' | 'critical' | 'all'>('all');

  // State for event detail modal
  const [selectedEventForModal, setSelectedEventForModal] = useState<number | null>(null);

  // Create a memoized camera name lookup map that updates when cameras change
  // This ensures the component re-renders with correct camera names when cameras load
  const cameraNameMap = useMemo(() => {
    const map = new Map<string, string>();
    cameras.forEach((camera) => {
      map.set(camera.id, camera.name);
    });
    return map;
  }, [cameras]);

  // Load cameras for camera name lookup
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

  // Load high/critical risk events (with AbortController to cancel stale requests)
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

        // Combine and sort by timestamp (most recent first)
        let allAlerts = [...highResponse.events, ...criticalResponse.events];
        allAlerts.sort(
          (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
        );

        // Apply risk filter if not 'all'
        if (riskFilter !== 'all') {
          allAlerts = allAlerts.filter((event) => {
            const level = event.risk_level || getRiskLevel(event.risk_score || 0);
            return level === riskFilter;
          });
        }

        // Handle pagination manually since we're combining two API calls
        const totalCombined = highResponse.count + criticalResponse.count;
        const paginatedAlerts = allAlerts.slice(0, pagination.limit);

        setEvents(paginatedAlerts);
        setTotalCount(totalCombined);
      } catch (err) {
        // Ignore aborted requests - user changed filters before request completed
        if (isAbortError(err)) return;
        setError(err instanceof Error ? err.message : 'Failed to load alerts');
      } finally {
        // Only update loading state if request wasn't aborted
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };
    void loadAlerts();

    // Cleanup: abort pending request when filters change or component unmounts
    return () => controller.abort();
  }, [pagination, riskFilter]);

  // Handle pagination
  const handlePreviousPage = () => {
    if (pagination.offset > 0) {
      setPagination((prev) => ({
        ...prev,
        offset: Math.max(0, prev.offset - prev.limit),
      }));
    }
  };

  const handleNextPage = () => {
    if (pagination.offset + pagination.limit < totalCount) {
      setPagination((prev) => ({
        ...prev,
        offset: prev.offset + prev.limit,
      }));
    }
  };

  // Handle refresh
  const handleRefresh = () => {
    setPagination((prev) => ({ ...prev })); // Trigger re-fetch
  };

  // Calculate risk level counts
  const riskCounts = events.reduce(
    (acc, event) => {
      const level = event.risk_level || getRiskLevel(event.risk_score || 0);
      acc[level as RiskLevel] = (acc[level as RiskLevel] || 0) + 1;
      return acc;
    },
    { critical: 0, high: 0, medium: 0, low: 0 } as Record<RiskLevel, number>
  );

  // Calculate pagination info
  const currentPage = Math.floor(pagination.offset / pagination.limit) + 1;
  const totalPages = Math.ceil(totalCount / pagination.limit);

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
      // Reload events to reflect changes
      setPagination((prev) => ({ ...prev })); // Trigger re-fetch
    } catch (err) {
      console.error('Failed to mark event as reviewed:', err);
    }
  };

  // Handle navigation between events in modal
  const handleNavigate = (direction: 'prev' | 'next') => {
    if (selectedEventForModal === null) return;

    const currentIndex = events.findIndex((e) => e.id === selectedEventForModal);
    if (currentIndex === -1) return;

    const newIndex = direction === 'prev' ? currentIndex - 1 : currentIndex + 1;
    if (newIndex >= 0 && newIndex < events.length) {
      setSelectedEventForModal(events[newIndex].id);
    }
  };

  // Convert API Event to ModalEvent format
  const getModalEvent = (): ModalEvent | null => {
    if (selectedEventForModal === null) return null;

    const event = events.find((e) => e.id === selectedEventForModal);
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

  return (
    <div className={`flex flex-col ${className}`}>
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
            onChange={(e) => {
              setRiskFilter(e.target.value as 'high' | 'critical' | 'all');
              setPagination((prev) => ({ ...prev, offset: 0 }));
            }}
            className="rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
          >
            <option value="all">All Alerts</option>
            <option value="critical">Critical Only</option>
            <option value="high">High Only</option>
          </select>
        </div>

        <button
          onClick={handleRefresh}
          disabled={loading}
          className="flex items-center gap-2 rounded-md bg-[#76B900]/10 px-4 py-2 text-sm font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Results Summary */}
      <div className="mb-4 flex flex-col gap-2">
        <p className="text-sm text-gray-400">
          {loading ? 'Loading...' : `${totalCount} alert${totalCount !== 1 ? 's' : ''} found`}
        </p>
        {/* Risk Summary Badges */}
        {!loading && !error && events.length > 0 && (
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
      {loading ? (
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]">
          <div className="text-center">
            <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-700 border-t-[#76B900]" />
            <p className="text-gray-400">Loading alerts...</p>
          </div>
        </div>
      ) : error ? (
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-red-900/50 bg-red-950/20">
          <div className="text-center">
            <p className="mb-2 text-lg font-semibold text-red-400">Error Loading Alerts</p>
            <p className="text-sm text-gray-400">{error}</p>
          </div>
        </div>
      ) : events.length === 0 ? (
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
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
          {events.map((event) => (
            <EventCard key={event.id} {...getEventCardProps(event)} />
          ))}
        </div>
      )}

      {/* Pagination Controls */}
      {!loading && !error && totalCount > 0 && totalPages > 1 && (
        <div className="mt-6 flex items-center justify-between rounded-lg border border-gray-800 bg-[#1F1F1F] px-4 py-3">
          <button
            onClick={handlePreviousPage}
            disabled={pagination.offset === 0}
            className="flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#76B900]/10 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
            aria-label="Previous page"
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </button>

          <div className="text-sm text-gray-400">
            Page {currentPage} of {totalPages}
          </div>

          <button
            onClick={handleNextPage}
            disabled={pagination.offset + pagination.limit >= totalCount}
            className="flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#76B900]/10 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
            aria-label="Next page"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
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
