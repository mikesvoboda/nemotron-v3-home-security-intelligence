import { TrackPathVisualization } from './TrackPathVisualization';
import { useTrackHistory } from '../../hooks/useTracks';

export interface TrackHistorySectionProps {
  /** Database ID of the track to display */
  trackId: number;
  /** Width of the visualization area */
  width?: number;
  /** Height of the visualization area */
  height?: number;
}

/**
 * Section component that displays track movement history.
 *
 * Shows trajectory visualization and movement metrics.
 * Designed to be embedded in entity detail modals.
 */
export function TrackHistorySection({
  trackId,
  width = 400,
  height = 300,
}: TrackHistorySectionProps) {
  const { data: history, isLoading, error } = useTrackHistory(trackId);

  if (isLoading) {
    return (
      <div className="p-4 border rounded-lg bg-gray-50">
        <h3 className="text-sm font-medium text-gray-700 mb-2">Movement History</h3>
        <div className="animate-pulse bg-gray-200 rounded" style={{ width, height }} />
      </div>
    );
  }

  if (error || !history) {
    return (
      <div className="p-4 border rounded-lg bg-gray-50">
        <h3 className="text-sm font-medium text-gray-700 mb-2">Movement History</h3>
        <p className="text-sm text-gray-500">Unable to load track history</p>
      </div>
    );
  }

  const { trajectory, metrics } = history;

  return (
    <div className="p-4 border rounded-lg bg-gray-50">
      <h3 className="text-sm font-medium text-gray-700 mb-3">Movement History</h3>

      {/* Trajectory Visualization */}
      <div
        className="relative bg-gray-900 rounded overflow-hidden mb-4"
        style={{ width, height }}
      >
        <TrackPathVisualization
          trajectory={trajectory}
          width={width}
          height={height}
        />
        {trajectory.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-gray-400 text-sm">
            No movement data
          </div>
        )}
      </div>

      {/* Movement Metrics */}
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <span className="text-gray-500">Distance:</span>
          <span className="ml-2 font-medium">{metrics.total_distance.toFixed(1)} px</span>
        </div>
        <div>
          <span className="text-gray-500">Duration:</span>
          <span className="ml-2 font-medium">{metrics.duration_seconds.toFixed(1)}s</span>
        </div>
        <div>
          <span className="text-gray-500">Avg Speed:</span>
          <span className="ml-2 font-medium">{metrics.avg_speed.toFixed(1)} px/s</span>
        </div>
        {metrics.direction !== null && (
          <div>
            <span className="text-gray-500">Direction:</span>
            <span className="ml-2 font-medium">{metrics.direction.toFixed(0)}&deg;</span>
          </div>
        )}
      </div>

      {/* Trajectory point count */}
      <p className="mt-3 text-xs text-gray-400">
        {trajectory.length} position{trajectory.length !== 1 ? 's' : ''} recorded
      </p>
    </div>
  );
}
