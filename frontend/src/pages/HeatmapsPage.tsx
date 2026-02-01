/**
 * HeatmapsPage - Movement Heatmap Visualization Page
 *
 * Displays movement heatmaps for camera feeds showing activity intensity
 * across different time periods. Allows users to:
 * - Select camera to view heatmap
 * - Choose time range (hourly, daily, weekly)
 * - View merged heatmaps over custom date ranges
 * - See heatmap statistics and detection counts
 *
 * Features:
 * - Camera selector dropdown
 * - Time range picker with resolution options
 * - Heatmap image overlay on camera snapshot
 * - Activity intensity color scale legend
 * - NVIDIA dark theme styling with green accents
 *
 * @module pages/HeatmapsPage
 * @see NEM-4927 - Heatmaps Visualization Page
 * @see backend/api/routes/heatmaps.py - Backend API endpoints
 */

import { clsx } from 'clsx';
import {
  AlertTriangle,
  Camera,
  Clock,
  Download,
  Flame,
  Grid3X3,
  RefreshCw,
} from 'lucide-react';
import { memo, useCallback, useMemo, useState } from 'react';

import Button from '../components/common/Button';
import EmptyState from '../components/common/EmptyState';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { useCamerasQuery } from '../hooks/useCamerasQuery';
import { useHeatmapQuery, useHeatmapHistoryQuery } from '../hooks/useHeatmapQuery';

import type { Camera as CameraType } from '../services/api';

// ============================================================================
// Types
// ============================================================================

/**
 * Resolution options for heatmap data aggregation.
 */
type HeatmapResolution = 'hourly' | 'daily' | 'weekly';

/**
 * Time range options for filtering heatmap data.
 */
type HeatmapTimeRange = '1h' | '6h' | '24h' | '7d' | '30d';

/**
 * Colormap options for heatmap visualization.
 */
type HeatmapColormap = 'jet' | 'hot' | 'viridis' | 'plasma';

// ============================================================================
// Constants
// ============================================================================

const RESOLUTION_OPTIONS: { value: HeatmapResolution; label: string }[] = [
  { value: 'hourly', label: 'Hourly' },
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
];

const TIME_RANGE_OPTIONS: { value: HeatmapTimeRange; label: string }[] = [
  { value: '1h', label: '1 Hour' },
  { value: '6h', label: '6 Hours' },
  { value: '24h', label: '24 Hours' },
  { value: '7d', label: '7 Days' },
  { value: '30d', label: '30 Days' },
];

const COLORMAP_OPTIONS: { value: HeatmapColormap; label: string; gradient: string }[] = [
  {
    value: 'jet',
    label: 'Jet',
    gradient: 'linear-gradient(to right, #00007F, #0000FF, #00FFFF, #00FF00, #FFFF00, #FF0000, #7F0000)',
  },
  {
    value: 'hot',
    label: 'Hot',
    gradient: 'linear-gradient(to right, #000000, #E50000, #FF8000, #FFFF00, #FFFFFF)',
  },
  {
    value: 'viridis',
    label: 'Viridis',
    gradient: 'linear-gradient(to right, #440154, #3E4A89, #26838E, #6CCD5A, #FDE725)',
  },
  {
    value: 'plasma',
    label: 'Plasma',
    gradient: 'linear-gradient(to right, #0D0887, #7E03A8, #CC4778, #F89540, #F0F921)',
  },
];

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Page header with title and refresh button.
 */
interface PageHeaderProps {
  isRefetching: boolean;
  onRefresh: () => void;
}

function PageHeader({ isRefetching, onRefresh }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-2xl font-bold text-white">Movement Heatmaps</h1>
        <p className="mt-1 text-sm text-gray-400">
          Visualize activity intensity patterns across your cameras
        </p>
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
 * Time range and resolution controls.
 */
interface TimeControlsProps {
  resolution: HeatmapResolution;
  onResolutionChange: (resolution: HeatmapResolution) => void;
  timeRange: HeatmapTimeRange;
  onTimeRangeChange: (range: HeatmapTimeRange) => void;
}

function TimeControls({
  resolution,
  onResolutionChange,
  timeRange,
  onTimeRangeChange,
}: TimeControlsProps) {
  return (
    <div className="flex flex-wrap items-center gap-4">
      {/* Resolution Selector */}
      <div className="flex items-center gap-2">
        <Grid3X3 className="h-4 w-4 text-gray-400" />
        <label htmlFor="resolution-select" className="sr-only">
          Resolution
        </label>
        <select
          id="resolution-select"
          value={resolution}
          onChange={(e) => onResolutionChange(e.target.value as HeatmapResolution)}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
          data-testid="resolution-selector"
        >
          {RESOLUTION_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

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
    </div>
  );
}

/**
 * Colormap selector and legend.
 */
interface ColormapSelectorProps {
  colormap: HeatmapColormap;
  onColormapChange: (colormap: HeatmapColormap) => void;
}

function ColormapSelector({ colormap, onColormapChange }: ColormapSelectorProps) {
  const selectedColormap = COLORMAP_OPTIONS.find((opt) => opt.value === colormap);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <Flame className="h-4 w-4 text-gray-400" />
        <label htmlFor="colormap-select" className="text-sm text-gray-400">
          Color Scale
        </label>
        <select
          id="colormap-select"
          value={colormap}
          onChange={(e) => onColormapChange(e.target.value as HeatmapColormap)}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
          data-testid="colormap-selector"
        >
          {COLORMAP_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Color scale legend */}
      {selectedColormap && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Low</span>
          <div
            className="h-3 w-32 rounded"
            style={{ background: selectedColormap.gradient }}
            aria-hidden="true"
          />
          <span className="text-xs text-gray-500">High</span>
        </div>
      )}
    </div>
  );
}

