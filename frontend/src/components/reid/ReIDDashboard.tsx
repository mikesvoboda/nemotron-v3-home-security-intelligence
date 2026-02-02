/**
 * ReIDDashboard - Cross-camera entity matching visualization
 *
 * NEM-5024 Phase 8: Re-ID Dashboard
 *
 * Features:
 * - Cross-camera entity matching visualization
 * - Entity timeline showing appearances across cameras
 * - Camera journey visualization (entity path through property)
 * - Similarity scores display
 * - Link to household member if matched
 */
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Camera,
  Car,
  Clock,
  ExternalLink,
  Home,
  Loader2,
  MapPin,
  RefreshCw,
  Route,
  User,
  Users,
} from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { useCamerasQuery } from '../../hooks/useCamerasQuery';
import { useEntitiesInfiniteQuery, type EntityFilters } from '../../hooks/useEntitiesInfiniteQuery';
import { useEntityDetailQuery } from '../../hooks/useEntitiesQuery';
import { FeatureErrorBoundary, SafeErrorMessage } from '../common';

import type { EntitySummary } from '../../services/api';

/**
 * Extended EntitySummary with household member info
 */
interface EntityWithHousehold extends EntitySummary {
  household_member_id?: number;
  household_member_name?: string;
}

/**
 * Type filter options
 */
type EntityTypeFilter = 'all' | 'person' | 'vehicle';

/**
 * Minimum cameras filter options
 */
type MinCamerasFilter = 2 | 3 | 4 | 5;

/**
 * Loading skeleton for entity cards
 */
function ReIDEntityCardSkeleton() {
  return (
    <div
      data-testid="reid-loading-skeleton"
      className="animate-pulse rounded-lg border border-gray-800 bg-[#1F1F1F] p-4"
    >
      <div className="mb-3 flex items-center gap-3">
        <div className="h-12 w-12 rounded-full bg-gray-700" />
        <div className="flex-1">
          <div className="mb-2 h-4 w-24 rounded bg-gray-700" />
          <div className="h-3 w-32 rounded bg-gray-700" />
        </div>
      </div>
      <div className="flex gap-2">
        <div className="h-6 w-20 rounded bg-gray-700" />
        <div className="h-6 w-20 rounded bg-gray-700" />
        <div className="h-6 w-20 rounded bg-gray-700" />
      </div>
    </div>
  );
}

/**
 * Entity card for Re-ID dashboard showing cross-camera journey
 */
function ReIDEntityCard({
  entity,
  cameraNames,
  isSelected,
  onClick,
}: {
  entity: EntityWithHousehold;
  cameraNames: Map<string, string>;
  isSelected: boolean;
  onClick: () => void;
}) {
  const isLinkedToHousehold = !!entity.household_member_id;
  const normalizedType = entity.entity_type === 'person' ? 'person' : 'vehicle';
  const EntityIcon = normalizedType === 'person' ? User : Car;

  // Get camera display names
  const camerasDisplay = (entity.cameras_seen ?? []).map(
    (cameraId) => cameraNames.get(cameraId) || cameraId.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
  );

  // Format timestamp to relative time
  const formatTimestamp = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays < 7) return `${diffDays}d ago`;

      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return isoString;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <div
      data-testid={`reid-entity-card-${entity.id}`}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-pressed={isSelected}
      aria-label={`View ${normalizedType} entity ${entity.id}`}
      className={`cursor-pointer rounded-lg border bg-[#1F1F1F] p-4 transition-all hover:border-[#76B900]/50 ${
        isSelected ? 'border-[#76B900] ring-2 ring-[#76B900]/30' : 'border-gray-800'
      }`}
    >
      {/* Header: Entity type, household link badge, ID */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Thumbnail or icon */}
          <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full bg-gray-800">
            {entity.thumbnail_url ? (
              <img
                src={entity.thumbnail_url}
                alt={`${normalizedType} thumbnail`}
                className="h-full w-full object-cover"
              />
            ) : (
              <EntityIcon className="h-5 w-5 text-gray-400" />
            )}
          </div>

          <div>
            {/* Entity type badge */}
            <span className="flex items-center gap-1 text-xs font-medium text-[#76B900]">
              <EntityIcon className="h-3 w-3" />
              {normalizedType === 'person' ? 'Person' : 'Vehicle'}
            </span>
            {/* Household link */}
            {isLinkedToHousehold ? (
              <span
                data-testid="household-link-badge"
                className="flex items-center gap-1 text-sm font-medium text-blue-400"
              >
                <Home className="h-3 w-3" />
                {entity.household_member_name}
              </span>
            ) : (
              <span className="text-xs text-gray-500">
                {entity.id.length > 12 ? `${entity.id.substring(0, 12)}...` : entity.id}
              </span>
            )}
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span className="flex items-center gap-1">
            <Camera className="h-3 w-3" />
            {(entity.cameras_seen ?? []).length} cameras
          </span>
        </div>
      </div>

      {/* Camera journey badges */}
      <div className="mb-2 flex flex-wrap items-center gap-1">
        {camerasDisplay.slice(0, 4).map((camera, index) => (
          <span key={camera}>
            <span className="inline-flex items-center rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-300">
              <MapPin className="mr-1 h-3 w-3 text-gray-500" />
              {camera}
            </span>
            {index < Math.min(camerasDisplay.length - 1, 3) && (
              <ArrowRight className="mx-0.5 inline h-3 w-3 text-gray-600" />
            )}
          </span>
        ))}
        {camerasDisplay.length > 4 && (
          <span className="text-xs text-gray-500">+{camerasDisplay.length - 4} more</span>
        )}
      </div>

      {/* Last seen and appearance count */}
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <Clock className="h-3 w-3" />
          Last seen: {formatTimestamp(entity.last_seen)}
        </span>
        <span>{entity.appearance_count} appearances</span>
      </div>
    </div>
  );
}

