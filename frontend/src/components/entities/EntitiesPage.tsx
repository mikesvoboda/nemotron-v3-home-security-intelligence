import { AlertCircle, Car, Loader2, RefreshCw, User, Users } from 'lucide-react';
import { useCallback, useState } from 'react';

import EntitiesEmptyState from './EntitiesEmptyState';
import EntityCard from './EntityCard';
import EntityDetailModal from './EntityDetailModal';
import { useCamerasQuery } from '../../hooks/useCamerasQuery';
import {
  useEntitiesQuery,
  useEntityDetailQuery,
  type TimeRangeFilter,
} from '../../hooks/useEntitiesQuery';
import { EntityCardSkeleton } from '../common';

/**
 * EntitiesPage component - Display and manage tracked entities
 *
 * Features:
 * - List of tracked people and vehicles detected across cameras
 * - Filter by entity type (person/vehicle)
 * - Filter by time range (1h/24h/7d/30d)
 * - Filter by camera
 * - View entity detail with appearance timeline
 * - Auto-refresh every 30 seconds
 */
export default function EntitiesPage() {
  // State for filters
  const [entityTypeFilter, setEntityTypeFilter] = useState<'all' | 'person' | 'vehicle'>('all');
  const [timeRangeFilter, setTimeRangeFilter] = useState<TimeRangeFilter>('all');
  const [cameraFilter, setCameraFilter] = useState<string>('');

  // State for entity detail modal
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  // Fetch cameras for the filter dropdown
  const { cameras, isLoading: camerasLoading } = useCamerasQuery();

  // Fetch entities with TanStack Query and auto-refresh
  const {
    entities,
    isLoading: loading,
    isRefetching,
    error,
    refetch,
  } = useEntitiesQuery({
    entityType: entityTypeFilter,
    cameraId: cameraFilter || undefined,
    timeRange: timeRangeFilter,
    refetchInterval: 30000, // Auto-refresh every 30 seconds
  });

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

  // Count entities by type
  const personCount = entities.filter((e) => e.entity_type === 'person').length;
  const vehicleCount = entities.filter((e) => e.entity_type === 'vehicle').length;

  // Time range options
  const timeRangeOptions: { value: TimeRangeFilter; label: string }[] = [
    { value: 'all', label: 'All Time' },
    { value: '1h', label: 'Last 1h' },
    { value: '24h', label: 'Last 24h' },
    { value: '7d', label: 'Last 7d' },
    { value: '30d', label: 'Last 30d' },
  ];

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
            value={timeRangeFilter}
            onChange={(e) => setTimeRangeFilter(e.target.value as TimeRangeFilter)}
            className="rounded-lg border border-gray-700 bg-[#1F1F1F] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            aria-label="Filter by time range"
          >
            {timeRangeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

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

        {/* Stats */}
        {!loading && !error && entities.length > 0 && (
          <div className="flex items-center gap-4 text-sm text-gray-400">
            <span className="flex items-center gap-1">
              <User className="h-4 w-4" />
              {personCount} {personCount === 1 ? 'person' : 'persons'}
            </span>
            <span className="flex items-center gap-1">
              <Car className="h-4 w-4" />
              {vehicleCount} {vehicleCount === 1 ? 'vehicle' : 'vehicles'}
            </span>
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
            <p className="text-red-400">{errorMessage}</p>
            <button
              onClick={handleRefresh}
              className="mt-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
            >
              Try Again
            </button>
          </div>
        </div>
      ) : entities.length === 0 ? (
        /* Empty state */
        entityTypeFilter === 'all' && timeRangeFilter === 'all' && !cameraFilter ? (
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
                {timeRangeFilter !== 'all' && ` in the last ${getTimeRangeLabel(timeRangeFilter)}`}
                {cameraFilter && ` on this camera`}.
              </p>
              <button
                onClick={() => {
                  setEntityTypeFilter('all');
                  setTimeRangeFilter('all');
                  setCameraFilter('');
                }}
                className="mt-4 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
              >
                Clear Filters
              </button>
            </div>
          </div>
        )
      ) : (
        /* Entity grid */
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {entities.map((entity) => (
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
