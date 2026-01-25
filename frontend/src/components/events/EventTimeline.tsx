import {
  ArrowDownUp,
  Calendar,
  CheckSquare,
  Clock,
  Download,
  Filter,
  Layers,
  Square,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import EventCard from './EventCard';
import EventClusterCard from './EventClusterCard';
import EventDetailModal from './EventDetailModal';
import EventListView, { type SortField, type SortDirection } from './EventListView';
import FilterChips from './FilterChips';
import MobileEventCard from './MobileEventCard';
import { ExportButton } from '../ExportButton';
import LiveActivitySection from './LiveActivitySection';
import TimeGroupedEvents from './TimeGroupedEvents';
import TimelineScrubber, { type TimeRange, type ZoomLevel } from './TimelineScrubber';
import ViewToggle, { type ViewMode } from './ViewToggle';
import { useEventsInfiniteQuery, type EventFilters } from '../../hooks/useEventsQuery';
import { useEventStream } from '../../hooks/useEventStream';
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll';
import { useIsMobile } from '../../hooks/useIsMobile';
import { useLocalStorage } from '../../hooks/useLocalStorage';
import { usePaginationState } from '../../hooks/usePaginationState';
import { useTimelineData } from '../../hooks/useTimelineData';
import { bulkUpdateEvents, fetchCameras, searchEvents, updateEvent } from '../../services/api';
import {
  clusterEvents,
  getClusterStats,
  isEventCluster,
  type ClusteredItem,
} from '../../utils/eventClustering';
import { countBy } from '../../utils/groupBy';
import { pipe, getSortTransform, type SortOption } from '../../utils/pipeline';
import { getRiskLevel } from '../../utils/risk';
import { parseEventId } from '../../utils/validation';
import {
  EmptyState,
  EventCardSkeleton,
  InfiniteScrollStatus,
  PullToRefresh,
  SafeErrorMessage,
} from '../common';
import RiskBadge from '../common/RiskBadge';
import { type ActivityEvent } from '../dashboard/ActivityFeed';
import ExportModal from '../exports/ExportModal';
import { SearchBar, SearchResultsPanel } from '../search';

import type { Detection } from './EventCard';
import type { SearchFilters } from '../search';
import type { Event as ModalEvent } from './EventDetailModal';
import type { Camera, Event, SearchResult } from '../../services/api';
import type { RiskLevel } from '../../utils/risk';

// Confidence filter threshold options
type ConfidenceFilter = '' | 'high' | 'medium' | 'any';

// SortOption type is imported from '../../utils/pipeline'

export interface EventTimelineProps {
  onViewEventDetails?: (eventId: number) => void;
  className?: string;
}

/**
 * EventTimeline component displays a chronological list of security events
 * with filtering, search, and infinite scroll pagination capabilities
 */
export default function EventTimeline({ onViewEventDetails, className = '' }: EventTimelineProps) {
  // State for cameras (for filter dropdown)
  const [cameras, setCameras] = useState<Camera[]>([]);

  // State for filters
  const [eventFilters, setEventFilters] = useState<EventFilters>({});
  const [showFilters, setShowFilters] = useState(false);
  const [confidenceFilter, setConfidenceFilter] = useState<ConfidenceFilter>('');
  const [sortOption, setSortOption] = useState<SortOption>('newest');

  // State for selection and bulk actions
  const [selectedEventIds, setSelectedEventIds] = useState<Set<number>>(new Set());
  const [bulkActionLoading, setBulkActionLoading] = useState(false);
  const [bulkActionError, setBulkActionError] = useState<string | null>(null);

  // State for export
  const [showExportModal, setShowExportModal] = useState(false);

  // State for view mode (grid vs list) - persisted in localStorage
  const [viewMode, setViewMode] = useLocalStorage<ViewMode>('timeline-view-mode', 'grid');

  // State for clustering toggle - persisted in localStorage
  const [clusteringEnabled, setClusteringEnabled] = useLocalStorage<boolean>(
    'timeline-clustering-enabled',
    true
  );

  // State for list view sorting (separate from the main sortOption which is dropdown-based)
  const [listSortField, setListSortField] = useState<SortField>('time');
  const [listSortDirection, setListSortDirection] = useState<SortDirection>('desc');

  // State for event detail modal
  const [selectedEventForModal, setSelectedEventForModal] = useState<number | null>(null);

  // WebSocket hook for real-time live activity
  const { events: wsEvents, isConnected: wsConnected } = useEventStream();

  // Mobile detection for pull-to-refresh (NEM-2970)
  const isMobile = useIsMobile();

  // State for full-text search mode
  const [isSearchMode, setIsSearchMode] = useState(false);
  const [fullTextQuery, setFullTextQuery] = useState('');
  const [searchFilters, setSearchFilters] = useState<SearchFilters>({});
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchTotalCount, setSearchTotalCount] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // State for timeline scrubber (NEM-2932)
  const [timelineZoomLevel, setTimelineZoomLevel] = useState<ZoomLevel>('day');

  // URL search params for deep-linking (e.g., /timeline?camera=cam-1)
  const [searchParams] = useSearchParams();

  // Search pagination state with URL persistence
  // Uses custom param names to avoid conflicts with other URL params
  const searchPagination = usePaginationState({
    type: 'offset',
    defaultLimit: 20,
    paramNames: {
      page: 'search_page',
      limit: 'search_limit',
    },
    persistLimit: false, // Keep limit as default, only persist page
  });

  // Use infinite query for events with cursor-based pagination
  const {
    events,
    totalCount,
    isLoading: loading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    error: queryError,
    refetch,
  } = useEventsInfiniteQuery({
    filters: eventFilters,
    limit: 20,
    enabled: !isSearchMode,
  });

  // Timeline scrubber data hook (NEM-2932)
  const { buckets: timelineBuckets, isLoading: timelineLoading } = useTimelineData({
    zoomLevel: timelineZoomLevel,
    startDate: eventFilters.start_date,
    endDate: eventFilters.end_date,
    cameraId: eventFilters.camera_id,
    enabled: !isSearchMode,
  });

  // Convert query error to string
  const error = queryError?.message ?? bulkActionError;

  // Use infinite scroll hook
  const {
    sentinelRef,
    isLoadingMore,
    error: scrollError,
    retry,
  } = useInfiniteScroll({
    onLoadMore: fetchNextPage,
    hasMore: hasNextPage,
    isLoading: isFetchingNextPage,
    enabled: !isSearchMode && !loading && events.length > 0,
  });

  // Initialize filters from URL query parameters
  // Updates when searchParams changes (e.g., navigating from dashboard camera click or AI Performance risk chart)
  useEffect(() => {
    const cameraParam = searchParams.get('camera');
    const riskLevelParam = searchParams.get('risk_level');

    // Only update if we have at least one parameter
    if (cameraParam || riskLevelParam) {
      setEventFilters((prev) => ({
        ...prev,
        ...(cameraParam && { camera_id: cameraParam }),
        ...(riskLevelParam && { risk_level: riskLevelParam }),
      }));
      // Show filters panel when coming with URL parameters
      setShowFilters(true);
    }

    // Open event detail modal if event ID is in URL (e.g., from dashboard click)
    // Uses parseEventId for safe validation (NEM-2561)
    const eventParam = searchParams.get('event');
    const { eventId, isValid } = parseEventId(eventParam);
    if (isValid && eventId !== null) {
      setSelectedEventForModal(eventId);
    }
  }, [searchParams]);

  // Create a memoized camera name lookup map that updates when cameras change
  // This ensures the component re-renders with correct camera names when cameras load
  const cameraNameMap = useMemo(() => {
    const map = new Map<string, string>();
    cameras.forEach((camera) => {
      map.set(camera.id, camera.name);
    });
    return map;
  }, [cameras]);

  // Convert WebSocket events to ActivityEvent[] for ActivityFeed
  // Resolve camera_name from cameras list or fall back to 'Unknown Camera'
  const activityEvents: ActivityEvent[] = useMemo(() => {
    return wsEvents.map((event) => ({
      id: String(event.id),
      timestamp: event.timestamp ?? event.started_at ?? new Date().toISOString(),
      camera_name: event.camera_name ?? cameraNameMap.get(event.camera_id) ?? 'Unknown Camera',
      risk_score: event.risk_score,
      summary: event.summary,
    }));
  }, [wsEvents, cameraNameMap]);

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

  // Handle filter changes
  const handleFilterChange = (key: keyof EventFilters, value: string | boolean) => {
    setEventFilters((prev) => ({
      ...prev,
      [key]: value === '' ? undefined : value,
    }));
    // Clear selections when filters change
    setSelectedEventIds(new Set());
  };

  // Clear all filters
  const handleClearFilters = () => {
    setEventFilters({});
    setConfidenceFilter('');
    setSortOption('newest');
    setSelectedEventIds(new Set());
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
      searchPagination.goToFirstPage(); // Reset to page 1 on new search

      try {
        const response = await searchEvents({
          q: query,
          camera_id: filters.camera_id,
          start_date: filters.start_date,
          end_date: filters.end_date,
          severity: filters.severity,
          object_type: filters.object_type,
          reviewed: filters.reviewed,
          limit: searchPagination.limit,
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
    [searchPagination]
  );

  // Handle search pagination - converts offset to page number
  const handleSearchPageChange = useCallback(
    async (newOffset: number) => {
      // Increment request ID to track this request
      const requestId = ++searchRequestIdRef.current;

      setIsSearching(true);

      // Calculate page from offset and update pagination state
      const newPage = Math.floor(newOffset / searchPagination.limit) + 1;
      searchPagination.setPage(newPage);

      try {
        const response = await searchEvents({
          q: fullTextQuery,
          camera_id: searchFilters.camera_id,
          start_date: searchFilters.start_date,
          end_date: searchFilters.end_date,
          severity: searchFilters.severity,
          object_type: searchFilters.object_type,
          reviewed: searchFilters.reviewed,
          limit: searchPagination.limit,
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
    [fullTextQuery, searchFilters, searchPagination]
  );

  // Clear search and return to browse mode
  const handleClearSearch = useCallback(() => {
    setIsSearchMode(false);
    setFullTextQuery('');
    setSearchFilters({});
    setSearchResults([]);
    setSearchTotalCount(0);
    searchPagination.reset(); // Reset pagination state and clear URL params
    setSearchError(null);
  }, [searchPagination]);

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
      // Select all loaded events
      setSelectedEventIds(new Set(filteredEvents.map((event) => event.id)));
    }
  };

  // Handle bulk mark as reviewed
  const handleBulkMarkAsReviewed = async () => {
    if (selectedEventIds.size === 0) return;

    setBulkActionLoading(true);
    setBulkActionError(null);
    try {
      const result = await bulkUpdateEvents(Array.from(selectedEventIds), { reviewed: true });

      if (result.failed.length > 0) {
        console.error('Some events failed to update:', result.failed);
        setBulkActionError(
          `Updated ${result.successful.length} events, but ${result.failed.length} failed`
        );
      }

      // Refetch events to reflect changes
      void refetch();

      // Clear selections
      setSelectedEventIds(new Set());
    } catch (err) {
      setBulkActionError(err instanceof Error ? err.message : 'Failed to update events');
    } finally {
      setBulkActionLoading(false);
    }
  };

  // Handle bulk mark as not reviewed
  const handleBulkMarkAsNotReviewed = async () => {
    if (selectedEventIds.size === 0) return;

    setBulkActionLoading(true);
    setBulkActionError(null);
    try {
      const result = await bulkUpdateEvents(Array.from(selectedEventIds), { reviewed: false });

      if (result.failed.length > 0) {
        console.error('Some events failed to update:', result.failed);
        setBulkActionError(
          `Updated ${result.successful.length} events, but ${result.failed.length} failed`
        );
      }

      // Refetch events to reflect changes
      void refetch();

      // Clear selections
      setSelectedEventIds(new Set());
    } catch (err) {
      setBulkActionError(err instanceof Error ? err.message : 'Failed to update events');
    } finally {
      setBulkActionLoading(false);
    }
  };

  // Apply sorting using functional pipeline pattern
  // Note: Confidence filtering would ideally be done server-side with detection data.
  // The filter UI still provides value as it indicates user intent and could be passed to backend.
  const filteredEvents = pipe(getSortTransform<Event>(sortOption))(events);

  // Apply list view sorting when in list view mode
  const listViewEvents = useMemo(() => {
    if (viewMode !== 'list') return filteredEvents;

    return [...filteredEvents].sort((a, b) => {
      let comparison = 0;
      switch (listSortField) {
        case 'time':
          comparison = new Date(a.started_at).getTime() - new Date(b.started_at).getTime();
          break;
        case 'camera':
          comparison = (cameraNameMap.get(a.camera_id) || '').localeCompare(
            cameraNameMap.get(b.camera_id) || ''
          );
          break;
        case 'risk':
          comparison = (a.risk_score || 0) - (b.risk_score || 0);
          break;
      }
      return listSortDirection === 'asc' ? comparison : -comparison;
    });
  }, [filteredEvents, viewMode, listSortField, listSortDirection, cameraNameMap]);

  // Apply event clustering to reduce visual noise
  // Clusters events from same camera within 5-minute window
  const clusteredItems: ClusteredItem[] = useMemo(() => {
    if (viewMode === 'list') {
      // Don't cluster in list view
      return filteredEvents;
    }
    return clusterEvents(filteredEvents, {
      enabled: clusteringEnabled,
      maxTimeGapMinutes: 5,
      minClusterSize: 3,
      sameCamera: true,
    });
  }, [filteredEvents, clusteringEnabled, viewMode]);

  // Add camera names to clusters for display
  const clusteredItemsWithNames: ClusteredItem[] = useMemo(() => {
    return clusteredItems.map((item) => {
      if (isEventCluster(item)) {
        return {
          ...item,
          cameraName: cameraNameMap.get(item.cameraId) || 'Unknown Camera',
        };
      }
      return item;
    });
  }, [clusteredItems, cameraNameMap]);

  // Calculate clustering stats for display
  const clusterStats = useMemo(() => {
    return getClusterStats(filteredEvents, clusteredItemsWithNames);
  }, [filteredEvents, clusteredItemsWithNames]);

  // Calculate risk level counts for the currently displayed events
  const riskCountsPartial = countBy(
    filteredEvents,
    (event) => (event.risk_level || getRiskLevel(event.risk_score || 0)) as RiskLevel
  );
  const riskCounts: Record<RiskLevel, number> = {
    critical: riskCountsPartial.critical ?? 0,
    high: riskCountsPartial.high ?? 0,
    medium: riskCountsPartial.medium ?? 0,
    low: riskCountsPartial.low ?? 0,
  };

  // Calculate if there are active filters
  const hasActiveFilters =
    eventFilters.camera_id ||
    eventFilters.risk_level ||
    eventFilters.start_date ||
    eventFilters.end_date ||
    eventFilters.reviewed !== undefined ||
    eventFilters.object_type ||
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
      thumbnail_url: event.thumbnail_url || undefined,
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
      // Refetch events to reflect changes
      void refetch();
    } catch (err) {
      console.error('Failed to mark event as reviewed:', err);
    }
  };

  // Handle mark as reviewed from list view (takes number instead of string)
  const handleListMarkReviewed = async (eventId: number) => {
    try {
      await updateEvent(eventId, { reviewed: true });
      // Refetch events to reflect changes
      void refetch();
    } catch (err) {
      console.error('Failed to mark event as reviewed:', err);
    }
  };

  // Handle list view column sort
  const handleListSort = (field: SortField) => {
    if (field === listSortField) {
      // Toggle direction if same field
      setListSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      // New field, default to descending
      setListSortField(field);
      setListSortDirection('desc');
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

  // Handle pull-to-refresh (NEM-2970)
  // Note: refetch returns void, so we wrap it in a Promise for PullToRefresh
  const handlePullToRefresh = useCallback((): Promise<void> => {
    refetch();
    return Promise.resolve();
  }, [refetch]);

  // Handle swipe left action (delete/archive event) - Mobile gesture (NEM-3070)
  const handleSwipeLeft = useCallback(
    async (eventId: string) => {
      // For now, swipe left marks as reviewed (archive behavior)
      // Future enhancement: could add delete confirmation modal
      try {
        await updateEvent(parseInt(eventId, 10), { reviewed: true });
        void refetch();
      } catch (err) {
        console.error('Failed to archive event:', err);
      }
    },
    [refetch]
  );

  // Handle swipe right action (mark as reviewed) - Mobile gesture (NEM-3070)
  const handleSwipeRight = useCallback(
    async (eventId: string) => {
      try {
        await updateEvent(parseInt(eventId, 10), { reviewed: true });
        void refetch();
      } catch (err) {
        console.error('Failed to mark event as reviewed:', err);
      }
    },
    [refetch]
  );

  // Convert API Event to MobileEventCard props (NEM-3070)
  const getMobileEventCardProps = (event: Event) => {
    const camera_name = cameraNameMap.get(event.camera_id) || 'Unknown Camera';

    return {
      id: String(event.id),
      timestamp: event.started_at,
      camera_name,
      risk_score: event.risk_score || 0,
      risk_label: event.risk_level || getRiskLevel(event.risk_score || 0),
      summary: event.summary || 'No summary available',
      thumbnail_url: event.thumbnail_url || undefined,
      detections: [], // Detections not available in list view
      started_at: event.started_at,
      ended_at: event.ended_at,
      onSwipeLeft: (id: string) => void handleSwipeLeft(id),
      onSwipeRight: (id: string) => void handleSwipeRight(id),
      onClick: (eventId: string) => setSelectedEventForModal(parseInt(eventId, 10)),
    };
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
      reasoning: event.reasoning ?? undefined,
      detections: [], // Detections fetched by modal via API
      started_at: event.started_at,
      ended_at: event.ended_at,
      reviewed: event.reviewed,
      notes: event.notes,
    };
  };

  return (
    <div className={`flex flex-col ${className}`} data-testid="timeline-page">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white">Event Timeline</h1>
        <p className="mt-2 text-gray-400">View and filter all security events from your cameras</p>
      </div>

      {/* Live Activity Section */}
      <LiveActivitySection
        events={activityEvents}
        isConnected={wsConnected}
        onEventClick={(eventId) => setSelectedEventForModal(parseInt(eventId, 10))}
        maxItems={10}
        className="mb-8"
      />

      {/* Section Divider - Clear separation between live and historical */}
      <div className="mb-6 flex items-center gap-4">
        <div className="h-px flex-1 bg-gradient-to-r from-transparent via-gray-700 to-transparent" />
        <span className="text-xs font-medium uppercase tracking-wider text-gray-500">
          Historical Events
        </span>
        <div className="h-px flex-1 bg-gradient-to-r from-transparent via-gray-700 to-transparent" />
      </div>

      {/* Timeline Scrubber (NEM-2932) - Visual timeline for navigating events */}
      {!isSearchMode && (
        <TimelineScrubber
          buckets={timelineBuckets}
          onTimeRangeChange={(range: TimeRange) => {
            setEventFilters((prev) => ({
              ...prev,
              start_date: range.startDate.split('T')[0],
              end_date: range.endDate.split('T')[0],
            }));
          }}
          zoomLevel={timelineZoomLevel}
          onZoomChange={setTimelineZoomLevel}
          isLoading={timelineLoading}
          className="mb-6"
        />
      )}

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
          offset={searchPagination.offset}
          limit={searchPagination.limit}
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
          {/* Quick Filter Chips */}
          <div className="mb-4 rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
            <FilterChips
              filters={eventFilters}
              riskCounts={riskCounts}
              onFilterChange={handleFilterChange}
              onClearFilters={handleClearFilters}
            />
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

              {/* Export Button with dropdown for CSV/JSON/ZIP formats (NEM-3066) */}
              <ExportButton
                cameraId={eventFilters.camera_id}
                riskLevel={eventFilters.risk_level}
                startDate={eventFilters.start_date}
                endDate={eventFilters.end_date}
                reviewed={eventFilters.reviewed}
                disabled={totalCount === 0}
              />

              {/* Export Modal Button for advanced options */}
              <button
                onClick={() => setShowExportModal(true)}
                className="flex items-center gap-2 rounded-md border border-gray-700 bg-[#1A1A1A] px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:border-gray-600 hover:bg-[#252525]"
                aria-label="Open export modal with more options"
              >
                <Download className="h-4 w-4" />
                <span>More Options</span>
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
                    value={eventFilters.camera_id || ''}
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
                  <label
                    htmlFor="risk-filter"
                    className="mb-1 block text-sm font-medium text-gray-300"
                  >
                    Risk Level
                  </label>
                  <select
                    id="risk-filter"
                    value={eventFilters.risk_level || ''}
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
                    value={
                      eventFilters.reviewed === undefined
                        ? ''
                        : eventFilters.reviewed
                          ? 'true'
                          : 'false'
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
                  <label
                    htmlFor="object-type-filter"
                    className="mb-1 block text-sm font-medium text-gray-300"
                  >
                    Object Type
                  </label>
                  <select
                    id="object-type-filter"
                    value={eventFilters.object_type || ''}
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
                      value={eventFilters.start_date || ''}
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
                      value={eventFilters.end_date || ''}
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
            <div className="flex flex-col gap-2">
              <p className="text-sm text-gray-400">
                {totalCount === 0
                  ? '0 events'
                  : `Showing ${filteredEvents.length} of ${totalCount} events`}
              </p>
              {/* Clustering Stats - only show when clustering is active and has effect */}
              {clusteringEnabled && viewMode === 'grid' && clusterStats.clusterCount > 0 && (
                <p className="flex items-center gap-1.5 text-sm text-[#76B900]">
                  <Layers className="h-3.5 w-3.5" />
                  <span>
                    {clusterStats.originalCount} events grouped into {clusterStats.clusterCount}{' '}
                    cluster{clusterStats.clusterCount !== 1 ? 's' : ''} ({clusterStats.displayCount}{' '}
                    items)
                  </span>
                </p>
              )}
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

            {/* View Toggle and Bulk Actions Bar */}
            {!loading && !error && filteredEvents.length > 0 && (
              <div className="flex items-center gap-3">
                {/* View Mode Toggle */}
                <ViewToggle
                  viewMode={viewMode}
                  onChange={setViewMode}
                  persistKey="timeline-view-mode"
                />

                {/* Clustering Toggle - only show in grid view */}
                {viewMode === 'grid' && (
                  <button
                    onClick={() => setClusteringEnabled(!clusteringEnabled)}
                    className={`flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors ${
                      clusteringEnabled
                        ? 'border-[#76B900] bg-[#76B900]/10 text-[#76B900]'
                        : 'border-gray-700 bg-[#1A1A1A] text-gray-300 hover:border-gray-600 hover:bg-[#252525]'
                    }`}
                    aria-pressed={clusteringEnabled}
                    title={
                      clusteringEnabled ? 'Disable event clustering' : 'Enable event clustering'
                    }
                  >
                    <Layers className="h-4 w-4" />
                    <span>Cluster</span>
                  </button>
                )}

                {/* Select All Checkbox - show in grid and grouped views since list view has its own */}
                {(viewMode === 'grid' || viewMode === 'grouped') && (
                  <button
                    onClick={handleToggleSelectAll}
                    className="flex items-center gap-2 rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-1.5 text-sm text-gray-300 transition-colors hover:border-gray-600 hover:bg-[#252525]"
                    aria-label={
                      selectedEventIds.size === filteredEvents.length && filteredEvents.length > 0
                        ? 'Deselect all events'
                        : 'Select all events'
                    }
                  >
                    {selectedEventIds.size === filteredEvents.length &&
                    filteredEvents.length > 0 ? (
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
                )}

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

          {/* Event List - wrapped with PullToRefresh on mobile (NEM-2970) */}
          {(() => {
            const eventListContent = loading ? (
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
                {Array.from({ length: 6 }, (_, i) => (
                  <EventCardSkeleton key={i} />
                ))}
              </div>
            ) : error ? (
              <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-red-900/50 bg-red-950/20">
                <div className="text-center">
                  <p className="mb-2 text-lg font-semibold text-red-400">Error Loading Events</p>
                  <SafeErrorMessage message={error} size="sm" color="gray" />
                </div>
              </div>
            ) : filteredEvents.length === 0 ? (
              <div className="rounded-lg border border-gray-800 bg-[#1F1F1F]">
                <EmptyState
                  icon={Clock}
                  title="No Events Found"
                  description={
                    hasActiveFilters
                      ? 'No events match your current filters. Try adjusting your search criteria or clearing some filters.'
                      : 'No security events have been recorded yet. Events will appear here as they are detected by your cameras.'
                  }
                  variant={hasActiveFilters ? 'muted' : 'default'}
                  actions={
                    hasActiveFilters
                      ? [
                          {
                            label: 'Clear All Filters',
                            onClick: handleClearFilters,
                            variant: 'secondary',
                          },
                        ]
                      : undefined
                  }
                  testId="timeline-empty-state"
                />
              </div>
            ) : viewMode === 'list' ? (
              <>
                {/* List View */}
                <EventListView
                  events={listViewEvents.map((event) => ({
                    id: event.id,
                    camera_id: event.camera_id,
                    camera_name: cameraNameMap.get(event.camera_id) || 'Unknown Camera',
                    started_at: event.started_at,
                    ended_at: event.ended_at,
                    risk_score: event.risk_score || 0,
                    risk_level: event.risk_level || getRiskLevel(event.risk_score || 0),
                    summary: event.summary || null,
                    thumbnail_url: event.thumbnail_url || null,
                    reviewed: event.reviewed || false,
                  }))}
                  selectedIds={selectedEventIds}
                  onToggleSelection={handleToggleSelection}
                  onToggleSelectAll={handleToggleSelectAll}
                  onEventClick={(eventId) => setSelectedEventForModal(eventId)}
                  onMarkReviewed={(eventId) => void handleListMarkReviewed(eventId)}
                  sortField={listSortField}
                  sortDirection={listSortDirection}
                  onSort={handleListSort}
                />

                {/* Infinite Scroll Status */}
                <InfiniteScrollStatus
                  sentinelRef={sentinelRef}
                  isLoading={isFetchingNextPage || isLoadingMore}
                  hasMore={hasNextPage}
                  error={scrollError}
                  onRetry={retry}
                  totalCount={totalCount}
                  loadedCount={listViewEvents.length}
                  endMessage="You've seen all events"
                  loadingMessage="Loading more events..."
                  className="mt-6"
                />
              </>
            ) : viewMode === 'grouped' ? (
              <>
                {/* Grouped View - Events grouped by time period */}
                <TimeGroupedEvents
                  events={filteredEvents}
                  cameraNameMap={cameraNameMap}
                  selectedEventIds={selectedEventIds}
                  onToggleSelection={handleToggleSelection}
                  onEventClick={(eventId) => setSelectedEventForModal(eventId)}
                  onViewEventDetails={onViewEventDetails}
                  isLoading={loading}
                />

                {/* Infinite Scroll Status */}
                <InfiniteScrollStatus
                  sentinelRef={sentinelRef}
                  isLoading={isFetchingNextPage || isLoadingMore}
                  hasMore={hasNextPage}
                  error={scrollError}
                  onRetry={retry}
                  totalCount={totalCount}
                  loadedCount={filteredEvents.length}
                  endMessage="You've seen all events"
                  loadingMessage="Loading more events..."
                  className="mt-6"
                />
              </>
            ) : (
              <>
                {/* Grid View */}
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
                  {clusteredItemsWithNames.map((item) => {
                    // Render cluster card for clusters
                    if (isEventCluster(item)) {
                      return (
                        <EventClusterCard
                          key={item.clusterId}
                          cluster={item}
                          onEventClick={(eventId) => setSelectedEventForModal(eventId)}
                          hasCheckboxOverlay={false}
                        />
                      );
                    }

                    // Render regular event card for individual events
                    const event = item;

                    // Mobile: Use MobileEventCard with swipe gestures (NEM-3070)
                    if (isMobile) {
                      return <MobileEventCard key={event.id} {...getMobileEventCardProps(event)} />;
                    }

                    // Desktop: Use EventCard with selection checkbox
                    return (
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
                    );
                  })}
                </div>

                {/* Infinite Scroll Status */}
                <InfiniteScrollStatus
                  sentinelRef={sentinelRef}
                  isLoading={isFetchingNextPage || isLoadingMore}
                  hasMore={hasNextPage}
                  error={scrollError}
                  onRetry={retry}
                  totalCount={totalCount}
                  loadedCount={filteredEvents.length}
                  endMessage="You've seen all events"
                  loadingMessage="Loading more events..."
                  className="mt-6"
                />
              </>
            );

            // Wrap with PullToRefresh on mobile devices
            if (isMobile) {
              return (
                <PullToRefresh
                  onRefresh={handlePullToRefresh}
                  isRefreshing={loading}
                  disabled={loading || isSearchMode}
                >
                  {eventListContent}
                </PullToRefresh>
              );
            }

            return eventListContent;
          })()}
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

      {/* Export Modal */}
      <ExportModal
        isOpen={showExportModal}
        onClose={() => setShowExportModal(false)}
        initialFilters={{
          camera_id: eventFilters.camera_id,
          risk_level: eventFilters.risk_level,
          start_date: eventFilters.start_date,
          end_date: eventFilters.end_date,
        }}
        onExportComplete={() => {
          setShowExportModal(false);
        }}
      />
    </div>
  );
}
