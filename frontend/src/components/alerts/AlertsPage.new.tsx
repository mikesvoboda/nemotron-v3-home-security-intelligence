import { AlertTriangle, CheckCheck, Settings } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import AlertActions from './AlertActions';
import AlertCard from './AlertCard';
import AlertFilters from './AlertFilters';
import { fetchCameras, fetchEvents, isAbortError, updateEvent } from '../../services/api';
import { getRiskLevel } from '../../utils/risk';

import type { AlertFilterType } from './AlertFilters';
import type { Camera, Event, EventsQueryParams } from '../../services/api';

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
  const cameraNameMap = useMemo(() => {
    const map = new Map<string, string>();
    cameras.forEach((camera) => {
      map.set(camera.id, camera.name);
    });
    return map;
  }, [cameras]);

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
      await updateEvent(state.eventId, { reviewed: true });
      setAlertStates((prev) => {
        const next = new Map(prev);
        next.set(alertId, { ...state, acknowledged: true });
        return next;
      });
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
      ) : filteredAlerts.length === 0 ? (
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
    </div>
  );
}
