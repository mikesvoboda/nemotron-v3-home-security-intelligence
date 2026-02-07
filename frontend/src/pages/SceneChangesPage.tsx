/**
 * SceneChangesPage - Scene Change Detection History Page
 *
 * Comprehensive page for viewing and managing scene change detection history.
 * Provides filtering by camera, date range, change type, and acknowledgement status.
 *
 * Features:
 * - Camera selector dropdown
 * - Time range selector (1h, 6h, 24h, 7d, 30d, all)
 * - Change type filter (all, view_blocked, angle_changed, view_tampered)
 * - Acknowledgement status filter
 * - Scene change history list with details
 * - Summary statistics
 * - NVIDIA dark theme styling with green accents
 *
 * @module pages/SceneChangesPage
 * @see NEM-4935 - Scene Change Detection History Page
 */

import { clsx } from 'clsx';
import {
  AlertTriangle,
  Camera,
  CheckCircle,
  Clock,
  Eye,
  Filter,
  Loader2,
  Radio,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react';
import { memo, useCallback, useState } from 'react';

import { SceneChangeHistory } from '../components/cameras';
import Button from '../components/common/Button';
import EmptyState from '../components/common/EmptyState';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { useCamerasQuery } from '../hooks/useCamerasQuery';
import { useSceneChangeEvents } from '../hooks/useSceneChangeEvents';
import {
  useSceneChangesQuery,
  type AcknowledgementFilter,
  type SceneChangeTimeRange,
  type SceneChangeType,
  type SceneChangeWithCamera,
} from '../hooks/useSceneChangesQuery';
import { acknowledgeSceneChange } from '../services/api';

import type { Camera as CameraType } from '../services/api';

// ============================================================================
// Types
// ============================================================================

// Re-export types for easier access
export type { AcknowledgementFilter, SceneChangeTimeRange, SceneChangeType };

// ============================================================================
// Constants
// ============================================================================

const TIME_RANGE_OPTIONS: { value: SceneChangeTimeRange; label: string }[] = [
  { value: '1h', label: '1 Hour' },
  { value: '6h', label: '6 Hours' },
  { value: '24h', label: '24 Hours' },
  { value: '7d', label: '7 Days' },
  { value: '30d', label: '30 Days' },
  { value: 'all', label: 'All Time' },
];

const CHANGE_TYPE_OPTIONS: { value: SceneChangeType; label: string }[] = [
  { value: 'all', label: 'All Types' },
  { value: 'view_blocked', label: 'View Blocked' },
  { value: 'angle_changed', label: 'Angle Changed' },
  { value: 'view_tampered', label: 'Tampered' },
];

const ACKNOWLEDGEMENT_OPTIONS: { value: AcknowledgementFilter; label: string }[] = [
  { value: 'all', label: 'All Status' },
  { value: 'unacknowledged', label: 'Unacknowledged' },
  { value: 'acknowledged', label: 'Acknowledged' },
];

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get change type display info.
 */
function getChangeTypeInfo(changeType: string): {
  label: string;
  colorClass: string;
  bgClass: string;
  icon: typeof AlertTriangle;
} {
  switch (changeType) {
    case 'view_blocked':
      return {
        label: 'View Blocked',
        colorClass: 'text-red-400',
        bgClass: 'bg-red-500/10',
        icon: ShieldAlert,
      };
    case 'view_tampered':
      return {
        label: 'Tampered',
        colorClass: 'text-red-400',
        bgClass: 'bg-red-500/10',
        icon: ShieldAlert,
      };
    case 'angle_changed':
      return {
        label: 'Angle Changed',
        colorClass: 'text-amber-400',
        bgClass: 'bg-amber-500/10',
        icon: AlertTriangle,
      };
    default:
      return {
        label: 'Unknown',
        colorClass: 'text-gray-400',
        bgClass: 'bg-gray-500/10',
        icon: AlertTriangle,
      };
  }
}

/**
 * Format similarity score as percentage.
 */
function formatSimilarity(score: number): string {
  return `${Math.round(score * 100)}%`;
}

/**
 * Format timestamp for display.
 */
function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Format relative time.
 */
function formatRelativeTime(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) {
    return 'just now';
  } else if (diffMins < 60) {
    return `${diffMins}m ago`;
  } else if (diffHours < 24) {
    return `${diffHours}h ago`;
  } else {
    return `${diffDays}d ago`;
  }
}

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Page header with title and refresh button.
 */
interface PageHeaderProps {
  totalCount: number;
  unacknowledgedCount: number;
  isRefetching: boolean;
  onRefresh: () => void;
}