/**
 * Camera journey timeline component
 */
function CameraJourneyTimeline({
  appearances,
  cameraNames,
}: {
  appearances: Array<{
    detection_id: string;
    camera_id: string;
    camera_name?: string | null;
    timestamp: string;
    thumbnail_url?: string | null;
    similarity_score?: number | null;
    attributes?: Record<string, unknown>;
  }>;
  cameraNames: Map<string, string>;
}) {
  // Sort appearances chronologically (oldest first for journey visualization)
  const sortedAppearances = [...appearances].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  // Calculate time differences between consecutive appearances
  const getTimeDiff = (index: number): string => {
    if (index === 0) return 'Start';
    const prevTime = new Date(sortedAppearances[index - 1].timestamp).getTime();
    const currTime = new Date(sortedAppearances[index].timestamp).getTime();
    const diffMs = currTime - prevTime;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);

    if (diffMins < 1) return '<1m';
    if (diffMins < 60) return `${diffMins}m`;
    return `${diffHours}h ${diffMins % 60}m`;
  };

  const getCameraName = (cameraId: string, cameraName?: string | null): string => {
    return (
      cameraName ||
      cameraNames.get(cameraId) ||
      cameraId.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
    );
  };

  const formatSimilarity = (score: number | null | undefined): string => {
    if (score === null || score === undefined) return 'N/A';
    return `${Math.round(score * 100)}%`;
  };

  return (
    <div data-testid="camera-journey-timeline" className="space-y-0">
      {sortedAppearances.map((appearance, index) => (
        <div key={appearance.detection_id} className="relative">
          {/* Timeline connector */}
          {index < sortedAppearances.length - 1 && (
            <div className="absolute left-5 top-10 h-full w-px border-l-2 border-dashed border-gray-700" />
          )}

          <div className="flex gap-3 pb-4">
            {/* Thumbnail */}
            <div className="relative flex h-10 w-10 flex-shrink-0 items-center justify-center overflow-hidden rounded-full bg-gray-800">
              {appearance.thumbnail_url ? (
                <img
                  src={appearance.thumbnail_url}
                  alt={`Detection at ${getCameraName(appearance.camera_id, appearance.camera_name)}`}
                  className="h-full w-full object-cover"
                />
              ) : (
                <Camera className="h-5 w-5 text-gray-600" />
              )}
              {/* Step number */}
              <div className="absolute -bottom-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-[#76B900] text-[10px] font-bold text-black">
                {index + 1}
              </div>
            </div>

            {/* Content */}
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between">
                <span className="font-medium text-white">
                  {getCameraName(appearance.camera_id, appearance.camera_name)}
                </span>
                {appearance.similarity_score !== null && appearance.similarity_score !== undefined && (
                  <span className="rounded bg-[#76B900]/20 px-1.5 py-0.5 text-xs font-medium text-[#76B900]">
                    {formatSimilarity(appearance.similarity_score)}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 text-xs text-gray-400">
                <span>
                  {new Date(appearance.timestamp).toLocaleString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    hour: 'numeric',
                    minute: '2-digit',
                    hour12: true,
                  })}
                </span>
                {index > 0 && (
                  <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px]">
                    +{getTimeDiff(index)}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Camera journey diagram showing path through property
 */
function CameraJourneyDiagram({
  appearances,
  cameraNames,
}: {
  appearances: Array<{
    detection_id: string;
    camera_id: string;
    camera_name?: string | null;
    timestamp: string;
  }>;
  cameraNames: Map<string, string>;
}) {
  // Sort appearances chronologically
  const sortedAppearances = [...appearances].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  // Calculate total journey time
  const totalTime = (() => {
    if (sortedAppearances.length < 2) return 'N/A';
    const firstTime = new Date(sortedAppearances[0].timestamp).getTime();
    const lastTime = new Date(sortedAppearances[sortedAppearances.length - 1].timestamp).getTime();
    const diffMs = lastTime - firstTime;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);

    if (diffHours > 0) return `${diffHours}h ${diffMins % 60}m`;
    return `${diffMins}m`;
  })();

  const getCameraName = (cameraId: string, cameraName?: string | null): string => {
    return (
      cameraName ||
      cameraNames.get(cameraId) ||
      cameraId.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
    );
  };

  return (
    <div data-testid="camera-journey-diagram" className="rounded-lg border border-gray-800 bg-black/30 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="flex items-center gap-2 text-sm font-semibold text-white">
          <Route className="h-4 w-4 text-[#76B900]" />
          Journey Path
        </h4>
        <span className="text-xs text-gray-400">Duration: {totalTime}</span>
      </div>

      {/* Journey path visualization */}
      <div className="flex flex-wrap items-center gap-2">
        {sortedAppearances.map((appearance, index) => (
          <div key={appearance.detection_id} className="flex items-center">
            <div className="flex flex-col items-center">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#76B900]/20 text-xs font-bold text-[#76B900]">
                {index + 1}
              </div>
              <span className="mt-1 max-w-[80px] truncate text-center text-[10px] text-gray-400">
                {getCameraName(appearance.camera_id, appearance.camera_name)}
              </span>
            </div>
            {index < sortedAppearances.length - 1 && (
              <ArrowRight className="mx-2 h-4 w-4 text-gray-600" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Detail panel for selected entity
 */
function ReIDDetailPanel({
  entity,
  cameraNames,
  onClose,
}: {
  entity: EntityWithHousehold;
  cameraNames: Map<string, string>;
  onClose: () => void;
}) {
  // Fetch detailed entity data with appearances
  const {
    data: entityDetail,
    isLoading,
    error,
  } = useEntityDetailQuery(entity.id, {
    enabled: true,
  });

  const normalizedType = entity.entity_type === 'person' ? 'person' : 'vehicle';
  const EntityIcon = normalizedType === 'person' ? User : Car;
  const isLinkedToHousehold = !!entity.household_member_id;

  if (isLoading) {
    return (
      <div
        data-testid="reid-detail-panel"
        className="flex h-full items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F] p-6"
      >
        <div className="flex flex-col items-center gap-3 text-gray-400">
          <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
          <p>Loading entity details...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        data-testid="reid-detail-panel"
        className="flex h-full items-center justify-center rounded-lg border border-red-900/50 bg-red-900/10 p-6"
      >
        <div className="flex flex-col items-center gap-3 text-center">
          <AlertCircle className="h-8 w-8 text-red-500" />
          <SafeErrorMessage message={error.message} />
        </div>
      </div>
    );
  }

  const appearances = entityDetail?.appearances ?? [];

  return (
    <div data-testid="reid-detail-panel" className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between border-b border-gray-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-full bg-gray-800">
            {entity.thumbnail_url ? (
              <img
                src={entity.thumbnail_url}
                alt={`${normalizedType} thumbnail`}
                className="h-full w-full object-cover"
              />
            ) : (
              <EntityIcon className="h-6 w-6 text-gray-400" />
            )}
          </div>
          <div>
            <span className="flex items-center gap-2 text-lg font-semibold text-white">
              {isLinkedToHousehold ? (
                <Link
                  to="/household"
                  className="flex items-center gap-1 text-blue-400 hover:text-blue-300"
                >
                  {entity.household_member_name}
                  <ExternalLink className="h-3 w-3" />
                </Link>
              ) : (
                <span>Unknown {normalizedType === 'person' ? 'Person' : 'Vehicle'}</span>
              )}
            </span>
            <span className="text-xs text-gray-500">{entity.id}</span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg px-3 py-1.5 text-sm text-gray-400 hover:bg-gray-800 hover:text-white"
        >
          Close
        </button>
      </div>

      {/* Stats row */}
      <div className="mb-4 grid grid-cols-3 gap-4">
        <div className="rounded-lg bg-black/30 p-3 text-center">
          <div className="text-2xl font-bold text-white">{entity.appearance_count}</div>
          <div className="text-xs text-gray-500">Appearances</div>
        </div>
        <div className="rounded-lg bg-black/30 p-3 text-center">
          <div className="text-2xl font-bold text-white">{(entity.cameras_seen ?? []).length}</div>
          <div className="text-xs text-gray-500">Cameras</div>
        </div>
        <div className="rounded-lg bg-black/30 p-3 text-center">
          <div className="text-lg font-bold text-white">
            {new Date(entity.first_seen).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
            })}
          </div>
          <div className="text-xs text-gray-500">First Seen</div>
        </div>
      </div>

      {/* Journey diagram */}
      {appearances.length > 0 && (
        <div className="mb-4">
          <CameraJourneyDiagram appearances={appearances} cameraNames={cameraNames} />
        </div>
      )}

      {/* Timeline */}
      {appearances.length > 0 ? (
        <div>
          <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
            <Clock className="h-4 w-4 text-[#76B900]" />
            Appearance Timeline
          </h4>
          <CameraJourneyTimeline appearances={appearances} cameraNames={cameraNames} />
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-8 text-gray-500">
          <Camera className="mb-2 h-12 w-12" />
          <p>No appearance data available</p>
        </div>
      )}
    </div>
  );
}

/**
 * Main ReIDDashboard component
 */
function ReIDDashboard() {
  // State for filters
  const [entityTypeFilter, setEntityTypeFilter] = useState<EntityTypeFilter>('all');
  const [minCamerasFilter, setMinCamerasFilter] = useState<MinCamerasFilter>(2);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);

  // Fetch cameras for name mapping
  const { cameras } = useCamerasQuery();
  const cameraNames = useMemo(() => {
    const map = new Map<string, string>();
    cameras.forEach((camera) => {
      map.set(camera.id, camera.name);
    });
    return map;
  }, [cameras]);

  // Build filters for the entities query
  const filters: EntityFilters = useMemo(() => {
    const f: EntityFilters = {};
    if (entityTypeFilter !== 'all') {
      f.entity_type = entityTypeFilter;
    }
    return f;
  }, [entityTypeFilter]);

  // Fetch entities
  const {
    entities,
    isLoading: loading,
    isFetching,
    error,
    refetch,
  } = useEntitiesInfiniteQuery({
    filters,
    limit: 100,
    refetchInterval: 60000, // Auto-refresh every minute
  });

  // Filter entities by minimum cameras seen
  const filteredEntities = useMemo(() => {
    return entities.filter((entity) => (entity.cameras_seen ?? []).length >= minCamerasFilter);
  }, [entities, minCamerasFilter]);

  // Sort by number of cameras (most cameras first), then by last seen
  const sortedEntities = useMemo(() => {
    return [...filteredEntities].sort((a, b) => {
      const camerasA = (a.cameras_seen ?? []).length;
      const camerasB = (b.cameras_seen ?? []).length;
      if (camerasB !== camerasA) return camerasB - camerasA;
      return new Date(b.last_seen).getTime() - new Date(a.last_seen).getTime();
    });
  }, [filteredEntities]);

  // Get selected entity
  const selectedEntity = useMemo(() => {
    if (!selectedEntityId) return null;
    return sortedEntities.find((e) => e.id === selectedEntityId) ?? null;
  }, [selectedEntityId, sortedEntities]);

  // Handle entity selection
  const handleEntityClick = useCallback((entityId: string) => {
    setSelectedEntityId((prev) => (prev === entityId ? null : entityId));
  }, []);

  // Handle refresh
  const handleRefresh = useCallback(() => {
    void refetch();
  }, [refetch]);

  // Stats
  const personCount = sortedEntities.filter((e) => e.entity_type === 'person').length;
  const vehicleCount = sortedEntities.filter((e) => e.entity_type === 'vehicle').length;

  const isRefetching = isFetching && !loading;

  return (
    <div className="flex flex-col">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <Route className="h-8 w-8 text-[#76B900]" />
            <h1 className="text-3xl font-bold text-white">Re-Identification Dashboard</h1>
          </div>
          <p className="mt-2 text-gray-400">
            Track entity movements across cameras and view cross-camera matching visualization
          </p>
        </div>

        {/* Refresh button */}
        <button
          onClick={handleRefresh}
          disabled={loading || isRefetching}
          className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:opacity-50"
          aria-label="Refresh data"
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

        {/* Minimum cameras filter */}
        <div className="flex items-center gap-2">
          <label htmlFor="min-cameras-filter" className="text-sm text-gray-400">
            Minimum cameras:
          </label>
          <select
            id="min-cameras-filter"
            value={minCamerasFilter}
            onChange={(e) => setMinCamerasFilter(Number(e.target.value) as MinCamerasFilter)}
            className="rounded-lg border border-gray-700 bg-[#1F1F1F] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            aria-label="Minimum cameras"
          >
            <option value={2}>2+ cameras</option>
            <option value={3}>3+ cameras</option>
            <option value={4}>4+ cameras</option>
            <option value={5}>5+ cameras</option>
          </select>
        </div>
      </div>

      {/* Stats summary */}
      {!loading && !error && sortedEntities.length > 0 && (
        <div className="mb-4 flex items-center gap-4 text-sm text-gray-400">
          <span className="flex items-center gap-1">
            <Users className="h-4 w-4 text-[#76B900]" />
            {sortedEntities.length} cross-camera entities
          </span>
          <span className="flex items-center gap-1">
            <User className="h-4 w-4" />
            {personCount} persons
          </span>
          <span className="flex items-center gap-1">
            <Car className="h-4 w-4" />
            {vehicleCount} vehicles
          </span>
          {isRefetching && (
            <span className="flex items-center gap-1 text-xs text-gray-500">
              <RefreshCw className="h-3 w-3 animate-spin" />
              Updating...
            </span>
          )}
        </div>
      )}

      {/* Content */}
      {loading ? (
        /* Loading state */
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <ReIDEntityCardSkeleton key={i} />
          ))}
        </div>
      ) : error ? (
        /* Error state */
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-red-900/50 bg-red-900/10">
          <div className="flex flex-col items-center gap-3 text-center">
            <AlertCircle className="h-8 w-8 text-red-500" />
            <SafeErrorMessage message={error.message} />
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
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]">
          <div className="max-w-md text-center">
            <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-[#76B900]/10">
              <Route className="h-10 w-10 text-[#76B900]" />
            </div>
            <h2 className="mb-3 text-xl font-semibold text-white">No Cross-Camera Matches</h2>
            <p className="text-gray-400">
              No entities have been tracked across {minCamerasFilter}+ cameras yet. Cross-camera
              re-identification requires entities to be detected on multiple cameras with matching
              embeddings.
            </p>
            {minCamerasFilter > 2 && (
              <button
                onClick={() => setMinCamerasFilter(2)}
                className="mt-4 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
              >
                Show 2+ cameras
              </button>
            )}
          </div>
        </div>
      ) : (
        /* Main content: Entity list + Detail panel */
        <div className="flex flex-col gap-6 lg:flex-row">
          {/* Entity list */}
          <div className={`flex-1 ${selectedEntity ? 'lg:max-w-[55%]' : ''}`}>
            <div className="grid gap-4 md:grid-cols-2">
              {sortedEntities.map((entity) => (
                <ReIDEntityCard
                  key={entity.id}
                  entity={entity as EntityWithHousehold}
                  cameraNames={cameraNames}
                  isSelected={entity.id === selectedEntityId}
                  onClick={() => handleEntityClick(entity.id)}
                />
              ))}
            </div>
          </div>

          {/* Detail panel */}
          {selectedEntity && (
            <div className="lg:w-[45%]">
              <ReIDDetailPanel
                entity={selectedEntity as EntityWithHousehold}
                cameraNames={cameraNames}
                onClose={() => setSelectedEntityId(null)}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * ReIDDashboard with FeatureErrorBoundary wrapper
 */
function ReIDDashboardWithErrorBoundary() {
  return (
    <FeatureErrorBoundary
      feature="Re-ID Dashboard"
      fallback={
        <div className="flex min-h-[400px] flex-col items-center justify-center rounded-lg border border-red-500/30 bg-red-900/20 p-8 text-center">
          <AlertTriangle className="mb-4 h-12 w-12 text-red-400" />
          <h3 className="mb-2 text-lg font-semibold text-red-400">Re-ID Dashboard Unavailable</h3>
          <p className="max-w-md text-sm text-gray-400">
            Unable to load Re-ID dashboard. Please refresh the page or try again later. Other parts
            of the application should still work.
          </p>
        </div>
      }
    >
      <ReIDDashboard />
    </FeatureErrorBoundary>
  );
}

export default ReIDDashboard;
export { ReIDDashboardWithErrorBoundary };
