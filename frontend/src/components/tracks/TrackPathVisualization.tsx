/**
 * TrackPathVisualization - SVG overlay for visualizing object movement paths.
 *
 * NEM-4766: This component renders a track's trajectory as an SVG overlay
 * designed to be placed on top of camera snapshots. It displays:
 * - A polyline connecting all trajectory points
 * - Optional dots at each position with opacity indicating age
 * - Start marker (green) and end marker (red) for multi-point trajectories
 *
 * @example
 * ```tsx
 * // Basic usage
 * <TrackPathVisualization
 *   trajectory={[
 *     { x: 100, y: 150, timestamp: '2024-01-15T10:00:00Z' },
 *     { x: 120, y: 160, timestamp: '2024-01-15T10:00:01Z' },
 *     { x: 140, y: 170, timestamp: '2024-01-15T10:00:02Z' },
 *   ]}
 *   width={640}
 *   height={480}
 * />
 *
 * // Customized appearance
 * <TrackPathVisualization
 *   trajectory={trajectory}
 *   width={1920}
 *   height={1080}
 *   strokeColor="#EF4444"
 *   strokeWidth={3}
 *   showDots={false}
 * />
 * ```
 */

/**
 * A single point in the track trajectory.
 */
export interface TrajectoryPoint {
  /** X coordinate in pixels */
  x: number;
  /** Y coordinate in pixels */
  y: number;
  /** ISO 8601 timestamp */
  timestamp: string;
}

export interface TrackPathVisualizationProps {
  /** Array of trajectory points to render */
  trajectory: TrajectoryPoint[];
  /** Width of the container/image in pixels */
  width: number;
  /** Height of the container/image in pixels */
  height: number;
  /** Stroke color for the path (default: blue-500) */
  strokeColor?: string;
  /** Stroke width in pixels (default: 2) */
  strokeWidth?: number;
  /** Whether to show dots at each position (default: true) */
  showDots?: boolean;
  /** Dot radius in pixels (default: 4) */
  dotRadius?: number;
}

/**
 * SVG overlay component that visualizes a track's movement path.
 *
 * Renders a polyline connecting trajectory points and optional dots
 * at each position. Designed to be overlaid on camera snapshots.
 */
export function TrackPathVisualization({
  trajectory,
  width,
  height,
  strokeColor = '#3B82F6', // blue-500
  strokeWidth = 2,
  showDots = true,
  dotRadius = 4,
}: TrackPathVisualizationProps) {
  // Return null for empty trajectories
  if (trajectory.length === 0) {
    return null;
  }

  // Build SVG path from trajectory points
  // Points are assumed to be in pixel coordinates already
  const pathPoints = trajectory.map((point) => `${point.x},${point.y}`).join(' L ');
  const pathD = `M ${pathPoints}`;

  return (
    <svg
      width={width}
      height={height}
      className="absolute inset-0 pointer-events-none"
      style={{ overflow: 'visible' }}
      data-testid="track-path-visualization"
      role="img"
      aria-label={`Track path with ${trajectory.length} points`}
    >
      {/* Movement path */}
      <path
        d={pathD}
        fill="none"
        stroke={strokeColor}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.8}
        data-testid="track-path-line"
      />

      {/* Position dots - opacity increases from old to new */}
      {showDots &&
        trajectory.map((point, index) => (
          <circle
            key={`dot-${index}`}
            cx={point.x}
            cy={point.y}
            r={dotRadius}
            fill={strokeColor}
            opacity={0.6 + (index / trajectory.length) * 0.4}
            data-testid={`track-path-dot-${index}`}
          />
        ))}

      {/* Start marker (green) - only show for multi-point trajectories */}
      {trajectory.length > 1 && (
        <circle
          cx={trajectory[0].x}
          cy={trajectory[0].y}
          r={dotRadius + 2}
          fill="#22C55E" // green-500
          stroke="white"
          strokeWidth={2}
          data-testid="track-path-start-marker"
        />
      )}

      {/* End marker (red) - only show for multi-point trajectories */}
      {trajectory.length > 1 && (
        <circle
          cx={trajectory[trajectory.length - 1].x}
          cy={trajectory[trajectory.length - 1].y}
          r={dotRadius + 2}
          fill="#EF4444" // red-500
          stroke="white"
          strokeWidth={2}
          data-testid="track-path-end-marker"
        />
      )}
    </svg>
  );
}

export default TrackPathVisualization;