/**
 * Heatmap display panel with image and stats.
 */
interface HeatmapDisplayProps {
  imageBase64: string | null;
  totalDetections: number;
  isLoading: boolean;
  cameraName: string;
  resolution: HeatmapResolution;
  onDownload: () => void;
}

function HeatmapDisplay({
  imageBase64,
  totalDetections,
  isLoading,
  cameraName,
  resolution,
  onDownload,
}: HeatmapDisplayProps) {
  if (isLoading) {
    return (
      <div
        className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-700 bg-gray-800/50"
        data-testid="heatmap-loading"
      >
        <LoadingSpinner />
      </div>
    );
  }

  if (!imageBase64) {
    return (
      <div
        className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-700 bg-gray-800/50"
        data-testid="heatmap-empty"
      >
        <div className="text-center">
          <Flame className="mx-auto mb-4 h-12 w-12 text-gray-600" />
          <p className="text-gray-400">No heatmap data available for this period</p>
          <p className="mt-2 text-sm text-gray-500">
            Activity data will appear as detections are recorded
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Heatmap Image */}
      <div
        className="relative overflow-hidden rounded-lg border border-gray-700 bg-gray-900"
        data-testid="heatmap-container"
      >
        <img
          src={`data:image/png;base64,${imageBase64}`}
          alt={`Movement heatmap for ${cameraName}`}
          className="h-auto w-full"
          data-testid="heatmap-image"
        />
      </div>

      {/* Stats and download */}
      <div className="flex items-center justify-between rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-3">
        <div className="flex items-center gap-6">
          <div>
            <span className="text-sm text-gray-400">Total Detections</span>
            <p className="text-xl font-semibold text-white" data-testid="detection-count">
              {totalDetections.toLocaleString()}
            </p>
          </div>
          <div>
            <span className="text-sm text-gray-400">Resolution</span>
            <p className="text-xl font-semibold text-white capitalize">{resolution}</p>
          </div>
        </div>

        <Button
          variant="outline-primary"
          size="sm"
          leftIcon={<Download className="h-4 w-4" />}
          onClick={onDownload}
          data-testid="download-button"
        >
          Download
        </Button>
      </div>
    </div>
  );
}

/**
 * Heatmap history list panel.
 */
interface HeatmapHistoryProps {
  history: Array<{
    id: number;
    time_bucket: string;
    resolution: string;
    total_detections: number;
  }>;
  isLoading: boolean;
  onSelectEntry: (id: number) => void;
}

