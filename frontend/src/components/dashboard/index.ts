/**
 * Dashboard components for the main security monitoring view
 *
 * @see ./DashboardPage.tsx - Main dashboard page composition
 * @see ./ActivityFeed.tsx - Live event activity feed
 * @see ./CameraGrid.tsx - Camera status grid display
 * @see ./GpuStats.tsx - GPU performance statistics
 * @see ./PipelineQueues.tsx - AI pipeline queue depths
 * @see ./PipelineTelemetry.tsx - Rich pipeline latency metrics
 * @see ./RiskGauge.tsx - Current risk level gauge
 * @see ./StatsRow.tsx - Summary statistics row
 * @see ./EventStatsCard.tsx - Event statistics card with charts
 */

export { default as ActivityFeed } from './ActivityFeed';
export { default as CameraGrid } from './CameraGrid';
export { default as DashboardPage } from './DashboardPage';
export { default as GpuStats } from './GpuStats';
export { default as PipelineQueues } from './PipelineQueues';
export { default as PipelineTelemetry } from './PipelineTelemetry';
export { default as RiskGauge } from './RiskGauge';
export { default as StatsRow } from './StatsRow';
export { default as EventStatsCard } from './EventStatsCard';

// Type exports
export type { ActivityFeedProps } from './ActivityFeed';
export type { CameraGridProps } from './CameraGrid';
// DashboardPage has no props - uses internal state and hooks
export type { GpuStatsProps } from './GpuStats';
export type { PipelineQueuesProps } from './PipelineQueues';
export type { PipelineTelemetryProps } from './PipelineTelemetry';
export type { RiskGaugeProps } from './RiskGauge';
export type { StatsRowProps } from './StatsRow';
export type { EventStatsCardProps } from './EventStatsCard';
