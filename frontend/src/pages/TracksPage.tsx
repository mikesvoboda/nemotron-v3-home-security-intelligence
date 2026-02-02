/**
 * TracksPage - Object Trajectory Visualization Page
 *
 * Displays object tracks and trajectories for camera feeds, showing
 * movement patterns and statistics. Allows users to:
 * - Select camera to view tracks
 * - Filter tracks by object type
 * - View track statistics (active, total, duration)
 * - Visualize individual track trajectories
 * - See active tracks indicator with real-time updates
 *
 * Features:
 * - Camera selector dropdown
 * - Object class filter
 * - Statistics panel (active, total today, avg duration, by type)
 * - Track list with cards showing metrics
 * - Trajectory visualization SVG panel
 * - Active tracks badge with pulse animation
 * - Pagination for large track lists
 * - NVIDIA dark theme styling with green accents
 *
 * @module pages/TracksPage
 * @see NEM-5024 Phase 5 - Tracks Visualization UI
 * @see backend/api/routes/tracks.py - Backend API endpoints
 */

import { clsx } from 'clsx';
import {
  AlertTriangle,
  ArrowRight,
  Camera,
  ChevronLeft,
  ChevronRight,
  Clock,
  Compass,
  Filter,
  MapPin,
  RefreshCw,
  Route,
  Timer,
  X,
  Zap,
} from 'lucide-react';
import { memo, useCallback, useEffect, useState } from 'react';

import Button from '../components/common/Button';
import EmptyState from '../components/common/EmptyState';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { useCamerasQuery } from '../hooks/useCamerasQuery';
import {
  useCameraTracks,
  useCameraTracksStats,
  useActiveTracks,
  useTrackHistory,
} from '../hooks/useTracks';

import type { Track, TrackHistory } from '../hooks/useTracks';
import type { Camera as CameraType } from '../services/api';

// ============================================================================
// Types
// ============================================================================

/**
 * Object class filter options.
 */
type ObjectClassFilter = 'all' | 'person' | 'vehicle' | 'animal';

// ============================================================================
// Constants
// ============================================================================

const OBJECT_CLASS_OPTIONS: { value: ObjectClassFilter; label: string }[] = [
  { value: 'all', label: 'All Types' },
  { value: 'person', label: 'Person' },
  { value: 'vehicle', label: 'Vehicle' },
  { value: 'animal', label: 'Animal' },
];

const PAGE_SIZE = 20;

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format duration in seconds to human-readable string.
 */
function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  if (remainingSeconds === 0) {
    return `${minutes}m`;
  }
  return `${minutes}m ${remainingSeconds}s`;
}

/**
 * Format direction in degrees to cardinal direction.
 */
function formatDirection(degrees: number | null): string {
  if (degrees === null) return 'N/A';
  const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  const index = Math.round(degrees / 45) % 8;
  return directions[index];
}

/**
 * Get color for object class.
 */
function getObjectClassColor(objectClass: string): string {
  const colors: Record<string, string> = {
    person: '#76B900', // NVIDIA Green
    vehicle: '#3B82F6', // Blue
    animal: '#F59E0B', // Amber
    default: '#6B7280', // Gray
  };
  return colors[objectClass.toLowerCase()] || colors.default;
}

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Page header with title, active tracks badge, and refresh button.
 */
interface PageHeaderProps {
  isRefetching: boolean;
  onRefresh: () => void;
  activeCount: number;
  showActiveBadge: boolean;
}

function PageHeader({ isRefetching, onRefresh, activeCount, showActiveBadge }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Object Tracks</h1>
          <p className="mt-1 text-sm text-gray-400">
            Visualize object trajectories and movement patterns
          </p>
        </div>
        {showActiveBadge && activeCount > 0 && (
          <span
            className="animate-pulse rounded-full bg-[#76B900] px-2.5 py-1 text-sm font-medium text-black"
            data-testid="active-tracks-badge"
          >
            {activeCount}
          </span>
        )}
      </div>

      <Button
        variant="ghost"
        size="sm"
        leftIcon={<RefreshCw className={clsx('h-4 w-4', isRefetching && 'animate-spin')} />}
        onClick={onRefresh}
        disabled={isRefetching}
        data-testid="refresh-button"
      >
        Refresh
      </Button>
    </div>
  );
}

/**
 * Camera selector dropdown.
 */