function HeatmapHistory({ history, isLoading, onSelectEntry }: HeatmapHistoryProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="h-16 animate-pulse rounded-lg bg-gray-800"
            data-testid="history-skeleton"
          />
        ))}
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4 text-center">
        <p className="text-sm text-gray-400">No historical data available</p>
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-[400px] overflow-y-auto" data-testid="heatmap-history">
      {history.map((entry) => (
        <button
          key={entry.id}
          type="button"
          onClick={() => onSelectEntry(entry.id)}
          className="w-full rounded-lg border border-gray-700 bg-gray-800/50 p-3 text-left transition-all hover:border-[#76B900] hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-[#76B900]"
          data-testid={`history-entry-${entry.id}`}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-white">
                {new Date(entry.time_bucket).toLocaleString()}
              </p>
              <p className="text-xs text-gray-400 capitalize">{entry.resolution}</p>
            </div>
            <div className="text-right">
              <p className="text-sm font-medium text-[#76B900]">
                {entry.total_detections.toLocaleString()}
              </p>
              <p className="text-xs text-gray-400">detections</p>
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * HeatmapsPage provides visualization of movement heatmaps for cameras.
 */
function HeatmapsPageComponent() {
  // State
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [resolution, setResolution] = useState<HeatmapResolution>('hourly');
  const [timeRange, setTimeRange] = useState<HeatmapTimeRange>('24h');
  const [colormap, setColormap] = useState<HeatmapColormap>('jet');

  // Data fetching
  const {
    cameras,
    isLoading: isCamerasLoading,
    error: camerasError,
    refetch: refetchCameras,
    isRefetching: isCamerasRefetching,
  } = useCamerasQuery();

  // Heatmap query
  const {
    data: heatmapData,
    isLoading: isHeatmapLoading,
    error: heatmapError,
    refetch: refetchHeatmap,
    isRefetching: isHeatmapRefetching,
  } = useHeatmapQuery({
    cameraId: selectedCameraId ?? undefined,
    resolution,
    colormap,
    enabled: !!selectedCameraId,
  });

  // Heatmap history query
  const {
    data: historyData,
    isLoading: isHistoryLoading,
  } = useHeatmapHistoryQuery({
    cameraId: selectedCameraId ?? undefined,
    timeRange,
    resolution,
    enabled: !!selectedCameraId,
  });

  // Get selected camera
  const selectedCamera = useMemo(
    () => cameras.find((cam) => cam.id === selectedCameraId),
    [cameras, selectedCameraId]
  );

  // Handlers
  const handleRefresh = useCallback(() => {
    void refetchCameras();
    if (selectedCameraId) {
      void refetchHeatmap();
    }
  }, [refetchCameras, refetchHeatmap, selectedCameraId]);

  const handleCameraChange = useCallback((cameraId: string) => {
    setSelectedCameraId(cameraId || null);
  }, []);

  const handleDownload = useCallback(() => {
    if (!heatmapData?.image_base64 || !selectedCamera) return;

    // Create download link for the heatmap image
    const link = document.createElement('a');
    link.href = `data:image/png;base64,${heatmapData.image_base64}`;
    link.download = `heatmap-${selectedCamera.name}-${resolution}-${new Date().toISOString().split('T')[0]}.png`;
    link.click();
  }, [heatmapData, selectedCamera, resolution]);

  const handleSelectHistoryEntry = useCallback((_id: number) => {
    // Future: Load specific historical heatmap
    // TODO: Implement historical heatmap loading
  }, []);

  const isRefetching = isCamerasRefetching || isHeatmapRefetching;
  const error = camerasError ?? heatmapError;

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
      <div className="min-h-screen bg-[#121212] p-6" data-testid="heatmaps-page">
        <div className="mx-auto max-w-[1400px]">
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-6">
            <div className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="h-5 w-5" />
              <span className="font-medium">Failed to load heatmap data</span>
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
      <div className="min-h-screen bg-[#121212] p-6" data-testid="heatmaps-page">
        <div className="mx-auto max-w-[1400px]">
          <PageHeader isRefetching={isRefetching} onRefresh={handleRefresh} />
          <EmptyState
            icon={Camera}
            title="No cameras configured"
            description="Add cameras to your system to start viewing movement heatmaps."
            variant="muted"
          />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#121212] p-6" data-testid="heatmaps-page">
      <div className="mx-auto max-w-[1400px]">
        {/* Header */}
        <PageHeader isRefetching={isRefetching} onRefresh={handleRefresh} />

        {/* Controls Bar */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-lg border border-gray-700 bg-gray-800/50 p-4">
          <CameraSelector
            cameras={cameras}
            selectedCameraId={selectedCameraId}
            onCameraChange={handleCameraChange}
            isLoading={isCamerasLoading}
          />

          <TimeControls
            resolution={resolution}
            onResolutionChange={setResolution}
            timeRange={timeRange}
            onTimeRangeChange={setTimeRange}
          />
        </div>

        {/* Main Content */}
        {!selectedCameraId ? (
          <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-8">
            <EmptyState
              icon={Flame}
              title="Select a camera"
              description="Choose a camera from the dropdown above to view its movement heatmap."
              variant="muted"
            />
          </div>
        ) : (
          <div className="grid gap-6 lg:grid-cols-3">
            {/* Main heatmap display */}
            <div className="lg:col-span-2 space-y-4">
              <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-white">
                    {selectedCamera?.name ?? 'Camera'} Heatmap
                  </h2>
                  <ColormapSelector colormap={colormap} onColormapChange={setColormap} />
                </div>

                <HeatmapDisplay
                  imageBase64={heatmapData?.image_base64 ?? null}
                  totalDetections={heatmapData?.total_detections ?? 0}
                  isLoading={isHeatmapLoading}
                  cameraName={selectedCamera?.name ?? 'Camera'}
                  resolution={resolution}
                  onDownload={handleDownload}
                />
              </div>
            </div>

            {/* History sidebar */}
            <div className="space-y-4">
              <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
                <h2 className="mb-4 text-lg font-semibold text-white">History</h2>
                <HeatmapHistory
                  history={historyData?.heatmaps ?? []}
                  isLoading={isHistoryLoading}
                  onSelectEntry={handleSelectHistoryEntry}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Memoized HeatmapsPage for performance.
 */
export const HeatmapsPage = memo(HeatmapsPageComponent);

export default HeatmapsPage;
