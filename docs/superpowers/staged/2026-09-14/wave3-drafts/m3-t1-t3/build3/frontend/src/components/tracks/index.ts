/**
 * Track Visualization Components
 *
 * This module provides components for visualizing object tracks and movement paths.
 * Tracks represent the trajectory of detected objects (people, vehicles, etc.)
 * across camera frames over time.
 *
 * Components:
 * - ActiveTracksBadge: Badge showing the number of active tracks on a camera
 * - TrackHistorySection: Section component for entity detail modals showing movement history
 * - TrackPathVisualization: SVG overlay for displaying movement paths on camera snapshots
 */

export { ActiveTracksBadge } from './ActiveTracksBadge';
export type { ActiveTracksBadgeProps } from './ActiveTracksBadge';

export { TrackHistorySection } from './TrackHistorySection';
export type { TrackHistorySectionProps } from './TrackHistorySection';

export { TrackPathVisualization } from './TrackPathVisualization';
export type { TrackPathVisualizationProps, TrajectoryPoint } from './TrackPathVisualization';