interface CameraSelectorProps {
  cameras: CameraType[];
  selectedCameraId: string | null;
  onCameraChange: (cameraId: string) => void;
  isLoading: boolean;
}

function CameraSelector({
  cameras,
  selectedCameraId,
  onCameraChange,
  isLoading,
}: CameraSelectorProps) {
  return (
    <div className="flex items-center gap-3">
      <Camera className="h-5 w-5 text-gray-400" />
      <label htmlFor="camera-select" className="sr-only">
        Select Camera
      </label>
      <select
        id="camera-select"
        value={selectedCameraId ?? ''}
        onChange={(e) => onCameraChange(e.target.value)}
        disabled={isLoading || cameras.length === 0}
        className="min-w-[200px] rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900] disabled:opacity-50"
        data-testid="camera-selector"
      >
        <option value="">Select a camera</option>
        {cameras.map((camera) => (
          <option key={camera.id} value={camera.id}>
            {camera.name} {camera.status === 'offline' && '(Offline)'}
          </option>
        ))}
      </select>
    </div>
  );
}

/**
 * Object class filter dropdown.
 */
interface ObjectClassFilterProps {
  filter: ObjectClassFilter;
  onFilterChange: (filter: ObjectClassFilter) => void;
}

function ObjectClassFilterSelect({ filter, onFilterChange }: ObjectClassFilterProps) {
  return (
    <div className="flex items-center gap-2">
      <Filter className="h-4 w-4 text-gray-400" />
      <label htmlFor="object-class-filter" className="sr-only">
        Filter by Object Type
      </label>
      <select
        id="object-class-filter"
        value={filter}
        onChange={(e) => onFilterChange(e.target.value as ObjectClassFilter)}
        className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
        data-testid="object-class-filter"
      >
        {OBJECT_CLASS_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

/**
 * Statistics panel showing track metrics.
 */
interface StatsPanelProps {
  stats: {
    active_count: number;
    total_today: number;
    avg_duration_seconds: number;
    by_object_type: Record<string, number>;
  } | undefined;
  isLoading: boolean;
}

function StatsPanel({ stats, isLoading }: StatsPanelProps) {
  if (isLoading) {
    return (
      <div
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
        data-testid="stats-panel"
      >
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-lg bg-gray-800"
          />
        ))}
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  return (
    <div
      className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
      data-testid="stats-panel"
    >
      {/* Active Tracks */}
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
        <div className="flex items-center gap-2 text-gray-400">
          <Zap className="h-4 w-4" />
          <span className="text-sm">Active Now</span>
        </div>
        <p
          className="mt-2 text-2xl font-bold text-[#76B900]"
          data-testid="stat-active-count"
        >
          {stats.active_count}
        </p>
      </div>

      {/* Total Today */}
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
        <div className="flex items-center gap-2 text-gray-400">
          <Route className="h-4 w-4" />
          <span className="text-sm">Total Today</span>
        </div>
        <p
          className="mt-2 text-2xl font-bold text-white"
          data-testid="stat-total-today"
        >
          {stats.total_today}
        </p>
      </div>

      {/* Average Duration */}
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
        <div className="flex items-center gap-2 text-gray-400">
          <Timer className="h-4 w-4" />
          <span className="text-sm">Avg Duration</span>
        </div>
        <p
          className="mt-2 text-2xl font-bold text-white"
          data-testid="stat-avg-duration"
        >
          {formatDuration(stats.avg_duration_seconds)}
        </p>
      </div>

      {/* By Object Type */}
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
        <div className="flex items-center gap-2 text-gray-400">
          <Filter className="h-4 w-4" />
          <span className="text-sm">By Type</span>
        </div>
        <div
          className="mt-2 flex flex-wrap gap-2"
          data-testid="stat-object-types"
        >
          {Object.entries(stats.by_object_type).map(([type, count]) => (
            <span
              key={type}
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs"
              style={{ backgroundColor: `${getObjectClassColor(type)}20`, color: getObjectClassColor(type) }}
            >
              {type}: {count}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * Individual track card.
 */
interface TrackCardProps {
  track: Track;
  isSelected: boolean;
  onSelect: () => void;
}

function TrackCard({ track, isSelected, onSelect }: TrackCardProps) {
  const duration = track.metrics?.duration_seconds ?? 0;
  const color = getObjectClassColor(track.object_class);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect();
        }
      }}
      className={clsx(
        'cursor-pointer rounded-lg border p-4 transition-all',
        isSelected
          ? 'border-[#76B900] bg-[#76B900]/10 ring-1 ring-[#76B900]'
          : 'border-gray-700 bg-gray-800/50 hover:border-gray-600 hover:bg-gray-800'
      )}
      data-testid={`track-card-${track.id}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <div
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: color }}
            aria-hidden="true"
          />
          <span className="text-sm font-medium capitalize text-white">
            {track.object_class}
          </span>
        </div>
        <span className="text-xs text-gray-500">
          #{track.track_id}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-400">
        <div className="flex items-center gap-1">
          <Timer className="h-3 w-3" />
          <span>{formatDuration(duration)}</span>
        </div>
        {track.metrics && (
          <>
            <div className="flex items-center gap-1">
              <ArrowRight className="h-3 w-3" />
              <span>{track.metrics.total_distance.toFixed(0)} px</span>
            </div>
            <div className="flex items-center gap-1">
              <Compass className="h-3 w-3" />
              <span>{formatDirection(track.metrics.direction)}</span>
            </div>
          </>
        )}
        <div className="flex items-center gap-1">
          <Clock className="h-3 w-3" />
          <span>{new Date(track.first_seen).toLocaleTimeString()}</span>
        </div>
      </div>
    </div>
  );
}

/**
 * Track list loading skeleton.
 */
function TrackListSkeleton() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
        <div
          key={i}
          className="h-28 animate-pulse rounded-lg bg-gray-800"
          data-testid="track-skeleton"
        />
      ))}
    </div>
  );
}

/**
 * Pagination controls.
 */
interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

function Pagination({ currentPage, totalPages, onPageChange }: PaginationProps) {
  return (
    <div
      className="mt-4 flex items-center justify-center gap-4"
      data-testid="pagination"
    >
      <Button
        variant="ghost"
        size="sm"
        leftIcon={<ChevronLeft className="h-4 w-4" />}
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage <= 1}
        data-testid="prev-page-button"
      >
        Previous
      </Button>

      <span className="text-sm text-gray-400">
        Page <span data-testid="current-page">{currentPage}</span> of {totalPages}
      </span>

      <Button
        variant="ghost"
        size="sm"
        rightIcon={<ChevronRight className="h-4 w-4" />}
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage >= totalPages}
        data-testid="next-page-button"
      >
        Next
      </Button>
    </div>
  );
}

/**
 * Trajectory visualization panel.
 */
interface TrajectoryPanelProps {
  history: TrackHistory | undefined;
  isLoading: boolean;
  onClose: () => void;
}

function TrajectoryPanel({ history, isLoading, onClose }: TrajectoryPanelProps) {
  // Handle escape key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (isLoading) {
    return (
      <div
        className="rounded-lg border border-gray-700 bg-gray-800/50 p-4"
        data-testid="trajectory-loading"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">Trajectory</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-white"
            data-testid="close-trajectory-button"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="mt-4 flex h-64 items-center justify-center">
          <LoadingSpinner />
        </div>
      </div>
    );
  }

  if (!history) {
    return null;
  }

  // Calculate SVG bounds
  const padding = 20;
  const svgWidth = 400;
  const svgHeight = 300;

  // Scale trajectory points to SVG coordinates
  const scaledPoints = history.trajectory.map((point) => ({
    x: padding + point.x * (svgWidth - 2 * padding),
    y: padding + point.y * (svgHeight - 2 * padding),
    timestamp: point.timestamp,
  }));

  // Create path from points
  const pathData = scaledPoints
    .map((point, i) => (i === 0 ? `M ${point.x} ${point.y}` : `L ${point.x} ${point.y}`))
    .join(' ');

  return (
    <div
      className="rounded-lg border border-gray-700 bg-gray-800/50 p-4"
      data-testid="trajectory-panel"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">Trajectory</h3>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-white"
          data-testid="close-trajectory-button"
          aria-label="Close trajectory panel"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* SVG Visualization */}
      <div className="mt-4 rounded-lg bg-gray-900 p-2">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="h-auto w-full"
          data-testid="trajectory-svg"
        >
          {/* Grid lines */}
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#374151" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />

          {/* Trajectory path */}
          <path
            d={pathData}
            fill="none"
            stroke="#76B900"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Start point */}
          {scaledPoints.length > 0 && (
            <circle
              cx={scaledPoints[0].x}
              cy={scaledPoints[0].y}
              r="6"
              fill="#3B82F6"
              stroke="#1E40AF"
              strokeWidth="2"
            >
              <title>Start</title>
            </circle>
          )}

          {/* End point */}
          {scaledPoints.length > 1 && (
            <circle
              cx={scaledPoints[scaledPoints.length - 1].x}
              cy={scaledPoints[scaledPoints.length - 1].y}
              r="6"
              fill="#EF4444"
              stroke="#B91C1C"
              strokeWidth="2"
            >
              <title>End</title>
            </circle>
          )}

          {/* Intermediate points */}
          {scaledPoints.slice(1, -1).map((point, i) => (
            <circle
              key={i}
              cx={point.x}
              cy={point.y}
              r="3"
              fill="#76B900"
              opacity="0.6"
            />
          ))}
        </svg>
      </div>

      {/* Metrics */}
      <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-gray-400">Distance</span>
          <p className="font-medium text-white">
            {history.metrics.total_distance.toFixed(1)} px
          </p>
        </div>
        <div>
          <span className="text-gray-400">Speed</span>
          <p className="font-medium text-white">
            {history.metrics.avg_speed.toFixed(2)} px/s
          </p>
        </div>
        <div>
          <span className="text-gray-400">Direction</span>
          <p className="font-medium text-white">
            {formatDirection(history.metrics.direction)}
            {history.metrics.direction !== null && ` (${history.metrics.direction.toFixed(0)})`}
          </p>
        </div>
        <div>
          <span className="text-gray-400">Duration</span>
          <p className="font-medium text-white">
            {formatDuration(history.metrics.duration_seconds)}
          </p>
        </div>
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center gap-4 text-xs text-gray-400">
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded-full bg-[#3B82F6]" />
          <span>Start</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded-full bg-[#EF4444]" />
          <span>End</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded-full bg-[#76B900]" />
          <span>Path</span>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * TracksPage provides visualization of object tracks and trajectories.
 */
function TracksPageComponent() {
  // State
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [objectClassFilter, setObjectClassFilter] = useState<ObjectClassFilter>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedTrackId, setSelectedTrackId] = useState<number | null>(null);

  // Data fetching
  const {
    cameras,
    isLoading: isCamerasLoading,
    error: camerasError,
    refetch: refetchCameras,
    isRefetching: isCamerasRefetching,
  } = useCamerasQuery();

  // Track queries (only run when camera is selected)
  const {
    tracks,
    total,
    page,
    pageSize,
    isLoading: isTracksLoading,
    isRefetching: isTracksRefetching,
    error: tracksError,
    refetch: refetchTracks,
  } = useCameraTracks(selectedCameraId ?? '', {
    objectClass: objectClassFilter === 'all' ? undefined : objectClassFilter,
    page: currentPage,
    pageSize: PAGE_SIZE,
  });

  const { data: stats, isLoading: isStatsLoading } = useCameraTracksStats(
    selectedCameraId ?? ''
  );

  const { count: activeCount } = useActiveTracks(
    selectedCameraId ?? ''
  );

  const { data: trackHistory, isLoading: isHistoryLoading } = useTrackHistory(
    selectedTrackId ?? 0
  );

  // Computed values
  const totalPages = Math.ceil(total / pageSize);

  // Handlers
  const handleRefresh = useCallback(() => {
    void refetchCameras();
    if (selectedCameraId) {
      void refetchTracks();
    }
  }, [refetchCameras, refetchTracks, selectedCameraId]);

  const handleCameraChange = useCallback((cameraId: string) => {
    setSelectedCameraId(cameraId || null);
    setCurrentPage(1);
    setSelectedTrackId(null);
  }, []);

  const handleFilterChange = useCallback((filter: ObjectClassFilter) => {
    setObjectClassFilter(filter);
    setCurrentPage(1);
  }, []);

  const handleTrackSelect = useCallback((trackId: number) => {
    setSelectedTrackId((prev) => (prev === trackId ? null : trackId));
  }, []);

  const handleCloseTrajectory = useCallback(() => {
    setSelectedTrackId(null);
  }, []);

  const handlePageChange = useCallback((newPage: number) => {
    setCurrentPage(newPage);
    setSelectedTrackId(null);
  }, []);

  const isRefetching = isCamerasRefetching || isTracksRefetching;
  const error = camerasError ?? tracksError;

  // Loading state
  if (isCamerasLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center" data-testid="page-loading">
        <LoadingSpinner />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-[#121212] p-6" data-testid="tracks-page">
        <div className="mx-auto max-w-[1400px]">
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-6">
            <div className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="h-5 w-5" />
              <span className="font-medium">Failed to load track data</span>
            </div>
            <p className="mt-2 text-sm text-red-300">{error.message}</p>
            <Button
              variant="outline-primary"
              size="sm"
              onClick={handleRefresh}
              className="mt-4"
              leftIcon={<RefreshCw className="h-4 w-4" />}
            >
              Try Again
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Empty cameras state
  if (cameras.length === 0) {
    return (
      <div className="min-h-screen bg-[#121212] p-6" data-testid="tracks-page">
        <div className="mx-auto max-w-[1400px]">
          <PageHeader
            isRefetching={isRefetching}
            onRefresh={handleRefresh}
            activeCount={0}
            showActiveBadge={false}
          />
          <EmptyState
            icon={Camera}
            title="No cameras configured"
            description="Add cameras to your system to start tracking objects."
            variant="muted"
          />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#121212] p-6" data-testid="tracks-page">
      <div className="mx-auto max-w-[1400px]">
        {/* Header */}
        <PageHeader
          isRefetching={isRefetching}
          onRefresh={handleRefresh}
          activeCount={activeCount}
          showActiveBadge={!!selectedCameraId}
        />

        {/* Controls Bar */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-lg border border-gray-700 bg-gray-800/50 p-4">
          <CameraSelector
            cameras={cameras}
            selectedCameraId={selectedCameraId}
            onCameraChange={handleCameraChange}
            isLoading={isCamerasLoading}
          />

          {selectedCameraId && (
            <ObjectClassFilterSelect
              filter={objectClassFilter}
              onFilterChange={handleFilterChange}
            />
          )}
        </div>

        {/* Main Content */}
        {!selectedCameraId ? (
          <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-8">
            <EmptyState
              icon={Route}
              title="Select a camera"
              description="Choose a camera from the dropdown above to view object tracks."
              variant="muted"
            />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Statistics Panel */}
            <StatsPanel stats={stats} isLoading={isStatsLoading} />

            {/* Main Content Grid */}
            <div className="grid gap-6 lg:grid-cols-3">
              {/* Track List */}
              <div className="lg:col-span-2">
                <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
                  <h2 className="mb-4 text-lg font-semibold text-white">
                    Tracks
                    {total > 0 && (
                      <span className="ml-2 text-sm font-normal text-gray-400">
                        ({total} total)
                      </span>
                    )}
                  </h2>

                  {isTracksLoading ? (
                    <TrackListSkeleton />
                  ) : tracks.length === 0 ? (
                    <EmptyState
                      icon={MapPin}
                      title="No tracks recorded"
                      description="Object tracks will appear here as they are detected."
                      variant="muted"
                    />
                  ) : (
                    <>
                      <div
                        className="grid gap-3 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3"
                        data-testid="track-list"
                      >
                        {tracks.map((track) => (
                          <TrackCard
                            key={track.id}
                            track={track}
                            isSelected={selectedTrackId === track.id}
                            onSelect={() => handleTrackSelect(track.id)}
                          />
                        ))}
                      </div>

                      {totalPages > 1 && (
                        <Pagination
                          currentPage={page}
                          totalPages={totalPages}
                          onPageChange={handlePageChange}
                        />
                      )}
                    </>
                  )}
                </div>
              </div>

              {/* Trajectory Panel */}
              <div>
                {selectedTrackId ? (
                  <TrajectoryPanel
                    history={trackHistory}
                    isLoading={isHistoryLoading}
                    onClose={handleCloseTrajectory}
                  />
                ) : (
                  <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
                    <h3 className="text-lg font-semibold text-white">Trajectory</h3>
                    <p className="mt-4 text-center text-sm text-gray-400">
                      Select a track to view its trajectory visualization.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Memoized TracksPage for performance.
 */
export const TracksPage = memo(TracksPageComponent);

export default TracksPage;
