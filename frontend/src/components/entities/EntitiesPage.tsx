import {
  AlertCircle,
  ArrowDownAZ,
  Calendar,
  Car,
  Database,
  Loader2,
  RefreshCw,
  User,
  Users,
} from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';

import EntitiesEmptyState from './EntitiesEmptyState';
import EntityCard from './EntityCard';
import EntityDetailModal from './EntityDetailModal';
import EntityStatsCard from './EntityStatsCard';
import { useCamerasQuery } from '../../hooks/useCamerasQuery';
import {
  useEntitiesInfiniteQuery,
  type EntityFilters,
  type EntityTimeRangeFilter,
} from '../../hooks/useEntitiesInfiniteQuery';
import { useEntityDetailQuery, type TimeRangeFilter } from '../../hooks/useEntitiesQuery';
import { useInfiniteScroll } from '../../hooks/useInfiniteScroll';
import { EntityCardSkeleton, InfiniteScrollStatus, SafeErrorMessage } from '../common';

import type { SourceFilter } from '../../services/api';

/**
 * Sort options for entity list
 */
type SortOption = 'last_seen' | 'first_seen' | 'appearance_count';

import type { SourceFilter } from '../../services/api';

/**
 * Sort options for entity list
 */
type SortOption = 'last_seen' | 'first_seen' | 'appearance_count';

/**
 * EntitiesPage component - Display and manage tracked entities
 *
 * Features:
 * - List of tracked people and vehicles detected across cameras
 * - Filter by entity type (person/vehicle)
 * - Filter by time range (1h/24h/7d/30d) or custom date range
 * - Filter by camera
 * - Filter by data source (Redis real-time, PostgreSQL historical, or both)
 * - Sort by last seen, first seen, or appearance count
 * - View entity detail with appearance timeline
 * - Entity statistics card
 * - Auto-refresh every 30 seconds
 * - Infinite scroll for large entity lists
 */