function PageHeader({ totalCount, unacknowledgedCount, isRefetching, onRefresh }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-2xl font-bold text-white">Scene Change History</h1>
        <p className="mt-1 text-sm text-gray-400">
          Monitor and review detected scene changes across your cameras
        </p>
      </div>

      <div className="flex items-center gap-4">
        {/* Summary counts */}
        <div className="flex items-center gap-4 rounded-lg bg-gray-800/50 px-4 py-2">
          <div className="flex items-center gap-2">
            <Eye className="h-4 w-4 text-gray-400" />
            <span className="text-sm text-gray-300">{totalCount} total</span>
          </div>
          {unacknowledgedCount > 0 && (
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400" />
              <span className="text-sm text-amber-400">{unacknowledgedCount} unreviewed</span>
            </div>
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
    </div>
  );
}

/**
 * Camera selector dropdown.
 */
interface CameraSelectorProps {
  cameras: CameraType[];
  selectedCameraId: string | null;
  onCameraChange: (cameraId: string | null) => void;
  isLoading: boolean;
}

function CameraSelector({
  cameras,
  selectedCameraId,
  onCameraChange,
  isLoading,
}: CameraSelectorProps) {
  return (
    <div className="flex items-center gap-2">
      <Camera className="h-4 w-4 text-gray-400" />
      <label htmlFor="camera-select" className="sr-only">
        Select Camera
      </label>
      <select
        id="camera-select"
        value={selectedCameraId ?? ''}
        onChange={(e) => onCameraChange(e.target.value || null)}
        disabled={isLoading || cameras.length === 0}
        className="min-w-[160px] rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900] disabled:opacity-50"
        data-testid="camera-selector"
      >
        <option value="">All Cameras</option>
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
 * Filter bar with all filter controls.
 */
interface FilterBarProps {
  cameras: CameraType[];
  selectedCameraId: string | null;
  onCameraChange: (cameraId: string | null) => void;
  timeRange: SceneChangeTimeRange;
  onTimeRangeChange: (range: SceneChangeTimeRange) => void;
  changeType: SceneChangeType;
  onChangeTypeChange: (type: SceneChangeType) => void;
  acknowledgementFilter: AcknowledgementFilter;
  onAcknowledgementChange: (filter: AcknowledgementFilter) => void;
  isLoading: boolean;
}

function FilterBar({
  cameras,
  selectedCameraId,
  onCameraChange,
  timeRange,
  onTimeRangeChange,
  changeType,
  onChangeTypeChange,
  acknowledgementFilter,
  onAcknowledgementChange,
  isLoading,
}: FilterBarProps) {
  return (
    <div
      className="mb-6 flex flex-wrap items-center gap-4 rounded-lg border border-gray-700 bg-gray-800/50 p-4"
      data-testid="filter-bar"
    >
      {/* Camera Selector */}
      <CameraSelector
        cameras={cameras}
        selectedCameraId={selectedCameraId}
        onCameraChange={onCameraChange}
        isLoading={isLoading}
      />

      {/* Time Range Selector */}
      <div className="flex items-center gap-2">
        <Clock className="h-4 w-4 text-gray-400" />
        <div
          className="flex rounded-lg border border-gray-700 p-0.5"
          role="group"
          aria-label="Time range selection"
          data-testid="time-range-selector"
        >
          {TIME_RANGE_OPTIONS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              onClick={() => onTimeRangeChange(value)}
              aria-pressed={timeRange === value}
              className={clsx(
                'rounded-md px-3 py-1.5 text-sm font-medium transition-all',
                timeRange === value
                  ? 'bg-[#76B900] text-black'
                  : 'text-gray-400 hover:bg-gray-700 hover:text-gray-200'
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Change Type Filter */}
      <div className="flex items-center gap-2">
        <Filter className="h-4 w-4 text-gray-400" />
        <label htmlFor="change-type-select" className="sr-only">
          Change Type
        </label>
        <select
          id="change-type-select"
          value={changeType}
          onChange={(e) => onChangeTypeChange(e.target.value as SceneChangeType)}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
          data-testid="change-type-selector"
        >
          {CHANGE_TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Acknowledgement Filter */}
      <div className="flex items-center gap-2">
        <CheckCircle className="h-4 w-4 text-gray-400" />
        <label htmlFor="acknowledgement-select" className="sr-only">
          Acknowledgement Status
        </label>
        <select
          id="acknowledgement-select"
          value={acknowledgementFilter}
          onChange={(e) => onAcknowledgementChange(e.target.value as AcknowledgementFilter)}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
          data-testid="acknowledgement-selector"
        >
          {ACKNOWLEDGEMENT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

/**
 * Single scene change item in the list.
 */
interface SceneChangeItemProps {
  sceneChange: SceneChangeWithCamera;
  onAcknowledge: (cameraId: string, sceneChangeId: number) => void | Promise<void>;
  isAcknowledging: boolean;
}

const SceneChangeItem = memo(function SceneChangeItem({
  sceneChange,
  onAcknowledge,
  isAcknowledging,
}: SceneChangeItemProps) {
  const typeInfo = getChangeTypeInfo(sceneChange.change_type);
  const TypeIcon = typeInfo.icon;

  return (
    <div
      className="rounded-lg border border-gray-800 bg-gray-900/50 p-4 transition-colors hover:border-gray-700"
      data-testid={`scene-change-item-${sceneChange.id}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Camera name and timestamp */}
          <div className="flex items-center gap-3 mb-2">
            <Camera className="h-4 w-4 text-gray-400 flex-shrink-0" aria-hidden="true" />
            <span className="text-sm font-medium text-white">{sceneChange.camera_name}</span>
            <span className="text-xs text-gray-500" title={formatTimestamp(sceneChange.detected_at)}>
              {formatRelativeTime(sceneChange.detected_at)}
            </span>
          </div>

          {/* Change type and details */}
          <div className="flex items-center gap-3 flex-wrap">
            <span
              className={clsx(
                'flex items-center gap-1 rounded px-2 py-1 text-xs font-medium',
                typeInfo.bgClass,
                typeInfo.colorClass
              )}
            >
              <TypeIcon className="h-3.5 w-3.5" aria-hidden="true" />
              {typeInfo.label}
            </span>
            <span className="text-xs text-gray-500">
              Similarity:{' '}
              <span className="text-gray-400">{formatSimilarity(sceneChange.similarity_score)}</span>
              <span className="ml-1 text-gray-600">(lower = more different)</span>
            </span>
            {sceneChange.acknowledged && (
              <span className="flex items-center gap-1 rounded bg-green-500/10 px-2 py-1 text-xs text-green-400">
                <CheckCircle className="h-3 w-3" />
                Acknowledged
                {sceneChange.acknowledged_at && (
                  <span className="text-green-500">
                    {' '}
                    {formatRelativeTime(sceneChange.acknowledged_at)}
                  </span>
                )}
              </span>
            )}
          </div>

          {/* Detected at full timestamp */}
          <div className="mt-2 text-xs text-gray-500">
            Detected: {formatTimestamp(sceneChange.detected_at)}
          </div>
        </div>

        {/* Action buttons */}
        {!sceneChange.acknowledged && (
          <button
            onClick={() => void onAcknowledge(sceneChange.camera_id, sceneChange.id)}
            disabled={isAcknowledging}
            className="flex items-center gap-2 rounded bg-[#76B900] px-3 py-2 text-xs font-medium text-black transition-colors hover:bg-[#8BD000] disabled:opacity-50"
            data-testid={`acknowledge-${sceneChange.id}`}
          >
            {isAcknowledging ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <CheckCircle className="h-3.5 w-3.5" />
            )}
            Acknowledge
          </button>
        )}
      </div>
    </div>
  );
});

/**
 * Scene changes list.
 */
interface SceneChangesListProps {
  sceneChanges: SceneChangeWithCamera[];
  onAcknowledge: (cameraId: string, sceneChangeId: number) => void | Promise<void>;
  acknowledgingIds: Set<number>;
}

function SceneChangesList({
  sceneChanges,
  onAcknowledge,
  acknowledgingIds,
}: SceneChangesListProps) {
  if (sceneChanges.length === 0) {
    return (
      <div
        className="rounded-lg border border-gray-700 bg-gray-800/50 p-8"
        data-testid="scene-changes-empty"
      >
        <EmptyState
          icon={CheckCircle}
          title="No scene changes found"
          description="No scene changes match the current filters. Try adjusting the time range or filters."
          variant="muted"
        />
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="scene-changes-list" role="list" aria-label="Scene changes">
      {sceneChanges.map((sceneChange) => (
        <SceneChangeItem
          key={`${sceneChange.camera_id}-${sceneChange.id}`}
          sceneChange={sceneChange}
          onAcknowledge={onAcknowledge}
          isAcknowledging={acknowledgingIds.has(sceneChange.id)}
        />
      ))}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * SceneChangesPage provides a comprehensive view of scene change detection history.
 */
function SceneChangesPageComponent() {
  // Filter state
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<SceneChangeTimeRange>('24h');
  const [changeType, setChangeType] = useState<SceneChangeType>('all');
  const [acknowledgementFilter, setAcknowledgementFilter] = useState<AcknowledgementFilter>('all');
  const [acknowledgingIds, setAcknowledgingIds] = useState<Set<number>>(new Set());

  // Data fetching
  const {
    cameras,
    isLoading: isCamerasLoading,
    error: camerasError,
  } = useCamerasQuery();

  const {
    sceneChanges,
    isLoading: isSceneChangesLoading,
    isRefetching,
    error: sceneChangesError,
    refetch,
    totalCount,
    unacknowledgedCount,
  } = useSceneChangesQuery({
    cameraId: selectedCameraId ?? undefined,
    changeType,
    timeRange,
    acknowledgementFilter,
    enabled: !isCamerasLoading,
  });

  // Real-time scene change events via WebSocket (NEM-3575)
  const {
    recentEvents: realtimeEvents,
    isConnected: isWsConnected,
  } = useSceneChangeEvents({
    enabled: !isCamerasLoading,
    showToasts: false, // Toasts are handled globally by the dashboard
  });

  // Handlers
  const handleRefresh = useCallback(() => {
    void refetch();
  }, [refetch]);

  const handleAcknowledge = useCallback(
    async (cameraId: string, sceneChangeId: number) => {
      setAcknowledgingIds((prev) => new Set(prev).add(sceneChangeId));
      try {
        await acknowledgeSceneChange(cameraId, sceneChangeId);
        await refetch();
      } catch (err) {
        console.error('Failed to acknowledge scene change:', err);
      } finally {
        setAcknowledgingIds((prev) => {
          const next = new Set(prev);
          next.delete(sceneChangeId);
          return next;
        });
      }
    },
    [refetch]
  );

  const isLoading = isCamerasLoading || isSceneChangesLoading;
  const error = camerasError ?? sceneChangesError;

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
      <div className="min-h-screen bg-[#121212] p-6" data-testid="scene-changes-page">
        <div className="mx-auto max-w-[1400px]">
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-6">
            <div className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="h-5 w-5" />
              <span className="font-medium">Failed to load scene changes</span>
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
      <div className="min-h-screen bg-[#121212] p-6" data-testid="scene-changes-page">
        <div className="mx-auto max-w-[1400px]">
          <PageHeader
            totalCount={0}
            unacknowledgedCount={0}
            isRefetching={isRefetching}
            onRefresh={handleRefresh}
          />
          <EmptyState
            icon={Camera}
            title="No cameras configured"
            description="Add cameras to your system to start monitoring scene changes."
            variant="muted"
          />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#121212] p-6" data-testid="scene-changes-page">
      <div className="mx-auto max-w-[1400px]">
        {/* Header */}
        <PageHeader
          totalCount={totalCount}
          unacknowledgedCount={unacknowledgedCount}
          isRefetching={isRefetching}
          onRefresh={handleRefresh}
        />

        {/* Filters */}
        <FilterBar
          cameras={cameras}
          selectedCameraId={selectedCameraId}
          onCameraChange={setSelectedCameraId}
          timeRange={timeRange}
          onTimeRangeChange={setTimeRange}
          changeType={changeType}
          onChangeTypeChange={setChangeType}
          acknowledgementFilter={acknowledgementFilter}
          onAcknowledgementChange={setAcknowledgementFilter}
          isLoading={isLoading}
        />

        {/* Real-time Scene Change Events (NEM-3575) */}
        {realtimeEvents.length > 0 && (
          <div className="mb-6" data-testid="realtime-scene-changes">
            <div className="mb-3 flex items-center gap-2">
              <Radio className={clsx('h-4 w-4', isWsConnected ? 'text-green-400' : 'text-gray-500')} />
              <h2 className="text-sm font-semibold text-white">Real-time Events</h2>
              <span className="rounded-full bg-gray-800 px-2 py-0.5 text-xs text-gray-400">
                {realtimeEvents.length} recent
              </span>
              {!isWsConnected && (
                <span className="text-xs text-yellow-500">Reconnecting...</span>
              )}
            </div>
            <SceneChangeHistory
              events={realtimeEvents}
              maxItems={5}
              showEmptyState={false}
            />
          </div>
        )}

        {/* Historical Scene Changes List */}
        {isSceneChangesLoading && !isRefetching ? (
          <div
            className="flex min-h-[300px] items-center justify-center rounded-lg border border-gray-700 bg-gray-800/50"
            data-testid="scene-changes-loading"
          >
            <LoadingSpinner />
          </div>
        ) : (
          <SceneChangesList
            sceneChanges={sceneChanges}
            onAcknowledge={handleAcknowledge}
            acknowledgingIds={acknowledgingIds}
          />
        )}

        {/* Info footer */}
        <div className="mt-6 rounded-lg border border-gray-800 bg-gray-900/30 p-4 text-xs text-gray-500">
          <p>
            Scene changes are detected when the camera view significantly differs from the baseline.
            Low similarity scores indicate potential tampering, camera movement, or view obstructions.
            Review and acknowledge changes to keep your monitoring logs organized.
          </p>
        </div>
      </div>
    </div>
  );
}

/**
 * Memoized SceneChangesPage for performance.
 */
export const SceneChangesPage = memo(SceneChangesPageComponent);

export default SceneChangesPage;
