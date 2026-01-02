import {
  ArrowDownUp,
  Calendar,
  CheckSquare,
  ChevronLeft,
  ChevronRight,
  Download,
  Filter,
  Search,
  Square,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import EventCard from './EventCard';
import EventDetailModal from './EventDetailModal';
import ExportPanel from './ExportPanel';
import {
  bulkUpdateEvents,
  exportEventsCSV,
  fetchCameras,
  fetchEvents,
  isAbortError,
  searchEvents,
  updateEvent,
} from '../../services/api';
import { getRiskLevel } from '../../utils/risk';
import RiskBadge from '../common/RiskBadge';
import { SearchBar, SearchResultsPanel } from '../search';

import type { Detection } from './EventCard';
import type { SearchFilters } from '../search';
import type { Event as ModalEvent } from './EventDetailModal';
import type { Camera, Event, EventsQueryParams, SearchResult } from '../../services/api';
import type { RiskLevel } from '../../utils/risk';

// Confidence filter threshold options
type ConfidenceFilter = '' | 'high' | 'medium' | 'any';

// Sorting options for events
type SortOption = 'newest' | 'oldest' | 'risk_high' | 'risk_low';

export interface EventTimelineProps {
  onViewEventDetails?: (eventId: number) => void;
  className?: string;
}

/**
 * EventTimeline component displays a chronological list of security events
 * with filtering, search, and pagination capabilities
 */
export default function EventTimeline({ onViewEventDetails, className = '' }: EventTimelineProps) {
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
  const [confidenceFilter, setConfidenceFilter] = useState<ConfidenceFilter>('');
  const [sortOption, setSortOption] = useState<SortOption>('newest');

  // State for selection and bulk actions
  const [selectedEventIds, setSelectedEventIds] = useState<Set<number>>(new Set());
  const [bulkActionLoading, setBulkActionLoading] = useState(false);

  // State for export
  const [exportLoading, setExportLoading] = useState(false);
  const [showExportPanel, setShowExportPanel] = useState(false);

  // State for event detail modal
  const [selectedEventForModal, setSelectedEventForModal] = useState<number | null>(null);

  // State for full-text search mode
  const [isSearchMode, setIsSearchMode] = useState(false);
  const [fullTextQuery, setFullTextQuery] = useState('');
  const [searchFilters, setSearchFilters] = useState<SearchFilters>({});
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchTotalCount, setSearchTotalCount] = useState(0);
  const [searchOffset, setSearchOffset] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Create a memoized camera name lookup map that updates when cameras change
  // This ensures the component re-renders with correct camera names when cameras load
  const cameraNameMap = useMemo(() => {
    const map = new Map<string, string>();
    cameras.forEach((camera) => {
      map.set(camera.id, camera.name);
    });
    return map;
  }, [cameras]);

  // Ref to track the latest search request ID to prevent race conditions
  const searchRequestIdRef = useRef(0);

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

  // Load events whenever filters change (with AbortController to cancel stale requests)
  useEffect(() => {
    const controller = new AbortController();

    const loadEvents = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetchEvents(filters, { signal: controller.signal });
        setEvents(response.events);
        setTotalCount(response.count);
      } catch (err) {
        // Ignore aborted requests - user changed filters before request completed
        if (isAbortError(err)) return;
        setError(err instanceof Error ? err.message : 'Failed to load events');
      } finally {
        // Only update loading state if request wasn't aborted
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };
    void loadEvents();

    // Cleanup: abort pending request when filters change or component unmounts
    return () => controller.abort();
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
    setConfidenceFilter('');
    setSortOption('newest');
  };

  // Handle full-text search
  const handleFullTextSearch = useCallback(
    async (query: string, filters: SearchFilters) => {
      if (!query.trim()) return;

      // Increment request ID to track this request
      const requestId = ++searchRequestIdRef.current;

      setIsSearchMode(true);
      setIsSearching(true);
      setSearchError(null);
      setFullTextQuery(query);
      setSearchFilters(filters);
      setSearchOffset(0);

      try {
        const response = await searchEvents({
          q: query,
          camera_id: filters.camera_id,
          start_date: filters.start_date,
          end_date: filters.end_date,
          severity: filters.severity,
          object_type: filters.object_type,
          reviewed: filters.reviewed,
          limit: 20,
          offset: 0,
        });
        // Only update state if this is still the latest request
        if (requestId === searchRequestIdRef.current) {
          setSearchResults(response.results);
          setSearchTotalCount(response.total_count);
        }
      } catch (err) {
        // Only update error state if this is still the latest request
        if (requestId === searchRequestIdRef.current) {
          setSearchError(err instanceof Error ? err.message : 'Search failed');
          setSearchResults([]);
          setSearchTotalCount(0);
        }
      } finally {
        // Only update loading state if this is still the latest request
        if (requestId === searchRequestIdRef.current) {
          setIsSearching(false);
        }
      }
    },
    []
  );

  // Handle search pagination
  const handleSearchPageChange = useCallback(
    async (newOffset: number) => {
      // Increment request ID to track this request
      const requestId = ++searchRequestIdRef.current;

      setIsSearching(true);
      setSearchOffset(newOffset);

      try {
        const response = await searchEvents({
          q: fullTextQuery,
          camera_id: searchFilters.camera_id,
          start_date: searchFilters.start_date,
          end_date: searchFilters.end_date,
          severity: searchFilters.severity,
          object_type: searchFilters.object_type,
          reviewed: searchFilters.reviewed,
          limit: 20,
          offset: newOffset,
        });
        // Only update state if this is still the latest request
        if (requestId === searchRequestIdRef.current) {
          setSearchResults(response.results);
          setSearchTotalCount(response.total_count);
        }
      } catch (err) {
        // Only update error state if this is still the latest request
        if (requestId === searchRequestIdRef.current) {
          setSearchError(err instanceof Error ? err.message : 'Search failed');
        }
      } finally {
        // Only update loading state if this is still the latest request
        if (requestId === searchRequestIdRef.current) {
          setIsSearching(false);
        }
      }
    },
    [fullTextQuery, searchFilters]
  );

  // Clear search and return to browse mode
  const handleClearSearch = useCallback(() => {
    setIsSearchMode(false);
    setFullTextQuery('');
    setSearchFilters({});
    setSearchResults([]);
    setSearchTotalCount(0);
    setSearchOffset(0);
    setSearchError(null);
  }, []);

  // Handle clicking a search result
  const handleSearchResultClick = useCallback((eventId: number) => {
    setSelectedEventForModal(eventId);
  }, []);

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
        setError(`Updated ${result.successful.length} events, but ${result.failed.length} failed`);
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

  // Handle bulk mark as not reviewed
  const handleBulkMarkAsNotReviewed = async () => {
    if (selectedEventIds.size === 0) return;

    setBulkActionLoading(true);
    try {
      const result = await bulkUpdateEvents(Array.from(selectedEventIds), { reviewed: false });

      if (result.failed.length > 0) {
        console.error('Some events failed to update:', result.failed);
        setError(`Updated ${result.successful.length} events, but ${result.failed.length} failed`);
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

  // Handle export to CSV
  const handleExport = async () => {
    setExportLoading(true);
    setError(null);
    try {
      // Pass current filters to export (excluding pagination and object_type which isn't supported by export)
      await exportEventsCSV({
        camera_id: filters.camera_id,
        risk_level: filters.risk_level,
        start_date: filters.start_date,
        end_date: filters.end_date,
        reviewed: filters.reviewed,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export events');
    } finally {
      setExportLoading(false);
    }
  };

  // Filter events by search query (client-side for summary search)
  let filteredEvents = searchQuery
    ? events.filter((event) => event.summary?.toLowerCase().includes(searchQuery.toLowerCase()))
    : events;

  // Note: Confidence filtering would ideally be done server-side with detection data
  // For now, this is a placeholder since events in list view don't include detections
  // The filter UI still provides value as it indicates user intent and could be passed to backend

  // Apply sorting (client-side)
  filteredEvents = [...filteredEvents].sort((a, b) => {
    switch (sortOption) {
      case 'newest':
        return new Date(b.started_at).getTime() - new Date(a.started_at).getTime();
      case 'oldest':
        return new Date(a.started_at).getTime() - new Date(b.started_at).getTime();
      case 'risk_high':
        return (b.risk_score || 0) - (a.risk_score || 0);
      case 'risk_low':
        return (a.risk_score || 0) - (b.risk_score || 0);
      default:
        return 0;
    }
  });

  // Calculate risk level counts for the currently displayed events
  const riskCounts = filteredEvents.reduce(
    (acc, event) => {
      const level = event.risk_level || getRiskLevel(event.risk_score || 0);
      acc[level as RiskLevel] = (acc[level as RiskLevel] || 0) + 1;
      return acc;
    },
    { critical: 0, high: 0, medium: 0, low: 0 } as Record<RiskLevel, number>
  );

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
    searchQuery ||
    confidenceFilter ||
    sortOption !== 'newest';

  // Convert Event to EventCard props
  const getEventCardProps = (event: Event) => {
    // Use memoized camera name map for efficient lookup
    const camera_name = cameraNameMap.get(event.camera_id) || 'Unknown Camera';

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
      const response = await fetchEvents(filters);
      setEvents(response.events);
      setTotalCount(response.count);
    } catch (err) {
      console.error('Failed to mark event as reviewed:', err);
    }
  };

  // Handle navigation between events in modal
  const handleNavigate = (direction: 'prev' | 'next') => {
    if (selectedEventForModal === null) return;

    const currentIndex = filteredEvents.findIndex((e) => e.id === selectedEventForModal);
    if (currentIndex === -1) return;

    const newIndex = direction === 'prev' ? currentIndex - 1 : currentIndex + 1;
    if (newIndex >= 0 && newIndex < filteredEvents.length) {
      setSelectedEventForModal(filteredEvents[newIndex].id);
    }
  };

  // Convert API Event to ModalEvent format
  const getModalEvent = (): ModalEvent | null => {
    if (selectedEventForModal === null) return null;

    const event = filteredEvents.find((e) => e.id === selectedEventForModal);
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
        <h1 className="text-3xl font-bold text-white">Event Timeline</h1>
        <p className="mt-2 text-gray-400">View and filter all security events from your cameras</p>
      </div>

      {/* Full-Text Search Bar */}
      <div className="mb-6 rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Full-Text Search</h2>
          {isSearchMode && (
            <button
              onClick={handleClearSearch}
              className="text-sm text-gray-400 transition-colors hover:text-white"
            >
              Back to browse
            </button>
          )}
        </div>
        <SearchBar
          query={fullTextQuery}
          onQueryChange={setFullTextQuery}
          onSearch={(q, f) => void handleFullTextSearch(q, f)}
          isSearching={isSearching}
          cameras={cameras}
          initialFilters={searchFilters}
          placeholder='Search events (e.g., "suspicious person", vehicle OR animal)...'
        />
      </div>

      {/* Search Results */}
      {isSearchMode && (
        <SearchResultsPanel
          results={searchResults}
          totalCount={searchTotalCount}
          offset={searchOffset}
          limit={20}
          isLoading={isSearching}
          error={searchError}
          onPageChange={(offset) => void handleSearchPageChange(offset)}
          onResultClick={handleSearchResultClick}
          onClearSearch={handleClearSearch}
          searchQuery={fullTextQuery}
          className="mb-6"
        />
      )}

      {/* Browse Mode: Filter Bar */}
      {!isSearchMode && (
        <>
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

          {/* Quick Export Button */}
          <button
            onClick={() => void handleExport()}
            disabled={exportLoading || totalCount === 0}
            className="flex items-center gap-2 rounded-md border border-gray-700 bg-[#1A1A1A] px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:border-gray-600 hover:bg-[#252525] disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Quick export events to CSV"
            title="Quick export with current filters"
          >
            {exportLoading ? (
              <>
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-transparent" />
                <span>Exporting...</span>
              </>
            ) : (
              <>
                <Download className="h-4 w-4" />
                <span>Quick Export</span>
              </>
            )}
          </button>

          {/* Advanced Export Panel Toggle */}
          <button
            onClick={() => setShowExportPanel(!showExportPanel)}
            className={`flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium transition-colors ${
              showExportPanel
                ? 'border-[#76B900] bg-[#76B900]/10 text-[#76B900]'
                : 'border-gray-700 bg-[#1A1A1A] text-gray-300 hover:border-gray-600 hover:bg-[#252525]'
            }`}
            aria-expanded={showExportPanel}
            aria-label="Toggle advanced export options"
          >
            <Download className="h-4 w-4" />
            <span>Advanced Export</span>
          </button>
        </div>

        {/* Filter Options */}
        {showFilters && (
          <div className="grid grid-cols-1 gap-4 border-t border-gray-800 pt-4 sm:grid-cols-2 lg:grid-cols-3">
            {/* Camera Filter */}
            <div>
              <label
                htmlFor="camera-filter"
                className="mb-1 block text-sm font-medium text-gray-300"
              >
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
              <label
                htmlFor="reviewed-filter"
                className="mb-1 block text-sm font-medium text-gray-300"
              >
                Status
              </label>
              <select
                id="reviewed-filter"
                value={filters.reviewed === undefined ? '' : filters.reviewed ? 'true' : 'false'}
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
              <label
                htmlFor="object-type-filter"
                className="mb-1 block text-sm font-medium text-gray-300"
              >
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

            {/* Confidence Filter */}
            <div>
              <label
                htmlFor="confidence-filter"
                className="mb-1 block text-sm font-medium text-gray-300"
              >
                Min Confidence
              </label>
              <select
                id="confidence-filter"
                value={confidenceFilter}
                onChange={(e) => setConfidenceFilter(e.target.value as ConfidenceFilter)}
                className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
              >
                <option value="">All Confidence Levels</option>
                <option value="high">High Only (85%+)</option>
                <option value="medium">Medium+ (70%+)</option>
                <option value="any">Any Detection</option>
              </select>
            </div>

            {/* Sort By */}
            <div>
              <label
                htmlFor="sort-filter"
                className="mb-1 block text-sm font-medium text-gray-300"
              >
                Sort By
              </label>
              <div className="relative">
                <ArrowDownUp className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <select
                  id="sort-filter"
                  value={sortOption}
                  onChange={(e) => setSortOption(e.target.value as SortOption)}
                  className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2 pl-10 pr-3 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
                >
                  <option value="newest">Newest First</option>
                  <option value="oldest">Oldest First</option>
                  <option value="risk_high">Highest Risk</option>
                  <option value="risk_low">Lowest Risk</option>
                </select>
              </div>
            </div>

            {/* Start Date Filter */}
            <div>
              <label
                htmlFor="start-date-filter"
                className="mb-1 block text-sm font-medium text-gray-300"
              >
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
              <label
                htmlFor="end-date-filter"
                className="mb-1 block text-sm font-medium text-gray-300"
              >
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

      {/* Advanced Export Panel */}
      {showExportPanel && (
        <div className="mb-6">
          <ExportPanel
            initialFilters={{
              camera_id: filters.camera_id,
              risk_level: filters.risk_level,
              start_date: filters.start_date,
              end_date: filters.end_date,
              reviewed: filters.reviewed,
            }}
            onExportStart={() => setExportLoading(true)}
            onExportComplete={(success) => {
              setExportLoading(false);
              if (!success) {
                // Error will be shown in the ExportPanel
              }
            }}
          />
        </div>
      )}

      {/* Results Summary and Bulk Actions */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-2">
          <p className="text-sm text-gray-400">
            {totalCount === 0
              ? '0 events'
              : `Showing ${offset + 1}-${Math.min(offset + filteredEvents.length, totalCount)} of ${totalCount} events`}
          </p>
          {/* Risk Summary Badges */}
          {!loading && !error && filteredEvents.length > 0 && (
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
              {riskCounts.medium > 0 && (
                <div className="flex items-center gap-1.5">
                  <RiskBadge level="medium" size="sm" animated={false} />
                  <span className="font-semibold text-yellow-400">{riskCounts.medium}</span>
                </div>
              )}
              {riskCounts.low > 0 && (
                <div className="flex items-center gap-1.5">
                  <RiskBadge level="low" size="sm" animated={false} />
                  <span className="font-semibold text-green-400">{riskCounts.low}</span>
                </div>
              )}
            </div>
          )}
          {hasActiveFilters && <p className="text-sm text-[#76B900]">Filters active</p>}
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
                {selectedEventIds.size > 0 ? `${selectedEventIds.size} selected` : 'Select all'}
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

            {/* Bulk Mark as Not Reviewed Button */}
            {selectedEventIds.size > 0 && (
              <button
                onClick={() => void handleBulkMarkAsNotReviewed()}
                disabled={bulkActionLoading}
                className="flex items-center gap-2 rounded-md border border-gray-600 bg-[#1A1A1A] px-4 py-1.5 text-sm font-semibold text-gray-300 transition-all hover:border-gray-500 hover:bg-[#252525] active:bg-[#1A1A1A] disabled:cursor-not-allowed disabled:opacity-50"
                aria-label={`Mark ${selectedEventIds.size} selected events as not reviewed`}
              >
                {bulkActionLoading ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-transparent" />
                    <span>Updating...</span>
                  </>
                ) : (
                  <>
                    <Square className="h-4 w-4" />
                    <span>Mark Not Reviewed</span>
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
              <EventCard {...getEventCardProps(event)} hasCheckboxOverlay />
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