export default function EntitiesPage() {
  // State for filters
  const [entityTypeFilter, setEntityTypeFilter] = useState<'all' | 'person' | 'vehicle'>('all');
  const [timeRangeFilter, setTimeRangeFilter] = useState<TimeRangeFilter>('all');
  const [cameraFilter, setCameraFilter] = useState<string>('');
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('both');
  const [sortOption, setSortOption] = useState<SortOption>('last_seen');
  const [showStats, setShowStats] = useState<boolean>(true);

  // Custom date range state
  const [customDateRange, setCustomDateRange] = useState<{ since?: Date; until?: Date }>({});
  const [useCustomDateRange, setUseCustomDateRange] = useState<boolean>(false);

  // State for entity detail modal
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  // Fetch cameras for the filter dropdown
  const { cameras, isLoading: camerasLoading } = useCamerasQuery();

  // Compute effective date range (custom or preset)
  const effectiveDateRange = useMemo(() => {
    if (useCustomDateRange && (customDateRange.since || customDateRange.until)) {
      return {
        since: customDateRange.since?.toISOString(),
        until: customDateRange.until?.toISOString(),
      };
    }
    // Convert time range filter to ISO timestamp
    const since = timeRangeToSince(timeRangeFilter);
    return { since, until: undefined };
  }, [useCustomDateRange, customDateRange, timeRangeFilter]);

  // Build filters for the infinite query
  const filters: EntityFilters = useMemo(() => {
    const f: EntityFilters = {};

    if (entityTypeFilter !== 'all') {
      f.entity_type = entityTypeFilter;
    }

    if (cameraFilter) {
      f.camera_id = cameraFilter;
    }

    // Apply date range
    if (effectiveDateRange.since) {
      f.since = effectiveDateRange.since;
    }

    return f;
  }, [entityTypeFilter, cameraFilter, effectiveDateRange]);

  // Fetch entities with cursor-based pagination and infinite scroll
  const {
    entities,
    totalCount,
    isLoading: loading,
    isFetching,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    error,
    refetch,
  } = useEntitiesInfiniteQuery({
    filters,
    limit: 50,
    refetchInterval: 30000, // Auto-refresh every 30 seconds
  });

  // Infinite scroll hook
  const { sentinelRef, isLoadingMore, error: scrollError, retry } = useInfiniteScroll({
    onLoadMore: fetchNextPage,
    hasMore: hasNextPage,
    isLoading: isFetchingNextPage,
    enabled: !loading && entities.length > 0,
  });

  // Sort entities based on selected sort option
  const sortedEntities = useMemo(() => {
    if (!entities.length) return entities;

    return [...entities].sort((a, b) => {
      switch (sortOption) {
        case 'last_seen':
          return new Date(b.last_seen).getTime() - new Date(a.last_seen).getTime();
        case 'first_seen':
          return new Date(b.first_seen).getTime() - new Date(a.first_seen).getTime();
        case 'appearance_count':
          return b.appearance_count - a.appearance_count;
        default:
          return 0;
      }
    });
  }, [entities, sortOption]);

  // Fetch entity detail when modal is open
  const {
    data: selectedEntity,
    isLoading: loadingDetail,
    error: detailError,
  } = useEntityDetailQuery(selectedEntityId ?? undefined, {
    enabled: modalOpen && !!selectedEntityId,
  });

  // Handle entity card click - open detail modal
  const handleEntityClick = useCallback((entityId: string) => {
    setSelectedEntityId(entityId);
    setModalOpen(true);
  }, []);

  // Handle modal close
  const handleCloseModal = useCallback(() => {
    setModalOpen(false);
    setSelectedEntityId(null);
  }, []);

  // Handle refresh button click
  const handleRefresh = useCallback(() => {
    void refetch();
  }, [refetch]);

  // Count entities by type (from loaded entities)
  const personCount = sortedEntities.filter((e) => e.entity_type === 'person').length;
  const vehicleCount = sortedEntities.filter((e) => e.entity_type === 'vehicle').length;

  // Time range options
  const timeRangeOptions: { value: TimeRangeFilter; label: string }[] = [
    { value: 'all', label: 'All Time' },
    { value: '1h', label: 'Last 1h' },
    { value: '24h', label: 'Last 24h' },
    { value: '7d', label: 'Last 7d' },
    { value: '30d', label: 'Last 30d' },
  ];

  // Determine if we're doing a background refresh (not initial load or pagination)
  const isRefetching = isFetching && !loading && !isFetchingNextPage;

  // Error message from entities or entity detail
  const errorMessage = error?.message ?? (detailError && modalOpen ? detailError.message : null);

  return (
    <div className="flex flex-col">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <Users className="h-8 w-8 text-[#76B900]" />
            <h1 className="text-3xl font-bold text-white">Entities</h1>
          </div>
          <p className="mt-2 text-gray-400">
            Track and identify people and vehicles across your cameras
          </p>
        </div>

        {/* Refresh button */}
        <button
          onClick={handleRefresh}
          disabled={loading || isRefetching}
          className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:opacity-50"
          aria-label="Refresh entities"
        >
          <RefreshCw className={`h-4 w-4 ${loading || isRefetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Entity Stats Card */}
      {showStats && (
        <EntityStatsCard
          since={effectiveDateRange.since ? new Date(effectiveDateRange.since) : undefined}
          until={effectiveDateRange.until ? new Date(effectiveDateRange.until) : undefined}
          className="mb-6"
          compact
        />
      )}

      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-center gap-4">
        {/* Entity type filter */}
        <div className="flex rounded-lg border border-gray-700 bg-[#1F1F1F]">
          <button
            onClick={() => setEntityTypeFilter('all')}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
              entityTypeFilter === 'all'
                ? 'bg-[#76B900] text-black'
                : 'text-gray-300 hover:text-white'
            } rounded-l-lg`}
            aria-pressed={entityTypeFilter === 'all'}
          >
            All
          </button>
          <button
            onClick={() => setEntityTypeFilter('person')}
            className={`flex items-center gap-2 border-l border-gray-700 px-4 py-2 text-sm font-medium transition-colors ${
              entityTypeFilter === 'person'
                ? 'bg-[#76B900] text-black'
                : 'text-gray-300 hover:text-white'
            }`}
            aria-pressed={entityTypeFilter === 'person'}
          >
            <User className="h-4 w-4" />
            Persons
          </button>
          <button
            onClick={() => setEntityTypeFilter('vehicle')}
            className={`flex items-center gap-2 border-l border-gray-700 px-4 py-2 text-sm font-medium transition-colors ${
              entityTypeFilter === 'vehicle'
                ? 'bg-[#76B900] text-black'
                : 'text-gray-300 hover:text-white'
            } rounded-r-lg`}
            aria-pressed={entityTypeFilter === 'vehicle'}
          >
            <Car className="h-4 w-4" />
            Vehicles
          </button>
        </div>

        {/* Time range filter */}
        <div className="flex items-center gap-2">
          <label htmlFor="time-range-filter" className="text-sm text-gray-400">
            Time:
          </label>
          <select
            id="time-range-filter"
            value={useCustomDateRange ? 'custom' : timeRangeFilter}
            onChange={(e) => {
              if (e.target.value === 'custom') {
                setUseCustomDateRange(true);
              } else {
                setUseCustomDateRange(false);
                setTimeRangeFilter(e.target.value as TimeRangeFilter);
              }
            }}
            className="rounded-lg border border-gray-700 bg-[#1F1F1F] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            aria-label="Filter by time range"
          >
            {timeRangeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
            <option value="custom">Custom Range</option>
          </select>
        </div>

        {/* Custom date range inputs */}
        {useCustomDateRange && (
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-gray-400" />
            <input
              type="date"
              value={customDateRange.since?.toISOString().split('T')[0] ?? ''}
              onChange={(e) =>
                setCustomDateRange((prev) => ({
                  ...prev,
                  since: e.target.value ? new Date(e.target.value) : undefined,
                }))
              }
              className="rounded-lg border border-gray-700 bg-[#1F1F1F] px-2 py-1.5 text-sm text-white focus:border-[#76B900] focus:outline-none"
              aria-label="Start date"
            />
            <span className="text-gray-400">to</span>
            <input
              type="date"
              value={customDateRange.until?.toISOString().split('T')[0] ?? ''}
              onChange={(e) =>
                setCustomDateRange((prev) => ({
                  ...prev,
                  until: e.target.value ? new Date(e.target.value) : undefined,
                }))
              }
              className="rounded-lg border border-gray-700 bg-[#1F1F1F] px-2 py-1.5 text-sm text-white focus:border-[#76B900] focus:outline-none"
              aria-label="End date"
            />
          </div>
        )}

        {/* Camera filter */}
        <div className="flex items-center gap-2">
          <label htmlFor="camera-filter" className="text-sm text-gray-400">
            Camera:
          </label>
          <select
            id="camera-filter"
            value={cameraFilter}
            onChange={(e) => setCameraFilter(e.target.value)}
            disabled={camerasLoading}
            className="rounded-lg border border-gray-700 bg-[#1F1F1F] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900] disabled:opacity-50"
            aria-label="Filter by camera"
          >
            <option value="">All Cameras</option>
            {cameras.map((camera) => (
              <option key={camera.id} value={camera.id}>
                {camera.name}
              </option>
            ))}
          </select>
        </div>

        {/* Data source filter */}
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-gray-400" />
          <select
            id="source-filter"
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value as SourceFilter)}
            className="rounded-lg border border-gray-700 bg-[#1F1F1F] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            aria-label="Filter by data source"
          >
            <option value="both">All Sources</option>
            <option value="redis">Real-time (24h)</option>
            <option value="postgres">Historical (30d)</option>
          </select>
        </div>

        {/* Sort option */}
        <div className="flex items-center gap-2">
          <ArrowDownAZ className="h-4 w-4 text-gray-400" />
          <select
            id="sort-option"
            value={sortOption}
            onChange={(e) => setSortOption(e.target.value as SortOption)}
            className="rounded-lg border border-gray-700 bg-[#1F1F1F] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            aria-label="Sort by"
          >
            <option value="last_seen">Last Seen</option>
            <option value="first_seen">First Seen</option>
            <option value="appearance_count">Appearances</option>
          </select>
        </div>

        {/* Toggle stats display */}
        <button
          onClick={() => setShowStats(!showStats)}
          className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
            showStats
              ? 'border-[#76B900] bg-[#76B900]/20 text-[#76B900]'
              : 'border-gray-700 text-gray-400 hover:text-white'
          }`}
          aria-label={showStats ? 'Hide statistics' : 'Show statistics'}
          aria-pressed={showStats}
        >
          Stats
        </button>
      </div>

      {/* Result summary */}
      <div className="mb-4 flex flex-wrap items-center gap-4">
        {/* Stats */}
        {!loading && !error && sortedEntities.length > 0 && (
          <div className="flex items-center gap-4 text-sm text-gray-400">
            <span className="flex items-center gap-1">
              <User className="h-4 w-4" />
              {personCount} {personCount === 1 ? 'person' : 'persons'}
            </span>
            <span className="flex items-center gap-1">
              <Car className="h-4 w-4" />
              {vehicleCount} {vehicleCount === 1 ? 'vehicle' : 'vehicles'}
            </span>
            {totalCount > sortedEntities.length && (
              <span className="text-gray-500">
                (showing {sortedEntities.length} of {totalCount})
              </span>
            )}
          </div>
        )}

        {/* Auto-refresh indicator */}
        {isRefetching && !loading && (
          <span className="flex items-center gap-1 text-xs text-gray-500">
            <RefreshCw className="h-3 w-3 animate-spin" />
            Updating...
          </span>
        )}
      </div>

      {/* Content */}
      {loading ? (
        /* Loading state with skeletons */
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }, (_, i) => (
            <EntityCardSkeleton key={i} />
          ))}
        </div>
      ) : error ? (
        /* Error state */
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-red-900/50 bg-red-900/10">
          <div className="flex flex-col items-center gap-3 text-center">
            <AlertCircle className="h-8 w-8 text-red-500" />
            <SafeErrorMessage message={errorMessage} />
            <button
              onClick={handleRefresh}
              className="mt-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
            >
              Try Again
            </button>
          </div>
        </div>
      ) : sortedEntities.length === 0 ? (
        /* Empty state */
        entityTypeFilter === 'all' && timeRangeFilter === 'all' && !cameraFilter && !useCustomDateRange ? (
          <EntitiesEmptyState />
        ) : (
          /* Filtered empty state - simpler message */
          <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]">
            <div className="max-w-md text-center">
              <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-[#76B900]/10">
                {entityTypeFilter === 'person' ? (
                  <User className="h-10 w-10 text-[#76B900]" />
                ) : entityTypeFilter === 'vehicle' ? (
                  <Car className="h-10 w-10 text-[#76B900]" />
                ) : (
                  <Users className="h-10 w-10 text-[#76B900]" />
                )}
              </div>
              <h2 className="mb-3 text-xl font-semibold text-white">
                {entityTypeFilter === 'person'
                  ? 'No Persons Found'
                  : entityTypeFilter === 'vehicle'
                    ? 'No Vehicles Found'
                    : 'No Entities Found'}
              </h2>
              <p className="text-gray-400">
                {entityTypeFilter === 'person'
                  ? 'No persons have been tracked'
                  : entityTypeFilter === 'vehicle'
                    ? 'No vehicles have been tracked'
                    : 'No entities have been tracked'}
                {useCustomDateRange
                  ? ' in the selected date range'
                  : timeRangeFilter !== 'all' && ` in the last ${getTimeRangeLabel(timeRangeFilter)}`}
                {cameraFilter && ` on this camera`}.
              </p>
              <button
                onClick={() => {
                  setEntityTypeFilter('all');
                  setTimeRangeFilter('all');
                  setCameraFilter('');
                  setSourceFilter('both');
                  setUseCustomDateRange(false);
                  setCustomDateRange({});
                }}
                className="mt-4 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
              >
                Clear Filters
              </button>
            </div>
          </div>
        )
      ) : (
        /* Entity grid with infinite scroll */
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {sortedEntities.map((entity) => (
              <EntityCard
                key={entity.id}
                id={entity.id}
                entity_type={entity.entity_type}
                first_seen={entity.first_seen}
                last_seen={entity.last_seen}
                appearance_count={entity.appearance_count}
                cameras_seen={entity.cameras_seen}
                thumbnail_url={entity.thumbnail_url}
                onClick={handleEntityClick}
              />
            ))}
          </div>

          {/* Infinite Scroll Status */}
          <InfiniteScrollStatus
            sentinelRef={sentinelRef}
            isLoading={isFetchingNextPage || isLoadingMore}
            hasMore={hasNextPage}
            error={scrollError}
            onRetry={retry}
            totalCount={totalCount}
            loadedCount={sortedEntities.length}
            endMessage="You've seen all entities"
            loadingMessage="Loading more entities..."
            className="mt-6"
          />
        </>
      )}

      {/* Entity Detail Modal */}
      <EntityDetailModal
        entity={selectedEntity ?? null}
        isOpen={modalOpen}
        onClose={handleCloseModal}
      />

      {/* Loading overlay for modal */}
      {loadingDetail && modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75">
          <div className="flex flex-col items-center gap-3 text-white">
            <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
            <p>Loading entity details...</p>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Converts a time range filter to an ISO timestamp string.
 * Returns undefined for 'all' (no filtering).
 */
function timeRangeToSince(timeRange: TimeRangeFilter | EntityTimeRangeFilter): string | undefined {
  if (timeRange === 'all') {
    return undefined;
  }

  const now = new Date();
  let sinceDate: Date;

  switch (timeRange) {
    case '1h':
      sinceDate = new Date(now.getTime() - 60 * 60 * 1000);
      break;
    case '24h':
      sinceDate = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      break;
    case '7d':
      sinceDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      break;
    case '30d':
      sinceDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      break;
    default:
      return undefined;
  }

  return sinceDate.toISOString();
}

/**
 * Helper to get a human-readable label for time range
 */
function getTimeRangeLabel(timeRange: TimeRangeFilter): string {
  switch (timeRange) {
    case '1h':
      return 'hour';
    case '24h':
      return '24 hours';
    case '7d':
      return '7 days';
    case '30d':
      return '30 days';
    default:
      return '';
  }
}
