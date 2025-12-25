import { Calendar, CheckSquare, ChevronLeft, ChevronRight, Filter, Search, Square, X } from 'lucide-react';
import { useEffect, useState } from 'react';

import EventCard from './EventCard';
import { bulkUpdateEvents, fetchCameras, fetchEvents } from '../../services/api';
import { getRiskLevel } from '../../utils/risk';

import type { Detection } from './EventCard';
import type { Camera, Event, EventsQueryParams } from '../../services/api';

export interface EventTimelineProps {
  onViewEventDetails?: (eventId: number) => void;
  className?: string;
}

/**
 * EventTimeline component displays a chronological list of security events
 * with filtering, search, and pagination capabilities
 */
export default function EventTimeline({
  onViewEventDetails,
  className = '',
}: EventTimelineProps) {
  // State for events data
  const [events, setEvents] = useState<Event[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // State for cameras (for filter dropdown)
  const [cameras, setCameras] = useState<Camera[]>([]);

  // State for filters
  const [filters, setFilters] = useState<EventsQueryParams>({
    limit: 20,
    offset: 0,
  });
  const [showFilters, setShowFilters] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // State for selection and bulk actions
  const [selectedEventIds, setSelectedEventIds] = useState<Set<number>>(new Set());
  const [bulkActionLoading, setBulkActionLoading] = useState(false);

  // Load cameras for filter dropdown
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

  // Load events whenever filters change
  useEffect(() => {
    const loadEvents = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetchEvents(filters);
        setEvents(response.events);
        setTotalCount(response.count);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load events');
      } finally {
        setLoading(false);
      }
    };
    void loadEvents();
  }, [filters]);

  // Handle filter changes
  const handleFilterChange = (key: keyof EventsQueryParams, value: string | boolean) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value === '' ? undefined : value,
      offset: 0, // Reset to first page when filters change
    }));
  };

  // Handle pagination
  const handlePreviousPage = () => {
    const limit = filters.limit || 20;
    const offset = filters.offset || 0;
    if (offset > 0) {
      setFilters((prev) => ({
        ...prev,
        offset: Math.max(0, offset - limit),
      }));
    }
  };

  const handleNextPage = () => {
    const limit = filters.limit || 20;
    const offset = filters.offset || 0;
    if (offset + limit < totalCount) {
      setFilters((prev) => ({
        ...prev,
        offset: offset + limit,
      }));
    }
  };

  // Clear all filters
  const handleClearFilters = () => {
    setFilters({ limit: 20, offset: 0 });
    setSearchQuery('');
  };

  // Handle selection toggle for individual event
  const handleToggleSelection = (eventId: number) => {
    setSelectedEventIds((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(eventId)) {
        newSet.delete(eventId);
      } else {
        newSet.add(eventId);
      }
      return newSet;
    });
  };

  // Handle select all toggle
  const handleToggleSelectAll = () => {
    if (selectedEventIds.size === filteredEvents.length && filteredEvents.length > 0) {
      // If all are selected, deselect all
      setSelectedEventIds(new Set());
    } else {
      // Select all current page events
      setSelectedEventIds(new Set(filteredEvents.map((event) => event.id)));
    }
  };

  // Handle bulk mark as reviewed
  const handleBulkMarkAsReviewed = async () => {
    if (selectedEventIds.size === 0) return;

    setBulkActionLoading(true);
    try {
      const result = await bulkUpdateEvents(Array.from(selectedEventIds), { reviewed: true });

      if (result.failed.length > 0) {
        console.error('Some events failed to update:', result.failed);
        setError(
          `Updated ${result.successful.length} events, but ${result.failed.length} failed`
        );
      }

      // Reload events to reflect changes
      const response = await fetchEvents(filters);
      setEvents(response.events);
      setTotalCount(response.count);

      // Clear selections
      setSelectedEventIds(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update events');
    } finally {
      setBulkActionLoading(false);
    }
  };

  // Filter events by search query (client-side for summary search)
  const filteredEvents = searchQuery
    ? events.filter((event) =>
        event.summary?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : events;

  // Calculate pagination info
  const limit = filters.limit || 20;
  const offset = filters.offset || 0;
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(totalCount / limit);
  const hasActiveFilters =
    filters.camera_id ||
    filters.risk_level ||
    filters.start_date ||
    filters.end_date ||
    filters.reviewed !== undefined ||
    filters.object_type ||
    searchQuery;

  // Convert Event to EventCard props
  const getEventCardProps = (event: Event) => {
    // Find camera name
    const camera = cameras.find((c) => c.id === event.camera_id);
    const camera_name = camera?.name || 'Unknown Camera';

    // Convert detections (not available in list view, would need separate API call)
    const detections: Detection[] = [];

    return {
      id: String(event.id),
      timestamp: event.started_at,
      camera_name,
      risk_score: event.risk_score || 0,
      risk_label: event.risk_level || getRiskLevel(event.risk_score || 0),
      summary: event.summary || 'No summary available',
      detections,
      onViewDetails: onViewEventDetails
        ? () => onViewEventDetails(event.id)
        : undefined,
    };
  };

  return (
    <div className={`flex flex-col ${className}`}>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white">Event Timeline</h1>
        <p className="mt-2 text-gray-400">
          View and filter all security events from your cameras
        </p>
      </div>

      {/* Filter Bar */}
      <div className="mb-6 rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
        {/* Filter Toggle and Search */}
        <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 rounded-md bg-[#76B900]/10 px-4 py-2 text-sm font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/20"
            aria-expanded={showFilters}
          >
            <Filter className="h-4 w-4" />
            {showFilters ? 'Hide Filters' : 'Show Filters'}
            {hasActiveFilters && (
              <span className="ml-1 rounded-full bg-[#76B900] px-2 py-0.5 text-xs text-black">
                Active
              </span>
            )}
          </button>

          {/* Search */}
          <div className="relative flex-1 sm:max-w-xs">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search summaries..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2 pl-10 pr-10 text-sm text-white placeholder-gray-500 focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                aria-label="Clear search"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        {/* Filter Options */}
        {showFilters && (
          <div className="grid grid-cols-1 gap-4 border-t border-gray-800 pt-4 sm:grid-cols-2 lg:grid-cols-3">
            {/* Camera Filter */}
            <div>
              <label htmlFor="camera-filter" className="mb-1 block text-sm font-medium text-gray-300">
                Camera
              </label>
              <select
                id="camera-filter"
                value={filters.camera_id || ''}
                onChange={(e) => handleFilterChange('camera_id', e.target.value)}
                className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
              >
                <option value="">All Cameras</option>
                {cameras.map((camera) => (
                  <option key={camera.id} value={camera.id}>
                    {camera.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Risk Level Filter */}
            <div>
              <label htmlFor="risk-filter" className="mb-1 block text-sm font-medium text-gray-300">
                Risk Level
              </label>
              <select
                id="risk-filter"
                value={filters.risk_level || ''}
                onChange={(e) => handleFilterChange('risk_level', e.target.value)}
                className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
              >
                <option value="">All Risk Levels</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>

            {/* Reviewed Status Filter */}
            <div>
              <label htmlFor="reviewed-filter" className="mb-1 block text-sm font-medium text-gray-300">
                Status
              </label>
              <select
                id="reviewed-filter"
                value={
                  filters.reviewed === undefined ? '' : filters.reviewed ? 'true' : 'false'
                }
                onChange={(e) =>
                  handleFilterChange(
                    'reviewed',
                    e.target.value === '' ? '' : e.target.value === 'true'
                  )
                }
                className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
              >
                <option value="">All Events</option>
                <option value="false">Unreviewed</option>
                <option value="true">Reviewed</option>
              </select>
            </div>

            {/* Object Type Filter */}
            <div>
              <label htmlFor="object-type-filter" className="mb-1 block text-sm font-medium text-gray-300">
                Object Type
              </label>
              <select
                id="object-type-filter"
                value={filters.object_type || ''}
                onChange={(e) => handleFilterChange('object_type', e.target.value)}
                className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
              >
                <option value="">All Object Types</option>
                <option value="person">Person</option>
                <option value="vehicle">Vehicle</option>
                <option value="animal">Animal</option>
                <option value="package">Package</option>
                <option value="other">Other</option>
              </select>
            </div>

            {/* Start Date Filter */}
            <div>
              <label htmlFor="start-date-filter" className="mb-1 block text-sm font-medium text-gray-300">
                Start Date
              </label>
              <div className="relative">
                <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  id="start-date-filter"
                  type="date"
                  value={filters.start_date || ''}
                  onChange={(e) => handleFilterChange('start_date', e.target.value)}
                  className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2 pl-10 pr-3 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
                />
              </div>
            </div>

            {/* End Date Filter */}
            <div>
              <label htmlFor="end-date-filter" className="mb-1 block text-sm font-medium text-gray-300">
                End Date
              </label>
              <div className="relative">
                <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  id="end-date-filter"
                  type="date"
                  value={filters.end_date || ''}
                  onChange={(e) => handleFilterChange('end_date', e.target.value)}
                  className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2 pl-10 pr-3 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
                />
              </div>
            </div>

            {/* Clear Filters Button */}
            <div className="flex items-end">
              <button
                onClick={handleClearFilters}
                disabled={!hasActiveFilters}
                className="w-full rounded-md border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:border-gray-600 hover:bg-[#1A1A1A] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Clear All Filters
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Results Summary and Bulk Actions */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4 text-sm">
          <p className="text-gray-400">
            Showing {offset + 1}-{Math.min(offset + filteredEvents.length, totalCount)} of {totalCount} events
          </p>
          {hasActiveFilters && (
            <p className="text-[#76B900]">
              Filters active
            </p>
          )}
        </div>

        {/* Bulk Actions Bar */}
        {!loading && !error && filteredEvents.length > 0 && (
          <div className="flex items-center gap-3">
            {/* Select All Checkbox */}
            <button
              onClick={handleToggleSelectAll}
              className="flex items-center gap-2 rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-1.5 text-sm text-gray-300 transition-colors hover:border-gray-600 hover:bg-[#252525]"
              aria-label={
                selectedEventIds.size === filteredEvents.length && filteredEvents.length > 0
                  ? 'Deselect all events'
                  : 'Select all events'
              }
            >
              {selectedEventIds.size === filteredEvents.length && filteredEvents.length > 0 ? (
                <CheckSquare className="h-4 w-4 text-[#76B900]" />
              ) : (
                <Square className="h-4 w-4" />
              )}
              <span>
                {selectedEventIds.size > 0
                  ? `${selectedEventIds.size} selected`
                  : 'Select all'}
              </span>
            </button>

            {/* Bulk Mark as Reviewed Button */}
            {selectedEventIds.size > 0 && (
              <button
                onClick={() => void handleBulkMarkAsReviewed()}
                disabled={bulkActionLoading}
                className="flex items-center gap-2 rounded-md bg-[#76B900] px-4 py-1.5 text-sm font-semibold text-black transition-all hover:bg-[#88d200] active:bg-[#68a000] disabled:cursor-not-allowed disabled:opacity-50"
                aria-label={`Mark ${selectedEventIds.size} selected events as reviewed`}
              >
                {bulkActionLoading ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-black border-t-transparent" />
                    <span>Updating...</span>
                  </>
                ) : (
                  <>
                    <CheckSquare className="h-4 w-4" />
                    <span>Mark as Reviewed</span>
                  </>
                )}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Event List */}
      {loading ? (
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]">
          <div className="text-center">
            <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-700 border-t-[#76B900]" />
            <p className="text-gray-400">Loading events...</p>
          </div>
        </div>
      ) : error ? (
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-red-900/50 bg-red-950/20">
          <div className="text-center">
            <p className="mb-2 text-lg font-semibold text-red-500">Error Loading Events</p>
            <p className="text-sm text-gray-400">{error}</p>
          </div>
        </div>
      ) : filteredEvents.length === 0 ? (
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]">
          <div className="text-center">
            <p className="mb-2 text-lg font-semibold text-gray-300">No Events Found</p>
            <p className="text-sm text-gray-500">
              {hasActiveFilters
                ? 'Try adjusting your filters or search query'
                : 'No security events have been recorded yet'}
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
          {filteredEvents.map((event) => (
            <div key={event.id} className="relative">
              {/* Selection Checkbox */}
              <div className="absolute left-2 top-2 z-10">
                <button
                  onClick={() => handleToggleSelection(event.id)}
                  className="flex h-8 w-8 items-center justify-center rounded-md border border-gray-700 bg-[#1A1A1A]/90 backdrop-blur-sm transition-colors hover:border-gray-600 hover:bg-[#252525]/90"
                  aria-label={
                    selectedEventIds.has(event.id)
                      ? `Deselect event ${event.id}`
                      : `Select event ${event.id}`
                  }
                >
                  {selectedEventIds.has(event.id) ? (
                    <CheckSquare className="h-5 w-5 text-[#76B900]" />
                  ) : (
                    <Square className="h-5 w-5 text-gray-400" />
                  )}
                </button>
              </div>
              <EventCard {...getEventCardProps(event)} />
            </div>
          ))}
        </div>
      )}

      {/* Pagination Controls */}
      {!loading && !error && totalCount > 0 && (
        <div className="mt-6 flex items-center justify-between rounded-lg border border-gray-800 bg-[#1F1F1F] px-4 py-3">
          <button
            onClick={handlePreviousPage}
            disabled={offset === 0}
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
            disabled={offset + limit >= totalCount}
            className="flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#76B900]/10 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
            aria-label="Next page"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
